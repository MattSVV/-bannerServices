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
"""The placeholder engine: single-pass substitution, escaping, strict placeholder validation."""
import pytest
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.domain.errors import DomainError
from contrib.plugins.portadas.domain.templating import (
    ALL_PLACEHOLDERS,
    CONTENT_PLACEHOLDERS,
    TemplateError,
    TemplateManifest,
    find_placeholders,
    render,
    render_cover,
    validate_placeholders,
)

FULL = ('<h1>{{title_main}}</h1><h2>{{title_accent}}</h2><p>{{subtitle}}</p><b>{{key_verse}}</b>'
        '<i>{{label}}</i><u>{{readings_label}}</u><ul>{{readings}}</ul><div>{{icon}}</div>')


def test_placeholder_vocabulary():
    assert set(CONTENT_PLACEHOLDERS) == {
        'label', 'title_main', 'title_accent', 'subtitle', 'key_verse', 'readings_label', 'readings', 'icon'}
    assert set(ALL_PLACEHOLDERS) == set(CONTENT_PLACEHOLDERS) | {'empty_fields'}


def test_substitution_of_every_placeholder():
    html = render(FULL, text={'title_main': 'Resistir', 'title_accent': 'al diablo', 'subtitle': 'sub',
                              'key_verse': 'Efesios 6:11', 'label': 'MENSAJE', 'readings_label': 'LECTURAS'},
                  readings=['Salmos 23', 'Juan 3:16'], icon_svg='<svg viewBox="0 0 1 1"/>')

    assert html == ('<h1>Resistir</h1><h2>al diablo</h2><p>sub</p><b>Efesios 6:11</b><i>MENSAJE</i><u>LECTURAS</u>'
                    '<ul><li>Salmos 23</li>\n<li>Juan 3:16</li></ul><div><svg viewBox="0 0 1 1"/></div>')


def test_whitespace_inside_braces_is_tolerated():
    assert render('{{ title_main }}', text={'title_main': 'A'}) == 'A'


@pytest.mark.parametrize('evil', [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "' onmouseover='x",
    'a & b < c > d',
])
def test_text_values_are_escaped(evil):
    html = render('<h1 title="{{title_main}}">{{title_main}}</h1>', text={'title_main': evil})

    assert '<script' not in html and '<img' not in html
    assert '"' not in html.split('title="', 1)[1].split('">', 1)[0]
    assert html.count('&lt;') == 2 * evil.count('<')  # the value is used twice


def test_placeholder_syntax_in_user_text_is_not_expanded():
    html = render('<h1>{{title_main}}</h1><h2>{{subtitle}}</h2>',
                  text={'title_main': '{{subtitle}}', 'subtitle': '{{title_main}} {{icon}}'},
                  icon_svg='<svg/>')

    assert html == '<h1>{{subtitle}}</h1><h2>{{title_main}} {{icon}}</h2>'


def test_user_text_cannot_inject_through_readings_or_subtitle():
    html = render('{{subtitle}}|{{readings}}', text={'subtitle': 'a\n<b>b</b>'}, readings=['<i>x</i>'])

    assert html == 'a<br>&lt;b&gt;b&lt;/b&gt;|<li>&lt;i&gt;x&lt;/i&gt;</li>'


def test_empty_optionals_render_empty_and_flag_the_body_classes():
    html = render('<body class="{{empty_fields}}">{{title_accent}}{{readings}}</body>',
                  text={'title_main': 'T', 'title_accent': ''})

    assert html == ('<body class="no-label no-title-accent no-subtitle no-key-verse no-readings-label '
                    'no-readings no-icon"></body>')


def test_empty_fields_lists_only_empty_ones_in_stable_order():
    text = {name: 'x' for name in CONTENT_PLACEHOLDERS if name not in ('readings', 'icon')}

    html = render('{{empty_fields}}', text=text, readings=['Salmos 23'], icon_svg='<svg/>')

    assert html == ''


def test_unknown_placeholder_is_an_error():
    with pytest.raises(TemplateError, match='Unknown placeholder "nope"'):
        render('{{nope}}', text={})
    with pytest.raises(TemplateError, match='Unknown placeholder'):
        find_placeholders('{{Title_Main}}')


@pytest.mark.parametrize('broken', ['{{title_main', '{{ }}', '{{title main}}', '{{{title_main}}}', '{{}}',
                                    '{{title_main}', '{{a-b}}'])
def test_malformed_placeholders_are_errors(broken):
    with pytest.raises(TemplateError):
        find_placeholders(broken)


def test_find_placeholders_returns_names_in_order_without_duplicates():
    assert find_placeholders('{{icon}}{{title_main}}{{icon}}') == ('icon', 'title_main')


def test_required_placeholders_must_appear_in_the_template():
    validate_placeholders('{{title_main}}{{readings}}', required=('title_main', 'readings'))

    with pytest.raises(TemplateError, match='missing the required placeholder "readings"'):
        validate_placeholders('{{title_main}}', required=('title_main', 'readings'))
    with pytest.raises(TemplateError, match='Unknown placeholder'):
        validate_placeholders('{{title_main}}', required=('nope',))


def test_required_value_must_be_non_empty_at_render_time():
    with pytest.raises(TemplateError, match='"title_main" is required'):
        render('{{title_main}}', text={'title_main': ' '}, required=('title_main',))


def test_template_errors_are_domain_errors():
    assert issubclass(TemplateError, DomainError)


def test_render_cover_uses_the_cover_fields():
    cover = Cover.from_raw('Resistir', title_accent='al diablo', subtitle='uno\ndos', key_verse='ef 6:11',
                           readings=['Salmos 119:5, 9', 'Romanos 8:1 · 12:1-2'])

    template = ('{{label}}|{{title_main}}|{{title_accent}}|{{subtitle}}|{{key_verse}}|{{readings_label}}|'
                '{{readings}}|{{icon}}')

    html = render_cover(template, cover, icon_svg='<svg/>')

    assert html == ('MENSAJE|Resistir|al diablo|uno<br>dos|Efesios 6:11|LECTURAS|'
                    '<li>Salmos 119:5, 9</li>\n<li>Romanos 8:1 · 12:1-2</li>|<svg/>')


MANIFEST = {
    'id': 'demo', 'name': 'Demo', 'description': 'A demo.',
    'required': ['title_main'], 'optional': ['subtitle'], 'canvas': {'width': 1920, 'height': 1080},
}


def test_manifest_from_dict():
    manifest = TemplateManifest.from_dict(MANIFEST)

    assert (manifest.id, manifest.name, manifest.width, manifest.height) == ('demo', 'Demo', 1920, 1080)
    assert manifest.required == ('title_main',)
    assert manifest.optional == ('subtitle',)


@pytest.mark.parametrize('change', [
    {'id': '../x'}, {'id': ''}, {'name': ''}, {'required': []}, {'required': ['nope']},
    {'optional': ['title_main']}, {'canvas': {'width': 100, 'height': 100}}, {'canvas': {}}, {'required': 'x'},
    {'description': 5},
])
def test_manifest_rejects_invalid_data(change):
    with pytest.raises(TemplateError):
        TemplateManifest.from_dict({**MANIFEST, **change})


def test_manifest_missing_key_is_reported():
    data = dict(MANIFEST)
    del data['name']

    with pytest.raises(TemplateError, match='name'):
        TemplateManifest.from_dict(data)
