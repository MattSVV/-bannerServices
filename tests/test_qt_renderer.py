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
The Qt renderer: HTML in, a 1920x1080 PNG out, inside a sandbox.

These tests need a usable Qt platform plugin and QtWebEngine. When the smoke render in ``renderer`` cannot
complete, the whole module is skipped with the reason (set ``PORTADAS_REQUIRE_RENDER=1`` to fail instead, for CI).
"""
import http.server
import os
import struct
import threading
from pathlib import Path

import pytest
from contrib.plugins.portadas.adapters.qt_renderer import QtCoverRenderer
from contrib.plugins.portadas.application.ports import CoverRenderer, RenderError, RenderResult
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.domain.templating import render_cover

from .conftest import event_loops_alive

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'portadas' / 'templates'
PAGE = '<!DOCTYPE html><html><body style="margin:0;background:{background}">{body}</body></html>'


def page(body='', background='#102030'):
    return PAGE.format(background=background, body=body)


@pytest.fixture(scope='module')
def renderer(qapp):
    instance = QtCoverRenderer(timeout_ms=30000)
    try:
        instance.render(page(), TEMPLATE_DIR, size=(64, 36))
    except RenderError as error:
        if os.environ.get('PORTADAS_REQUIRE_RENDER'):
            raise
        pytest.skip(f'QtWebEngine cannot render on this platform ({os.environ.get("QT_QPA_PLATFORM")}): {error}')
    yield instance
    instance.close()


def decode(png_bytes):
    from PyQt5 import QtGui
    image = QtGui.QImage.fromData(png_bytes, 'PNG')
    assert not image.isNull()
    return image


def rgb(image, x, y):
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def close_to(actual, expected, tolerance=6):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


def noche_dorada(**overrides):
    values = dict(title_main='Resistir', title_accent='al diablo', label='MENSAJE', subtitle='Una serie sobre firmeza',
                  key_verse='Santiago 4:7', readings=['Efesios 6:11-12', 'Santiago 4:7'], template_id='noche-dorada')
    values.update(overrides)
    cover = Cover.from_raw(**values)
    catalog = TemplateCatalog()
    from contrib.plugins.portadas.application.icon_catalog import IconCatalog
    template = catalog.load(cover.template_id)
    return render_cover(template.html, cover, IconCatalog().svg('shield-heart'), required=template.manifest.required)


def test_the_adapter_implements_the_port(renderer):
    assert isinstance(renderer, CoverRenderer)


def test_render_returns_a_1920x1080_png(renderer):
    result = renderer.render(page(), TEMPLATE_DIR)

    assert isinstance(result, RenderResult)
    assert result.png_bytes[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', result.png_bytes[16:24]) == (1920, 1080)
    assert result.overflow == ()


def test_render_honours_a_custom_size(renderer):
    result = renderer.render(page(), TEMPLATE_DIR, size=(640, 360))

    assert decode(result.png_bytes).size().width() == 640
    assert decode(result.png_bytes).size().height() == 360


@pytest.mark.parametrize('size', [(0, 10), (10, 0), (-1, 5), (100000, 100), (1920,), 'big'])
def test_render_rejects_unreasonable_sizes(renderer, size):
    with pytest.raises(ValueError):
        renderer.render(page(), TEMPLATE_DIR, size=size)


def test_the_page_background_is_painted_exactly(renderer):
    image = decode(renderer.render(page(background='#336699'), TEMPLATE_DIR).png_bytes)

    assert rgb(image, 3, 3) == (0x33, 0x66, 0x99)
    assert rgb(image, 1900, 1070) == (0x33, 0x66, 0x99)


def test_noche_dorada_renders_the_reference_look(renderer):
    result = renderer.render(noche_dorada(), TEMPLATE_DIR / 'noche-dorada')
    image = decode(result.png_bytes)

    assert image.width() == 1920 and image.height() == 1080
    assert close_to(rgb(image, 4, 4), (0x0e, 0x14, 0x22))
    assert close_to(rgb(image, 1915, 1075), (0x11, 0x18, 0x27))
    colors = {rgb(image, x, y) for x in range(0, 1920, 7) for y in range(0, 1080, 7)}
    assert len(colors) > 50
    gold = sum(1 for x in range(0, 1920, 3) for y in range(0, 1080, 3)
               if (lambda c: c[0] > 170 and 120 < c[1] < 200 and c[2] < 130)(rgb(image, x, y)))
    assert gold > 200
    assert result.overflow == ()


def test_the_icon_and_text_do_not_render_when_fields_are_empty(renderer):
    with_text = decode(renderer.render(noche_dorada(), TEMPLATE_DIR / 'noche-dorada').png_bytes)
    bare = decode(renderer.render(noche_dorada(subtitle=None, readings=[], key_verse=None, title_accent=None),
                                  TEMPLATE_DIR / 'noche-dorada').png_bytes)

    assert with_text != bare
    assert close_to(rgb(bare, 1600, 500), (0x10, 0x16, 0x26), tolerance=8)


def test_a_title_that_does_not_fit_is_reported_as_overflowing(renderer):
    html = noche_dorada(title_main='Impresionantemente' * 4, title_accent=None)

    result = renderer.render(html, TEMPLATE_DIR / 'noche-dorada')

    assert 'title_main' in result.overflow


def test_a_reading_that_is_too_wide_is_reported(renderer):
    html = noche_dorada(readings=['1 Corintios 15:1-11, 20-28, 35-49, 50-58 · 16:1-24 · 1:1-24 · 2:1-16 · 3:1-23'])

    result = renderer.render(html, TEMPLATE_DIR / 'noche-dorada')

    assert 'readings' in result.overflow


def test_colliding_fields_are_both_reported(renderer):
    body = ('<div class="title-main" style="position:absolute;left:10px;top:10px;font-size:80px">Uno</div>'
            '<div class="subtitle" style="position:absolute;left:10px;top:30px;font-size:80px">Dos</div>')

    result = renderer.render(page(body), TEMPLATE_DIR)

    assert set(result.overflow) == {'title_main', 'subtitle'}


def test_hidden_fields_are_never_reported(renderer):
    body = '<div class="subtitle" style="display:none;width:5px;white-space:nowrap">a very long hidden text</div>'

    assert renderer.render(page(body), TEMPLATE_DIR).overflow == ()


def test_page_javascript_is_disabled(renderer):
    html = page('<script>document.body.style.background="#ff0000"</script>'
                '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" '
                'onerror="document.body.style.background=\'#ff0000\'" '
                'onload="document.body.style.background=\'#ff0000\'">')

    image = decode(renderer.render(html, TEMPLATE_DIR).png_bytes)

    assert rgb(image, 500, 500) == (0x10, 0x20, 0x30)


def write_png(path, color):
    from PyQt5 import QtGui
    image = QtGui.QImage(40, 40, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor(color))
    assert image.save(str(path), 'PNG')


def image_tag(src, left=0):
    return f'<img src="{src}" style="position:absolute;left:{left}px;top:0;width:40px;height:40px">'


def count_color(image, color, x_range, y_range):
    return sum(1 for x in x_range for y in y_range if rgb(image, x, y) == color)


def test_a_local_image_inside_base_dir_is_loaded(renderer, tmp_path):
    write_png(tmp_path / 'inside.png', '#00ff00')

    image = decode(renderer.render(page(image_tag('inside.png')), tmp_path).png_bytes)

    assert rgb(image, 10, 10) == (0, 255, 0)


def test_a_local_image_outside_the_allowed_dirs_is_blocked(renderer, tmp_path):
    base = tmp_path / 'base'
    outside = tmp_path / 'outside'
    base.mkdir()
    outside.mkdir()
    write_png(outside / 'secret.png', '#ff0000')
    write_png(base / 'control.png', '#00ff00')
    html = page(image_tag(outside.joinpath('secret.png').as_uri()) + image_tag('../outside/secret.png', 50)
                + image_tag('control.png', 100))

    image = decode(renderer.render(html, base).png_bytes)

    assert count_color(image, (255, 0, 0), range(0, 100), range(40)) == 0
    assert count_color(image, (0, 255, 0), range(100, 140), range(40)) == 1600


class _CountingServer(http.server.ThreadingHTTPServer):
    hits = 0


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        type(self.server).hits += 1
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def remote_server():
    server = _CountingServer(('127.0.0.1', 0), _Handler)
    server.hits = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_remote_urls_are_blocked_before_any_connection(renderer, remote_server):
    url = f'http://127.0.0.1:{remote_server.server_address[1]}/pixel.png'
    html = page(f'<img src="{url}"><link rel="stylesheet" href="{url}">'
                f'<div style="background:url({url});width:5px;height:5px"></div>')

    renderer.render(html, TEMPLATE_DIR)

    assert remote_server.hits == 0


def test_a_remote_font_or_stylesheet_import_is_blocked(renderer, remote_server):
    url = f'http://127.0.0.1:{remote_server.server_address[1]}/x.css'

    renderer.render(page(f'<style>@import url({url}); @font-face {{ font-family: X; src: url({url}); }}</style>'),
                    TEMPLATE_DIR)

    assert remote_server.hits == 0


def test_a_failed_render_leaves_the_renderer_usable(renderer):
    broken = QtCoverRenderer(timeout_ms=1)
    with pytest.raises(RenderError):
        broken.render(page(), TEMPLATE_DIR)
    broken.close()

    assert renderer.render(page(), TEMPLATE_DIR, size=(64, 36)).png_bytes


def test_a_render_that_never_finishes_times_out_with_a_clear_error(qapp):
    impatient = QtCoverRenderer(timeout_ms=1)

    with pytest.raises(RenderError, match='timed out'):
        impatient.render(page(), TEMPLATE_DIR)

    impatient.close()


def test_render_async_reports_through_callbacks(renderer, qtbot):
    done, failed = [], []

    renderer.render_async(page(), TEMPLATE_DIR, done.append, failed.append, size=(64, 36))
    qtbot.waitUntil(lambda: bool(done or failed), timeout=30000)

    assert failed == []
    assert isinstance(done[0], RenderResult)


def test_render_async_reports_errors_through_the_error_callback(qapp, qtbot):
    done, failed = [], []
    impatient = QtCoverRenderer(timeout_ms=1)

    impatient.render_async(page(), TEMPLATE_DIR, done.append, failed.append)
    qtbot.waitUntil(lambda: bool(done or failed), timeout=30000)
    impatient.close()

    assert done == []
    assert isinstance(failed[0], RenderError)


def test_concurrent_async_renders_do_not_mix_up_results(renderer, qtbot):
    results = {}
    for name, color in (('a', '#ff0000'), ('b', '#00ff00'), ('c', '#0000ff')):
        renderer.render_async(page(background=color), TEMPLATE_DIR,
                              lambda result, name=name: results.__setitem__(name, result),
                              lambda error: pytest.fail(str(error)), size=(64, 36))
    qtbot.waitUntil(lambda: len(results) == 3, timeout=60000)

    assert [rgb(decode(results[name].png_bytes), 5, 5) for name in 'abc'] == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


# --- T07b regressions -------------------------------------------------------------------------------------------------

@pytest.fixture
def watchdog(qapp):
    """
    ``arm(renderer, milliseconds)``: close the renderer after a while, so a regression that hangs fails the test.

    It must never call ``QCoreApplication.exit``: with no ``QCoreApplication.exec`` running (pytest-qt never runs one)
    that call leaves every later ``QEventLoop.exec`` returning at once, forever, and a timer left armed by a passing
    test fired in a later one and hung the whole suite (T20). The timers are stopped when the test ends.
    """
    from PyQt5 import QtCore
    timers = []

    def arm(renderer, milliseconds=15000):
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(renderer.close)
        timer.start(milliseconds)
        timers.append(timer)
        return timer

    yield arm
    for timer in timers:
        timer.stop()


def test_closing_the_renderer_mid_render_raises_instead_of_hanging(qapp, watchdog):
    from PyQt5 import QtCore
    local = QtCoverRenderer(timeout_ms=30000)
    QtCore.QTimer.singleShot(30, local.close)
    watchdog(local)

    with pytest.raises(RenderError, match='closed'):
        local.render(page(), TEMPLATE_DIR, size=(64, 36))


def test_closing_the_renderer_does_not_run_async_callbacks(qapp):
    from PyQt5 import QtCore
    local = QtCoverRenderer(timeout_ms=30000)
    calls = []
    local.render_async(page(), TEMPLATE_DIR, calls.append, calls.append, size=(64, 36))
    local.close()
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(300, loop.quit)
    loop.exec_()

    assert calls == []


@pytest.mark.parametrize('size', [(3841, 10), (10, 3841), (3840, 3840), (7680, 4320)])
def test_the_canvas_is_capped_at_4k(renderer, size):
    with pytest.raises(ValueError):
        renderer.render(page(), TEMPLATE_DIR, size=size)


def test_a_4k_canvas_is_still_accepted():
    from contrib.plugins.portadas.adapters.qt_renderer import _check_size
    assert _check_size((3840, 2160)) == (3840, 2160)
    assert _check_size((2160, 3840)) == (2160, 3840)


def test_a_grab_that_overshoots_the_deadline_fails_the_render(qapp, monkeypatch, watchdog):
    import time

    from contrib.plugins.portadas.adapters import qt_renderer
    local = QtCoverRenderer(timeout_ms=300)

    calls = []

    def slow_grab(self):
        calls.append(1)
        if len(calls) > 1:
            time.sleep(0.6)  # a synchronous grab the timer cannot interrupt, right before the capture
        return len(calls) == 1  # the canary shows up, then disappears

    monkeypatch.setattr(qt_renderer._RenderJob, '_canary_visible', slow_grab)
    watchdog(local)

    with pytest.raises(RenderError, match='timed out'):
        local.render(page(), TEMPLATE_DIR, size=(64, 36))


def test_the_page_is_deleted_before_its_profile_after_a_failed_render(qapp):
    from PyQt5 import QtCore
    messages = []
    previous = QtCore.qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    try:
        local = QtCoverRenderer(timeout_ms=1)
        with pytest.raises(RenderError):
            local.render(page(), TEMPLATE_DIR, size=(64, 36))
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(1500, loop.quit)
        loop.exec_()
    finally:
        QtCore.qInstallMessageHandler(previous)

    assert not [message for message in messages if 'still not deleted' in message]


def test_an_event_loop_ended_from_outside_raises_render_error_not_a_key_error(renderer):
    """If something else ends the nested event loop of a blocking render, the caller gets a ``RenderError``."""
    from PyQt5 import QtCore
    QtCore.QTimer.singleShot(0, lambda: [loop.quit() for loop, _ in list(renderer._waiting)])

    with pytest.raises(RenderError, match='interrupted'):
        renderer.render(page(), TEMPLATE_DIR, size=(64, 36))
    assert not renderer._jobs  # the interrupted render's job was aborted, not left to live until its deadline
    QtCore.QCoreApplication.processEvents()


def test_the_watchdog_leaves_the_event_loops_usable_after_it_fires(qapp, watchdog):
    from PyQt5 import QtCore
    local = QtCoverRenderer(timeout_ms=30000)
    watchdog(local, 20)
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(80, loop.quit)
    loop.exec_()

    assert event_loops_alive()
