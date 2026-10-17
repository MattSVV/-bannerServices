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
from PyQt5 import QtCore, QtGui, QtSvg

from ..application.icon_upload import MAX_PNG_DIMENSION
from ..domain.cover import CoverError
from ..security.html_policy import MAX_PNG_ICON_BYTES

MAX_PNG_FILE_BYTES = 20 * 1024 * 1024  # an uploaded file is read only up to this size
ICON_SIDES = (256, 192, 128, 96, 64)  # an uploaded PNG is scaled down until it fits the size cap
PICKER_SIZE = 64


def prepare_png_icon(path):
    """
    Read the PNG at ``path`` and return PNG bytes small enough to embed in an icon (scaled down when needed).

    :raises CoverError: when the file cannot be read, is not an image, or cannot be made small enough.
    """
    try:
        with open(path, 'rb') as handle:
            raw = handle.read(MAX_PNG_FILE_BYTES + 1)
    except OSError as error:
        raise CoverError(f'The image could not be read: {error.strerror or "I/O error"}.') from error
    if len(raw) > MAX_PNG_FILE_BYTES:
        raise CoverError('The image file is too large.')
    image = QtGui.QImage.fromData(raw)
    if image.isNull() or image.width() > 16384 or image.height() > 16384:
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
    """Draw inline SVG markup on a transparent pixmap; ``currentColor`` becomes ``color``. Blank when unreadable."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(_qt_svg(svg_text, color).encode('utf-8')))
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
