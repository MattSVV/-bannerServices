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
Regression tests for the low-severity sanitizer residuals found when re-verifying T06b (T06c).

* ``-webkit-line-clamp`` makes the browser draw a hard-coded ellipsis, so it is not on the property allowlist.
* ``U+41url(...)`` is one unicode-range token for a browser but was read as a dimension followed by a function, so a
  value could carry a ``(`` that the tokenizer did not recognise as a function. The tokenizer now reads it the same way.
"""
import pytest
from contrib.plugins.portadas.security.css_policy import (
    sanitize_declarations,
    sanitize_stylesheet,
    tokenize,
    value_problem,
)
from contrib.plugins.portadas.security.html_policy import sanitize_svg

CLAMP = '.a{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:1;width:120px;overflow:hidden}'
URANGE_VALUES = ['U+414141attr(x)', 'U+41url(http://127.0.0.1:9/f)', 'U+41element(#a)', 'u+4??', 'U+0-7F', 'U+414141']


def test_line_clamp_is_dropped_but_the_rest_of_the_rule_survives():
    result = sanitize_stylesheet(CLAMP)

    assert 'line-clamp' not in result.css
    assert 'width:120px' in result.css
    assert any('line-clamp' in problem.message for problem in result.problems)


def test_line_clamp_is_dropped_from_style_attributes():
    assert 'line-clamp' not in sanitize_declarations('-webkit-line-clamp:2').css


def test_unicode_range_is_one_token():
    kinds = [token.kind for token in tokenize('U+41url(http://127.0.0.1:9/f)')]

    assert kinds[0] == 'urange'
    assert 'url' not in kinds[1:] or kinds.count('urange') == 1


@pytest.mark.parametrize('value', URANGE_VALUES)
def test_unicode_range_tokens_are_refused_in_declaration_values(value):
    result = sanitize_stylesheet('.a{color:' + value + '}')

    assert result.css == ''
    assert result.problems


@pytest.mark.parametrize('value', URANGE_VALUES)
def test_unicode_range_tokens_are_refused_in_svg_attributes(value):
    assert value_problem(value) is not None
    result = sanitize_svg('<svg><path stroke="' + value + '" d="M0 0"/></svg>')

    assert value not in result.html


def test_font_face_unicode_range_descriptor_stays_dropped():
    result = sanitize_stylesheet(
        '@font-face{font-family:Outfit;src:url(../../assets/fonts/a.ttf);unicode-range:U+0025}')

    assert 'unicode-range' not in result.css


@pytest.mark.parametrize('value', ['x(1)', '(1)', 'a:b', 'fill:red', '1(2)'])
def test_plain_attribute_values_reject_bare_brackets_and_colons(value):
    assert value_problem(value) is not None


@pytest.mark.parametrize('value', ['none', 'red', '#fff', 'rgb(1,2,3)', 'url(#grad)', '2px', '1 2 3', 'calc(1px+2px)'])
def test_plain_attribute_values_still_accept_normal_paint(value):
    assert value_problem(value) is None
