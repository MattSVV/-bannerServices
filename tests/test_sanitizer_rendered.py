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
"""
The sanitizer judged by what a real browser draws (QtWebEngine, off screen).

Approach: pixels. Every test page has a solid background and its only placeholder inside a ``display:none`` element,
so the user text is invisible and **any non-background pixel is text (or a marker) that did not come from a user
value**. Each hostile page is rendered twice:

* *unsanitized* (control): it must draw something, otherwise the harness could not see the attack at all;
* *sanitized*: the template is either refused, or accepted and then the page must be a flat background.

A last test renders the three built-in templates before and after sanitizing and requires identical pictures: the
sanitizer must not change a legitimate design.
"""
import os
from pathlib import Path

import pytest
from contrib.plugins.portadas.adapters.qt_renderer import QtCoverRenderer
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.ports import RenderError
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.domain.templating import render, render_cover
from contrib.plugins.portadas.security.html_policy import sanitize_template
from PyQt5 import QtGui

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'portadas' / 'templates'
SIZE = (640, 360)
BACKGROUND = 0xFF102030  # QImage.Format_RGB32 of #102030
BASE_CSS = ('html,body{margin:0;width:640px;height:360px;overflow:hidden;background:#102030}'
            'body{color:#ffffff;font-size:40px;font-family:Arial,sans-serif}')
BODY = ('<div style="display:none">{{title_main}}</div><div class="a" style="margin-left:100px"></div>'
        '<ul class="readings"><li><br></li></ul><div class="img"></div>')


def page(css, body=BODY):
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><style>{BASE_CSS}</style>'
            f'<style>{css}</style></head><body>{body}</body></html>')


@pytest.fixture(scope='module')
def renderer(qapp):
    instance = QtCoverRenderer(timeout_ms=30000)
    try:
        instance.render('<!DOCTYPE html><html><body></body></html>', TEMPLATE_DIR, size=(64, 36))
    except RenderError as error:
        if os.environ.get('PORTADAS_REQUIRE_RENDER'):
            raise
        pytest.skip(f'QtWebEngine cannot render on this platform ({os.environ.get("QT_QPA_PLATFORM")}): {error}')
    yield instance
    instance.close()


def draw(renderer, html, size=SIZE):
    result = renderer.render(render(html, text={'title_main': 'USER TEXT'}, required=('title_main',)), TEMPLATE_DIR,
                             size=size)
    image = QtGui.QImage.fromData(result.png_bytes, 'PNG').convertToFormat(QtGui.QImage.Format_RGB32)
    return image


def colours(image):
    """The set of distinct pixel values of an image (``0xffRRGGBB``)."""
    return set(memoryview(image.constBits().asstring(image.sizeInBytes())).cast('I'))


def is_flat(image):
    return colours(image) == {BACKGROUND}


# (id, css, body) - these draw hard-coded text or markers in Chromium when left alone.
TEXT_ATTACKS = [
    ('comment-in-string-content', '.a::before{content:"" ; y:"/*" ; content:"HELLO-A"; z:"*/"}', BODY),
    ('escaped-quote-content', '.a::before{content:"\\";HELLO-B"}', BODY),
    ('escaped-slash-comment', '.a{b:c\\/*} .a::before{content:"HELLO-C"} e{f:g*/}', BODY),
    ('list-style-type-string', '.readings{list-style-type:"HELLO-D "}', BODY),
    ('list-style-shorthand-string', 'li{list-style:"HELLO " inside}', BODY),
    ('list-style-decimal', '.readings{list-style-type:decimal}', BODY),
    ('ol-numbering', '', BODY.replace('<ul', '<ol').replace('</ul>', '</ol>')),
    ('content-var', ':root{--t:"HELLO"} .a::before{content:var(--t)}', BODY),
    ('open-quote', '.a::before{content:open-quote}', BODY),
]


@pytest.mark.parametrize('css, body', [pytest.param(c, b, id=i) for i, c, b in TEXT_ATTACKS])
def test_control_the_unsanitised_attack_really_draws_something(renderer, css, body):
    assert not is_flat(draw(renderer, page(css, body)))


@pytest.mark.parametrize('css, body', [pytest.param(c, b, id=i) for i, c, b in TEXT_ATTACKS])
def test_the_sanitized_attack_is_refused_or_draws_nothing(renderer, css, body):
    result = sanitize_template(page(css, body))

    if result.accepted:
        assert is_flat(draw(renderer, result.html))


# (id, css, body) - neutralised rather than refused: accepted, and must then draw nothing.
NEUTRALISED = [
    ('empty-template', '', BODY),
    ('hidden-url', '.img{b:"/*"} .img{background:url(http://127.0.0.1:9/EVIL-URL);height:50px} .img{e:"*/"}', BODY),
    ('empty-content-with-comment-strings', '.a::before{content:"";y:"/*";z:"*/"}', BODY),
    ('list-item-display', '.a{display:list-item;height:20px}', BODY),
    ('bare-list-items', '', '<div style="display:none">{{title_main}}</div><div><li><br></li><li><br></li></div>'),
    ('list-item-in-list', 'ul{margin-left:120px}', BODY),
    ('marker-pseudo', 'li::marker{content:""}', BODY),
    ('ol-removed', '', BODY.replace('<ul', '<ol').replace('</ul>', '</ol>')),
    ('local-font-face', '@font-face{font-family:Outfit;src:local("Wingdings")} .a{font-family:Outfit}', BODY),
]


@pytest.mark.parametrize('css, body', [pytest.param(c, b, id=i) for i, c, b in NEUTRALISED])
def test_neutralised_pages_draw_no_text_in_a_real_browser(renderer, css, body):
    result = sanitize_template(page(css, body))

    assert result.accepted, [violation.message for violation in result.violations]
    assert is_flat(draw(renderer, result.html))


def test_the_default_list_markers_are_drawn_without_the_forced_rule(renderer):
    """Control for the list tests above: a bare ``<li>`` does draw a bullet when nothing removes it."""
    assert not is_flat(draw(renderer, page('', '<div style="display:none">{{title_main}}</div><ul><li><br></li></ul>')))


@pytest.mark.parametrize('template_id', ['noche-dorada', 'luz-clara', 'minimal'])
def test_sanitizing_does_not_change_the_built_in_designs(renderer, template_id):
    template = TemplateCatalog().load(template_id)
    cover = Cover.from_raw(
        'Resistir', title_accent='al diablo', subtitle='Firmes en la batalla de la mente', key_verse='Efesios 6:11',
        readings=['Efesios 6:11-12', 'Romanos 8:1 · 12:1-2'], template_id=template_id)
    icon = IconCatalog().svg('shield-heart')
    sanitized = sanitize_template(template.html, required=template.manifest.required)

    original_png = renderer.render(render_cover(template.html, cover, icon, required=template.manifest.required),
                                   TEMPLATE_DIR / template_id)
    clean_png = renderer.render(render_cover(sanitized.html, cover, icon, required=template.manifest.required),
                                TEMPLATE_DIR / template_id)

    assert sanitized.accepted and not sanitized.violations
    assert QtGui.QImage.fromData(original_png.png_bytes) == QtGui.QImage.fromData(clean_png.png_bytes)
    assert len(colours(QtGui.QImage.fromData(clean_png.png_bytes).convertToFormat(QtGui.QImage.Format_RGB32))) > 50


def test_a_template_with_only_placeholders_draws_only_the_user_values(renderer):
    """The positive side: the sanitized built-in-like page shows the value exactly where its element is."""
    html = sanitize_template(page('.t{font-size:60px}', '<div class="t">{{title_main}}</div>')).html
    image = draw(renderer, html)

    assert not is_flat(image)
    assert all(image.pixel(x, 300) == BACKGROUND for x in range(0, 640, 7))  # below the single text line
