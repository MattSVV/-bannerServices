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
"""OpenAI Chat Completions (``POST /v1/chat/completions``, JSON response format)."""
from urllib.parse import quote

from ...application.ports import DesignError
from .http import HttpDesigner, text_parts, unusable

CHAT_URL = 'https://api.openai.com/v1/chat/completions'
MODELS_URL = 'https://api.openai.com/v1/models/'
MAX_OUTPUT_TOKENS = 16000


class OpenAiDesigner(HttpDesigner):
    provider = 'OpenAI'
    token_field = 'max_completion_tokens'  # noqa: S105 - a JSON field name, not a secret

    def _headers(self):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    def _chat_url(self):
        return CHAT_URL

    def _build_design(self, request):
        body = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': request.system_prompt},
                         {'role': 'user', 'content': request.user_prompt}],
            'response_format': {'type': 'json_object'},
            self.token_field: MAX_OUTPUT_TOKENS,
        }
        return 'POST', self._chat_url(), self._headers(), body

    def _build_probe(self):
        return 'GET', MODELS_URL + quote(self.model, safe=''), self._headers()

    def _extract_text(self, data):
        choices = data.get('choices')
        message = choices[0].get('message') if isinstance(choices, list) and choices and isinstance(choices[0], dict) \
            else None
        if not isinstance(message, dict):
            raise DesignError(f'{self.provider} sent an unexpected answer (no choices).')
        if message.get('refusal'):
            raise DesignError(f'{self.provider} refused to design this cover.')
        text = text_parts(message.get('content'))
        if not text.strip():
            raise unusable('The reply was empty.')
        return text
