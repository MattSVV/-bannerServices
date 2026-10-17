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
CSS rules for untrusted templates: a real CSS tokenizer, an allowlist validator and a canonical re-serializer.

Untrusted CSS (a ``<style>`` block or a ``style`` attribute) is never searched with regular expressions. It is

1. **tokenized** exactly as CSS Syntax Module Level 3 describes (the algorithm Chromium implements): comments, strings
   with both quotes, escapes and line continuations, identifiers with escapes (``\\75 rl``), ``url()`` tokens,
   functions, at-keywords, numbers and so on. Anything the specification calls a parse error that could move a rule
   boundary (unterminated string or comment, bad ``url()``, unbalanced brackets) rejects the whole sheet;
2. **validated** on tokens: at-rules, selectors, properties, functions, ``url()`` targets and string tokens are
   checked against allowlists. An invalid declaration or rule is dropped and reported; the rest survives;
3. **re-serialized from the validated tokens** in a canonical form, and the result is tokenized again and compared with
   what was validated. What is checked is therefore exactly what the browser reads back, and sanitizing the output
   again changes nothing. A comment is replaced by whitespace; nothing else of the original text is kept.

Allowlist (see ``docs/templates.md``)
    * At-rules: ``@font-face`` (descriptors ``font-family``, ``src``, ``font-style``, ``font-weight``,
      ``font-stretch``, ``font-display``; ``src`` only ``url(../../assets/fonts/<file>)`` with an optional
      ``format("truetype"|"opentype"|"woff"|"woff2")``, never ``local()``) and ``@media`` (no strings or functions).
    * Selectors: type, class, id, attribute (without strings), combinators, pseudo-classes and pseudo-elements, plus
      ``:not``, ``:is``, ``:where`` and ``:nth-*``. No strings, urls or at-keywords.
    * Properties: layout, box, typography, colour, background, border, shadow, transform, filter, SVG paint properties
      and custom properties (``--x``). Everything else (``animation``, ``transition``, ``cursor``, ``font`` ...) is
      dropped.
    * Functions: colours, gradients, ``calc``/``min``/``max``/``clamp``/``var``, transforms, filters and grid helpers.
      ``attr()``, ``counter()``, ``image-set()``, ``element()``, ``src()``, ``local()`` and the rest are refused.
    * ``url()``: ``#fragment`` or ``../../assets/{fonts,backgrounds}/<file>`` only.
    * **Strings** are allowed only as ``font-family`` names (from a fixed list of bundled, common system and generic
      families), as ``format("...")`` in ``@font-face src`` and as the empty ``content: ""``.
    * **Text-bearing properties** (``content``, ``quotes``, ``list-style*``, ``counter-*``) accept nothing that could
      draw text: ``content`` only ``""``, ``none`` or ``normal``; ``quotes`` and ``list-style*`` only ``none``. Any
      other value is a fatal ``css-content-text`` problem (an attempt to inject visible text), not just a dropped
      declaration. ``var()`` is refused in these properties and in ``font-family``.
    * ``BASE_CSS`` (``* { list-style: none }``) is emitted ahead of every template, so no marker is ever drawn, even by
      ``display: list-item`` or a bare ``<li>``.
"""
import re
from dataclasses import dataclass

CSS_REJECTED = 'css-rejected'
MAX_PROBLEMS = 100  # distinct problems reported for one stylesheet; more means the whole sheet is refused
CSS_CONTENT_TEXT = 'css-content-text'

# A url() may point to a fragment of the same document or to a bundled font/background next to the templates.
ASSET_URL = re.compile(r'^\.\./\.\./assets/(?:fonts|backgrounds)/[A-Za-z0-9][A-Za-z0-9._-]*$')
FONT_URL = re.compile(r'^\.\./\.\./assets/fonts/[A-Za-z0-9][A-Za-z0-9._-]*\.(?:ttf|otf|woff2?)$', re.IGNORECASE)
FRAGMENT_URL = re.compile(r'^#[A-Za-z][A-Za-z0-9_:.-]*$')

# Emitted ahead of every template (canonical form of ``*{list-style:none}``).
BASE_CSS = '*{list-style:none;}'

MAX_NESTING = 32
MAX_MEDIA_DEPTH = 3

FONT_FORMATS = frozenset({'truetype', 'opentype', 'woff', 'woff2'})
FONT_FAMILIES = frozenset({
    # bundled (portadas/assets/fonts)
    'outfit', 'playfair display',
    # common system families
    'arial', 'helvetica', 'helvetica neue', 'georgia', 'times new roman', 'times', 'verdana', 'tahoma',
    'trebuchet ms', 'courier new', 'courier', 'segoe ui', 'roboto', 'open sans', 'dejavu sans', 'dejavu serif',
    'liberation sans', 'liberation serif', 'noto sans', 'noto serif',
    # generic families and CSS-wide keywords
    'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-serif', 'ui-sans-serif',
    'ui-monospace', 'inherit', 'initial', 'unset'})

FUNCTIONS = frozenset({
    'rgb', 'rgba', 'hsl', 'hsla', 'linear-gradient', 'radial-gradient', 'conic-gradient',
    'repeating-linear-gradient', 'repeating-radial-gradient', 'repeating-conic-gradient', 'calc', 'var', 'min', 'max',
    'clamp', 'translate', 'translatex', 'translatey', 'translatez', 'translate3d', 'scale', 'scalex', 'scaley',
    'scale3d', 'rotate', 'rotatex', 'rotatey', 'rotatez', 'rotate3d', 'skew', 'skewx', 'skewy', 'matrix', 'matrix3d',
    'perspective', 'blur', 'brightness', 'contrast', 'drop-shadow', 'grayscale', 'hue-rotate', 'invert', 'opacity',
    'saturate', 'sepia', 'repeat', 'minmax', 'fit-content'})
SELECTOR_FUNCTIONS = frozenset({'not', 'is', 'where', 'nth-child', 'nth-last-child', 'nth-of-type', 'nth-last-of-type'})

TEXT_PROPERTIES = frozenset({
    'content', 'quotes', 'list-style', 'list-style-type', 'list-style-image', 'counter-reset', 'counter-increment',
    'counter-set'})
NONE_ONLY_PROPERTIES = frozenset({'quotes', 'list-style', 'list-style-type', 'list-style-image'})
FONT_FACE_DESCRIPTORS = frozenset({'font-style', 'font-weight', 'font-stretch', 'font-display'})

PROPERTIES = frozenset("""
display position top right bottom left inset inset-block inset-inline z-index float clear width height min-width
min-height max-width max-height box-sizing overflow overflow-x overflow-y aspect-ratio object-fit object-position
margin margin-top margin-right margin-bottom margin-left padding padding-top padding-right padding-bottom padding-left
flex flex-basis flex-direction flex-flow flex-grow flex-shrink flex-wrap order align-content align-items align-self
justify-content justify-items justify-self place-content place-items place-self gap row-gap column-gap grid
grid-area grid-auto-columns grid-auto-flow grid-auto-rows grid-column grid-column-end grid-column-start grid-row
grid-row-end grid-row-start grid-template grid-template-areas grid-template-columns grid-template-rows vertical-align
visibility opacity white-space text-align text-align-last text-transform text-decoration text-decoration-color
text-decoration-line text-decoration-style text-decoration-thickness text-underline-offset text-indent text-shadow
line-height letter-spacing word-spacing word-break overflow-wrap word-wrap hyphens font-size font-weight font-style
font-variant font-variant-caps font-variant-numeric font-stretch font-kerning font-synthesis color background
background-color background-image background-position background-position-x background-position-y background-size
background-repeat background-attachment background-origin background-clip background-blend-mode border border-top
border-right border-bottom border-left border-color border-style border-width border-top-color border-right-color
border-bottom-color border-left-color border-top-style border-right-style border-bottom-style border-left-style
border-top-width border-right-width border-bottom-width border-left-width border-radius border-top-left-radius
border-top-right-radius border-bottom-left-radius border-bottom-right-radius border-collapse border-spacing outline
outline-color outline-style outline-width outline-offset box-shadow transform transform-origin transform-box
transform-style perspective perspective-origin filter backdrop-filter mix-blend-mode isolation clip-path mask
mask-image mask-position mask-repeat mask-size -webkit-mask -webkit-mask-image -webkit-mask-position
-webkit-mask-repeat -webkit-mask-size -webkit-background-clip -webkit-text-fill-color -webkit-text-stroke
-webkit-text-stroke-color -webkit-text-stroke-width -webkit-box-orient fill fill-opacity fill-rule
stroke stroke-width stroke-opacity stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset
stroke-miterlimit stop-color stop-opacity flood-color flood-opacity clip-rule vector-effect paint-order
""".split())

_IDENT = re.compile(r'^(?:--|-?[A-Za-z_])[A-Za-z0-9_-]*$')
_HASH = re.compile(r'^[A-Za-z0-9_-]+$')
_UNIT = re.compile(r'^[A-Za-z]{1,12}$')
_HEX = '0123456789abcdefABCDEF'
_PUNCTUATION = '{}()[]:;,'
_OPENERS = ('(', '[', '{', 'function')
_CLOSERS = {'(': ')', '[': ']', '{': '}', 'function': ')'}
_PLAIN_FORBIDDEN = ('javascript:', 'vbscript:', 'data:', 'expression(', '{{')


class CssSyntaxError(ValueError):
    """The CSS cannot be tokenized or its brackets do not match, so rule boundaries cannot be trusted."""


@dataclass(frozen=True)
class CssProblem:
    """One reason a piece of CSS is not acceptable (or was changed)."""
    code: str
    message: str


@dataclass(frozen=True)
class CssResult:
    """Canonical safe CSS (empty when nothing survived) and every problem found on the way."""
    css: str
    problems: tuple


@dataclass(frozen=True)
class Token:
    """A CSS token. ``value`` is decoded (escapes resolved); ``unit`` is only used by dimensions."""
    kind: str
    value: str = ''
    unit: str = ''


_WS = Token('ws')


def _is(char, chars):
    return char != '' and char in chars


def _digit(char):
    return char != '' and '0' <= char <= '9'


def _name_start(char):
    return char != '' and (char == '_' or (char.isascii() and char.isalpha()) or ord(char) >= 0x80)


def _name_char(char):
    return _name_start(char) or char == '-' or _digit(char)


# --- tokenizer (CSS Syntax Module Level 3, section 4) -------------------------------------------------------------

class _Tokenizer:
    def __init__(self, text):
        self.s = text.replace('\r\n', '\n').replace('\r', '\n').replace('\f', '\n').replace('\x00', '�')
        self.n = len(self.s)
        self.i = 0

    def at(self, index):
        return self.s[index] if 0 <= index < self.n else ''

    def run(self):
        tokens = []
        while self.i < self.n:
            token = self.next()
            if token.kind == 'ws' and tokens and tokens[-1].kind == 'ws':
                continue
            tokens.append(token)
        return _fold_urls(tokens)

    def next(self):
        s, i = self.s, self.i
        char = s[i]
        if char in ' \t\n':
            while self.i < self.n and s[self.i] in ' \t\n':
                self.i += 1
            return _WS
        if char == '/' and self.at(i + 1) == '*':
            end = s.find('*/', i + 2)
            if end < 0:
                raise CssSyntaxError('unterminated comment')
            self.i = end + 2
            return _WS
        if char in '"\'':
            self.i += 1
            return Token('string', self.string(char))
        if char == '#':
            self.i += 1
            if _name_char(self.at(i + 1)) or self.valid_escape(i + 1):
                return Token('hash', self.name())
            return Token('delim', '#')
        if char in _PUNCTUATION:
            self.i += 1
            return Token(char)
        if char in '+.' or char == '-' or _digit(char):
            if self.starts_number(i):
                return self.numeric()
            if char == '-' and s.startswith('-->', i):
                raise CssSyntaxError('unexpected "-->"')
            if char == '-' and self.starts_ident(i):
                return self.ident_like()
        elif char == '@':
            self.i += 1
            if self.starts_ident(i + 1):
                return Token('at', self.name())
            return Token('delim', '@')
        elif char in 'uU' and self.starts_unicode_range(i):
            return self.unicode_range()
        elif char == '\\' and self.valid_escape(i) or _name_start(char):
            return self.ident_like()
        self.i += 1
        return Token('delim', char)

    # predicates
    def valid_escape(self, index):
        return self.at(index) == '\\' and self.at(index + 1) not in ('', '\n')

    def starts_ident(self, index):
        char = self.at(index)
        if _name_start(char):
            return True
        if char == '-':
            nxt = self.at(index + 1)
            return _name_start(nxt) or nxt == '-' or self.valid_escape(index + 1)
        return self.valid_escape(index)

    def starts_unicode_range(self, index):
        """``U+`` followed by a hex digit or ``?`` begins a unicode-range token."""
        return self.at(index + 1) == '+' and _is(self.at(index + 2), _HEX + '?')

    def starts_number(self, index):
        char = self.at(index)
        if _is(char, '+-'):
            nxt = self.at(index + 1)
            return _digit(nxt) or (nxt == '.' and _digit(self.at(index + 2)))
        if char == '.':
            return _digit(self.at(index + 1))
        return _digit(char)

    # consumers
    def escape(self):
        """Consume what follows a backslash (already known to be a valid escape) and return the character."""
        s, i = self.s, self.i
        if s[i] in _HEX:
            j = i
            while j < self.n and j - i < 6 and s[j] in _HEX:
                j += 1
            code = int(s[i:j], 16)
            self.i = j + 1 if _is(self.at(j), ' \t\n') else j
            return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else '�'
        self.i = i + 1
        return s[i]

    def name(self):
        parts = []
        while self.i < self.n:
            char = self.s[self.i]
            if _name_char(char):
                parts.append(char)
                self.i += 1
            elif self.valid_escape(self.i):
                self.i += 1
                parts.append(self.escape())
            else:
                break
        return ''.join(parts)

    def number(self):
        start = self.i
        if _is(self.at(self.i), '+-'):
            self.i += 1
        while _digit(self.at(self.i)):
            self.i += 1
        if self.at(self.i) == '.' and _digit(self.at(self.i + 1)):
            self.i += 1
            while _digit(self.at(self.i)):
                self.i += 1
        if _is(self.at(self.i), 'eE'):
            sign = 1 if _is(self.at(self.i + 1), '+-') else 0
            if _digit(self.at(self.i + 1 + sign)):
                self.i += 1 + sign
                while _digit(self.at(self.i)):
                    self.i += 1
        return self.s[start:self.i]

    def unicode_range(self):
        """Consume ``U+hhhhhh``, ``U+hh??`` or ``U+hhhh-hhhh`` as one token, as Chromium does."""
        start = self.i
        self.i += 2
        digits = 0
        while digits < 6 and _is(self.at(self.i), _HEX):
            self.i += 1
            digits += 1
        wildcard = False
        while digits < 6 and self.at(self.i) == '?':
            self.i += 1
            digits += 1
            wildcard = True
        if not wildcard and self.at(self.i) == '-' and _is(self.at(self.i + 1), _HEX):
            self.i += 1
            digits = 0
            while digits < 6 and _is(self.at(self.i), _HEX):
                self.i += 1
                digits += 1
        return Token('urange', self.s[start:self.i])

    def numeric(self):
        value = self.number()
        if self.starts_ident(self.i):
            return Token('dimension', value, self.name())
        if self.at(self.i) == '%':
            self.i += 1
            return Token('percent', value)
        return Token('number', value)

    def string(self, quote):
        parts = []
        while True:
            char = self.at(self.i)
            if char == '':
                raise CssSyntaxError('unterminated string')
            self.i += 1
            if char == quote:
                return ''.join(parts)
            if char == '\n':
                raise CssSyntaxError('newline in string')
            if char != '\\':
                parts.append(char)
            elif self.at(self.i) == '':
                raise CssSyntaxError('unterminated string')
            elif self.at(self.i) == '\n':
                self.i += 1  # line continuation
            else:
                parts.append(self.escape())

    def ident_like(self):
        name = self.name()
        if self.at(self.i) != '(':
            return Token('ident', name)
        self.i += 1
        if name.lower() != 'url':
            return Token('function', name)
        j = self.i
        while _is(self.at(j), ' \t\n'):
            j += 1
        if _is(self.at(j), '"\''):
            return Token('function', 'url')  # folded into a url token by ``_fold_urls``
        return Token('url', self.url())

    def url(self):
        parts = []
        while _is(self.at(self.i), ' \t\n'):
            self.i += 1
        while True:
            char = self.at(self.i)
            if char == '':
                raise CssSyntaxError('unterminated url()')
            self.i += 1
            if char == ')':
                return ''.join(parts)
            if char in ' \t\n':
                while _is(self.at(self.i), ' \t\n'):
                    self.i += 1
                if self.at(self.i) != ')':
                    raise CssSyntaxError('bad url()')
            elif char in '"\'(' or ord(char) < 0x20 and char not in '\t\n' or ord(char) == 0x7F:
                raise CssSyntaxError('bad url()')
            elif char == '\\':
                if not self.valid_escape(self.i - 1):
                    raise CssSyntaxError('bad url()')
                parts.append(self.escape())
            else:
                parts.append(char)


def _fold_urls(tokens):
    """Turn ``url( "x" )`` (a function token, a string and ``)``) into one url token; refuse any other ``url(``."""
    folded, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind != 'function' or token.value != 'url':
            folded.append(token)
            index += 1
            continue
        args = [item for item in tokens[index + 1:index + 5] if item.kind != 'ws']
        if len(args) < 2 or args[0].kind != 'string' or args[1].kind != ')':
            raise CssSyntaxError('bad url()')
        folded.append(Token('url', args[0].value))
        index += 1
        for _ in range(2):  # the string and the closing bracket, with any whitespace around them
            while tokens[index].kind == 'ws':
                index += 1
            index += 1
    return folded


def tokenize(text):
    """
    Tokenize ``text`` per CSS Syntax Module Level 3. Comments become whitespace and are merged with adjacent whitespace.

    :raises CssSyntaxError: for an unterminated string or comment, a bad ``url()`` or a ``url(`` that is not a url.
    """
    return _Tokenizer(text).run()


def _match_brackets(tokens):
    """Map every opening bracket (or function) index to its closing index; mismatches raise ``CssSyntaxError``."""
    stack, match = [], {}
    for index, token in enumerate(tokens):
        if token.kind in _OPENERS:
            stack.append((index, _CLOSERS[token.kind]))
            if len(stack) > MAX_NESTING:
                raise CssSyntaxError('nested too deeply')
        elif token.kind in (')', ']', '}'):
            if not stack or stack[-1][1] != token.kind:
                raise CssSyntaxError(f'unbalanced "{token.kind}"')
            match[stack.pop()[0]] = index
    if stack:
        raise CssSyntaxError('unclosed bracket')
    return match


# --- serializer ---------------------------------------------------------------------------------------------------

def _text(token):
    kind = token.kind
    if kind == 'ws':
        return ' '
    if kind == 'ident':
        return token.value
    if kind == 'function':
        return token.value + '('
    if kind == 'at':
        return '@' + token.value
    if kind == 'hash':
        return '#' + token.value
    if kind == 'string':
        if not re.fullmatch(r'[A-Za-z0-9 _.-]*', token.value):
            raise CssSyntaxError('a string that cannot be written safely')
        return f'"{token.value}"'
    if kind == 'url':
        return f'url({token.value})'
    if kind in ('number', 'urange'):
        return token.value
    if kind == 'percent':
        return token.value + '%'
    if kind == 'dimension':
        return token.value + token.unit
    if kind == 'delim':
        return token.value
    return kind  # punctuation: the kind is the character


def _serialise(tokens):
    return ''.join(_text(token) for token in tokens)


def _signature(tokens):
    return [(token.kind, token.value, token.unit) for token in tokens if token.kind != 'ws']


# --- validation ---------------------------------------------------------------------------------------------------

def _non_ws(tokens):
    return [token for token in tokens if token.kind != 'ws']


def _url_problem(value, fonts_only=False):
    pattern_ok = FONT_URL.match(value) if fonts_only else (FRAGMENT_URL.match(value) or ASSET_URL.match(value))
    if pattern_ok:
        return None
    where = 'a bundled font' if fonts_only else 'a #fragment or a bundled asset'
    return CssProblem(CSS_REJECTED, f'url("{value[:40]}") is not {where}.')


def _family_problem(tokens):
    """Check the comma-separated font names of a ``font-family`` value."""
    groups = [[]]
    for token in _non_ws(tokens):
        if token.kind == ',':
            groups.append([])
        elif token.kind == 'string' or (token.kind == 'ident' and _IDENT.match(token.value)):
            groups[-1].append(token)
        else:
            return CssProblem(CSS_REJECTED, 'font-family may only list font names.')
    for group in groups:
        if len(group) == 1 and group[0].kind == 'string':
            name = group[0].value
        elif group and all(token.kind == 'ident' for token in group):
            name = ' '.join(token.value for token in group)
        else:
            return CssProblem(CSS_REJECTED, 'font-family may only list font names.')
        if name.lower() not in FONT_FAMILIES:
            return CssProblem(CSS_REJECTED, f'The font "{name[:30]}" is not available to templates.')
    return None


def _value_problem(tokens, allow_var=True):
    """Generic value check: no strings, urls only to fragments or bundled assets, allowlisted functions."""
    for token in tokens:
        kind = token.kind
        if kind in ('ws', 'number', 'percent', ',', '(', ')', '[', ']'):
            continue
        if kind == 'string':
            return CssProblem(CSS_REJECTED, 'Text strings are only allowed in font names, "content: \\"\\"" and '
                              'font-face formats.')
        if kind == 'url':
            problem = _url_problem(token.value)
            if problem:
                return problem
        elif kind == 'function':
            name = token.value.lower()
            if name not in FUNCTIONS or (name == 'var' and not allow_var):
                return CssProblem(CSS_REJECTED, f'The CSS function "{token.value[:30]}()" is not allowed here.')
        elif kind == 'dimension':
            if not _UNIT.match(token.unit):
                return CssProblem(CSS_REJECTED, 'A CSS unit is not valid.')
        elif kind == 'hash':
            if not _HASH.match(token.value):
                return CssProblem(CSS_REJECTED, 'A CSS colour or id is not valid.')
        elif kind == 'ident':
            if not _IDENT.match(token.value):
                return CssProblem(CSS_REJECTED, 'A CSS keyword is not valid.')
        elif not (kind == 'delim' and token.value in '+-*/'):
            return CssProblem(CSS_REJECTED, f'"{_text(token)[:20]}" is not allowed in a CSS value.')
    return None


def _text_property_problem(name, tokens):
    """``content``, ``quotes``, ``list-style*`` and ``counter-*`` must not be able to draw any text."""
    sig = _non_ws(tokens)
    only = sig[0] if len(sig) == 1 else None
    if name == 'content':
        ok = only is not None and ((only.kind == 'string' and only.value == '') or (
            only.kind == 'ident' and only.value.lower() in ('none', 'normal')))
        message = 'CSS "content" may only be empty: it could show hard-coded text.'
    elif name in NONE_ONLY_PROPERTIES:
        ok = only is not None and only.kind == 'ident' and only.value.lower() == 'none'
        message = f'CSS "{name}" may only be "none": it could show hard-coded text.'
    else:
        ok, message = False, 'CSS counters are not allowed: they could show hard-coded text.'
    return None if ok else CssProblem(CSS_CONTENT_TEXT, message)


def _property_problem(name, tokens):
    if not _IDENT.match(name):
        return CssProblem(CSS_REJECTED, 'A CSS property name is not valid.')
    if name in TEXT_PROPERTIES:
        return _text_property_problem(name, tokens)
    if name == 'font-family':
        return _family_problem(tokens)
    if not name.startswith('--') and name not in PROPERTIES:
        return CssProblem(CSS_REJECTED, f'The CSS property "{name[:40]}" is not allowed.')
    return _value_problem(tokens)


def _font_src_problem(tokens):
    entries = [[]]
    for token in _non_ws(tokens):
        if token.kind == ',':
            entries.append([])
        else:
            entries[-1].append(token)
    for entry in entries:
        if not entry or entry[0].kind != 'url':
            return CssProblem(CSS_REJECTED, 'A font "src" may only be url(../../assets/fonts/<file>).')
        problem = _url_problem(entry[0].value, fonts_only=True)
        if problem:
            return problem
        rest = entry[1:]
        if rest and not (len(rest) == 3 and rest[0].kind == 'function' and rest[0].value.lower() == 'format'
                         and rest[1].kind == 'string' and rest[1].value in FONT_FORMATS and rest[2].kind == ')'):
            return CssProblem(CSS_REJECTED, 'A font "src" may only add format("truetype|opentype|woff|woff2").')
    return None


def _descriptor_problem(name, tokens):
    if name == 'font-family':
        if any(token.kind == ',' for token in tokens):
            return CssProblem(CSS_REJECTED, 'A font-face needs exactly one font-family.')
        return _family_problem(tokens)
    if name == 'src':
        return _font_src_problem(tokens)
    if name in FONT_FACE_DESCRIPTORS:
        return _value_problem(tokens, allow_var=False)
    return CssProblem(CSS_REJECTED, f'The font-face descriptor "{name[:40]}" is not allowed.')


def _selector_problem(tokens):
    """Selectors: names, combinators, brackets and a few functions; no strings, urls or at-keywords."""
    if not tokens:
        return CssProblem(CSS_REJECTED, 'A rule needs a selector.')
    in_attribute = False
    for token in tokens:
        kind = token.kind
        if kind == '[':
            in_attribute = True
        elif kind == ']':
            in_attribute = False
        if kind in ('ws', ',', ':', '[', ']', '(', ')', 'number'):
            continue
        if kind == 'ident' and _IDENT.match(token.value) or kind == 'hash' and _HASH.match(token.value):
            continue
        if kind == 'dimension' and _UNIT.match(token.unit):
            continue
        if kind == 'function' and token.value.lower() in SELECTOR_FUNCTIONS:
            continue
        if kind == 'delim' and (token.value in '.*>+~|' or (in_attribute and token.value in '^$=')):
            continue
        return CssProblem(CSS_REJECTED, f'"{_text(token)[:20]}" is not allowed in a CSS selector.')
    return None


def _media_problem(tokens):
    for token in tokens:
        kind = token.kind
        if kind in ('ws', 'number', 'percent', '(', ')', ':', ',') or (kind == 'delim' and token.value in '/<>=') or (
                kind == 'ident' and _IDENT.match(token.value)) or (kind == 'dimension' and _UNIT.match(token.unit)):
            continue
        return CssProblem(CSS_REJECTED, f'"{_text(token)[:20]}" is not allowed in a @media condition.')
    return None


class _Sanitizer:
    def __init__(self, tokens):
        self.t = tokens
        self.match = _match_brackets(tokens)
        self.problems = []
        self._seen = set()
        self.overflowed = False

    def problem(self, problem):
        """Collect a problem once; past ``MAX_PROBLEMS`` distinct ones the whole sheet is refused (fail closed)."""
        if problem in self._seen:
            return
        if len(self.problems) >= MAX_PROBLEMS:
            if not self.overflowed:
                self.overflowed = True
                self.problems.append(CssProblem(CSS_REJECTED, 'The stylesheet has too many problems.'))
            return
        self._seen.add(problem)
        self.problems.append(problem)

    def reject(self, message):
        self.problem(CssProblem(CSS_REJECTED, message))

    def skip(self, index):
        return self.match[index] + 1 if self.t[index].kind in _OPENERS else index + 1

    def find(self, start, stop, kinds):
        index = start
        while index < stop and self.t[index].kind not in kinds:
            index = self.skip(index)
        return index

    def trim(self, lo, hi):
        while lo < hi and self.t[lo].kind == 'ws':
            lo += 1
        while hi > lo and self.t[hi - 1].kind == 'ws':
            hi -= 1
        return lo, hi

    # --- rules
    def rules(self, lo, hi, depth):
        out, index = [], lo
        while index < hi:
            kind = self.t[index].kind
            if kind == 'ws':
                index += 1
            elif kind == 'at':
                index = self.at_rule(index, hi, depth, out)
            else:
                index = self.qualified_rule(index, hi, out)
        return out

    def qualified_rule(self, index, hi, out):
        end = self.find(index, hi, ('{',))
        if end >= hi:
            self.reject('A rule without a block was ignored.')
            return hi
        after = self.match[end] + 1
        lo, stop = self.trim(index, end)
        problem = _selector_problem(self.t[lo:stop])
        if problem:
            self.problem(problem)
            return after
        declarations = self.declarations(end + 1, self.match[end], _property_problem)
        if declarations:
            out.extend(self.t[lo:stop] + [Token('{')] + declarations + [Token('}')])
        return after

    def at_rule(self, index, hi, depth, out):
        name = self.t[index].value.lower()
        end = self.find(index + 1, hi, ('{', ';'))
        block = end < hi and self.t[end].kind == '{'
        after = self.match[end] + 1 if block else min(end + 1, hi)
        lo, stop = self.trim(index + 1, end)
        prelude = self.t[lo:stop]
        if name == 'font-face' and block and not prelude:
            declarations = self.declarations(end + 1, self.match[end], _descriptor_problem)
            if declarations:
                out.extend([self.t[index], Token('{')] + declarations + [Token('}')])
        elif name == 'media' and block:
            problem = _media_problem(prelude)
            if problem:
                self.problem(problem)
            elif depth + 1 >= MAX_MEDIA_DEPTH:
                self.reject('@media rules are nested too deeply.')
            else:
                inner = self.rules(end + 1, self.match[end], depth + 1)
                if inner:
                    out.extend([self.t[index], _WS] + prelude + [Token('{')] + inner + [Token('}')])
        else:
            self.reject(f'The CSS rule "@{self.t[index].value[:30]}" is not allowed.')
        return after

    # --- declarations
    def declarations(self, lo, hi, check):
        out, start, index = [], lo, lo
        while True:
            if index >= hi or self.t[index].kind == ';':
                out.extend(self.declaration(start, index, check))
                if index >= hi:
                    return out
                start = index = index + 1
            else:
                index = self.skip(index)

    def declaration(self, lo, hi, check):
        lo, hi = self.trim(lo, hi)
        if lo >= hi:
            return []
        first = self.t[lo]
        colon = lo + 1
        while colon < hi and self.t[colon].kind == 'ws':
            colon += 1
        if first.kind != 'ident' or colon >= hi or self.t[colon].kind != ':':
            self.reject('Something that is not a "property: value" declaration was ignored.')
            return []
        name = first.value if first.value.startswith('--') else first.value.lower()
        lo, hi = self.trim(colon + 1, hi)
        important = False
        if hi - lo >= 2 and self.t[hi - 1].kind == 'ident' and self.t[hi - 1].value.lower() == 'important':
            bang = hi - 2
            while bang > lo and self.t[bang].kind == 'ws':
                bang -= 1
            if self.t[bang].kind == 'delim' and self.t[bang].value == '!':
                important = True
                hi = self.trim(lo, bang)[1]
        value = self.t[lo:hi]
        problem = check(name, value) if value else CssProblem(CSS_REJECTED, f'"{name[:40]}" has no value.')
        if problem:
            self.problem(problem)
            return []
        tail = [_WS, Token('delim', '!'), Token('ident', 'important')] if important else []
        return [first, Token(':')] + value + tail + [Token(';')]


def _run(css, declarations):
    if not isinstance(css, str):
        return CssResult('', (CssProblem(CSS_REJECTED, 'The CSS must be text.'),))
    if '<' in css or '&' in css:
        return CssResult('', (CssProblem(CSS_REJECTED, 'CSS must not contain "<" or "&".'),))
    if '{{' in css:
        return CssResult('', (CssProblem(CSS_REJECTED, 'Placeholders are not allowed inside CSS.'),))
    try:
        sanitizer = _Sanitizer(tokenize(css))
        count = len(sanitizer.t)
        if declarations:
            kept = sanitizer.declarations(0, count, _property_problem)
        else:
            kept = sanitizer.rules(0, count, 0)
        text = _serialise(kept)
        if _signature(tokenize(text)) != _signature(kept):
            raise CssSyntaxError('the result does not read back the same')
    except CssSyntaxError as error:
        return CssResult('', (CssProblem(CSS_REJECTED, f'The CSS could not be read safely ({error}).'),))
    if sanitizer.overflowed:  # so many problems that nothing in this sheet is trusted: keep none of it
        return CssResult('', tuple(sanitizer.problems))
    return CssResult(text, tuple(sanitizer.problems))


def sanitize_stylesheet(css):
    """Sanitize the text of a ``<style>`` block. Returns canonical safe CSS and the problems found."""
    return _run(css, declarations=False)


def sanitize_declarations(css):
    """Sanitize the value of a ``style`` attribute (a declaration list). Same contract as ``sanitize_stylesheet``."""
    return _run(css, declarations=True)


def value_problem(text):
    """
    Return a message when the value of a plain (SVG presentation) attribute is unsafe, else ``None``.

    The value is tokenized like CSS: strings and non-fragment ``url()`` targets are refused, functions must be on the
    allowlist, unicode-range tokens and bare ``(`` or ``:`` are refused, and script-like schemes are searched in the
    decoded text.
    """
    if '{{' in text:
        return 'a placeholder in an attribute'
    try:
        tokens = tokenize(text)
    except CssSyntaxError:
        return 'the value could not be read'
    for token in tokens:
        if token.kind in ('urange', '(', ':'):
            return 'a character that is not part of a plain value'
        if token.kind == 'string':
            return 'a text string'
        if token.kind == 'url' and _url_problem(token.value):
            return 'a url() that is not a #fragment or a bundled asset'
        if token.kind == 'function' and token.value.lower() not in FUNCTIONS:
            return f'the function {token.value[:30]}()'
    decoded = _serialise([token if token.kind != 'string' else Token('ident', 'x') for token in tokens]).lower()
    for forbidden in _PLAIN_FORBIDDEN:
        if forbidden in decoded:
            return f'"{forbidden}"'
    return None
