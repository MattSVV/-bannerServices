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
"""T15a / SEC-001: an icon "PNG" is trusted by its content, never by its suffix, and never read from a FIFO."""
import os
import threading

import pytest
from contrib.plugins.portadas.domain.cover import CoverError
from contrib.plugins.portadas.lib.iconimage import prepare_png_icon
from PyQt5 import QtCore, QtGui

from .fakes import png_bytes
from .test_edit_form import Form, services  # noqa: F401 - fixtures


def encoded(fmt):
    image = QtGui.QImage(32, 32, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('#336699'))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    assert image.save(buffer, fmt), f'Qt cannot write {fmt} here'
    return bytes(buffer.data())


SVG_AS_PNG = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="64" '
              b'height="64"><image xlink:href="/etc/hostname" width="64" height="64"/></svg>')


@pytest.mark.parametrize('name, data', [
    ('tiff', None), ('bmp', None), ('jpeg', None), ('svg', SVG_AS_PNG)])
def test_other_formats_named_png_are_rejected_before_any_qt_decoding(openlp_env, tmp_path, monkeypatch, name, data):
    path = tmp_path / f'{name}.png'
    path.write_bytes(data if data is not None else encoded(name))
    touched = []
    monkeypatch.setattr(QtGui.QImage, 'fromData', lambda *args: touched.append(args) or QtGui.QImage())
    monkeypatch.setattr(QtGui.QImageReader, 'size', lambda *args: touched.append(args) or QtCore.QSize())

    with pytest.raises(CoverError, match='not a PNG'):
        prepare_png_icon(path)

    assert touched == []


def test_a_real_png_is_still_prepared_and_decoded_as_png_only(openlp_env, tmp_path, monkeypatch):
    path = tmp_path / 'ok.png'
    path.write_bytes(png_bytes(300, 200))
    formats = []
    real = QtGui.QImage.fromData
    monkeypatch.setattr(QtGui.QImage, 'fromData', lambda data, fmt=None: formats.append(fmt) or real(data, fmt))

    assert prepare_png_icon(path).startswith(b'\x89PNG')
    assert formats == ['PNG']


def test_a_png_header_followed_by_a_tiff_is_rejected(openlp_env, tmp_path):
    path = tmp_path / 'mixed.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + encoded('tiff'))

    with pytest.raises(CoverError):
        prepare_png_icon(path)


def test_a_fifo_is_rejected_without_blocking(openlp_env, tmp_path):
    fifo = tmp_path / 'pipe.png'
    os.mkfifo(fifo)
    outcome = []

    def run():
        try:
            prepare_png_icon(fifo)
        except CoverError as error:
            outcome.append(str(error))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(5)
    if worker.is_alive():  # unblock the stuck open() so the thread (and the test run) can end
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(fd)
        worker.join(5)
        pytest.fail('prepare_png_icon blocked on a FIFO')
    assert outcome and 'regular file' in outcome[0]


@pytest.mark.parametrize('suffix', ['png', 'svg'])
def test_the_editor_rejects_a_fifo_without_blocking(qtbot, openlp_env, services, tmp_path, suffix):  # noqa: F811
    form = Form(None, services)
    qtbot.addWidget(form)
    fifo = tmp_path / f'pipe.{suffix}'
    os.mkfifo(fifo)
    outcome = []

    def run():
        try:
            form._icon_from_file(fifo)
        except Exception as error:  # noqa: BLE001 - any rejection is fine, only a hang is not
            outcome.append(error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(5)
    if worker.is_alive():
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        worker.join(5)
        pytest.fail('the editor blocked on a FIFO')
    assert outcome
