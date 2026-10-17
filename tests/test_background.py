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
"""The Qt helper that runs a blocking call (the AI designer) off the GUI thread and reports back on it."""
import threading

import pytest
from contrib.plugins.portadas.application.ports import DesignError
from contrib.plugins.portadas.lib.background import run_in_background
from PyQt5 import QtCore

from .ai_support import KEY


def test_the_result_arrives_on_the_gui_thread_and_the_work_runs_elsewhere(qtbot, openlp_env):
    seen = {}

    def work():
        seen['worker'] = threading.get_ident()
        return 41 + 1

    done = []
    run_in_background(work, lambda value: (seen.__setitem__('gui', threading.get_ident()), done.append(value)),
                      lambda message: done.append(('error', message)))

    qtbot.waitUntil(lambda: bool(done), timeout=5000)

    assert done == [42]
    assert seen['gui'] == threading.get_ident() and seen['worker'] != seen['gui']


def test_a_design_error_is_delivered_as_its_message(qtbot, openlp_env):
    failures = []

    def work():
        raise DesignError('The provider is busy.')

    run_in_background(work, lambda value: failures.append(value), failures.append)
    qtbot.waitUntil(lambda: bool(failures), timeout=5000)

    assert failures == ['The provider is busy.']


def test_an_unexpected_exception_is_delivered_without_its_text_or_any_key(qtbot, openlp_env):
    failures = []

    def work():
        raise RuntimeError(f'boom with {KEY}')

    run_in_background(work, lambda value: failures.append(value), failures.append)
    qtbot.waitUntil(lambda: bool(failures), timeout=5000)

    assert KEY not in failures[0] and failures[0]


def test_a_cancelled_job_never_calls_back(qtbot, openlp_env):
    release, finished, calls = threading.Event(), threading.Event(), []

    def work():
        release.wait(5)
        finished.set()
        return 1

    job = run_in_background(work, calls.append, calls.append)
    job.cancel()
    release.set()
    assert finished.wait(5)
    qtbot.wait(100)
    QtCore.QCoreApplication.processEvents()

    assert calls == []


def test_a_callback_that_raises_does_not_crash_the_application(qtbot, openlp_env):
    marker = []

    def explode(value):
        marker.append(value)
        raise ValueError('callback bug')

    run_in_background(lambda: 7, explode, explode)
    qtbot.waitUntil(lambda: bool(marker), timeout=5000)

    assert marker == [7]


@pytest.mark.parametrize('pool_given', [False, True])
def test_jobs_use_the_given_pool(qtbot, openlp_env, pool_given):
    pool = QtCore.QThreadPool() if pool_given else None
    done = []

    run_in_background(lambda: 'ok', done.append, done.append, pool=pool)
    qtbot.waitUntil(lambda: bool(done), timeout=5000)

    assert done == ['ok']
