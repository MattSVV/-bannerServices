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
"""Any server that speaks the OpenAI wire format (Ollama, OpenRouter, LM Studio, vLLM...) at a user-set base URL."""
from ...application.ai_config import validate_base_url
from ...application.ports import DesignError
from .openai import OpenAiDesigner


class OpenAiCompatibleDesigner(OpenAiDesigner):
    provider = 'the OpenAI-compatible server'
    key_required = False
    token_field = 'max_tokens'  # noqa: S105 - the older name every compatible server understands

    def __init__(self, api_key, model, timeout, base_url, session=None, sleep=None, clock=None):
        super().__init__(api_key, model, timeout, session, sleep, clock)
        try:
            self.base_url = validate_base_url(base_url).rstrip('/')
        except ValueError as error:
            self.base_url = None
            self._base_url_error = str(error)

    def _check_ready(self):
        if self.base_url is None:
            raise DesignError(f'The server address is not valid: {self._base_url_error}')
        super()._check_ready()

    def _chat_url(self):
        return self.base_url + '/chat/completions'

    def _build_probe(self):
        return 'GET', self.base_url + '/models', self._headers()

    def _probe_message(self, data):
        models = data.get('data')
        count = len(models) if isinstance(models, list) else 0
        return f'Connected to the server ({count} models listed).'
