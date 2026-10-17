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
"""Qt helpers for icons: preparing an uploaded PNG and drawing SVG icons as pixmaps."""
import os
import stat

from PyQt5 import QtCore, QtGui, QtSvg

from ..application.icon_upload import MAX_PNG_DIMENSION, png_decode_bytes, png_size
from ..domain.cover import CoverError
from ..security.html_policy import MAX_PNG_ICON_BYTES, PNG_SIGNATURE, sanitize_svg

MAX_PNG_FILE_BYTES = 20 * 1024 * 1024  # an uploaded file is read only up to this size
# An image that would need more once decoded is refused first: 25M pixels, or 12.5M at 16 bits per channel.
MAX_DECODE_BYTES = 100_000_000
ICON_SIDES = (256, 192, 128, 96, 64)  # an uploaded PNG is scaled down until it fits the size cap
PICKER_SIZE = 64


def read_regular_file(path, limit):
    """
    Read at most ``limit`` bytes of the regular file at ``path``.

    The file is opened without blocking and must be a regular file: opening a FIFO would otherwise wait for a writer
    forever, and a device or socket is never an icon.

    :raises CoverError: when the file cannot be read or is not a regular file.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
    except OSError as error:
        raise CoverError(f'The file could not be read: {error.strerror or "I/O error"}.') from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CoverError('The icon must be a regular file.')
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            return handle.read(limit)
    except OSError as error:
        raise CoverError(f'The file could not be read: {error.strerror or "I/O error"}.') from error
    finally:
        os.close(descriptor)


def prepare_png_icon(path):
    """
    Read the PNG at ``path`` and return PNG bytes small enough to embed in an icon (scaled down when needed).

    The content decides, never the file name: the bytes must start with the PNG signature and have a well-formed
    header before Qt sees them, and Qt is told to decode PNG only (other formats, such as TIFF or SVG, have decoders
    with their own bugs and, for SVG, file access).

    :raises CoverError: when the file cannot be read, is not a PNG, or cannot be made small enough.
    """
    raw = read_regular_file(path, MAX_PNG_FILE_BYTES + 1)
    if len(raw) > MAX_PNG_FILE_BYTES:
        raise CoverError('The image file is too large.')
    if not raw.startswith(PNG_SIGNATURE):
        raise CoverError('The file is not a PNG image.')
    width, height = png_size(raw)
    if width <= 0 or height <= 0 or png_decode_bytes(raw) > MAX_DECODE_BYTES:
        raise CoverError('The file is not a usable image.')
    image = QtGui.QImage.fromData(raw, 'PNG')
    if image.isNull():
        raise CoverError('The file is not a usable image.')
    for side in ICON_SIDES:
        scaled = image
        if max(image.width(), image.height()) > min(side, MAX_PNG_DIMENSION):
            scaled = image.scaled(side, side, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        data = _encode_png(scaled)
        if data is not None and len(data) <= MAX_PNG_ICON_BYTES:
            return data
    raise CoverError('The image is too complex to use as an icon; try a smaller or simpler one.')


def _encode_png(image):
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    if not image.save(buffer, 'PNG'):
        return None
    return bytes(buffer.data())


def svg_pixmap(svg_text, size=PICKER_SIZE, color='#555555'):
    """
    Draw inline SVG markup on a transparent pixmap; ``currentColor`` becomes ``color``. Blank when unreadable.

    The markup is sanitised first (a stored icon could have been edited by hand): QtSvg would otherwise follow
    ``<image href>`` to any local path, including ones that block forever. A rejected icon draws nothing.
    """
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    safe = sanitize_svg(svg_text, allow_png_image=True) if isinstance(svg_text, str) else None
    if safe is None or not safe.accepted:
        return pixmap
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(_qt_svg(safe.html, color).encode('utf-8')))
    if renderer.isValid():
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter, QtCore.QRectF(0, 0, size, size))
        painter.end()
    return pixmap


def _qt_svg(svg_text, color):
    """QtSvg understands ``xlink:href`` only and has no HTML-style attribute case folding."""
    text = svg_text.replace('currentColor', color).replace('viewbox=', 'viewBox=')
    text = text.replace(' href="', ' xlink:href="')
    if 'xmlns' not in text.split('>', 1)[0]:
        text = text.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg" '
                                    'xmlns:xlink="http://www.w3.org/1999/xlink"', 1)
    return text
