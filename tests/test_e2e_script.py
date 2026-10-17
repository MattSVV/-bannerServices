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
"""The headless end-to-end script (``scripts/e2e_flow.py``) in the gate: template, cover, render, library, service."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'scripts' / 'e2e_flow.py'


def run_script(data_dir):
    env = dict(os.environ, QT_QPA_PLATFORM=os.environ.get('QT_QPA_PLATFORM', 'offscreen'))
    return subprocess.run([sys.executable, str(SCRIPT), str(data_dir)], capture_output=True, text=True, env=env,
                          timeout=150, check=False)


def test_the_end_to_end_flow_passes_for_every_builtin_template(tmp_path):
    plugins = tmp_path / 'contrib' / 'plugins'
    plugins.mkdir(parents=True)
    (plugins / 'portadas').symlink_to(REPO / 'portadas', target_is_directory=True)

    result = run_script(tmp_path)

    if result.returncode != 0 and os.environ.get('PORTADAS_REQUIRE_RENDER') is None and 'RenderError' in result.stderr:
        pytest.skip('QtWebEngine cannot render on this platform')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'E2E OK: 3 templates' in result.stdout
    assert 'FAIL' not in result.stdout


def test_the_end_to_end_flow_fails_loudly_when_the_plugin_is_not_linked(tmp_path):
    result = run_script(tmp_path)

    assert result.returncode != 0
    assert 'E2E OK' not in result.stdout
