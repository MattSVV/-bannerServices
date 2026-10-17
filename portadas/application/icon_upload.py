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
"""
Turns a file the user uploaded as a cover icon (SVG or PNG) into a safe inline icon.

Uploads are the user's own files, so a PNG may be embedded (wrapped in an SVG ``<image>``, see
``sanitize_svg(allow_png_image=True)``), but active content in an SVG (scripts, event handlers, ``foreignObject``...)
is a reason to reject the file instead of silently cleaning it: it is most likely not an icon.
"""
import base64
import re
import struct
import zlib

from ..domain.cover import CoverError, IconKind, IconRef
from ..security.html_policy import MAX_PNG_ICON_BYTES, PNG_SIGNATURE, sanitize_svg

MAX_SVG_BYTES = 20000
MAX_PNG_DIMENSION = 2048

# Elements whose removal means the file was not a plain icon (matches the tag name in the sanitizer's message).
_ACTIVE_ELEMENTS = frozenset({'script', 'foreignobject', 'iframe', 'object', 'embed', 'a', 'animate', 'set',
                              'animatetransform', 'animatemotion', 'style', 'audio', 'video', 'canvas', 'text', 'tspan',
                              'textpath', 'image'})
_REMOVED_TAG = re.compile(r'The <([A-Za-z0-9:]+)> element')
_REMOVED_HANDLER = re.compile(r'The attribute "on[a-z]+"|The event handler')
_EMPTY_SVG = re.compile(r'^<svg[^>]*>\s*</svg>$')


def icon_from_svg_text(text):
    """
    Return an inline-SVG ``IconRef`` holding the sanitised markup of an uploaded SVG file.

    :raises CoverError: when the file is too large, is not a single text-free ``<svg>``, or contains active
        content, text or embedded images.
    """
    if not isinstance(text, str):
        raise CoverError('The SVG file could not be read as text.')
    if len(text.encode('utf-8', 'replace')) > MAX_SVG_BYTES:
        raise CoverError(f'The SVG file is too large (at most {MAX_SVG_BYTES // 1000} KB).')
    result = sanitize_svg(text)
    problems = _blocking_problems(result)
    if problems:
        raise CoverError('The SVG file was rejected: ' + '; '.join(problems))
    return IconRef(IconKind.INLINE_SVG, result.html)


def icon_from_png_bytes(data):
    """
    Return an inline-SVG ``IconRef`` that shows an uploaded PNG (embedded as a base64 data URI).

    :raises CoverError: when ``data`` is not a PNG, is too large or has unreasonable dimensions.
    """
    if not isinstance(data, bytes) or not data.startswith(PNG_SIGNATURE) or len(data) < 33:
        raise CoverError('The file is not a PNG image.')
    if len(data) > MAX_PNG_ICON_BYTES:
        raise CoverError(f'The PNG image is too large (at most {MAX_PNG_ICON_BYTES // 1024} KB).')
    width, height = png_size(data)
    if not 0 < width <= MAX_PNG_DIMENSION or not 0 < height <= MAX_PNG_DIMENSION:
        raise CoverError(f'The PNG image has unsupported dimensions (at most {MAX_PNG_DIMENSION} pixels per side).')
    uri = 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
    svg = (f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" class="portadas-icon" '
           f'aria-hidden="true"><image href="{uri}" x="0" y="0" width="{width}" height="{height}"/></svg>')
    result = sanitize_svg(svg, allow_png_image=True)
    if not result.accepted or 'href="data:image/png' not in result.html:
        raise CoverError('The PNG image was rejected.')
    return IconRef(IconKind.INLINE_SVG, result.html)


def png_size(data):
    """
    Walk the chunks of ``data`` and return ``(width, height)``. The file must start with a well-formed ``IHDR`` and
    end exactly after a valid ``IEND``: a truncated PNG, trailing bytes or a bad checksum is rejected.
    """
    position = len(PNG_SIGNATURE)
    size = None
    while position + 12 <= len(data):
        length, kind = struct.unpack('>I4s', data[position:position + 8])
        end = position + 12 + length
        if end > len(data):
            break
        if zlib.crc32(data[position + 4:end - 4]) != struct.unpack('>I', data[end - 4:end])[0]:
            raise CoverError('The PNG image is damaged (checksum mismatch).')
        if size is None:
            if kind != b'IHDR' or length != 13:
                raise CoverError('The file is not a PNG image.')
            size = struct.unpack('>II', data[position + 8:position + 16])
        if kind == b'IEND':
            if end != len(data):
                raise CoverError('The PNG image has extra data after its end.')
            return size
        position = end
    raise CoverError('The PNG image is incomplete.')


def _blocking_problems(result):
    problems = [violation.message for violation in result.violations if violation.fatal]
    for violation in result.violations:
        match = _REMOVED_TAG.search(violation.message)
        if violation.code == 'element-removed' and match and match.group(1).lower() in _ACTIVE_ELEMENTS:
            problems.append(violation.message)
        elif violation.code == 'attribute-removed' and _REMOVED_HANDLER.search(violation.message):
            problems.append(violation.message)
    if result.accepted and _EMPTY_SVG.match(result.html):
        problems.append('the SVG draws nothing')
    return problems
