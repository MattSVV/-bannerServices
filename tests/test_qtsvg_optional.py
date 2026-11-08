"""The plugin must load on OpenLP builds that do not bundle QtSvg (the Windows installer)."""
import importlib
import sys

import PyQt5
import pytest
from contrib.plugins.portadas.lib import iconimage

from .fakes import make_services
from .test_edit_form import Form

SIMPLE_SVG = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/></svg>'


@pytest.fixture
def without_qtsvg(openlp_env, monkeypatch):
    """Reload iconimage as if ``from PyQt5 import QtSvg`` raised ImportError, then restore it."""
    monkeypatch.setitem(sys.modules, 'PyQt5.QtSvg', None)
    monkeypatch.delattr(PyQt5, 'QtSvg', raising=False)
    importlib.reload(iconimage)
    yield
    monkeypatch.undo()
    importlib.reload(iconimage)


def test_iconimage_imports_without_qtsvg(without_qtsvg):
    assert iconimage.QtSvg is None
    assert iconimage.svg_preview_available() is False


def test_svg_pixmap_is_blank_without_qtsvg(without_qtsvg):
    pixmap = iconimage.svg_pixmap(SIMPLE_SVG)

    image = pixmap.toImage()
    assert not image.isNull()
    assert all(image.pixelColor(x, y).alpha() == 0 for x in range(0, 64, 8) for y in range(0, 64, 8))


def test_editor_labels_icons_when_thumbnails_are_unavailable(qtbot, tmp_path, without_qtsvg):
    dialog = Form(None, make_services(tmp_path))
    qtbot.addWidget(dialog)

    texts = [dialog.icon_list.item(row).text() for row in range(dialog.icon_list.count())]
    assert texts and all(texts)


def test_svg_pixmap_still_draws_with_qtsvg(openlp_env):
    assert iconimage.svg_preview_available() is True
    image = iconimage.svg_pixmap(SIMPLE_SVG).toImage()

    assert image.pixelColor(32, 32).alpha() > 0
