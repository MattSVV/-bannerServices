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
request to an AI provider, looks at ``is_cancelled()`` between chunks and between attempts and stops early. Nothing is
interrupted forcibly: a call that is waiting on the network ends at its own deadline. Pure Python.
"""
import contextlib
import threading

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
