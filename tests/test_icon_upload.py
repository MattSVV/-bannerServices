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
"""Turning a file the user uploaded (SVG or PNG) into a safe inline icon."""
import base64

import pytest
from contrib.plugins.portadas.application.create_cover import CreateCoverFromTemplate
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.icon_upload import (
    MAX_PNG_DIMENSION,
    MAX_SVG_BYTES,
    icon_from_png_bytes,
    icon_from_svg_text,
)
from contrib.plugins.portadas.application.ports import CoverRenderer, RenderResult
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import CoverError, IconKind
from contrib.plugins.portadas.security.html_policy import MAX_PNG_ICON_BYTES

from .test_svg_png_option import tiny_png

GOOD_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" fill="none" stroke="currentColor">'
            '<path d="M1 1 L7 7"/></svg>')


def test_a_clean_svg_becomes_an_inline_icon():
    icon = icon_from_svg_text(GOOD_SVG)

    assert icon.kind is IconKind.INLINE_SVG
    assert icon.value.startswith('<svg')
    assert 'xmlns' not in icon.value


@pytest.mark.parametrize('payload', [
    '<svg onload="alert(1)"><path d="M0 0"/></svg>',
    '<svg><script>alert(1)</script><path d="M0 0"/></svg>',
    '<svg><foreignObject><div>hi</div></foreignObject><path d="M0 0"/></svg>',
    '<svg><path d="M0 0" onclick="alert(1)"/></svg>',
    '<svg><a href="javascript:alert(1)"><path d="M0 0"/></a></svg>',
    '<svg><animate attributeName="d" values="x"/><path d="M0 0"/></svg>',
    '<svg><text>hello</text></svg>',
    '<div>not an svg</div>',
    '',
    '<svg><svg><path d="M0 0"/></svg></svg><svg/>',
])
def test_a_malicious_or_unusable_svg_is_rejected(payload):
    with pytest.raises(CoverError):
        icon_from_svg_text(payload)


def test_an_oversized_svg_is_rejected():
    with pytest.raises(CoverError, match='too large'):
        icon_from_svg_text('<svg>' + '<path d="M0 0"/>' * (MAX_SVG_BYTES // 10) + '</svg>')


def test_non_text_input_is_rejected():
    with pytest.raises(CoverError):
        icon_from_svg_text(None)


def test_a_png_is_wrapped_in_a_safe_svg():
    icon = icon_from_png_bytes(tiny_png(3, 2))

    assert icon.kind is IconKind.INLINE_SVG
    assert icon.value.startswith('<svg')
    assert 'data:image/png;base64,' + base64.b64encode(tiny_png(3, 2)).decode() in icon.value
    assert 'viewbox="0 0 3 2"' in icon.value.lower()


@pytest.mark.parametrize('payload', [b'', b'GIF89a', b'not a png', b'\x89PNG\r\n\x1a\n', b'<svg onload=alert(1)>'])
def test_data_that_is_not_a_png_is_rejected(payload):
    with pytest.raises(CoverError):
        icon_from_png_bytes(payload)


def test_a_png_that_is_too_big_is_rejected():
    with pytest.raises(CoverError, match='too large'):
        icon_from_png_bytes(tiny_png() + b'\x00' * MAX_PNG_ICON_BYTES)


def test_a_png_with_huge_dimensions_is_rejected():
    with pytest.raises(CoverError, match='dimensions'):
        icon_from_png_bytes(tiny_png(MAX_PNG_DIMENSION + 1, 1))


def test_non_bytes_input_is_rejected():
    with pytest.raises(CoverError):
        icon_from_png_bytes('text')


class RecordingRenderer(CoverRenderer):
    def __init__(self):
        self.html = None

    def render(self, html, base_dir, size=(1920, 1080)):
        self.html = html
        return RenderResult(tiny_png())

    def render_async(self, html, base_dir, on_done, on_error, size=(1920, 1080)):
        raise NotImplementedError


def test_the_use_case_renders_an_uploaded_png_icon():
    """Uploaded icons are no longer a gap: the stored inline SVG is re-sanitised, with the PNG option, at render."""
    renderer = RecordingRenderer()
    use_case = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), renderer, repository=None)
    icon = icon_from_png_bytes(tiny_png())
    cover = use_case.build_cover('Title', icon=icon)

    html, _ = use_case.compose(cover)

    assert 'data:image/png;base64,' in html
    assert '<image' in html


def test_the_use_case_still_rejects_a_hostile_inline_svg():
    use_case = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), RecordingRenderer(), repository=None)
    from contrib.plugins.portadas.domain.cover import IconRef
    cover = use_case.build_cover('Title', icon=IconRef(IconKind.INLINE_SVG, '<div>nope</div>'))

    with pytest.raises(CoverError, match='rejected'):
        use_case.compose(cover)
