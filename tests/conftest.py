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
import sys
from pathlib import Path

import pytest

PLUGIN_NAME = 'portadas'
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='session')
def contrib_data_dir(tmp_path_factory):
    """A fake OpenLP DataDir whose contrib/plugins/portadas links to the repo package."""
    data_dir = tmp_path_factory.mktemp('openlp-data')
    plugins_dir = data_dir / 'contrib' / 'plugins'
    plugins_dir.mkdir(parents=True)
    (plugins_dir / PLUGIN_NAME).symlink_to(REPO_ROOT / PLUGIN_NAME, target_is_directory=True)
    sys.path.insert(0, str(data_dir))
    yield data_dir
    sys.path.remove(str(data_dir))


@pytest.fixture(scope='session')
def community_module_name():
    """The module name OpenLP derives for the plugin entry point."""
    from openlp.core.common import path_to_module
    return path_to_module(Path('plugins') / PLUGIN_NAME / f'{PLUGIN_NAME}plugin.py', community=True)
