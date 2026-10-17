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
Shared HTTP plumbing of the AI adapters: one bounded, retrying, size-capped JSON call and its error mapping.

Rules every provider call follows (docs/security.md):

* the timeout is ``AiConfig.bounded_timeout``; redirects are never followed (a custom header such as ``x-api-key``
  would travel to the new host);
* 429 and 5xx are retried at most ``MAX_RETRIES`` times, with an exponential or ``Retry-After`` backoff capped at
  ``MAX_BACKOFF`` seconds;
* the response is read in chunks and refused beyond ``MAX_RESPONSE_BYTES``;
* errors become ``DesignError`` with a fixed, presentable message. The text of the underlying exception (which can
  carry headers or the URL) is never used, and anything taken from a provider's error body is redacted and shortened.
"""
import json
import logging
import re
import time
import unicodedata

import requests

from ...application.design_parse import parse_design_reply
from ...application.ports import CoverDesigner, DesignError, UnusableReply
from ...security.redaction import redact, register_secret

log = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RETRIES = 2
MAX_BACKOFF = 10.0
CONNECT_TIMEOUT = 10
MAX_PROVIDER_MESSAGE = 200
RETRYABLE = frozenset({429, 500, 502, 503, 504, 529})
MODEL_PATTERN = re.compile(r'\A[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,99}\Z')
KEY_PATTERN = re.compile(r'\A[\x21-\x7e]{6,500}\Z')  # printable ASCII without spaces: safe as a header value


class HttpDesigner(CoverDesigner):
    """
    Base of the provider adapters.

    :param provider: display name used in messages.
    :param api_key: the key, or ``None`` (only ``openai_compatible`` may work without one).
    :param model: the model id to call.
    :param timeout: seconds, already bounded (``AiConfig.bounded_timeout``).
    :param session: a ``requests.Session``-like object with ``request``; a fresh session by default.
    :param sleep: the sleep function used for backoff (replaced in tests).
    """
    provider = 'the AI provider'
    key_required = True

    def __init__(self, api_key, model, timeout, session=None, sleep=None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self.sleep = sleep if sleep is not None else time.sleep
        if isinstance(api_key, str):
            register_secret(api_key)  # the exact key is redacted from any text this process logs from now on

    # --- the public port ----------------------------------------------------------------------------------------
    def design(self, request):
        self._check_ready()
        method, url, headers, body = self._build_design(request)
        data = self._send(method, url, headers, body)
        return parse_design_reply(self._extract_text(data))

    def test_connection(self):
        self._check_ready()
        method, url, headers = self._build_probe()
        return self._probe_message(self._send(method, url, headers, None))

    # --- hooks for the providers --------------------------------------------------------------------------------
    def _build_design(self, request):
        raise NotImplementedError

    def _build_probe(self):
        raise NotImplementedError

    def _extract_text(self, data):
        raise NotImplementedError

    def _probe_message(self, data):
        return f'Connected to {self.provider}. The model "{self.model}" is available.'

    def _check_ready(self):
        if self.key_required and not self.api_key:
            raise DesignError(f'No API key is saved for {self.provider}. Add one in Settings > Configure OpenLP > '
                              'Covers.')
        if self.api_key and not KEY_PATTERN.match(self.api_key):
            raise DesignError(f'The API key for {self.provider} contains spaces or unsupported characters.')
        if not isinstance(self.model, str) or not MODEL_PATTERN.match(self.model):
            raise DesignError('The model name is not valid. Use letters, digits and . _ : / @ + - only.')

    # --- one call ------------------------------------------------------------------------------------------------
    def _send(self, method, url, headers, body):
        for attempt in range(MAX_RETRIES + 1):
            response = self._request(method, url, headers, body)
            try:
                status = response.status_code
                log.debug('%s answered HTTP %s (attempt %d)', self.provider, status, attempt + 1)
                if status in RETRYABLE and attempt < MAX_RETRIES:
                    delay = self._backoff(response, attempt)
                    response.close()
                    self.sleep(delay)
                    continue
                raw = self._read(response)
                if 200 <= status < 300:
                    return self._load(raw)
                raise DesignError(self._status_message(status, raw))
            finally:
                response.close()
        raise DesignError(f'{self.provider} did not answer.')  # pragma: no cover - the loop always returns or raises

    def _request(self, method, url, headers, body):
        try:
            return self.session.request(method, url, headers=headers, json=body, stream=True, allow_redirects=False,
                                        timeout=(min(CONNECT_TIMEOUT, self.timeout), self.timeout))
        except requests.exceptions.Timeout:
            raise DesignError(f'{self.provider} did not answer in time. Try again, or raise the request timeout in '
                              'the Covers settings.') from None
        except requests.exceptions.SSLError:
            raise DesignError(f'A secure connection to {self.provider} could not be made.') from None
        except requests.exceptions.ConnectionError:
            raise DesignError(f'Could not connect to {self.provider}. Check your internet connection and the '
                              'server address.') from None
        except (requests.exceptions.RequestException, ValueError):
            raise DesignError(f'The request to {self.provider} failed.') from None

    @staticmethod
    def _backoff(response, attempt):
        try:
            return max(0.0, min(MAX_BACKOFF, float(response.headers.get('Retry-After'))))
        except (TypeError, ValueError):
            return float(2 ** attempt)

    @staticmethod
    def _read(response):
        chunks, size = [], 0
        for chunk in response.iter_content(8192):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise DesignError('The answer of the AI provider is too large and was discarded.')
            chunks.append(chunk)
        return b''.join(chunks)

    def _load(self, raw):
        try:
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, RecursionError):
            data = None
        if not isinstance(data, dict):
            raise DesignError(f'{self.provider} sent an unexpected answer (it is not a JSON object).')
        return data

    def _status_message(self, status, raw):
        name = self.provider
        if status in (401, 403):
            text = f'{name} rejected the API key (HTTP {status}). Check the key in the Covers settings.'
        elif status == 404:
            text = f'{name} said that the model or address was not found (HTTP 404). Check the model name.'
        elif status == 400:
            text = f'{name} rejected the request (HTTP 400).'
        elif status == 429:
            text = f'{name} is limiting requests or the quota is used up (HTTP 429). Try again later.'
        elif 300 <= status < 400:
            text = f'{name} answered with a redirect (HTTP {status}), which is not followed. Check the server address.'
        elif status >= 500:
            text = f'{name} is unavailable right now (HTTP {status}). Try again later.'
        else:
            text = f'{name} answered with an error (HTTP {status}).'
        detail = self._provider_detail(raw)
        return f'{text} {detail}'.strip() if detail and status not in (401, 403) else text

    @staticmethod
    def _provider_detail(raw):
        try:
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, RecursionError, UnicodeDecodeError):
            return ''
        error = data.get('error') if isinstance(data, dict) else None
        message = error.get('message') if isinstance(error, dict) else error if isinstance(error, str) else None
        if not isinstance(message, str):
            return ''
        clean = ''.join(' ' if unicodedata.category(char) in ('Cc', 'Cf', 'Zl', 'Zp') else char for char in message)
        return redact(' '.join(clean.split()))[:MAX_PROVIDER_MESSAGE]


def text_parts(content):
    """A chat ``content`` that is a string or a list of ``{"text": ...}`` parts, as one string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(part.get('text', '') for part in content if isinstance(part, dict)
                       and isinstance(part.get('text'), str))
    return ''


def unusable(what):
    return UnusableReply(f'{what} The AI answered, but without a design.')
