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
"""The CSS tokenizer and sanitizer: tokenization per CSS Syntax Level 3, allowlists and re-serialization."""
import random
import time

import pytest
from contrib.plugins.portadas.security.css_policy import (
    BASE_CSS,
    CSS_CONTENT_TEXT,
    CSS_REJECTED,
    FONT_FAMILIES,
    CssSyntaxError,
    sanitize_declarations,
    sanitize_stylesheet,
    tokenize,
)


def kinds(css):
    return [(token.kind, token.value) for token in tokenize(css) if token.kind != 'ws']


# --- tokenizer ---------------------------------------------------------------------------------------------------

def test_comments_are_dropped_and_act_as_whitespace():
    assert kinds('a/* x */b') == [('ident', 'a'), ('ident', 'b')]
    assert [token.kind for token in tokenize('a/**/b')] == ['ident', 'ws', 'ident']


def test_comment_markers_inside_strings_are_string_content():
    assert kinds('"/*" x "*/"') == [('string', '/*'), ('ident', 'x'), ('string', '*/')]
    assert kinds("'/*'") == [('string', '/*')]


def test_string_escapes_and_line_continuations():
    assert kinds('"a\\"b"') == [('string', 'a"b')]
    assert kinds("'a\\'b'") == [('string', "a'b")]
    assert kinds('"a\\\nb"') == [('string', 'ab')]
    assert kinds('"\\41 B"') == [('string', 'AB')]
    assert kinds('"\\000041"') == [('string', 'A')]


@pytest.mark.parametrize('text', ['"open', "'open", '"a\nb"', '"a\\', '/* open', 'url(a b)', 'url(a"b)', "url(a'b)",
                                  'url(a(b)', 'url(open', 'url(a\\\n)', 'url(\x01)', '-->'])
def test_malformed_input_is_a_syntax_error(text):
    with pytest.raises(CssSyntaxError):
        tokenize(text)


def test_escapes_in_identifiers_are_decoded():
    assert kinds('\\75 rl') == [('ident', 'url')]
    assert kinds('c\\6fntent') == [('ident', 'content')]
    assert kinds('\\63 olor') == [('ident', 'color')]
    assert kinds('a\\:b') == [('ident', 'a:b')]
    assert kinds('\\0 x')[0][1] == '�' + 'x'
    assert kinds('\\d800 x')[0][1] == '�x'
    assert kinds('\\110000 x')[0][1] == '�x'


def test_escaped_url_is_still_a_url_token():
    assert kinds('\\75 rl(http://evil.example/x)') == [('url', 'http://evil.example/x')]
    assert kinds('URL( x )') == [('url', 'x')]
    assert kinds('ur\\6c(x)') == [('url', 'x')]


def test_quoted_url_is_folded_into_a_url_token():
    assert kinds('url( "a b" )') == [('url', 'a b')]
    assert kinds("url('x')") == [('url', 'x')]
    assert kinds('url(x)') == [('url', 'x')]


def test_a_quoted_url_with_extra_arguments_is_not_accepted():
    with pytest.raises(CssSyntaxError):
        tokenize('url("a" b)')


def test_numbers_dimensions_percentages_and_signs():
    tokens = [(token.kind, token.value, token.unit) for token in tokenize('1 +2 -3.5 .5 1e3 1E-3 10px 5% -0.01em 2n')
              if token.kind != 'ws']
    assert tokens == [
        ('number', '1', ''), ('number', '+2', ''), ('number', '-3.5', ''), ('number', '.5', ''),
        ('number', '1e3', ''), ('number', '1E-3', ''), ('dimension', '10', 'px'), ('percent', '5', ''),
        ('dimension', '-0.01', 'em'), ('dimension', '2', 'n')]


def test_functions_at_keywords_hashes_and_punctuation():
    assert kinds('rgb(1,2) @media #fff a:b;{}[]') == [
        ('function', 'rgb'), ('number', '1'), (',', ''), ('number', '2'), (')', ''), ('at', 'media'),
        ('hash', 'fff'), ('ident', 'a'), (':', ''), ('ident', 'b'), (';', ''), ('{', ''), ('}', ''), ('[', ''),
        (']', '')]
    assert kinds('--x -a -- _y') == [('ident', '--x'), ('ident', '-a'), ('ident', '--'), ('ident', '_y')]


def test_stray_characters_become_delimiters():
    assert kinds('@ # . - + \\\n !') == [
        ('delim', '@'), ('delim', '#'), ('delim', '.'), ('delim', '-'), ('delim', '+'), ('delim', '\\'),
        ('delim', '!')]


def test_newlines_and_form_feeds_are_normalised_and_nul_is_replaced():
    assert [token.kind for token in tokenize('a\r\nb\rc\fd')] == ['ident', 'ws', 'ident', 'ws', 'ident', 'ws', 'ident']
    assert kinds('a\x00b') == [('ident', 'a�b')]


# --- declarations ------------------------------------------------------------------------------------------------

def declarations(css):
    result = sanitize_declarations(css)
    return result.css, {problem.code for problem in result.problems}


def test_declarations_are_re_serialised_canonically():
    assert declarations('COLOR : red ;  margin:0 auto !IMPORTANT') == ('COLOR:red;margin:0 auto !important;', set())
    assert declarations('color:red;') == ('color:red;', set())
    assert declarations('') == ('', set())


def test_what_is_checked_is_what_is_emitted_for_comment_in_string_tricks():
    css, codes = declarations('content:""; y:"/*"; content:"HELLO"; z:"*/"')

    assert 'HELLO' not in css
    assert CSS_CONTENT_TEXT in codes


@pytest.mark.parametrize('value, kept', [
    ('""', True), ("''", True), ('none', True), ('normal', True), ('"" !important', True),
    ('" "', False), ('"x"', False), ('attr(x)', False), ('counter(x)', False), ('url(#a)', False),
    ('open-quote', False), ('"" ""', False), ('var(--x)', False), ('"\\41"', False),
])
def test_content_may_only_be_empty(value, kept):
    css, codes = declarations(f'content:{value}')

    assert bool(css) is kept
    assert (CSS_CONTENT_TEXT in codes) is (not kept)


@pytest.mark.parametrize('prop', ['list-style', 'list-style-type', 'list-style-image', 'quotes'])
def test_text_bearing_properties_only_accept_none(prop):
    assert declarations(f'{prop}:none')[0] == f'{prop}:none;'
    for bad in ('"x"', 'disc', 'decimal', 'none inside', 'url(#a)', 'var(--a)', 'inherit'):
        css, codes = declarations(f'{prop}:{bad}')
        assert css == '' and CSS_CONTENT_TEXT in codes, (prop, bad)


def test_counter_properties_are_refused():
    for prop in ('counter-reset', 'counter-increment', 'counter-set'):
        assert declarations(f'{prop}:a 1') == ('', {CSS_CONTENT_TEXT})


@pytest.mark.parametrize('css', [
    'color:"red"', 'background:url(http://evil.example/x)', 'background:url(//evil.example/x)',
    'background:url(../../../etc/passwd)', 'background:url(data:image/png;base64,AA)', 'width:expression(1)',
    'background:image-set("a" 1x)', 'color:javascript:alert(1)', 'text-overflow:"x"', 'animation:a 1s',
    'transition:all 1s', 'cursor:url(a)', 'behavior:url(a)', '-moz-binding:url(a)', 'position:{a}', 'x',
    ':red', 'color:', 'background:src(a)', 'color:red !', 'color:a!b', 'font:12px "Outfit"',
    'font-feature-settings:"liga"', '--x:"s"', '--x:{a}', '--x:url(http://evil.example)',
    'color:' + 'calc(' * 40 + '1' + ')' * 40,
])
def test_declarations_outside_the_allowlist_are_dropped(css):
    result = sanitize_declarations(css)

    assert result.css == ''
    assert result.problems


@pytest.mark.parametrize('css', [
    'color:#fff', 'color:rgba(1,2,3,.5)', 'width:calc(100% - 20px)', 'width:min(1px,2px)', 'width:clamp(1px,2vw,3px)',
    'background:linear-gradient(180deg,#000 0%,#fff 100%)', 'background:radial-gradient(circle at 10% 10%,#fff,#000)',
    'background:url(../../assets/backgrounds/bg.png)', 'fill:url(#g)', 'margin:-0.5em auto', '--accent:#fff',
    'color:var(--accent)', 'width:calc(var(--w) * 2)', 'transform:translate(1px,2px) rotate(3deg)',
    'filter:drop-shadow(0 0 2px #000)', 'font-family:"Outfit","Helvetica Neue",Arial,sans-serif',
    'font-family:Playfair Display,Georgia,serif', 'quotes:none', 'list-style:none', 'content:""',
    'grid-template-columns:repeat(2,minmax(0,1fr))', 'grid-template-columns:[a] 1fr [b] 2fr',
])
def test_allowlisted_declarations_survive(css):
    result = sanitize_declarations(css)

    assert not result.problems, (css, result.problems)
    assert result.css


def test_font_family_is_restricted_to_bundled_system_and_generic_families():
    kept = declarations('font-family:Wingdings,Arial')
    assert kept == ('', {CSS_REJECTED})
    assert declarations('font-family:"Webdings"') == ('', {CSS_REJECTED})
    assert declarations('font-family:Arial, f(x)') == ('', {CSS_REJECTED})
    assert declarations('font-family:var(--f)') == ('', {CSS_REJECTED})
    assert declarations('font-family:"Outfit", sans-serif')[0] == 'font-family:"Outfit", sans-serif;'


def test_var_is_refused_where_it_could_smuggle_text_or_fonts():
    assert declarations('content:var(--x)')[1] == {CSS_CONTENT_TEXT}
    assert declarations('font-family:var(--x)')[1] == {CSS_REJECTED}
    assert declarations('color:var(--x)') == ('color:var(--x);', set())


# --- style sheets ------------------------------------------------------------------------------------------------

def sheet(css):
    result = sanitize_stylesheet(css)
    return result.css, {problem.code for problem in result.problems}


def test_a_sheet_is_re_serialised_without_comments_or_extra_space():
    css = '/* c */ body , .a  >  b { color : red ; margin : 0 } @media (min-width:100px){ .c{ color:red } }'

    assert sheet(css) == ('body , .a > b{color:red;margin:0;}@media (min-width:100px){.c{color:red;}}', set())


def test_font_face_accepts_bundled_fonts_only():
    good = ('@font-face{font-family:"Outfit";font-weight:100 900;font-style:normal;font-display:swap;'
            'src:url(../../assets/fonts/Outfit-Variable.ttf) format("truetype"),'
            'url(../../assets/fonts/Outfit-Variable.woff2) format("woff2")}')

    assert sheet(good) == (good.replace('}', ';}'), set())
    for bad in ('src:local("Wingdings")', 'src:url(http://evil.example/f.ttf)',
                'src:url(../../assets/backgrounds/a.png)',
                'src:url(../../assets/fonts/a.ttf) format("x")', 'src:url(../../assets/fonts/a.ttf) tech(x)',
                'src:url(../../assets/fonts/a.ttf) format("truetype") x', 'src:"x"', 'src:',
                'src:url(../../assets/fonts/a.ttf),', 'font-family:Wingdings', 'unicode-range:U+0025',
                'font-family:"Outfit";src:var(--x)'):
        css, codes = sheet('@font-face{' + bad + '}')
        assert 'src:local' not in css and 'evil' not in css
        assert CSS_REJECTED in codes, bad
    assert sheet('@font-face{}')[0] == ''


def test_other_at_rules_are_dropped_with_their_blocks():
    for rule in ('@import url(http://evil.example/x.css);', '@import "x";', '@charset "x";', '@namespace url(x);',
                 '@keyframes a{from{opacity:0}}', '@supports (display:grid){a{color:red}}', '@page{margin:0}',
                 '@-webkit-keyframes a{}', '@media'):
        css, codes = sheet(rule + ' a{color:red}')
        assert css.endswith('a{color:red;}') or rule == '@media', rule
        assert CSS_REJECTED in codes, rule


def test_media_rules_nest_to_a_limited_depth():
    assert sheet('@media (a:b){@media (c:d){.x{color:red}}}')[0] == '@media (a:b){@media (c:d){.x{color:red;}}}'
    deep = '@media (a:b){' * 6 + '.x{color:red}' + '}' * 6
    assert sheet(deep)[0] == ''
    for prelude in ('url(http://evil.example)', '"x"', 'f(x)', 'x{y}'):
        assert sheet('@media ' + prelude + '{.x{color:red}}')[0] == ''


@pytest.mark.parametrize('selector', [
    'a', '.a', '#a', '*', 'a b', 'a>b', 'a+b', 'a~b', 'a,b', 'ul li:nth-child(2n+1)', 'a:not(.b)', '.a::before',
    '[x]', '[x=y]', '[x^=y]', '[x|=y]', 'svg|a', 'li:first-child', 'body.no-label .label-row',
])
def test_ordinary_selectors_pass(selector):
    assert sheet(selector + '{color:red}') == (selector + '{color:red;}', set())


@pytest.mark.parametrize('selector', [
    '[x="y"]', 'a:lang("es")', 'a:has(b)', 'a[x=url(y)]', '@x', 'a;b', ':host(x)', '', 'a{b', '#\\31 23\\',
    'a:f(b,"c")', 'a:where(.x', '$a', 'a::-x-y("z")',
])
def test_unsafe_or_unreadable_selectors_drop_the_rule(selector):
    css, codes = sheet(selector + '{color:red}')

    assert 'color' not in css or not css
    assert codes


def test_unreadable_sheets_are_dropped_whole():
    for text in ('a{color:red', 'a{color:red}}', 'a{color:rgb(1}', '/* x', 'a{b:"c}', 'a{b:url(c d)}', 'a{{color:red}}',
                 'a<b{color:red}', 'a{color:red;&:hover{color:blue}}'):
        css, codes = sheet(text)
        assert css == '' and codes == {CSS_REJECTED}, text


def test_a_rule_without_a_block_is_dropped():
    assert sheet('a{color:red} b')[1] == {CSS_REJECTED}
    assert sheet('a{color:red} b')[0] == 'a{color:red;}'


def test_base_css_is_itself_valid():
    assert sheet(BASE_CSS) == (BASE_CSS, set())
    assert sheet('*{list-style:none}') == (BASE_CSS, set())


def test_non_string_input_is_rejected():
    assert sanitize_stylesheet(None).css == ''
    assert sanitize_declarations(5).problems


# --- properties of the whole pipeline ----------------------------------------------------------------------------

PIECES = [
    'a', '.b', 'div', 'li', '::before', '::marker', ':hover', '{', '}', ';', ':', ',', '(', ')', '[', ']', ' ', '\n',
    '"', "'", '\\', '\\"', "\\'", '\\/', '/*', '*/', '/', '*', '@media', '@import', '@font-face', 'url(', 'url(x)',
    'url(http://evil.example/x)', '"HELLO"', "'HELLO'", 'content', 'content:', 'list-style-type:', 'list-style:',
    'font-family:', 'quotes:', 'counter(x)', 'attr(x)', 'var(--x)', '--x:', 'color:red', 'color:', 'red', '!important',
    '\\75 rl(', '\\63 ontent', 'src:', 'local(', 'format("truetype")', '"Outfit"', 'Arial', 'none', '""', 'open-quote',
    '1', '1px', '10%', '#fff', '-', '+', '=', '^', 'calc(', 'src(', 'image-set(', '\x01', '�', 'é', 'é',
]


def _generated(count, seed):
    rng = random.Random(seed)
    for _ in range(count):
        yield ''.join(rng.choice(PIECES) for _ in range(rng.randint(1, 40)))


def _string_contexts(css):
    """Yield ``(property, string value)`` for every string token of already-sanitised CSS."""
    tokens = [token for token in tokenize(css) if token.kind != 'ws']
    for index, token in enumerate(tokens):
        if token.kind != 'string':
            continue
        start = index
        while start > 0 and tokens[start - 1].kind not in ('{', ';', '}'):
            start -= 1
        yield tokens[start].value.lower(), token.value


def _assert_strings_are_in_allowed_contexts(css):
    for prop, value in _string_contexts(css):
        if prop == 'content':
            assert value == '', css
        elif prop == 'font-family':
            assert value.lower() in FONT_FAMILIES, css
        elif prop == 'src':
            assert value in ('truetype', 'opentype', 'woff', 'woff2'), css
        else:
            raise AssertionError(f'string "{value}" survived in "{prop}": {css}')


@pytest.mark.parametrize('seed', range(6))
def test_generated_sheets_are_idempotent_and_keep_strings_in_allowed_contexts(seed):
    for text in _generated(400, seed):
        for sanitize in (sanitize_stylesheet, sanitize_declarations):
            first = sanitize(text)
            second = sanitize(first.css)

            assert second.css == first.css, (text, first.css)
            assert not second.problems, (text, first.css, second.problems)
            assert '<' not in first.css and '&' not in first.css
            assert 'evil' not in first.css and '@import' not in first.css
            _assert_strings_are_in_allowed_contexts(first.css)


def test_no_string_survives_in_a_corpus_of_hostile_sheets():
    corpus = [
        'a{b:"/*"} c{content:"X"} d{e:"*/"}', 'a{content:"\\";X"}', 'a{b:c\\/*} d{content:"X"} e{f:g*/}',
        'li{list-style:"X " inside}', 'q{quotes:"a" "b"}', ':root{--t:"X"} a::before{content:var(--t)}',
        'a{font-family:"Wingdings"}', 'a{text-overflow:"X"}', 'a::before{content:"" "X"}',
    ]
    for text in corpus:
        out = sanitize_stylesheet(text).css
        assert 'X' not in out and 'Wingdings' not in out, (text, out)
        _assert_strings_are_in_allowed_contexts(out)


def test_the_tokenizer_is_linear_on_adversarial_input():
    started = time.perf_counter()
    for text in ('\\' * 50000, '/*' * 50000, 'url(' * 20000, '"' * 50000, 'a' * 100000, ' ' * 100000, '(' * 50000,
                 '\\75 ' * 20000):
        assert sanitize_stylesheet(text).css == ''
    assert time.perf_counter() - started < 5
