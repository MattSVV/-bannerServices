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
"""AI templates are stored with the cover (``custom_template_html``) and re-sanitised on load and on every render."""
import pytest
from contrib.plugins.portadas.application.cover_mapper import (
    cover_from_dict,
    cover_from_json,
    cover_to_dict,
    cover_to_json,
)
from contrib.plugins.portadas.application.create_cover import CreateCoverFromTemplate
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import MAX_CUSTOM_TEMPLATE, Cover, CoverError

from .fakes import FakeRenderer, InMemoryRepository

GOOD = ('<html><head><style>body{background:#123456;color:#fff}.t{font-size:90px}</style></head>'
        '<body class="{{empty_fields}}"><div class="title-main t">{{title_main}}</div>{{icon}}</body></html>')
EVIL = GOOD.replace('<div', '<script>alert(1)</script><div')


def use_case(tmp_path):
    repository = InMemoryRepository(tmp_path)
    renderer = FakeRenderer()
    return CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), renderer, repository), renderer, repository


def test_a_cover_without_a_custom_template_is_unchanged():
    cover = Cover.from_raw('Titulo', id='plain')

    assert cover.custom_template_html is None
    assert 'custom_template_html' not in cover_to_dict(cover)


def test_the_custom_template_round_trips_through_json():
    cover = Cover.from_raw('Titulo', id='ai1', custom_template_html=GOOD)

    again = cover_from_json(cover_to_json(cover))

    assert again.custom_template_html is not None
    assert 'background:#123456' in again.custom_template_html.replace(' ', '')


def test_loading_re_sanitises_the_stored_template():
    data = cover_to_dict(Cover.from_raw('Titulo', id='ai2', custom_template_html=GOOD))
    data['custom_template_html'] = EVIL

    loaded = cover_from_dict(data)

    assert '<script' not in loaded.custom_template_html


def test_a_stored_template_that_is_no_longer_acceptable_is_dropped_not_the_cover():
    data = cover_to_dict(Cover.from_raw('Titulo', id='ai3', custom_template_html=GOOD))
    data['custom_template_html'] = '<div>Texto fijo</div>'  # hard-coded visible text, no placeholder

    loaded = cover_from_dict(data)

    assert loaded.custom_template_html is None
    assert loaded.title_main == 'Titulo'


def test_a_non_text_template_in_the_data_is_an_error():
    from contrib.plugins.portadas.application.cover_mapper import CoverDataError
    data = cover_to_dict(Cover.from_raw('Titulo', id='ai4'))
    data['custom_template_html'] = 5

    with pytest.raises(CoverDataError):
        cover_from_dict(data)


@pytest.mark.parametrize('value', ['', 5, 'x' * (MAX_CUSTOM_TEMPLATE + 1)])
def test_the_domain_checks_the_custom_template_type_and_size(value):
    with pytest.raises(CoverError):
        Cover.from_raw('Titulo', custom_template_html=value)


def test_compose_uses_the_custom_template_and_sanitises_it_again(tmp_path):
    creator, _, _ = use_case(tmp_path)
    cover = creator.build_cover('Mi titulo', custom_template_html=EVIL)

    html, base_dir = creator.compose(cover)

    assert 'Mi titulo' in html and '<script' not in html
    assert base_dir == creator.templates.root / cover.template_id  # relative asset URLs resolve from here


def test_compose_rejects_a_custom_template_without_the_title(tmp_path):
    creator, _, _ = use_case(tmp_path)
    cover = creator.build_cover('Mi titulo', custom_template_html='<div class="x"></div>')

    with pytest.raises(CoverError, match='rejected'):
        creator.compose(cover)


def test_execute_stores_the_custom_template_with_the_cover(tmp_path):
    creator, _, repository = use_case(tmp_path)

    created = creator.execute('Mi titulo', custom_template_html=GOOD, id='ai5')

    assert repository.get('ai5').custom_template_html == created.cover.custom_template_html is not None
