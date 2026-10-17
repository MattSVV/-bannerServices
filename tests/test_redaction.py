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
"""Log redaction: key shapes and exact stored keys never reach a log handler."""
import logging

import pytest
from contrib.plugins.portadas.security import redaction
from contrib.plugins.portadas.security.redaction import (
    install_log_redaction,
    redact,
    register_secret,
    uninstall_log_redaction,
)

FAKE_OPENAI = 'sk-proj-FAKEFAKEFAKEFAKEFAKE1234567890'
FAKE_ANTHROPIC = 'sk-ant-api03-FAKEFAKEFAKEFAKE_1234-abcd'
FAKE_GEMINI = 'AIzaFAKEFAKEFAKEFAKEFAKEFAKE12345_-x'


@pytest.fixture(autouse=True)
def clean():
    uninstall_log_redaction()  # the plugin module installs it on import
    redaction.clear_secrets()
    yield
    uninstall_log_redaction()
    redaction.clear_secrets()


@pytest.mark.parametrize('text', [
    f'key {FAKE_OPENAI} end', f'key={FAKE_ANTHROPIC}', f'https://x/v1?key={FAKE_GEMINI}&alt=sse',
    'Authorization: Bearer abcdefghijklmnop1234567890', 'authorization: bearer ABCDEFGH.ijkl-mnop_qrst',
    'x-api-key: abcdefghijklmnop1234567890zz'])
def test_known_key_shapes_are_redacted(text):
    out = redact(text)

    assert '[redacted]' in out
    for secret in (FAKE_OPENAI, FAKE_ANTHROPIC, FAKE_GEMINI, 'abcdefghijklmnop', 'ABCDEFGH'):
        assert secret not in out


def test_ordinary_text_is_untouched():
    text = 'Rendered cover abc123 in 0.52 s (sk-1 is not a key, nor is task-force)'

    assert redact(text) == text


def test_exact_registered_keys_are_redacted_whatever_their_shape():
    register_secret('hunter2-custom-key')

    assert redact('using hunter2-custom-key now') == 'using [redacted] now'


def test_very_short_secrets_are_not_registered():
    register_secret('ab')

    assert redact('about') == 'about'


def logger_with_capture(name='contrib.plugins.portadas.adapters.demo'):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(self.format(record))

    handler = Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    return logging.getLogger(name), records, lambda: root.removeHandler(handler)


def test_installed_filter_redacts_records_of_child_loggers():
    install_log_redaction()
    register_secret('exact-secret-value')
    log, records, undo = logger_with_capture()
    log.setLevel(logging.INFO)
    try:
        log.info('plain %s and %s', FAKE_OPENAI, 'exact-secret-value')
        log.info('f-string ' + FAKE_ANTHROPIC)
        try:
            raise RuntimeError('failed with ' + FAKE_GEMINI)
        except RuntimeError:
            log.exception('boom')
    finally:
        undo()

    joined = '\n'.join(records)
    assert '[redacted]' in joined
    for secret in (FAKE_OPENAI, FAKE_ANTHROPIC, FAKE_GEMINI, 'exact-secret-value'):
        assert secret not in joined


def test_install_is_idempotent_and_uninstall_restores_the_logger():
    package = logging.getLogger('contrib.plugins.portadas')
    before = (list(package.filters), list(package.handlers))

    install_log_redaction()
    install_log_redaction()
    assert len(package.handlers) == len(before[1]) + 1
    assert len(package.filters) == len(before[0]) + 1

    uninstall_log_redaction()
    assert (list(package.filters), list(package.handlers)) == before


def test_without_the_filter_the_secret_would_leak():
    log, records, undo = logger_with_capture('some.other.logger')
    log.setLevel(logging.INFO)
    try:
        log.info(FAKE_OPENAI)
    finally:
        undo()

    assert FAKE_OPENAI in records[0]  # control: the harness does see secrets when nothing redacts them
