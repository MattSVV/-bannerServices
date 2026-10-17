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
"""Built-in templates and the icon set: manifests, placeholders and safety of the bundled files."""
import json
import re
import xml.etree.ElementTree as ET

import pytest
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.domain.errors import DomainError
from contrib.plugins.portadas.domain.templating import CONTENT_PLACEHOLDERS, find_placeholders, render_cover

BUILTIN_IDS = ['luz-clara', 'minimal', 'noche-dorada']
REQUIRED_ICONS = {'shield-heart', 'cross', 'dove', 'open-bible', 'flame', 'crown', 'anchor', 'praying-hands'}
FORBIDDEN_SVG_TAGS = {'script', 'foreignobject', 'iframe', 'object', 'embed', 'image', 'a', 'use', 'style'}


@pytest.fixture(scope='module')
def templates():
    return TemplateCatalog()


@pytest.fixture(scope='module')
def icons():
    return IconCatalog()


def test_builtin_templates_are_listed(templates):
    assert sorted(manifest.id for manifest in templates.list()) == BUILTIN_IDS


@pytest.mark.parametrize('template_id', BUILTIN_IDS)
def test_manifest_and_html_are_consistent(templates, template_id):
    template = templates.load(template_id)

    assert template.manifest.id == template_id
    assert (template.manifest.width, template.manifest.height) == (1920, 1080)
    found = set(find_placeholders(template.html))
    assert set(template.manifest.required) <= found
    assert found <= set(template.manifest.required) | set(template.manifest.optional) | {'empty_fields'}
    assert 'title_main' in template.manifest.required


@pytest.mark.parametrize('template_id', BUILTIN_IDS)
def test_builtin_templates_use_every_content_placeholder(templates, template_id):
    found = set(find_placeholders(templates.load(template_id).html))

    assert set(CONTENT_PLACEHOLDERS) <= found


@pytest.mark.parametrize('template_id', BUILTIN_IDS)
def test_builtin_templates_are_static_and_self_contained(templates, template_id):
    html = templates.load(template_id).html.lower()

    assert '<script' not in html
    assert not re.search(r'\bon[a-z]+\s*=', html)
    assert 'javascript:' not in html
    assert not re.search(r'(https?:)?//', html.replace('http://www.w3.org', ''))
    for url in re.findall(r'url\(([^)]*)\)', html):
        assert url.strip('\'" ').startswith(('#', '../../assets/fonts/')), url
    assert re.search(r'width:\s*1920px', html) and re.search(r'height:\s*1080px', html)


@pytest.mark.parametrize('template_id', BUILTIN_IDS)
def test_builtin_fonts_exist_on_disk(templates, template_id):
    html = templates.load(template_id).html
    fonts = re.findall(r'url\(["\']?(\.\./\.\./assets/fonts/[^)"\']+)', html)

    assert fonts
    for font in fonts:
        assert (templates.root / template_id / font).resolve().is_file(), font


def test_font_licenses_are_bundled(templates):
    fonts = templates.root.parent / 'assets' / 'fonts'

    assert (fonts / 'OFL-PlayfairDisplay.txt').is_file()
    assert (fonts / 'OFL-Outfit.txt').is_file()


@pytest.mark.parametrize('template_id', BUILTIN_IDS)
def test_templates_render_the_reference_cover(templates, icons, template_id):
    cover = Cover.from_raw(
        'Resistir', title_accent='al diablo', subtitle='Firmes en la batalla de la mente:\nun corazón guardado',
        key_verse='Efesios 6:11', readings=['Efesios 6:11-12', 'Romanos 8:1 · 12:1-2'])

    template = templates.load(template_id)
    html = render_cover(template.html, cover, icons.svg('shield-heart'), required=template.manifest.required)

    assert '{{' not in html
    assert '<li>Romanos 8:1 · 12:1-2</li>' in html
    assert 'Firmes en la batalla de la mente:<br>un corazón guardado' in html
    assert '<svg' in html


def test_unknown_or_unsafe_template_ids_are_rejected(templates):
    for bad in ('nope', '../minimal', 'Minimal', ''):
        with pytest.raises(DomainError):
            templates.load(bad)


def test_catalog_rejects_a_template_missing_a_required_placeholder(tmp_path):
    folder = tmp_path / 'broken'
    folder.mkdir()
    (folder / 'template.html').write_text('<p>{{title_accent}}</p>', encoding='utf-8')
    (folder / 'manifest.json').write_text(json.dumps({
        'id': 'broken', 'name': 'B', 'description': 'd', 'required': ['title_main'], 'optional': ['title_accent'],
        'canvas': {'width': 1920, 'height': 1080}}), encoding='utf-8')

    with pytest.raises(DomainError, match='required placeholder'):
        TemplateCatalog(tmp_path).load('broken')


def test_catalog_rejects_manifest_id_that_differs_from_folder(tmp_path):
    folder = tmp_path / 'one'
    folder.mkdir()
    (folder / 'template.html').write_text('{{title_main}}', encoding='utf-8')
    (folder / 'manifest.json').write_text(json.dumps({
        'id': 'two', 'name': 'B', 'description': 'd', 'required': ['title_main'], 'optional': [],
        'canvas': {'width': 1920, 'height': 1080}}), encoding='utf-8')

    with pytest.raises(DomainError, match='does not match'):
        TemplateCatalog(tmp_path).load('one')


def test_catalog_reports_unreadable_manifest(tmp_path):
    folder = tmp_path / 'bad'
    folder.mkdir()
    (folder / 'template.html').write_text('{{title_main}}', encoding='utf-8')
    (folder / 'manifest.json').write_text('{not json', encoding='utf-8')

    with pytest.raises(DomainError, match='manifest'):
        TemplateCatalog(tmp_path).load('bad')


def test_catalog_reports_missing_and_oversized_template_html(tmp_path):
    folder = tmp_path / 'bad'
    folder.mkdir()
    (folder / 'manifest.json').write_text(json.dumps({
        'id': 'bad', 'name': 'B', 'description': 'd', 'required': ['title_main'], 'optional': [],
        'canvas': {'width': 1920, 'height': 1080}}), encoding='utf-8')

    with pytest.raises(DomainError, match='template.html'):
        TemplateCatalog(tmp_path).load('bad')

    (folder / 'template.html').write_text('{{title_main}}' + 'x' * 600000, encoding='utf-8')
    with pytest.raises(DomainError, match='template.html'):
        TemplateCatalog(tmp_path).load('bad')


def test_listing_skips_broken_folders(tmp_path):
    (tmp_path / 'junk').mkdir()

    assert TemplateCatalog(tmp_path).list() == ()


def test_icon_catalog_has_the_required_icons(icons):
    assert REQUIRED_ICONS <= set(icons.ids())
    assert len(icons.ids()) >= 8


def test_every_icon_is_a_safe_svg(icons):
    for icon_id in icons.ids():
        svg = icons.svg(icon_id)
        root = ET.fromstring(svg)

        assert root.tag == '{http://www.w3.org/2000/svg}svg', icon_id
        assert root.get('viewBox'), icon_id
        assert 'currentColor' in svg, icon_id
        for element in root.iter():
            assert element.tag.rsplit('}', 1)[-1].lower() not in FORBIDDEN_SVG_TAGS, (icon_id, element.tag)
            for name, value in element.attrib.items():
                assert not name.lower().startswith('on'), (icon_id, name)
                assert 'href' not in name.lower(), (icon_id, name)
                assert 'url(' not in value.lower() or 'url(#' in value.lower(), (icon_id, value)
        assert 'http' not in svg.replace('http://www.w3.org/2000/svg', ''), icon_id


def test_icon_catalog_rejects_unknown_or_unsafe_ids(icons):
    for bad in ('nope', '../cross', 'Cross', ''):
        with pytest.raises(DomainError):
            icons.svg(bad)


def test_listing_of_a_missing_directory_is_empty(tmp_path):
    assert TemplateCatalog(tmp_path / 'missing').list() == ()
    assert IconCatalog(tmp_path / 'missing').ids() == ()


def test_icon_catalog_rejects_oversized_icons(tmp_path):
    (tmp_path / 'big.svg').write_text('<svg>' + 'x' * 30000 + '</svg>', encoding='utf-8')

    with pytest.raises(DomainError, match='too large'):
        IconCatalog(tmp_path).svg('big')
