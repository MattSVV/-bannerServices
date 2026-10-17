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
"""Google Gemini ``generateContent``. The key travels in the ``x-goog-api-key`` header, never in the URL."""
from urllib.parse import quote

from ...application.ports import DesignError
from .http import HttpDesigner, unusable

BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/models/'
MAX_OUTPUT_TOKENS = 16000


class GeminiDesigner(HttpDesigner):
    provider = 'Google Gemini'

    def __init__(self, api_key, model, timeout, session=None, sleep=None):
        model = model[len('models/'):] if isinstance(model, str) and model.startswith('models/') else model
        super().__init__(api_key, model, timeout, session, sleep)

    def _check_ready(self):
        if isinstance(self.model, str) and '/' in self.model:
            raise DesignError('The model name is not valid. Use letters, digits and . _ - only.')
        super()._check_ready()

    def _headers(self):
        return {'x-goog-api-key': self.api_key, 'Content-Type': 'application/json'}

    def _build_design(self, request):
        body = {
            'systemInstruction': {'parts': [{'text': request.system_prompt}]},
            'contents': [{'role': 'user', 'parts': [{'text': request.user_prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'maxOutputTokens': MAX_OUTPUT_TOKENS},
        }
        return 'POST', f'{BASE_URL}{quote(self.model, safe="")}:generateContent', self._headers(), body

    def _build_probe(self):
        return 'GET', BASE_URL + quote(self.model, safe=''), self._headers()

    def _extract_text(self, data):
        feedback = data.get('promptFeedback')
        if isinstance(feedback, dict) and feedback.get('blockReason'):
            raise DesignError(f'{self.provider} blocked the request ({feedback["blockReason"]}).')
        candidates = data.get('candidates')
        content = candidates[0].get('content') if isinstance(candidates, list) and candidates and \
            isinstance(candidates[0], dict) else None
        if not isinstance(content, dict):
            raise DesignError(f'{self.provider} sent an unexpected answer (no candidates).')
        parts = content.get('parts')
        text = ''.join(part.get('text', '') for part in parts if isinstance(part, dict)
                       and isinstance(part.get('text'), str)) if isinstance(parts, list) else ''
        if not text.strip():
            raise unusable('The reply was empty.')
        return text
