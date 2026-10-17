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
Sanitizer for untrusted (for example AI-produced) cover templates.

The input is tokenised with the standard library parser and **rebuilt** from an allowlist, never patched in place,
so the output is a canonical document whose structure does not depend on how a browser would have parsed the input.

Policy
    * Only allowlisted HTML and SVG elements survive; every other element is removed together with its content
      (``script``, ``iframe``, ``object``, ``embed``, ``link``, ``meta``, ``base``, ``form``, ``input``, ``a``,
      ``foreignObject``, ``image`` (except a user-uploaded PNG icon, see ``sanitize_svg``), ``img`` without a bundled
      src, ...). Comments are removed.
    * Only allowlisted attributes survive. ``on*`` attributes are always dropped; ``href`` / ``xlink:href`` are kept
      only as ``#fragment``; ``<style>`` blocks and ``style`` attributes are tokenized, validated and re-serialized by
      ``css_policy`` (what survives is canonical CSS, never the original text); placeholders are allowed in text and as
      ``{{empty_fields}}`` inside ``class``.
    * Lists: ``<ol>`` is not allowed, and ``css_policy.BASE_CSS`` (``* { list-style: none }``) is emitted first, with
      ``list-style*`` limited to ``none``, so no marker or number is ever drawn.
    * Limits: ``MAX_BYTES`` of input, ``MAX_DEPTH`` nesting levels, ``MAX_ELEMENTS`` elements.
    * **Text guarantee**: every non-whitespace text node must be exactly one content placeholder. A hard-coded visible
      string, or CSS ``content`` that could show one, makes the template unacceptable.
    * Required placeholders must be present.

Removals are reported as non-fatal ``Violation`` objects; the rest of the template is still usable. Fatal violations
make ``SanitizeResult.accepted`` false and ``SanitizeResult.html`` ``None``.
"""
import base64
import binascii
import html as html_lib
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from ..domain.errors import DomainError
from ..domain.templating import CONTENT_PLACEHOLDERS, EMPTY_FIELDS, TemplateError
from .css_policy import (
    ASSET_URL,
    BASE_CSS,
    CSS_CONTENT_TEXT,
    FRAGMENT_URL,
    sanitize_declarations,
    sanitize_stylesheet,
    value_problem,
)

MAX_BYTES = 200 * 1024
MAX_DEPTH = 24
MAX_ELEMENTS = 5000
MAX_PNG_ICON_BYTES = 96 * 1024  # decoded size of a PNG embedded in an uploaded icon
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

HTML_TAGS = frozenset({
    'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'li', 'br', 'hr', 'strong', 'em', 'b', 'i',
    'u', 'small', 'section', 'header', 'footer', 'main', 'article', 'aside', 'figure', 'figcaption', 'blockquote',
    'img'})
SVG_TAGS = frozenset({
    'svg', 'g', 'defs', 'path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon', 'lineargradient',
    'radialgradient', 'stop', 'clippath', 'mask', 'pattern', 'symbol', 'use', 'filter', 'fegaussianblur', 'feoffset',
    'feflood', 'fecomposite', 'femerge', 'femergenode', 'feblend', 'fecolormatrix'})
VOID_TAGS = frozenset({'br', 'hr', 'img', 'meta', 'link', 'base', 'input', 'embed', 'area', 'col', 'param', 'source',
                       'track', 'wbr', 'keygen', 'command', 'basefont', 'bgsound', 'frame'})
TRANSPARENT_TAGS = frozenset({'html', 'head', 'body'})
HREF_TAGS = frozenset({'use', 'lineargradient', 'radialgradient', 'pattern'})

SAFE_ATTRIBUTES = frozenset({
    'width', 'height', 'role', 'aria-hidden', 'focusable', 'viewbox', 'preserveaspectratio', 'd', 'x', 'y', 'cx',
    'cy', 'r', 'rx', 'ry', 'x1', 'y1', 'x2', 'y2', 'fx', 'fy', 'points', 'transform', 'fill', 'fill-opacity',
    'fill-rule', 'clip-rule', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-linecap', 'stroke-linejoin',
    'stroke-dasharray', 'stroke-dashoffset', 'stroke-miterlimit', 'opacity', 'offset', 'stop-color', 'stop-opacity',
    'gradientunits', 'gradienttransform', 'spreadmethod', 'clip-path', 'mask', 'filter', 'clippathunits', 'maskunits',
    'maskcontentunits', 'patternunits', 'patterncontentunits', 'patterntransform', 'stddeviation', 'dx', 'dy',
    'in', 'in2', 'result', 'mode', 'type', 'values', 'operator', 'flood-color', 'flood-opacity', 'color', 'display',
    'visibility', 'vector-effect'})

_PNG_DATA_URI = re.compile(r'^data:image/png;base64,([A-Za-z0-9+/]+={0,2})$')
_ID = re.compile(r'^[A-Za-z][A-Za-z0-9_:.-]{0,63}$')
_CLASS_TOKEN = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]{0,63}$')
_HOOK = re.compile(r'\{\{\s*' + EMPTY_FIELDS + r'\s*\}\}')
_HOOK_TOKEN = '{{' + EMPTY_FIELDS + '}}'
_TEXT_PLACEHOLDER = re.compile(r'^\{\{\s*([A-Za-z0-9_]+)\s*\}\}$')
_LANG = re.compile(r'^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$')
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


@dataclass(frozen=True)
class Violation:
    """One thing the sanitizer removed or objected to. ``fatal`` violations make the template unacceptable."""
    code: str
    message: str
    fatal: bool = False


@dataclass(frozen=True)
class SanitizeResult:
    """Outcome of sanitising: the safe HTML (``None`` when rejected) and everything that was reported."""
    html: str
    violations: tuple

    @property
    def accepted(self):
        return self.html is not None


class TemplateRejected(DomainError):
    """An untrusted template cannot be made acceptable. ``violations`` lists every reason."""

    def __init__(self, violations):
        self.violations = tuple(violations)
        fatal = [violation for violation in self.violations if violation.fatal]
        super().__init__(f'The template was rejected: {(fatal or self.violations)[0].message}')


class _Element:
    __slots__ = ('tag', 'attrs', 'children')

    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.children = tag, attrs, []


class _Placeholder:
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name


class _Builder(HTMLParser):
    """Collects an allowlisted tree and the problems found on the way."""

    def __init__(self, tags, allow_style, png_images=False):
        super().__init__(convert_charrefs=True)
        self.tags, self.allow_style, self.png_images = tags, allow_style, png_images
        self.root = []
        self.stack = []
        self.skip = []
        self.styles = []
        self.violations = []
        self.html_lang = None
        self.body_attrs = {}
        self.elements = 0
        self.too_deep = False
        self.top_level_removed = False
        self._style = None

    # --- helpers -----------------------------------------------------------------------------------------------
    def report(self, code, message, fatal=False):
        self.violations.append(Violation(code, message, fatal))

    def _children(self):
        return self.stack[-1].children if self.stack else self.root

    def _add_text(self, text):
        children = self._children()
        if children and isinstance(children[-1], str):
            children[-1] += text
        else:
            children.append(text)

    # --- parser callbacks --------------------------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        self.elements += 1
        if self.skip:
            if tag not in VOID_TAGS:
                self.skip.append(tag)
            return
        if tag in TRANSPARENT_TAGS:
            self._transparent(tag, attrs)
        elif tag == 'style' and self.allow_style:
            self._style = []
        elif tag in self.tags and not (tag == 'img' and not self._img_ok(attrs)):
            self._open(tag, attrs)
        else:
            if not (tag == 'meta' and [name for name, _ in attrs] == ['charset']):
                self.report('element-removed', f'The <{tag}> element is not allowed and was removed.')
            self.top_level_removed = self.top_level_removed or not self.stack
            if tag not in VOID_TAGS:
                self.skip.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skip:
            if tag in self.skip:
                while self.skip.pop() != tag:
                    pass
            return
        if tag == 'style' and self._style is not None:
            self._finish_style()
        elif tag in TRANSPARENT_TAGS or tag in VOID_TAGS:
            return
        else:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index].tag == tag:
                    del self.stack[index:]
                    return

    def handle_data(self, data):
        if self.skip:
            return
        if self._style is not None:
            self._style.append(data)
        else:
            self._add_text(data)

    def handle_comment(self, data):
        if not self.skip:
            self.report('comment-removed', 'An HTML comment was removed.')

    def close(self):
        super().close()
        if self._style is not None:
            self._finish_style()

    # --- structure ---------------------------------------------------------------------------------------------
    def _transparent(self, tag, attrs):
        values = dict(attrs)
        if tag == 'html' and _LANG.match((values.get('lang') or '').strip()):
            self.html_lang = values['lang'].strip()
        elif tag == 'body':
            self.body_attrs = self._clean_attributes('body', attrs, only=('class', 'style'))

    def _img_ok(self, attrs):
        return ASSET_URL.match((dict(attrs).get('src') or '').strip()) is not None

    def _open(self, tag, attrs):
        element = _Element(tag, self._clean_attributes(tag, attrs))
        self._children().append(element)
        if tag in VOID_TAGS:
            return
        if len(self.stack) + 1 > MAX_DEPTH:
            self.too_deep = True
        self.stack.append(element)

    def _finish_style(self):
        css = ''.join(self._style).strip()
        self._style = None
        result = sanitize_stylesheet(css)
        self._report_css(result.problems, 'A <style> block')
        if result.css and result.css != BASE_CSS:
            self.styles.append(result.css)

    def _report_css(self, problems, what):
        for problem in problems:
            self.report(problem.code, f'{what} was changed: {problem.message}', problem.code == CSS_CONTENT_TEXT)

    # --- attributes --------------------------------------------------------------------------------------------
    def _clean_attributes(self, tag, attrs, only=None):
        clean = {}
        for name, raw in attrs:
            value = (raw or '').strip()
            if name.startswith('xmlns') or (only and name not in only):
                if name.startswith('on'):
                    self.report('attribute-removed', f'The event handler "{name}" was removed.')
                continue
            kept = self._clean_attribute(tag, name, value)
            if kept is None:
                if not name.startswith('xmlns'):
                    self.report('attribute-removed', f'The attribute "{name}" on <{tag}> was removed.')
            elif kept is not False:
                clean[name] = kept
        return clean

    def _clean_attribute(self, tag, name, value):
        """Return the cleaned value, ``None`` to drop it (reported) or ``False`` to drop it (already reported)."""
        if name.startswith('on'):
            return None
        if name == 'style':
            result = sanitize_declarations(value)
            self._report_css(result.problems, 'A style attribute')
            return result.css or False
        if name == 'class':
            return _clean_class(value)
        if name == 'id':
            return value if _ID.match(value) else None
        if name in ('href', 'xlink:href'):
            if tag == 'image' and self.png_images:
                return value if _is_png_data_uri(value) else None
            return value if tag in HREF_TAGS and FRAGMENT_URL.match(value) else None
        if name == 'src':
            return value if tag == 'img' and ASSET_URL.match(value) else None
        if name in SAFE_ATTRIBUTES and _plain_value_ok(value):
            return value
        return None


def _clean_class(value):
    tokens = _HOOK.sub(' ' + _HOOK_TOKEN + ' ', value).split()
    if all(token == _HOOK_TOKEN or _CLASS_TOKEN.match(token) for token in tokens):
        return ' '.join(tokens)
    return None


def _is_png_data_uri(value):
    """True for ``data:image/png;base64,...`` that is strict base64, small enough and really starts like a PNG."""
    match = _PNG_DATA_URI.match(value)
    if match is None or len(match.group(1)) > MAX_PNG_ICON_BYTES * 4 // 3 + 4:
        return False
    try:
        data = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(data) <= MAX_PNG_ICON_BYTES and data.startswith(PNG_SIGNATURE)


def _plain_value_ok(value):
    return value_problem(value) is None


# --- tree checks and serialisation ---------------------------------------------------------------------------

def _check_text(nodes, violations, found):
    """Apply the text guarantee. Replaces valid placeholder text with ``_Placeholder`` objects in place."""
    for index, node in enumerate(nodes):
        if isinstance(node, _Element):
            _check_text(node.children, violations, found)
        elif node.strip():
            match = _TEXT_PLACEHOLDER.match(node.strip())
            if match and match.group(1) in CONTENT_PLACEHOLDERS:
                nodes[index] = _Placeholder(match.group(1))
                found.add(match.group(1))
            else:
                snippet = ' '.join(node.split())[:40]
                violations.append(Violation(
                    'hardcoded-text', f'Hard-coded text "{snippet}" is not allowed: every visible string must be a '
                    'placeholder.', True))
        else:
            nodes[index] = ' '


def _check_no_text(nodes, violations):
    """Icons carry no text at all, not even a placeholder-looking one (it would never be expanded, but is odd)."""
    for index, node in enumerate(nodes):
        if isinstance(node, _Element):
            _check_no_text(node.children, violations)
        elif node.strip():
            violations.append(Violation('hardcoded-text', 'An icon must not contain text, not even a placeholder.',
                                        True))
        else:
            nodes[index] = ' '


def _trim(nodes):
    """Drop whitespace-only text at both ends of a node list."""
    while nodes and nodes[0] == ' ':
        del nodes[0]
    while nodes and nodes[-1] == ' ':
        del nodes[-1]


def _attributes(attrs):
    return ''.join(f' {name}="{html_lib.escape(value, quote=True)}"' for name, value in attrs.items())


def _serialise(nodes):
    parts = []
    for node in nodes:
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, _Placeholder):
            parts.append('{{' + node.name + '}}')
        elif node.tag in VOID_TAGS:
            parts.append(f'<{node.tag}{_attributes(node.attrs)}>')
        else:
            parts.append(f'<{node.tag}{_attributes(node.attrs)}>{_serialise(node.children)}</{node.tag}>')
    return ''.join(parts)


def _prepare(untrusted, tags, allow_style, png_images=False):
    """Parse ``untrusted``; returns ``(builder, violations)`` or ``(None, violations)`` on a fatal early problem."""
    if not isinstance(untrusted, str):
        raise TemplateError('The template must be text.')
    if len(untrusted.encode('utf-8', 'replace')) > MAX_BYTES:
        return None, [Violation('too-large', f'The template is larger than {MAX_BYTES // 1024} KB.', True)]
    if _CONTROL.search(untrusted):
        return None, [Violation('control-characters', 'The template contains control characters.', True)]
    builder = _Builder(tags, allow_style, png_images)
    try:
        builder.feed(untrusted)
        builder.close()
    except Exception:  # noqa: BLE001 - html.parser can raise on pathological input; fail closed
        return None, [Violation('unparseable', 'The template could not be parsed.', True)]
    violations = list(builder.violations)
    if builder.elements > MAX_ELEMENTS:
        violations.append(Violation('too-many-elements', f'The template has more than {MAX_ELEMENTS} elements.', True))
    if builder.too_deep:
        # Fatal, and the tree is never walked: the walks below recurse and thousands of levels would exhaust the stack.
        violations.append(Violation('too-deep', f'The template is nested deeper than {MAX_DEPTH} levels.', True))
        return None, violations
    return builder, violations


def sanitize_template(untrusted, required=('title_main',)):
    """
    Sanitize an untrusted template.

    :param untrusted: the template HTML.
    :param required: content placeholders that must appear (default: the main title).
    :return: a ``SanitizeResult``. ``html`` is a canonical document, or ``None`` when a fatal violation exists.
    :raises TemplateError: for a non-string template or an unknown required placeholder.
    """
    for name in required:
        if name not in CONTENT_PLACEHOLDERS:
            raise TemplateError(f'Unknown placeholder "{name}".')
    builder, violations = _prepare(untrusted, HTML_TAGS | SVG_TAGS, allow_style=True)
    if builder is None:
        return SanitizeResult(None, tuple(violations))
    found = set()
    _check_text(builder.root, violations, found)
    for name in required:
        if name not in found:
            violations.append(Violation('missing-placeholder', f'The template is missing the required placeholder '
                                        f'"{name}".', True))
    if any(violation.fatal for violation in violations):
        return SanitizeResult(None, tuple(violations))
    styles = ''.join(f'<style>{css}</style>' for css in (BASE_CSS, *builder.styles))
    _trim(builder.root)
    document = (f'<!DOCTYPE html><html lang="{builder.html_lang or "es"}"><head><meta charset="utf-8">{styles}</head>'
                f'<body{_attributes(builder.body_attrs)}>{_serialise(builder.root)}</body></html>')
    return SanitizeResult(document, tuple(violations))


def require_safe_template(untrusted, required=('title_main',)):
    """Return the sanitized HTML of ``untrusted`` or raise ``TemplateRejected``."""
    result = sanitize_template(untrusted, required)
    if not result.accepted:
        raise TemplateRejected(result.violations)
    return result.html


def sanitize_svg(untrusted, allow_png_image=False):
    """
    Sanitize an untrusted inline SVG icon: exactly one ``<svg>`` root, SVG elements only, no text, no styles.

    :param allow_png_image: opt-in for icons the *user* uploads (a PNG wrapped in an SVG). It additionally allows
        ``<image href="data:image/png;base64,...">``: strict base64 that decodes to at most ``MAX_PNG_ICON_BYTES``
        and starts with the PNG signature. Any other ``href`` on it is dropped. Never use it for AI content.

    :return: a ``SanitizeResult`` whose ``html`` is the cleaned ``<svg>`` element, or ``None`` when rejected.
    """
    tags = SVG_TAGS | {'image'} if allow_png_image else SVG_TAGS
    builder, violations = _prepare(untrusted, tags, allow_style=False, png_images=allow_png_image)
    if builder is None:
        return SanitizeResult(None, tuple(violations))
    for node in builder.root:
        if isinstance(node, str) and node.strip():
            violations.append(Violation('hardcoded-text', 'An icon must not contain text.', True))
    elements = [node for node in builder.root if isinstance(node, _Element)]
    if len(elements) != 1 or elements[0].tag != 'svg' or builder.top_level_removed:
        violations.append(Violation('missing-svg', 'An icon must be exactly one <svg> element.', True))
    else:
        _check_no_text(elements[0].children, violations)
    if any(violation.fatal for violation in violations) or not elements:
        return SanitizeResult(None, tuple(violations))
    return SanitizeResult(_serialise(elements), tuple(violations))
