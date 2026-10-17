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
Keeps API keys out of logs.

Two things are redacted: text that has the *shape* of a known key (OpenAI, Anthropic, Gemini, bearer tokens) and the
*exact* keys the secret store has handled in this process. ``install_log_redaction`` hooks the
``contrib.plugins.portadas`` logger hierarchy so every record of the plugin is cleaned before any handler formats it.
"""
import logging
import re

PLUGIN_LOGGER = 'contrib.plugins.portadas'
PLACEHOLDER = '[redacted]'
MIN_SECRET_LENGTH = 6

_SHAPES = (
    re.compile(r'sk-ant-[A-Za-z0-9_-]{8,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{16,}'),
    re.compile(r'AIza[0-9A-Za-z_-]{20,}'),
    re.compile(r'(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}'),
    re.compile(r'(?i)(\b(?:x-api-key|api-key|x-goog-api-key)\s*[:=]\s*)[^\s,;&"\']{8,}'),
)
_secrets = set()


def register_secret(secret):
    """Remember an exact key so it is redacted wherever it appears. Very short strings are ignored."""
    if isinstance(secret, str) and len(secret) >= MIN_SECRET_LENGTH:
        _secrets.add(secret)


def clear_secrets():
    """Forget every registered key (tests, or when the user deletes a key)."""
    _secrets.clear()


def redact(text):
    """Return ``text`` with registered keys and key-shaped strings replaced by ``[redacted]``."""
    for secret in sorted(_secrets, key=len, reverse=True):  # longest first, so a prefix cannot leave a tail behind
        text = text.replace(secret, PLACEHOLDER)
    for shape in _SHAPES:
        text = shape.sub(lambda match: (match.group(1) if match.groups() else '') + PLACEHOLDER, text)
    return text


class RedactionFilter(logging.Filter):
    """Rewrites a record in place: message, arguments and traceback text. It never drops a record."""

    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True


class _RedactingHook(logging.Handler):
    """
    A handler that prints nothing. Python runs the handlers of a logger's ancestors for a child's record, but not the
    ancestors' filters, so this hook is what lets one filter on the package logger clean its whole subtree before the
    real handlers (OpenLP's log file, the console) see the record.
    """

    def emit(self, record):
        pass


_installed = None  # (logger, hook handler, logger filter) while the redaction is active


def install_log_redaction(logger_name=PLUGIN_LOGGER):
    """Install the redaction on the plugin's logger hierarchy. Calling it again does nothing."""
    global _installed
    if _installed is not None:
        return
    logger, hook, logger_filter = logging.getLogger(logger_name), _RedactingHook(), RedactionFilter()
    hook.addFilter(RedactionFilter())
    logger.addFilter(logger_filter)  # records logged directly on the package logger
    logger.addHandler(hook)  # records of its children
    _installed = (logger, hook, logger_filter)


def uninstall_log_redaction():
    """Remove what ``install_log_redaction`` added."""
    global _installed
    if _installed is not None:
        logger, hook, logger_filter = _installed
        logger.removeHandler(hook)
        logger.removeFilter(logger_filter)
        _installed = None
