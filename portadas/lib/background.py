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
Runs a blocking call (an AI request) on Qt's thread pool and delivers the outcome on the GUI thread.

Usage (the editor's AI mode and the settings page)::

    job = run_in_background(lambda: use_case.design(cover, hint), self._on_design, self._on_design_failed)
    ...
    job.cancel()   # when the dialog closes: the callbacks will not run any more

``on_done(result)`` and ``on_error(message)`` run on the thread that called ``run_in_background`` (it must be the GUI
thread). ``message`` is the text of a ``DesignError`` (presentable, key-free), or a generic sentence for any other
exception; the key-shaped text is redacted either way. An AI request stops at its next checkpoint after ``cancel``
(between chunks and attempts, see ``application/cancellation.py``); a wait on the socket ends by its own timeout.
"""
import logging

from openlp.core.common.i18n import translate
from PyQt5 import QtCore

from ..application import cancellation
from ..application.ports import DesignError
from ..security.redaction import redact

log = logging.getLogger(__name__)

_active = set()  # keeps jobs (and their signal objects) alive until their result was delivered


class BackgroundJob(QtCore.QObject):
    """A handle on one background call. Lives on the GUI thread; its signals are emitted from the worker thread."""
    _finished = QtCore.pyqtSignal(object, str)  # (result, error message); the message is empty on success

    def __init__(self, work, on_done, on_error):
        super().__init__()
        self._work, self._on_done, self._on_error = work, on_done, on_error
        self._cancelled = False
        self._cancel_event = cancellation.CancelEvent()  # seen by the work through ``application/cancellation.py``
        self._finished.connect(self._deliver)  # queued: emitted by the worker, received on the GUI thread

    def cancel(self):
        """Drop the outcome: neither callback will run, and the work is asked to stop at its next checkpoint."""
        self._cancelled = True
        self._cancel_event.set()

    @property
    def cancelled(self):
        return self._cancelled

    def run_work(self):
        """Executed on the worker thread."""
        try:
            with cancellation.bound(self._cancel_event):
                result = self._work()
            self._finished.emit(result, '')
        except DesignError as error:
            self._finished.emit(None, redact(str(error)) or type(error).__name__)
        except Exception as error:  # noqa: BLE001 - nothing may escape a worker thread
            log.warning('A background AI call failed unexpectedly (%s).', type(error).__name__)
            self._finished.emit(None, translate('PortadasPlugin.Background', 'The request failed unexpectedly '
                                                '({kind}).').format(kind=type(error).__name__))

    @QtCore.pyqtSlot(object, str)
    def _deliver(self, result, message):
        _active.discard(self)
        if self._cancelled:
            return
        try:
            (self._on_error(message) if message else self._on_done(result))
        except Exception:  # an exception escaping a slot would abort the application
            log.exception('A background callback raised')


class _Runnable(QtCore.QRunnable):
    def __init__(self, job):
        super().__init__()
        self._job = job

    def run(self):
        self._job.run_work()


def run_in_background(work, on_done, on_error, pool=None):
    """Start ``work()`` on ``pool`` (the global pool by default) and return its ``BackgroundJob``."""
    job = BackgroundJob(work, on_done, on_error)
    _active.add(job)
    (pool or QtCore.QThreadPool.globalInstance()).start(_Runnable(job))
    return job
