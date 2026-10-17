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
Cooperative cancellation for blocking calls that run on a worker thread.

The worker binds the job's ``threading.Event`` for the duration of its work (``bound``); a long call, such as an HTTP
request to an AI provider, looks at ``is_cancelled()`` between chunks and between attempts and stops early, and
pauses with ``wait``. A call that is blocked on the network is aborted by the caller's own watcher
(``adapters/ai/http.py``), which polls ``is_cancelled()``. Pure Python.
"""
import contextlib
import threading
import time

CancelEvent = threading.Event
_state = threading.local()


@contextlib.contextmanager
def bound(event):
    """Make ``event`` the cancellation signal of the current thread while the block runs."""
    previous = getattr(_state, 'event', None)
    _state.event = event
    try:
        yield
    finally:
        _state.event = previous


def is_cancelled():
    """True when the work running on this thread was cancelled."""
    event = getattr(_state, 'event', None)
    return event is not None and event.is_set()


def current_event():
    """The cancellation event bound to the current thread, or ``None``."""
    return getattr(_state, 'event', None)


def wait(seconds):
    """Sleep up to ``seconds``, waking at once when the job is cancelled. Returns True when it was cancelled."""
    event = current_event()
    if event is None:
        time.sleep(seconds)
        return False
    return event.wait(seconds)
