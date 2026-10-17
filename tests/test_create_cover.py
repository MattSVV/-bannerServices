# -*- coding: utf-8 -*-

##########################################################################
# Portadas - sermon cover plugin for OpenLP                              #
# ---------------------------------------------------------------------- #
# Copyright (c) 2026 Portadas contributors                               #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""The create-cover use case, with fakes for the renderer and the repository."""
from pathlib import Path

import pytest
from contrib.plugins.portadas.application.create_cover import CreateCoverFromTemplate
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.ports import (
    CoverRenderer,
    CoverRepository,
    RenderError,
    RenderResult,
    RepositoryError,
)
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import CoverError, IconKind, IconRef
from contrib.plugins.portadas.domain.errors import DomainError

PNG = b'\x89PNG\r\n\x1a\n-fake'


class FakeRenderer(CoverRenderer):
    def __init__(self, overflow=(), error=None):
        self.calls, self.overflow, self.error = [], overflow, error

    def render(self, html, base_dir, size=(1920, 1080)):
        self.calls.append((html, base_dir, size))
        if self.error:
            raise self.error
        return RenderResult(PNG, tuple(self.overflow))

    def render_async(self, html, base_dir, on_done, on_error, size=(1920, 1080)):
        raise NotImplementedError


class FakeRepository(CoverRepository):
    def __init__(self, error=None):
        self.saved, self.error = {}, error

    def save(self, cover, png_bytes):
        if self.error:
            raise self.error
        self.saved[cover.id] = (cover, png_bytes)

    def get(self, cover_id):
        return self.saved[cover_id][0]

    def list(self):
        return [cover for cover, _ in self.saved.values()]

    def delete(self, cover_id):
        del self.saved[cover_id]

    def export_png(self, cover_id, dest_path, overwrite=False):
        raise NotImplementedError

    def png_path(self, cover_id):
        raise NotImplementedError


@pytest.fixture
def renderer():
    return FakeRenderer()


@pytest.fixture
def repository():
    return FakeRepository()


@pytest.fixture
def use_case(renderer, repository):
    return CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), renderer, repository)


def test_the_port_fakes_are_complete():
    assert FakeRenderer() and FakeRepository()


def test_it_renders_and_persists_a_cover_from_raw_input(use_case, renderer, repository):
    created = use_case.execute('  Resistir ', title_accent='al diablo', key_verse='ef 6:11',
                               readings=['ef 6:11-12'], template_id='noche-dorada')

    html, base_dir, size = renderer.calls[0]
    assert created.cover.title_main == 'Resistir'
    assert str(created.cover.key_verse) == 'Efesios 6:11'
    assert created.overflow == ()
    assert repository.saved[created.cover.id] == (created.cover, PNG)
    assert '>Resistir<' in html and 'Efesios 6:11' in html and '<svg' in html and '{{' not in html
    assert base_dir == TemplateCatalog().root / 'noche-dorada'
    assert size == (1920, 1080)


def test_overflow_warnings_are_returned_not_raised(repository):
    use_case = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), FakeRenderer(('title_main',)), repository)

    created = use_case.execute('Titulo')

    assert created.overflow == ('title_main',)
    assert created.cover.id in repository.saved


def test_the_text_is_escaped_in_the_html(use_case, renderer):
    use_case.execute('<script>alert(1)</script> & "q"', subtitle='<b>x</b>')

    html = renderer.calls[0][0]
    assert '<script>alert' not in html and '&lt;script&gt;' in html and '&amp;' in html and '&lt;b&gt;' in html


def test_invalid_input_renders_and_saves_nothing(use_case, renderer, repository):
    with pytest.raises(CoverError):
        use_case.execute('Titulo', key_verse='not a reference')
    with pytest.raises(CoverError):
        use_case.execute('   ')

    assert renderer.calls == [] and repository.saved == {}


def test_an_unknown_template_renders_and_saves_nothing(use_case, renderer, repository):
    with pytest.raises(DomainError):
        use_case.execute('Titulo', template_id='nope')
    with pytest.raises(DomainError):
        use_case.execute('Titulo', template_id='../minimal')

    assert renderer.calls == [] and repository.saved == {}


def test_a_render_failure_saves_nothing(repository):
    use_case = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), FakeRenderer(error=RenderError('boom')),
                                       repository)

    with pytest.raises(RenderError):
        use_case.execute('Titulo')

    assert repository.saved == {}


def test_a_repository_failure_propagates(renderer):
    use_case = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), renderer,
                                       FakeRepository(error=RepositoryError('disk full')))

    with pytest.raises(RepositoryError):
        use_case.execute('Titulo')


def test_each_builtin_icon_and_template_composes(use_case, renderer):
    for template_id in TemplateCatalog().list():
        use_case.execute('Titulo', icon=IconRef(IconKind.BUILTIN, 'dove'), template_id=template_id.id)

    assert len(renderer.calls) == 3


def test_an_inline_svg_icon_is_sanitised_before_use(use_case, renderer):
    evil = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" onload="alert(1)">'
            '<script>alert(1)</script><path d="M0 0L10 10"/></svg>')

    use_case.execute('Titulo', icon=IconRef(IconKind.INLINE_SVG, evil))

    html = renderer.calls[0][0]
    assert 'alert' not in html and 'onload' not in html and '<path' in html


def test_an_unusable_inline_svg_is_rejected(use_case, renderer, repository):
    with pytest.raises(CoverError):
        use_case.execute('Titulo', icon=IconRef(IconKind.INLINE_SVG, 'just text, no svg'))

    assert renderer.calls == [] and repository.saved == {}


def test_uploaded_icons_are_not_supported_yet(use_case, renderer):
    with pytest.raises(CoverError, match='Uploaded'):
        use_case.execute('Titulo', icon=IconRef(IconKind.UPLOADED, 'logo.png'))

    assert renderer.calls == []


def test_an_unknown_builtin_icon_is_rejected(use_case):
    with pytest.raises(DomainError):
        use_case.execute('Titulo', icon=IconRef(IconKind.BUILTIN, 'no-such-icon'))


def test_reusing_an_id_overwrites_for_editing(use_case, repository):
    first = use_case.execute('Primero', id='same')
    second = use_case.execute('Segundo', id='same', created_at=first.cover.created_at)

    assert list(repository.saved) == ['same']
    assert repository.saved['same'][0].title_main == 'Segundo' and second.cover.id == 'same'


def test_compose_returns_the_html_and_base_dir_without_rendering_or_saving(use_case, renderer, repository):
    cover = use_case.build_cover('Titulo', template_id='luz-clara')

    html, base_dir = use_case.compose(cover)

    assert '>Titulo<' in html
    assert isinstance(base_dir, Path) and base_dir.name == 'luz-clara'
    assert renderer.calls == [] and repository.saved == {}


def test_preview_renders_without_saving(use_case, repository):
    cover, result = use_case.preview('Titulo')

    assert cover.title_main == 'Titulo' and result.png_bytes == PNG
    assert repository.saved == {}
