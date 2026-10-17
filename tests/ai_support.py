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
"""Doubles for the AI adapter tests: a scripted ``requests.Session`` that never touches the network."""
import json

import requests

KEY = 'sk-test-0123456789abcdefghijkl'
GOOD_HTML = ('<html><head><style>body{background:#123456;color:#fff}.title-main{font-size:90px}</style></head>'
             '<body class="{{empty_fields}}"><div class="title-main">{{title_main}}</div>{{icon}}</body></html>')
GOOD_SVG = '<svg viewBox="0 0 8 8" fill="none" stroke="currentColor"><path d="M1 1 L7 7"/></svg>'
DESIGN_JSON = json.dumps({'html': GOOD_HTML, 'icon_svg': GOOD_SVG, 'notes': 'warm'})


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, raw=None):
        self.status_code = status
        self.headers = headers or {}
        self._raw = raw if raw is not None else json.dumps(body if body is not None else {}).encode('utf-8')
        self.closed = False
        self.chunks_read = 0

    def iter_content(self, chunk_size=8192):
        for start in range(0, len(self._raw), chunk_size):
            self.chunks_read += 1
            yield self._raw[start:start + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    """Answers ``request`` calls from a script: a response, or an exception to raise. Records every call."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({'method': method, 'url': url, **kwargs})
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


def openai_body(text=DESIGN_JSON):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}]}


def anthropic_body(text=DESIGN_JSON):
    return {'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn'}


def gemini_body(text=DESIGN_JSON):
    return {'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'STOP'}]}


class Sleeper:
    def __init__(self):
        self.delays = []

    def __call__(self, seconds):
        self.delays.append(seconds)


def timeout_error():
    return requests.exceptions.ReadTimeout(
        'Read timed out. (read timeout=60) for headers {"Authorization": "Bearer %s"}' % KEY)
