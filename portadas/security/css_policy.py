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
CSS rules for untrusted templates.

The checks run on a normalised copy (comments removed, CSS escapes decoded, lower-cased) so that tricks such as
``\\75rl(...)``, ``ur/**/l(...)`` or ``@\\69mport`` cannot hide a forbidden construct. Anything that is not clearly
safe is a problem; the caller drops the whole ``<style>`` block or ``style`` attribute that has one.
"""
import re
from dataclasses import dataclass

CSS_REJECTED = 'css-rejected'
CSS_CONTENT_TEXT = 'css-content-text'

# A url() may point to a fragment of the same document or to a bundled font/background next to the templates.
ASSET_URL = re.compile(r'^\.\./\.\./assets/(?:fonts|backgrounds)/[A-Za-z0-9][A-Za-z0-9._-]*$')
FRAGMENT_URL = re.compile(r'^#[A-Za-z][A-Za-z0-9_:.-]*$')

ALLOWED_AT_RULES = frozenset({'font-face', 'media', 'keyframes', '-webkit-keyframes', 'supports', 'page'})
ALLOWED_CONTENT = frozenset({'""', "''", 'none', 'normal'})

_COMMENT = re.compile(r'/\*.*?(?:\*/|$)', re.DOTALL)
_ESCAPE = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(.))', re.DOTALL)
_AT_RULE = re.compile(r'@\s*([a-z-]*)')
_URL_START = re.compile(r'(?<![\w-])url\s*\(')
_URL_FULL = re.compile(r'(?<![\w-])url\s*\(\s*(?:"([^"]*)"|\'([^\']*)\'|([^\'")\s]*))\s*\)')
_FORBIDDEN_FUNCTIONS = re.compile(
    r'(?<![\w-])(?:image-set|-webkit-image-set|cross-fade|-webkit-cross-fade|element|-moz-element|paint|image|src'
    r'|expression)\s*\(')
_FORBIDDEN_TOKENS = ('javascript:', 'vbscript:', 'livescript:', 'behavior:', 'behaviour:', '-moz-binding')
_CONTENT = re.compile(r'(?<![\w-])content\s*:([^;}]*)')


@dataclass(frozen=True)
class CssProblem:
    """One reason a piece of CSS is not acceptable."""
    code: str
    message: str


def normalise(css):
    """Return ``css`` without comments, with escapes decoded, lower-cased."""
    def unescape(match):
        if match.group(1):
            code = int(match.group(1), 16)
            return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else '�'
        return match.group(2)
    return _ESCAPE.sub(unescape, _COMMENT.sub('', css)).lower()


def url_targets(text):
    """Return the targets of every ``url()`` in normalised ``text`` or ``None`` if one is malformed."""
    found = _URL_FULL.findall(text)
    if len(found) != len(_URL_START.findall(text)):
        return None
    return [(quoted or single or bare).strip() for quoted, single, bare in found]


def url_problem(text):
    """Return a message when normalised ``text`` has a ``url()`` that is not a fragment or bundled asset."""
    targets = url_targets(text)
    if targets is None:
        return 'a url() could not be read'
    for target in targets:
        if not (FRAGMENT_URL.match(target) or ASSET_URL.match(target)):
            return f'url("{target[:40]}") is not a #fragment or a bundled asset'
    return None


def check_css(css):
    """Return the list of ``CssProblem`` found in a style sheet or a declaration list (empty when it is safe)."""
    problems = []
    if '<' in css or '&' in css:
        problems.append(CssProblem(CSS_REJECTED, 'CSS must not contain "<" or "&".'))
    if '{{' in css:
        problems.append(CssProblem(CSS_REJECTED, 'Placeholders are not allowed inside CSS.'))
    text = normalise(css)
    for name in _AT_RULE.findall(text):
        if name not in ALLOWED_AT_RULES:
            problems.append(CssProblem(CSS_REJECTED, f'The CSS rule "@{name}" is not allowed.'))
    for token in _FORBIDDEN_TOKENS:
        if token in text:
            problems.append(CssProblem(CSS_REJECTED, f'"{token}" is not allowed in CSS.'))
    if _FORBIDDEN_FUNCTIONS.search(text):
        problems.append(CssProblem(CSS_REJECTED, 'This CSS function can load external content.'))
    message = url_problem(text)
    if message:
        problems.append(CssProblem(CSS_REJECTED, f'CSS {message}.'))
    for value in _CONTENT.findall(text):
        cleaned = value.replace('!important', '').strip()
        if cleaned not in ALLOWED_CONTENT:
            problems.append(CssProblem(
                CSS_CONTENT_TEXT, 'CSS "content" may only be empty: it could show hard-coded text.'))
    return problems
