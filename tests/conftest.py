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
Test configuration.

OpenLP loads community plugins by putting <DataDir> on sys.path and importing
contrib.plugins.<name>.<name>plugin (see openlp.core.common.extension_loader).
The fixtures below reproduce that scheme with a temporary data dir that holds a symlink
to this repository's ``portadas`` package, so tests import the plugin exactly as OpenLP does.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Qt tests run off screen unless the caller picks a platform (for example QT_QPA_PLATFORM=xcb on a real desktop).
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    # QtWebEngine must be imported, and this attribute set, before any QApplication exists.
    from PyQt5 import QtCore, QtWebEngineWidgets  # noqa: F401
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
except ImportError:  # pure-Python tests still run without Qt
    pass

pytest_plugins = ['tests.library_support']

PLUGIN_NAME = 'portadas'
REPO_ROOT = Path(__file__).resolve().parent.parent

# The data dir is built at import time so test modules can import ``contrib.plugins.portadas.*`` at module level
# (collection happens before any fixture runs).
_DATA_DIR = Path(tempfile.mkdtemp(prefix='openlp-data-'))
_PLUGINS_DIR = _DATA_DIR / 'contrib' / 'plugins'
_PLUGINS_DIR.mkdir(parents=True)
(_PLUGINS_DIR / PLUGIN_NAME).symlink_to(REPO_ROOT / PLUGIN_NAME, target_is_directory=True)
sys.path.insert(0, str(_DATA_DIR))
atexit.register(shutil.rmtree, _DATA_DIR, ignore_errors=True)


@pytest.fixture(scope='session')
def contrib_data_dir():
    """A fake OpenLP DataDir whose contrib/plugins/portadas links to the repo package."""
    return _DATA_DIR


@pytest.fixture(scope='session')
def community_module_name():
    """The module name OpenLP derives for the plugin entry point."""
    from openlp.core.common import path_to_module
    return path_to_module(Path('plugins') / PLUGIN_NAME / f'{PLUGIN_NAME}plugin.py', community=True)


def event_loops_alive():
    """False when ``QEventLoop.exec`` returns at once because something called ``QCoreApplication.exit``."""
    from PyQt5 import QtCore
    loop, clock = QtCore.QEventLoop(), QtCore.QElapsedTimer()
    QtCore.QTimer.singleShot(40, loop.quit)
    clock.start()
    loop.exec_()
    return clock.elapsed() >= 20


@pytest.fixture(autouse=True)
def event_loops_stay_alive(request):
    """
    Stop the run at the first test that leaves Qt's event loops dead (T20).

    ``QCoreApplication.exit()`` (or ``quit()``) sets a flag that only ``QCoreApplication.exec`` clears, and pytest-qt
    never runs that: from then on every ``QEventLoop.exec`` returns immediately, ``qtbot.waitUntil`` spins creating
    signal proxies by the hundred thousand and the suite appears to hang. Failing here names the culprit instead.
    """
    yield
    if 'qapp' in request.fixturenames and not event_loops_alive():
        pytest.exit(f'{request.node.nodeid} left the Qt event loops dead (QCoreApplication.exit/quit was called).',
                    returncode=3)


@pytest.fixture
def openlp_env(qapp, tmp_path):
    """The bits of OpenLP's global state widgets need: a Registry holding a Settings object backed by a temp file."""
    from openlp.core.common.actions import ActionList
    from openlp.core.common.registry import Registry
    from openlp.core.common.settings import Settings
    ActionList.instance, ActionList.shortcut_map = None, {}  # actions of earlier tests may be deleted by now
    Registry.create()
    Settings.set_filename(str(tmp_path / 'openlp-test.ini'))
    settings = Settings()
    settings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings.init_default_shortcuts()
    Registry().register('settings', settings)
    Registry().register('settings_thread', settings)
    Registry().register('application', qapp)
    yield settings
    ActionList.instance, ActionList.shortcut_map = None, {}
    Registry._instances = {}
