#!/usr/bin/env python3
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
Create sample covers in a throwaway OpenLP data dir, through the plugin's own use case and the real renderer.

Used by ``scripts/run-headless.sh`` so the library tab has something to list. Usage (with OpenLP's interpreter)::

    python scripts/seed_cover.py <openlp-data-dir>

The plugin must already be linked at ``<openlp-data-dir>/contrib/plugins/portadas`` (``scripts/dev-install.sh``).
The second cover uses an uploaded PNG icon; the script checks that the PNG really shows up in the render.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def main(data_dir):
    data_dir = Path(data_dir)
    sys.path.insert(0, str(data_dir))
    from PyQt5 import QtCore, QtGui, QtWebEngineWidgets, QtWidgets  # noqa: F401 - WebEngine before the QApplication
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv[:1])

    from contrib.plugins.portadas.application.icon_upload import icon_from_png_bytes
    from contrib.plugins.portadas.lib.services import build_services

    services = build_services(data_dir / 'portadas')
    first = services.creator.execute(
        'Resistir', title_accent='al diablo', subtitle='Una serie sobre firmeza', key_verse='Santiago 4:7',
        readings=['Efesios 6:11-12', 'Santiago 4:7'], template_id='noche-dorada')
    print(f'seeded cover {first.cover.id} (overflow: {first.overflow})')

    square = QtGui.QImage(64, 64, QtGui.QImage.Format_RGB32)
    square.fill(QtGui.QColor(255, 0, 0))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    square.save(buffer, 'PNG')
    second = services.creator.execute('Con icono propio', icon=icon_from_png_bytes(bytes(buffer.data())),
                                      template_id='luz-clara')
    image = QtGui.QImage.fromData(services.repository.png_path(second.cover.id).read_bytes(), 'PNG')
    red = sum(1 for y in range(0, image.height(), 4) for x in range(0, image.width(), 4)
              if image.pixelColor(x, y).red() > 240 and image.pixelColor(x, y).green() < 30)
    print(f'seeded cover {second.cover.id} with an uploaded PNG icon; sampled red pixels in the render: {red}')
    services.close()
    del app
    if red < 200:
        print('the uploaded PNG icon did not show in the render', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
