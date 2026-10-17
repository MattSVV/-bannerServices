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
"""Anthropic Messages API (``POST /v1/messages``)."""
from urllib.parse import quote

from ...application.ports import DesignError
from .http import HttpDesigner, unusable

MESSAGES_URL = 'https://api.anthropic.com/v1/messages'
MODELS_URL = 'https://api.anthropic.com/v1/models/'
API_VERSION = '2023-06-01'
MAX_OUTPUT_TOKENS = 16000


class AnthropicDesigner(HttpDesigner):
    provider = 'Anthropic'

    def _headers(self):
        return {'x-api-key': self.api_key, 'anthropic-version': API_VERSION, 'content-type': 'application/json'}

    def _build_design(self, request):
        body = {'model': self.model, 'max_tokens': MAX_OUTPUT_TOKENS, 'system': request.system_prompt,
                'messages': [{'role': 'user', 'content': request.user_prompt}]}
        return 'POST', MESSAGES_URL, self._headers(), body

    def _build_probe(self):
        return 'GET', MODELS_URL + quote(self.model, safe=''), self._headers()

    def _extract_text(self, data):
        blocks = data.get('content')
        if not isinstance(blocks, list):
            raise DesignError(f'{self.provider} sent an unexpected answer (no content).')
        if data.get('stop_reason') == 'refusal':
            raise DesignError(f'{self.provider} refused to design this cover.')
        text = ''.join(block.get('text', '') for block in blocks
                       if isinstance(block, dict) and block.get('type') == 'text'
                       and isinstance(block.get('text'), str))
        if not text.strip():
            raise unusable('The reply was empty.')
        return text
