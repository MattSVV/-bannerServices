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
T12c: the wall-clock budget holds against a real server that trickles bytes (the fake-clock tests of
``test_ai_adapters.py`` cannot reach the blocking reads inside ``requests``), and cancellation interrupts both a
blocked read and the backoff pause. Every test is bounded: the budget is 2 x 0.5 s.
"""
import socket
import threading
import time

import pytest
from contrib.plugins.portadas.adapters.ai.openai_compatible import OpenAiCompatibleDesigner
from contrib.plugins.portadas.application import cancellation
from contrib.plugins.portadas.application.ports import DesignError, DesignRequest
from contrib.plugins.portadas.security.redaction import clear_secrets

from .ai_support import KEY, FakeResponse, FakeSession

REQUEST = DesignRequest('SYSTEM RULES', 'USER TEXT')
TIMEOUT = 0.5  # seconds per wait; the whole call may take twice that
TRICKLE_PAUSE = 0.05  # well under TIMEOUT, so the per-read timeout of ``requests`` never fires on its own


@pytest.fixture(autouse=True)
def _forget_keys():
    clear_secrets()
    yield
    clear_secrets()


class TrickleServer:
    """A local server that answers every request with a never-ending trickle, in the body or in the headers."""

    def __init__(self, mode):
        self.mode = mode
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(4)
        self.port = self.listener.getsockname()[1]
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}/v1'

    def _accept(self):
        self.listener.settimeout(0.1)
        while not self.stopping.is_set():
            try:
                connection, _ = self.listener.accept()
            except OSError:
                continue
            threading.Thread(target=self._serve, args=(connection,), daemon=True).start()

    def _serve(self, connection):
        with connection:
            try:
                connection.settimeout(2)
                connection.recv(65536)
                if self.mode == 'body':
                    connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                                       b'Content-Length: 100000000\r\n\r\n')
                    piece = b' '
                else:
                    connection.sendall(b'HTTP/1.1 200 OK\r\n')
                    piece = b'X'
                while not self.stopping.is_set():
                    connection.sendall(piece)
                    time.sleep(TRICKLE_PAUSE)
            except OSError:
                pass

    def close(self):
        self.stopping.set()
        self.listener.close()
        self.thread.join(2)


@pytest.fixture
def server(request):
    started = TrickleServer(request.param)
    yield started
    started.close()


def designer_for(url, **kwargs):
    return OpenAiCompatibleDesigner(KEY, 'model-x', TIMEOUT, url, **kwargs)


@pytest.mark.parametrize('server', ['body', 'headers'], indirect=True)
def test_a_server_that_trickles_bytes_is_cut_off_at_the_total_deadline(server):
    designer = designer_for(server.url)
    started = time.monotonic()

    with pytest.raises(DesignError, match='in time'):
        designer.design(REQUEST)

    assert time.monotonic() - started < 2 * TIMEOUT + 1.5


@pytest.mark.parametrize('server', ['body', 'headers'], indirect=True)
def test_cancelling_aborts_a_read_that_is_blocked_on_the_network(server):
    designer = OpenAiCompatibleDesigner(KEY, 'model-x', 30, server.url)  # a 60 s budget: only cancellation can end it
    event = cancellation.CancelEvent()
    threading.Timer(0.3, event.set).start()
    started = time.monotonic()

    with cancellation.bound(event):
        with pytest.raises(DesignError, match='cancel'):
            designer.design(REQUEST)

    assert time.monotonic() - started < 3


def test_cancelling_interrupts_the_backoff_pause():
    session = FakeSession(FakeResponse(503, {}, {'Retry-After': '8'}))
    designer = OpenAiCompatibleDesigner(KEY, 'model-x', 30, 'http://127.0.0.1:1/v1', session=session)
    event = cancellation.CancelEvent()
    threading.Timer(0.2, event.set).start()
    started = time.monotonic()

    with cancellation.bound(event):
        with pytest.raises(DesignError, match='cancel'):
            designer.design(REQUEST)

    assert time.monotonic() - started < 3  # the default sleep waits on the cancel event instead of for 8 s
    assert len(session.calls) == 1
