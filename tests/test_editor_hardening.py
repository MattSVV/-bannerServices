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
"""Regression tests for the editor defects found by independent verification (T09b). Every wait is bounded."""
import faulthandler
import struct
import zlib

import pytest
from contrib.plugins.portadas.application.icon_upload import icon_from_png_bytes
from contrib.plugins.portadas.application.ports import RenderResult
from contrib.plugins.portadas.domain.cover import Cover, CoverError, IconKind, IconRef
from contrib.plugins.portadas.lib import iconimage
from contrib.plugins.portadas.lib.iconimage import prepare_png_icon, svg_pixmap
from PyQt5 import QtCore, QtWidgets, sip

from .fakes import FakeRenderer, make_services, png_bytes
from .test_edit_form import Form

HOSTILE_SVG = '<svg viewBox="0 0 8 8"><image href="file:///etc/passwd" width="8" height="8"/></svg>'


@pytest.fixture
def watchdog():
    """Abort the whole run instead of hanging forever when the code under test blocks."""
    faulthandler.dump_traceback_later(30, exit=True)
    yield
    faulthandler.cancel_dump_traceback_later()


class ReentrantRenderer(FakeRenderer):
    """Renders at once; the first synchronous render 'clicks Save again' like a nested event loop would allow."""

    def __init__(self):
        super().__init__()
        self.form = None
        self.reentries = 0
        self.save_enabled_during_render = None
        self.closed_during_save = None

    def render(self, html, base_dir, size=(1920, 1080)):
        if self.form is not None and not self.reentries:
            self.reentries += 1
            self.save_enabled_during_render = self.form.save_button.isEnabled()
            self.form.on_save()  # the second click
            self.form.reject()  # and Escape
            self.closed_during_save = self.form._closed
        return RenderResult(png_bytes(32, 18))


# --- 1. double Save -------------------------------------------------------------------------------------------------

def test_a_second_save_click_during_the_save_stores_one_cover(openlp_env, qtbot, tmp_path, watchdog):
    renderer = ReentrantRenderer()
    services = make_services(tmp_path, renderer=renderer)
    form = Form(None, services)
    qtbot.addWidget(form)
    renderer.form = form
    form.load_cover(None)
    form.title_main_edit.setText('Nuevo')

    form.on_save()

    assert len(services.repository.covers) == 1
    assert renderer.save_enabled_during_render is False
    assert renderer.closed_during_save is False  # Escape is ignored while saving
    assert form.result() == QtWidgets.QDialog.Accepted


def test_a_new_cover_gets_its_id_once_per_dialog(form, services):
    from contrib.plugins.portadas.application.ports import RepositoryError

    calls = []

    def broken_save(cover, png):
        calls.append(cover.id)
        raise RepositoryError('disk full')
    services.repository.save = broken_save
    form.load_cover(None)
    form.title_main_edit.setText('Nuevo')

    form.on_save()
    form.on_save()

    assert len(calls) == 2 and calls[0] == calls[1]
    assert form.save_button.isEnabled()  # a failed save re-enables Save


@pytest.fixture
def services(tmp_path):
    return make_services(tmp_path)


@pytest.fixture
def form(qtbot, openlp_env, services):
    dialog = Form(None, services)
    qtbot.addWidget(dialog)
    return dialog


# --- 2. tampered inline SVG icon ------------------------------------------------------------------------------------

def test_svg_pixmap_never_hands_hostile_markup_to_qt(openlp_env, monkeypatch):
    seen = []
    real = iconimage.QtSvg.QSvgRenderer

    class Spy(real):
        def __init__(self, data, *args):
            seen.append(bytes(data).decode('utf-8', 'replace'))
            super().__init__(data, *args)
    monkeypatch.setattr(iconimage.QtSvg, 'QSvgRenderer', Spy)

    pixmap = svg_pixmap(HOSTILE_SVG)

    assert all('passwd' not in text for text in seen)
    assert pixmap.toImage().isNull() is False
    image = pixmap.toImage()
    assert all(image.pixelColor(x, y).alpha() == 0 for x in range(0, 64, 8) for y in range(0, 64, 8))


def test_loading_a_cover_with_a_tampered_icon_keeps_only_the_sanitised_icon(form, monkeypatch):
    seen = []
    real = iconimage.QtSvg.QSvgRenderer

    class Spy(real):
        def __init__(self, data, *args):
            seen.append(bytes(data).decode('utf-8', 'replace'))
            super().__init__(data, *args)
    monkeypatch.setattr(iconimage.QtSvg, 'QSvgRenderer', Spy)
    cover = Cover.from_raw('Titulo', icon=IconRef(IconKind.INLINE_SVG, HOSTILE_SVG), id='tampered')

    form.load_cover(cover)

    assert all('passwd' not in text for text in seen)
    assert 'passwd' not in form.icon().value


def test_loading_a_cover_with_an_unusable_icon_falls_back_to_the_default_icon(form):
    cover = Cover.from_raw('Titulo', icon=IconRef(IconKind.INLINE_SVG, '<div>not an icon</div>'), id='tampered')

    form.load_cover(cover)

    assert form.icon().kind is IconKind.BUILTIN
    assert form._custom_icon_item is None
    assert 'not valid' in form.status_label.text()


# --- 3. leaks and late callbacks ------------------------------------------------------------------------------------

def test_the_editor_is_deleted_after_it_closes(item):
    item.form.save_as = None

    item.on_new_click()

    assert item.form.deleted


def test_the_editor_is_deleted_even_when_it_raises(item):
    def boom():
        raise RuntimeError('boom')
    item.form.exec = boom

    with pytest.raises(RuntimeError):
        item.on_new_click()

    assert item.form.deleted


def test_late_render_callbacks_after_the_dialog_is_gone_are_harmless(openlp_env, tmp_path, watchdog):
    services = make_services(tmp_path)
    dialog = Form(None, services)
    dialog.load_cover(Cover.from_raw('Titulo', id='late'))
    deadline = QtCore.QDeadlineTimer(2000)
    while not services.renderer.pending and not deadline.hasExpired():
        QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
    assert len(services.renderer.pending) == 1
    dialog.done(QtWidgets.QDialog.Rejected)
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert sip.isdeleted(dialog)

    services.renderer.finish()  # must not touch the deleted widgets

    assert services.renderer.pending == []


# --- 4. PNG bounds --------------------------------------------------------------------------------------------------

def header_only_png(width, height):
    """A PNG whose header announces a huge image but whose pixel data is a few bytes: decoding it would explode."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\x00')) + chunk(b'IEND', b''))


def test_a_huge_png_is_rejected_before_it_is_decoded(openlp_env, tmp_path, monkeypatch):
    path = tmp_path / 'bomb.png'
    path.write_bytes(header_only_png(16000, 16000))
    decoded = []
    monkeypatch.setattr(iconimage.QtGui.QImage, 'fromData', lambda *args: decoded.append(args) or None)

    with pytest.raises(CoverError, match='usable image'):
        prepare_png_icon(path)

    assert decoded == []


def test_a_normal_png_is_still_prepared(openlp_env, tmp_path):
    path = tmp_path / 'ok.png'
    path.write_bytes(png_bytes(300, 200))

    assert prepare_png_icon(path).startswith(b'\x89PNG')


def test_a_truncated_png_is_rejected():
    data = png_bytes(4, 4)

    with pytest.raises(CoverError):
        icon_from_png_bytes(data[:-12])  # no IEND chunk


def test_a_png_with_trailing_bytes_is_rejected():
    with pytest.raises(CoverError):
        icon_from_png_bytes(png_bytes(4, 4) + b'<script>alert(1)</script>')


def test_a_png_with_a_broken_chunk_checksum_is_rejected():
    data = bytearray(png_bytes(4, 4))
    data[29] ^= 0xFF  # inside IHDR's CRC
    with pytest.raises(CoverError):
        icon_from_png_bytes(bytes(data))


# --- identifiers ends with a newline --------------------------------------------------------------------------------

@pytest.mark.parametrize('field,value', [('id', 'default\n'), ('template_id', 'default\n')])
def test_a_trailing_newline_is_not_a_valid_identifier(field, value):
    with pytest.raises(CoverError):
        Cover.from_raw('Titulo', **{field: value})
