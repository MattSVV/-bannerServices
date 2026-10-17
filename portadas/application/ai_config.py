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
"""AI settings that are not secret: providers, default models, timeout bounds and the base URL policy. Pure Python."""
from dataclasses import dataclass
from urllib.parse import urlsplit

PROVIDERS = ('openai', 'anthropic', 'gemini', 'openai_compatible')
COMPATIBLE = 'openai_compatible'

# Starting points only: the model field is free text and the user can change it. Verified 2026-10-17 against:
#   anthropic  https://platform.claude.com/docs/en/about-claude/models/overview  (Haiku 5.5: fastest, from $0.10/$0.50
#              per MTok; same family as claude-sonnet-5-5 and claude-opus-5-5)
#   openai     https://developers.openai.com/api/docs/models and .../models/gpt-6-luna  (most efficient model; the model
#              page lists Chat Completions among its endpoints)
#   gemini     https://ai.google.dev/gemini-api/docs/models  (Flash-Lite: fastest, most cost-effective stable 3.5 model)
#   openai_compatible: NOT verified. Models differ per server; "llama3.1" is the usual Ollama example. Editable.
DEFAULT_MODELS = {
    'openai': 'gpt-6-luna',
    'anthropic': 'claude-haiku-5-5',
    'gemini': 'gemini-3.5-flash-lite',
    'openai_compatible': 'llama3.1',
}

DEFAULT_PROVIDER = 'openai'
DEFAULT_TIMEOUT = 60
MIN_TIMEOUT = 5
MAX_TIMEOUT = 300
MAX_URL_LENGTH = 300
LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})


@dataclass(frozen=True)
class AiConfig:
    """The non-secret AI settings. The API key is never part of it (see ``SecretStore``)."""
    provider: str
    model: str
    base_url: str
    timeout: int
    background_images: bool

    @property
    def effective_model(self):
        """The model to call: the user's choice, or the provider default when the field is empty."""
        return self.model.strip() or DEFAULT_MODELS[self.provider]

    @property
    def bounded_timeout(self):
        """The timeout in seconds, clamped to the supported range."""
        return max(MIN_TIMEOUT, min(MAX_TIMEOUT, int(self.timeout)))


def validate_base_url(url):
    """
    Check the base URL of an OpenAI-compatible server and return it stripped.

    ``https://`` is required, except for ``http://`` to ``localhost``, ``127.0.0.1`` or ``::1`` (local servers such as
    Ollama). Credentials in the URL, whitespace, queries and fragments are refused: keys belong in the secret store, and
    a URL ends up in logs and error messages.

    :raises ValueError: with a message that is safe to show to the user.
    """
    url = (url or '').strip()
    if not url:
        raise ValueError('The server address is empty.')
    if len(url) > MAX_URL_LENGTH or any(char.isspace() or ord(char) < 0x20 for char in url):
        raise ValueError('The server address is not valid.')
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError for a bad port
    except ValueError:
        raise ValueError('The server address is not valid.') from None
    scheme = parts.scheme.lower()
    if scheme not in ('http', 'https') or not host:
        raise ValueError('The server address must start with https:// (or http://localhost for a local server).')
    if parts.username is not None or parts.password is not None:
        raise ValueError('The server address must not contain a user name or password.')
    if parts.query or parts.fragment:
        raise ValueError('The server address must not contain a query or a fragment.')
    if scheme == 'http' and not _is_local(host):
        raise ValueError('Plain http:// is only allowed for localhost or 127.0.0.1. Use https:// otherwise.')
    return url


def _is_local(host):
    return host.lower() in LOCAL_HOSTS
