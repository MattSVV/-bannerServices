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
AI provider adapters: ``create_designer`` builds the ``CoverDesigner`` for the configured provider and
``test_connection`` runs the cheap check behind the settings page's button. Both block: use a worker thread.
"""
from ...application.ai_config import COMPATIBLE, AiConfig
from ...application.ports import DesignError


def create_designer(config, api_key, session=None, sleep=None, clock=None):
    """
    The designer for ``config.provider``.

    :param config: an ``AiConfig`` (provider, model, base URL and timeout).
    :param api_key: the key from the secret store, or ``None``.
    :param session: a ``requests.Session``-like object (tests); a fresh session otherwise.
    :param sleep: replaces ``time.sleep`` for the retry backoff (tests).
    :param clock: replaces ``time.monotonic`` for the total deadline (tests).
    :raises DesignError: for an unknown provider.
    """
    from .anthropic import AnthropicDesigner
    from .gemini import GeminiDesigner
    from .openai import OpenAiDesigner
    from .openai_compatible import OpenAiCompatibleDesigner
    if not isinstance(config, AiConfig):
        raise DesignError('The AI settings are missing.')
    common = dict(api_key=api_key, model=config.effective_model if config.provider in _KNOWN else '',
                  timeout=config.bounded_timeout if config.provider in _KNOWN else 60, session=session, sleep=sleep,
                  clock=clock)
    if config.provider == 'openai':
        return OpenAiDesigner(**common)
    if config.provider == 'anthropic':
        return AnthropicDesigner(**common)
    if config.provider == 'gemini':
        return GeminiDesigner(**common)
    if config.provider == COMPATIBLE:
        return OpenAiCompatibleDesigner(base_url=config.base_url, **common)
    raise DesignError('The AI provider is not supported.')


_KNOWN = ('openai', 'anthropic', 'gemini', COMPATIBLE)


def test_connection(config, api_key, session=None, sleep=None, clock=None):
    """Check the key, model and address with one cheap request. Returns a message; raises ``DesignError``."""
    return create_designer(config, api_key, session=session, sleep=sleep, clock=clock).test_connection()
