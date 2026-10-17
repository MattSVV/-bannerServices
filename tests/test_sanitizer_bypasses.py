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
Regression tests for the sanitizer bypasses confirmed by the T06 adversarial verification (T06b).

Every payload is checked end to end through ``sanitize_template``. A payload is either **rejected** (a fatal violation
with a given code, no output) or **neutralised** (the template is accepted, the dangerous part is gone from the output
and a violation says so). The rendered counterparts live in ``test_sanitizer_rendered.py``.
"""
import pytest
from contrib.plugins.portadas.domain.templating import find_placeholders
from contrib.plugins.portadas.security.html_policy import sanitize_svg, sanitize_template

BODY = '<div class="a">{{title_main}}</div><ul class="readings"><li>{{readings}}</li></ul><div class="img"></div>'


def doc(css='', body=BODY):
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><style>{css}</style></head>'
            f'<body>{body}</body></html>')


def attr_doc(style):
    quote = '"' if '"' not in style else "'"
    return doc('', f'<div style={quote}{style}{quote}>{{{{title_main}}}}</div>')


# (id, document, fatal code) - the text-bearing payloads must be refused outright.
REJECTED = [
    ('comment-in-string-content', doc('.a::before{content:"" ; y:"/*" ; content:"HELLO-A"; z:"*/"}'),
     'css-content-text'),
    ('escaped-quote-content', doc('.a::before{content:"\\";HELLO-B"}'), 'css-content-text'),
    ('escaped-slash-comment', doc('.a{b:c\\/*} .a::before{content:"HELLO-C"} e{f:g*/}'), 'css-content-text'),
    ('list-style-type-string', doc('.readings{list-style-type:"HELLO-D "}'), 'css-content-text'),
    ('list-style-shorthand-string', doc('li{list-style:"HELLO " inside}'), 'css-content-text'),
    ('list-style-type-decimal', doc('.readings{list-style-type:decimal}'), 'css-content-text'),
    ('list-style-image-url', doc('li{list-style-image:url(#a)}'), 'css-content-text'),
    ('list-style-via-var', doc(':root{--m:decimal} li{list-style-type:var(--m)}'), 'css-content-text'),
    ('counter-content', doc('.a::before{content:counter(x)}'), 'css-content-text'),
    ('counter-reset', doc('.a{counter-reset:x 5}'), 'css-content-text'),
    ('content-attr', doc('.a::before{content:attr(class)}'), 'css-content-text'),
    ('content-open-quote', doc('.a::before{content:open-quote}'), 'css-content-text'),
    ('content-via-var', doc(':root{--t:open-quote} .a::before{content:var(--t)}'), 'css-content-text'),
    ('content-unicode-escape', doc('.a::before{content:"\\0041"}'), 'css-content-text'),
    ('content-escaped-property-name', doc('.a::before{c\\6fntent:"HELLO"}'), 'css-content-text'),
    ('content-uppercase-property', doc('.a::before{CONTENT:"HELLO"}'), 'css-content-text'),
    ('content-important', doc('.a::before{content:"HELLO" !important}'), 'css-content-text'),
    ('quotes-pair', doc('q{quotes:"a" "b"}'), 'css-content-text'),
    ('marker-content', doc('li::marker{content:"HELLO"}'), 'css-content-text'),
    ('style-attr-comment-in-string', attr_doc("content:''; a:'/*'; content:'HI'; b:'*/'"), 'css-content-text'),
    ('style-attr-escaped-quote', attr_doc('content:"\\";HI"'), 'css-content-text'),
    ('style-attr-list-style', attr_doc('list-style:"HI " inside'), 'css-content-text'),
    ('unclosed-style-swallows-body', '<style>.a::before{content:"HI"}\n<div>{{title_main}}</div>',
     'missing-placeholder'),
]


@pytest.mark.parametrize('document, code', [pytest.param(d, c, id=i) for i, d, c in REJECTED])
def test_text_bearing_payloads_are_rejected(document, code):
    result = sanitize_template(document)

    assert not result.accepted, result.html
    assert result.html is None
    assert code in {violation.code for violation in result.violations}


# (id, document, fragments that must not survive in the output, violation code that must be reported)
NEUTRALISED = [
    ('hide-url-behind-comment-string',
     doc('.img{b:"/*"} .img{background:url(http://127.0.0.1:9/EVIL-URL)} .img{e:"*/"}'), ('evil', '127.0.0.1', 'http'),
     'css-rejected'),
    ('hide-import-behind-comment-string', doc('a{b:"/*"} @import "file:///etc/hostname"; c{d:"*/"}'),
     ('@import', 'file:', '/etc'), 'css-rejected'),
    ('style-attr-hide-url', attr_doc("b:'/*'; background:url(http://evil.example/x); e:'*/'"),
     ('evil', 'http', '/*'), 'css-rejected'),
    ('ol-numbering', doc('', '<div>{{title_main}}</div><ol><li>{{subtitle}}</li></ol>'), ('<ol', '</ol>'),
     'element-removed'),
    ('font-face-local', doc('@font-face{font-family:Outfit;src:local("Wingdings")}'), ('local', 'wingdings'),
     'css-rejected'),
    ('font-face-remote', doc('@font-face{font-family:Outfit;src:url(http://evil.example/f.ttf)}'), ('evil', 'http'),
     'css-rejected'),
    ('font-face-background-asset', doc('@font-face{font-family:Outfit;src:url(../../assets/backgrounds/a.png)}'),
     ('backgrounds',), 'css-rejected'),
    ('font-family-symbol-font', doc('.a{font-family:Wingdings,"Webdings",sans-serif}'), ('wingdings', 'webdings'),
     'css-rejected'),
    ('font-family-via-var', doc(':root{--f:Wingdings} .a{font-family:var(--f)}'), ('var(',), 'css-rejected'),
    ('custom-property-string', doc(':root{--t:"HELLO"} .a{color:red}'), ('hello',), 'css-rejected'),
    ('text-overflow-string', doc('.a{text-overflow:"HELLO"}'), ('hello',), 'css-rejected'),
    ('font-feature-string', doc('.a{font-feature-settings:"liga"}'), ('liga',), 'css-rejected'),
    ('keyframes', doc('@keyframes x{from{opacity:0}to{opacity:1}} .a{animation:x 1s}'), ('keyframes', 'animation'),
     'css-rejected'),
    ('namespace', doc('@namespace url(http://evil.example);'), ('evil', 'namespace'), 'css-rejected'),
    ('charset', doc('@charset "x";'), ('@charset',), 'css-rejected'),
    ('import-escaped', doc('@\\69mport "x.css";'), ('import',), 'css-rejected'),
    ('url-escaped-name', doc('.a{background:\\75 rl(http://evil.example/x)}'), ('evil',), 'css-rejected'),
    ('url-partly-escaped-name', doc('.a{background:ur\\6c(http://evil.example/x)}'), ('evil',), 'css-rejected'),
    ('url-comment-split', doc('.a{background:ur/**/l(http://evil.example/x)}'), ('evil',), 'css-rejected'),
    ('url-uppercase', doc('A{BACKGROUND:URL(http://evil.example/x)}'), ('evil',), 'css-rejected'),
    ('url-quoted-escaped-scheme', doc('.a{background:url("ht\\74 p://evil.example/x")}'), ('evil',), 'css-rejected'),
    ('image-set-prefixed', doc('.a{background:-webkit-image-set(url(#a) 1x)}'), ('image-set',), 'css-rejected'),
    ('src-function', doc('.a{background:src("http://evil.example/x")}'), ('evil', 'src'), 'css-rejected'),
    ('expression', doc('.a{width:expression(alert(1))}'), ('expression',), 'css-rejected'),
    ('javascript-value', doc('.a{background:javascript:alert(1)}'), ('javascript',), 'css-rejected'),
    ('behavior', doc('.a{behavior:url(x.htc)}'), ('behavior',), 'css-rejected'),
    ('nested-block-in-value', doc('.a{color:{red}}'), ('{red}',), 'css-rejected'),
    ('unknown-pseudo-function', doc('.a:lang("es"){color:red}'), (':lang',), 'css-rejected'),
    ('selector-string', doc('[x="HELLO"]{color:red}'), ('hello',), 'css-rejected'),
    ('selector-url', doc('a[x=url(http://evil.example)]{color:red}'), ('evil',), 'css-rejected'),
    ('media-with-url', doc('@media url(http://evil.example){.a{color:red}}'), ('evil',), 'css-rejected'),
    # Unreadable style sheets are dropped as a whole: where a rule ends cannot be trusted.
    ('placeholder-in-css', doc('div{color:{{title_main}}}'), ('color',), 'css-rejected'),
    ('unterminated-string', doc('.a{color:red;font-family:"Outfit}'), ('color',), 'css-rejected'),
    ('newline-in-string', doc('.a{color:red;font-family:"Out\nfit"}'), ('color',), 'css-rejected'),
    ('unterminated-comment', doc('.a{color:red} /* never closed'), ('color',), 'css-rejected'),
    ('bad-url-space', doc('.a{color:red;background:url(a b)}'), ('color',), 'css-rejected'),
    ('bad-url-quote', doc('.a{color:red;background:url(a"b)}'), ('color',), 'css-rejected'),
    ('unbalanced-brace', doc('.a{color:red'), ('color',), 'css-rejected'),
    ('stray-close-brace', doc('.a{color:red}} .b{color:blue}'), ('color',), 'css-rejected'),
    ('unbalanced-paren', doc('.a{color:rgb(1,2,3}'), ('color',), 'css-rejected'),
    ('svg-text-placeholder-in-body', doc('', '<svg><text>HELLO</text></svg><div>{{title_main}}</div>'), ('hello',),
     'element-removed'),
]


@pytest.mark.parametrize('document, absent, code', [pytest.param(d, a, c, id=i) for i, d, a, c in NEUTRALISED])
def test_dangerous_parts_are_neutralised(document, absent, code):
    result = sanitize_template(document)

    assert result.accepted, [violation.message for violation in result.violations]
    assert code in {violation.code for violation in result.violations}
    lowered = result.html.lower()
    for fragment in absent:
        assert fragment not in lowered, fragment
    assert find_placeholders(result.html)[0] == 'title_main'


def test_the_forced_list_style_rule_is_emitted_first_and_only_once():
    once = sanitize_template(doc('.a{color:red}'))
    twice = sanitize_template(once.html)

    assert once.html.count('list-style:none') == 1
    assert once.html.index('list-style:none') < once.html.index('color:red')
    assert twice.html == once.html


def test_lists_may_only_set_list_style_none():
    result = sanitize_template(doc('li{list-style:none} ul{list-style-type:none!important}'))

    assert result.accepted
    assert not result.violations


@pytest.mark.parametrize('payload', [
    '<svg>{{title_main}}<path d="M0 0"/></svg>',
    '<svg><path d="M0 0"/>{{readings}}</svg>',
    '<svg><g>{{icon}}</g></svg>',
    '<svg>{{ title_main }}</svg>',
])
def test_icons_reject_placeholder_looking_text(payload):
    result = sanitize_svg(payload)

    assert not result.accepted
    assert 'hardcoded-text' in {violation.code for violation in result.violations}


def test_icon_styles_use_the_same_tokenizer():
    result = sanitize_svg('<svg><path style="b:\'/*\'; fill:url(http://evil.example/x); e:\'*/\'" d="M0 0"/></svg>')

    assert result.accepted
    assert 'evil' not in result.html
    assert 'css-rejected' in {violation.code for violation in result.violations}


def test_every_bundled_icon_passes_the_svg_sanitizer_unchanged():
    from contrib.plugins.portadas.application.icon_catalog import IconCatalog
    catalog = IconCatalog()

    assert catalog.ids()
    for icon_id in catalog.ids():
        result = sanitize_svg(catalog.svg(icon_id))

        assert result.accepted and not result.violations, icon_id
