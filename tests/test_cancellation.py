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
"""The cooperative cancellation helpers the AI worker and the HTTP adapter share."""
import threading
import time

from contrib.plugins.portadas.application import cancellation


def test_nothing_is_cancelled_outside_a_bound_job():
    assert cancellation.is_cancelled() is False
    assert cancellation.current_event() is None


def test_wait_without_a_job_sleeps_for_the_time_and_reports_not_cancelled():
    started = time.monotonic()

    assert cancellation.wait(0.05) is False
    assert time.monotonic() - started >= 0.04


def test_wait_wakes_at_once_when_the_bound_job_is_cancelled():
    event = cancellation.CancelEvent()
    threading.Timer(0.05, event.set).start()

    with cancellation.bound(event):
        started = time.monotonic()
        assert cancellation.wait(10) is True
        assert cancellation.is_cancelled() is True

    assert time.monotonic() - started < 5


def test_wait_returns_false_when_the_budget_ends_before_any_cancel():
    with cancellation.bound(cancellation.CancelEvent()):
        assert cancellation.wait(0.02) is False


def test_nested_bindings_restore_the_outer_job_and_nothing_leaks_after():
    outer, inner = cancellation.CancelEvent(), cancellation.CancelEvent()
    with cancellation.bound(outer):
        with cancellation.bound(inner):
            assert cancellation.current_event() is inner
        assert cancellation.current_event() is outer
    assert cancellation.current_event() is None
