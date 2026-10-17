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
"""``sanitize_svg(allow_png_image=True)``: the narrow, opt-in exception that lets a user-uploaded PNG be an icon."""
import base64

import pytest
from contrib.plugins.portadas.security.html_policy import (
    MAX_PNG_ICON_BYTES,
    sanitize_svg,
    sanitize_template,
)

from .fakes import png_bytes


def tiny_png(width=2, height=2):
    return png_bytes(width, height)


def data_uri(payload, mime='image/png'):
    return f'data:{mime};base64,' + base64.b64encode(payload).decode('ascii')


def svg_with_image(href, extra=''):
    return f'<svg viewBox="0 0 2 2"><image href="{href}" width="2" height="2"{extra}/></svg>'


def test_png_image_is_removed_by_default():
    result = sanitize_svg(svg_with_image(data_uri(tiny_png())))

    assert result.accepted
    assert 'image' not in result.html
    assert any(violation.code == 'element-removed' for violation in result.violations)


def test_png_image_survives_when_the_option_is_on():
    result = sanitize_svg(svg_with_image(data_uri(tiny_png())), allow_png_image=True)

    assert result.accepted
    assert '<image' in result.html
    assert 'data:image/png;base64,' in result.html


@pytest.mark.parametrize('href', [
    'http://evil.example/x.png',
    'https://evil.example/x.png',
    'file:///etc/passwd',
    '//evil.example/x.png',
    '#fragment',
    'x.png',
    'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',
    'data:image/jpeg;base64,/9j/4AAQ',
    'data:text/html;base64,PHNjcmlwdD4=',
    'data:image/png,not-base64',
    'javascript:alert(1)',
])
def test_only_png_data_uris_are_accepted(href):
    result = sanitize_svg(svg_with_image(href), allow_png_image=True)

    assert result.accepted
    assert href not in result.html
    assert 'href' not in result.html


def test_the_data_uri_must_decode_to_a_png():
    not_png = data_uri(b'<svg onload=alert(1)>')

    result = sanitize_svg(svg_with_image(not_png), allow_png_image=True)

    assert 'href' not in result.html


def test_the_data_uri_must_be_strict_base64():
    result = sanitize_svg(svg_with_image('data:image/png;base64,iVBORw0KGgo!!!!'), allow_png_image=True)

    assert 'href' not in result.html


def test_oversized_png_is_dropped():
    big = tiny_png() + b'\x00' * (MAX_PNG_ICON_BYTES + 1)

    result = sanitize_svg(svg_with_image(data_uri(big)), allow_png_image=True)

    assert 'href' not in result.html


def test_xlink_href_is_checked_the_same_way():
    uri = data_uri(tiny_png())
    ok = sanitize_svg(f'<svg><image xlink:href="{uri}" width="2" height="2"/></svg>', allow_png_image=True)
    bad = sanitize_svg('<svg><image xlink:href="http://evil.example/a.png"/></svg>', allow_png_image=True)

    assert 'data:image/png' in ok.html
    assert 'evil.example' not in bad.html


def test_the_option_does_not_relax_anything_else():
    payload = ('<svg onload="alert(1)"><script>alert(1)</script><foreignObject><div>x</div></foreignObject>'
               '<image href="data:image/png;base64,' + base64.b64encode(tiny_png()).decode() + '" onerror="x()" '
               'style="background:url(http://evil.example/)"/></svg>')

    result = sanitize_svg(payload, allow_png_image=True)

    assert result.accepted
    for forbidden in ('onload', 'onerror', 'script', 'foreignobject', 'evil.example', 'alert'):
        assert forbidden not in result.html.lower()


def test_the_option_never_reaches_template_sanitising():
    """AI templates go through ``sanitize_template``, which has no such option and never keeps an ``<image>``."""
    uri = data_uri(tiny_png())
    template = f'<div class="title-main">{{{{title_main}}}}</div><svg viewBox="0 0 2 2"><image href="{uri}"/></svg>'

    result = sanitize_template(template, required=('title_main',))

    assert '<image' not in (result.html or '')
    assert 'data:image' not in (result.html or '')
    with pytest.raises(TypeError):
        sanitize_template(template, allow_png_image=True)
