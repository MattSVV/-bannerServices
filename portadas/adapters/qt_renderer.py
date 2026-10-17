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
``CoverRenderer`` on top of QtWebEngine: an off-screen, sandboxed ``QWebEngineView`` captured to PNG.

Sandbox (see ``docs/testing.md`` and ``docs/security.md``):

* every render gets its own off-the-record profile and page, so nothing is shared between covers and nothing is
  written to disk;
* page JavaScript is off; the renderer's own scripts run in the isolated ``ApplicationWorld``, which keeps working;
* a URL request interceptor blocks everything except ``data:`` URLs and files inside the plugin's ``assets`` and
  ``templates`` folders and the render's ``base_dir`` (``security/request_policy.py``);
* navigation away from the first document, pop-up windows, plugins, WebGL, storage and error pages are refused.

The adapter needs a ``QApplication`` and must be used from the GUI thread.
"""
import json
import logging
from pathlib import Path

from PyQt5 import QtCore, QtWebEngineCore, QtWebEngineWidgets, QtWidgets

from ..application.ports import DEFAULT_SIZE, CoverRenderer, RenderError, RenderResult
from ..security.request_policy import is_url_allowed

log = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = (PLUGIN_DIR / 'assets', PLUGIN_DIR / 'templates')
DEFAULT_TIMEOUT_MS = 20000
MAX_HTML_BYTES = 2 * 1024 * 1024  # QWebEnginePage.setHtml() refuses more than 2 MB
MAX_SIDE = 7680
POLL_MS = 40
GRAB_POLL_MS = 20
PAINT_GRACE_POLLS = 25
CANARY_GRACE_POLLS = 50

# Fields are found by CSS class: the placeholder name with "_" turned into "-" (docs/templates.md).
FIELD_CLASSES = ('label', 'title-main', 'title-accent', 'subtitle', 'key-verse', 'readings-label', 'readings')

# Runs in the ApplicationWorld. Loads every declared font face, waits for the font set and two animation frames,
# then raises ``ready``. Promises are not awaited by runJavaScript, so Python polls the flags.
_PREPARE_JS = """
(function () {
  var state = window.__portadas = {fonts: false, ready: false};
  try {
    var loads = Array.from(document.fonts).map(function (face) { return face.load().catch(function () {}); });
    Promise.all(loads).then(function () { return document.fonts.ready; }).then(function () {
      state.fonts = true;
      requestAnimationFrame(function () { requestAnimationFrame(function () { state.ready = true; }); });
    }, function () { state.fonts = true; state.ready = true; });
  } catch (error) { state.fonts = true; state.ready = true; }
  return true;
})()
"""
# Painting is asynchronous: a frame can reach the widget well after the page is "ready". To know a grab shows the
# finished page, a 4px canary square is added (wait until a grab shows it), then removed (wait until a grab no longer
# shows it); the first grab without the canary is a frame produced after the whole page was laid out.
_CANARY_COLOR = (254, 1, 253)
_CANARY_ON_JS = """
(function () {
  var canary = document.createElement('div');
  canary.id = '__portadas_canary';
  canary.style.cssText = 'position:fixed;left:0;top:0;width:4px;height:4px;z-index:2147483647;background:#fe01fd';
  document.documentElement.appendChild(canary);
  return true;
})()
"""
_CANARY_OFF_JS = (
    "(function () { var c = document.getElementById('__portadas_canary'); if (c) { c.remove(); } return true; })()")
_POLL_JS = "JSON.stringify(window.__portadas || {})"

# Returns a JSON array of the field classes that overflow their box, leave the canvas or collide with another field.
_MEASURE_JS = """
(function (classes, canvasWidth, canvasHeight) {
  var tolerance = 1, boxes = [], bad = {};
  classes.forEach(function (name) {
    Array.prototype.forEach.call(document.querySelectorAll('.' + name), function (element) {
      var style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden') { return; }
      var range = document.createRange();
      range.selectNodeContents(element);
      var lines = Array.prototype.filter.call(range.getClientRects(), function (rect) {
        return rect.width > 0 && rect.height > 0;
      });
      if (!lines.length) { return; }
      // Only the horizontal scroll size is trustworthy: a line-height below the font's content area makes
      // scrollHeight exceed clientHeight even though the text fits; vertical problems show up as collisions.
      if (style.display !== 'inline' && element.scrollWidth > element.clientWidth + tolerance) { bad[name] = true; }
      var lineHeight = parseFloat(style.lineHeight);
      lines.forEach(function (rect) {
        if (rect.left < -tolerance || rect.top < -tolerance ||
            rect.right > canvasWidth + tolerance || rect.bottom > canvasHeight + tolerance) { bad[name] = true; }
        // Collisions use the text's width and the line box height: the taller font content area of adjacent
        // lines overlaps by design when the line-height is tight.
        var height = isNaN(lineHeight) ? rect.height : Math.min(lineHeight, rect.height);
        var middle = (rect.top + rect.bottom) / 2;
        boxes.push({name: name, rect: {left: rect.left, right: rect.right,
                                       top: middle - height / 2, bottom: middle + height / 2}});
      });
    });
  });
  boxes.forEach(function (a, i) {
    boxes.slice(i + 1).forEach(function (b) {
      if (a.name === b.name) { return; }
      var x = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
      var y = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
      if (x > 2 && y > 2) { bad[a.name] = true; bad[b.name] = true; }
    });
  });
  return JSON.stringify(Object.keys(bad));
})(%s, %d, %d)
"""

_PAGE_SETTINGS = {
    'JavascriptEnabled': False,
    'JavascriptCanOpenWindows': False,
    'JavascriptCanAccessClipboard': False,
    'JavascriptCanPaste': False,
    'LocalContentCanAccessRemoteUrls': False,
    'PluginsEnabled': False,
    'AutoLoadIconsForPage': False,
    'TouchIconsEnabled': False,
    'ErrorPageEnabled': False,
    'WebGLEnabled': False,
    'Accelerated2dCanvasEnabled': False,
    'LocalStorageEnabled': False,
    'HyperlinkAuditingEnabled': False,
    'ScreenCaptureEnabled': False,
    'PdfViewerEnabled': False,
    'FullScreenSupportEnabled': False,
    'DnsPrefetchEnabled': False,
    'AllowRunningInsecureContent': False,
    'AllowGeolocationOnInsecureOrigins': False,
    'PlaybackRequiresUserGesture': True,
    'ScrollAnimatorEnabled': False,
    'FocusOnNavigationEnabled': False,
}


class _Interceptor(QtWebEngineCore.QWebEngineUrlRequestInterceptor):
    """Blocks every request ``is_url_allowed`` refuses. Runs on the IO thread, so it only holds immutable data."""

    def __init__(self, roots, parent=None):
        super().__init__(parent)
        self._roots = tuple(str(root) for root in roots)

    def interceptRequest(self, info):
        url = info.requestUrl().toString(QtCore.QUrl.FullyEncoded)
        if not is_url_allowed(url, self._roots):
            log.debug('Blocked cover request: %s', url[:200])
            info.block(True)


class _SandboxPage(QtWebEngineWidgets.QWebEnginePage):
    """A page that accepts exactly one navigation (the document we set) and never opens windows."""

    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self._navigated = False

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if is_main_frame and not self._navigated:
            self._navigated = True
            return True
        log.debug('Refused cover navigation to %s', url.scheme())
        return False

    def createWindow(self, window_type):
        return None

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        log.debug('Cover page console: %s', message)


def _check_size(size):
    try:
        width, height = size
    except (TypeError, ValueError):
        raise ValueError('The size must be a (width, height) pair.') from None
    for side in (width, height):
        if not isinstance(side, int) or isinstance(side, bool) or not 1 <= side <= MAX_SIDE:
            raise ValueError(f'Each side of the image must be a whole number from 1 to {MAX_SIDE}.')
    return width, height


class _RenderJob(QtCore.QObject):
    """One render: owns a profile, a page and a view, walks load -> fonts -> measure -> capture, then cleans up."""

    def __init__(self, renderer, html, base_dir, size, on_done, on_error):
        super().__init__()
        self._renderer = renderer
        self._size = size
        self._on_done = on_done
        self._on_error = on_error
        self._stage = 'starting'
        self._finished = False
        self._polls = 0
        self._overflow = ()

        roots = tuple(renderer.roots) + (Path(base_dir),)
        self._profile = QtWebEngineWidgets.QWebEngineProfile(self)  # no name: off the record, nothing on disk
        self._profile.setHttpCacheType(QtWebEngineWidgets.QWebEngineProfile.NoCache)
        self._profile.setPersistentCookiesPolicy(QtWebEngineWidgets.QWebEngineProfile.NoPersistentCookies)
        self._interceptor = _Interceptor(roots)
        self._profile.setUrlRequestInterceptor(self._interceptor)

        self._view = QtWebEngineWidgets.QWebEngineView()
        self._page = _SandboxPage(self._profile, self._view)
        self._view.setPage(self._page)
        for name, value in _PAGE_SETTINGS.items():
            attribute = getattr(QtWebEngineWidgets.QWebEngineSettings, name, None)
            if attribute is not None:
                self._page.settings().setAttribute(attribute, value)
        self._view.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
        self._view.resize(*size)
        self._view.show()

        self._deadline = QtCore.QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.timeout.connect(lambda: self._fail(f'The render timed out while {self._stage}.'))
        self._deadline.start(renderer.timeout_ms)
        self._page.loadFinished.connect(self._loaded)
        self._page.renderProcessTerminated.connect(
            lambda status, code: self._fail(f'The render process stopped unexpectedly (exit code {code}).'))

        self._stage = 'loading the page'
        base_url = QtCore.QUrl.fromLocalFile(str(Path(base_dir).resolve()) + '/')
        self._page.setHtml(html, base_url)

    def _loaded(self, ok):
        if self._finished:
            return
        if not ok:
            self._fail('The page failed to load.')
            return
        self._stage = 'loading fonts'
        self._run(_PREPARE_JS, lambda _: self._poll())

    def _run(self, script, callback):
        self._page.runJavaScript(script, QtWebEngineWidgets.QWebEngineScript.ApplicationWorld, callback)

    def _poll(self):
        if self._finished:
            return
        self._run(_POLL_JS, self._polled)

    def _polled(self, answer):
        if self._finished:
            return
        try:
            state = json.loads(answer or '{}')
        except ValueError:
            state = {}
        if state.get('fonts'):
            self._polls += 1
        if state.get('ready') or self._polls > PAINT_GRACE_POLLS:
            self._stage = 'measuring the text'
            classes = json.dumps(list(FIELD_CLASSES))
            self._run(_MEASURE_JS % (classes, *self._size), self._measured)
        else:
            QtCore.QTimer.singleShot(POLL_MS, self._poll)

    def _measured(self, answer):
        if self._finished:
            return
        try:
            classes = json.loads(answer or '[]')
        except ValueError:
            classes = []
        self._overflow = tuple(name.replace('-', '_') for name in FIELD_CLASSES if name in classes)
        self._stage = 'painting the page'
        self._run(_CANARY_ON_JS, lambda _: self._await_canary(shown=True, polls=0))

    def _canary_visible(self):
        color = self._view.grab().toImage().pixelColor(1, 1)
        return (color.red(), color.green(), color.blue()) == _CANARY_COLOR

    def _await_canary(self, shown, polls):
        """Wait until a grab shows (``shown``) or no longer shows the canary, then continue the sequence."""
        if self._finished:
            return
        if self._canary_visible() == shown or polls > CANARY_GRACE_POLLS:
            if shown:
                self._run(_CANARY_OFF_JS, lambda _: self._await_canary(shown=False, polls=0))
            else:
                self._capture()
            return
        QtCore.QTimer.singleShot(GRAB_POLL_MS, lambda: self._await_canary(shown, polls + 1))

    def _capture(self):
        if self._finished:
            return
        self._stage = 'capturing the image'
        image = self._view.grab().toImage()
        if image.isNull():
            self._fail('The page could not be captured.')
            return
        if (image.width(), image.height()) != tuple(self._size):
            # A device pixel ratio other than 1 (HiDPI screens) makes grab() return a larger image.
            image = image.scaled(*self._size, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
        image.setDevicePixelRatio(1.0)
        data = QtCore.QByteArray()
        buffer = QtCore.QBuffer(data)
        buffer.open(QtCore.QIODevice.WriteOnly)
        if not image.save(buffer, 'PNG'):
            self._fail('The image could not be encoded as PNG.')
            return
        self._finish(RenderResult(bytes(data), self._overflow), None)

    def _fail(self, message):
        self._finish(None, RenderError(message))

    def abort(self):
        """Stop without calling back (the renderer is closing)."""
        self._finish(None, None)

    def _finish(self, result, error):
        if self._finished:
            return
        self._finished = True
        self._deadline.stop()
        self._renderer._forget(self)
        self._page.setHtml('')
        self._view.hide()
        self._view.deleteLater()  # also deletes the page, which is its child
        self._profile.deleteLater()
        self.deleteLater()
        callback, argument = (self._on_done, result) if error is None else (self._on_error, error)
        if result is None and error is None:
            return
        try:
            callback(argument)
        except Exception:  # an exception escaping a Qt slot would abort the application
            log.exception('A render callback raised')


class QtCoverRenderer(CoverRenderer):
    """Renders cover HTML with QtWebEngine. Create it after the ``QApplication``; use it from the GUI thread."""

    def __init__(self, roots=DEFAULT_ROOTS, timeout_ms=DEFAULT_TIMEOUT_MS):
        self.roots = tuple(Path(root) for root in roots)
        self.timeout_ms = timeout_ms
        self._jobs = set()

    def render(self, html, base_dir, size=DEFAULT_SIZE):
        outcome = {}
        loop = QtCore.QEventLoop()

        def done(result):
            outcome['result'] = result
            loop.quit()

        def failed(error):
            outcome['error'] = error
            loop.quit()

        self.render_async(html, base_dir, done, failed, size)
        if not outcome:
            loop.exec_()
        if 'error' in outcome:
            raise outcome['error']
        return outcome['result']

    def render_async(self, html, base_dir, on_done, on_error, size=DEFAULT_SIZE):
        size = _check_size(size)
        if QtWidgets.QApplication.instance() is None:
            raise RenderError('No QApplication is running.')
        if not isinstance(html, str) or len(html.encode('utf-8')) > MAX_HTML_BYTES:
            raise RenderError('The cover HTML is missing or larger than 2 MB.')
        job = _RenderJob(self, html, base_dir, size, on_done, on_error)
        self._jobs.add(job)

    def close(self):
        """Cancel renders in progress (their callbacks do not run) and release their resources."""
        for job in list(self._jobs):
            job.abort()

    def _forget(self, job):
        self._jobs.discard(job)

