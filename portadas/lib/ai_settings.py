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
Non-secret AI settings in OpenLP's ``Settings`` (``portadas/ai ...``), plus the factory for the secret store.

The API key is deliberately not here: it lives in the ``SecretStore`` so OpenLP's settings export never contains it.
"""
from urllib.parse import urlsplit

from openlp.core.common.applocation import AppLocation
from openlp.core.common.settings import Settings

from ..adapters.secret_store import FileSecretStore
from ..application.ai_config import (
    COMPATIBLE,
    DEFAULT_PROVIDER,
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
    PROVIDERS,
    AiConfig,
    origin_of,
)

PROVIDER_KEY = 'portadas/ai provider'
MODEL_KEY = 'portadas/ai model'
BASE_URL_KEY = 'portadas/ai base url'
TIMEOUT_KEY = 'portadas/ai timeout'
BACKGROUND_KEY = 'portadas/ai background images'

# OpenLP reads defaults while a plugin is instantiated, so they must exist at import time.
Settings.extend_default_settings({
    PROVIDER_KEY: DEFAULT_PROVIDER,
    MODEL_KEY: '',
    BASE_URL_KEY: '',
    TIMEOUT_KEY: DEFAULT_TIMEOUT,
    BACKGROUND_KEY: False,
})


def load_ai_config(settings=None):
    """Read the AI settings, replacing anything corrupt (hand-edited ini files) with the default."""
    settings = settings or Settings()
    provider = settings.value(PROVIDER_KEY)
    try:
        timeout = int(settings.value(TIMEOUT_KEY))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    return AiConfig(provider=provider if provider in PROVIDERS else DEFAULT_PROVIDER,
                    model=str(settings.value(MODEL_KEY) or ''),
                    base_url=str(settings.value(BASE_URL_KEY) or ''),
                    timeout=max(MIN_TIMEOUT, min(MAX_TIMEOUT, timeout)),
                    background_images=bool(settings.value(BACKGROUND_KEY)))


def save_ai_config(settings, config):
    """Write the AI settings. The caller validates ``config.base_url`` first."""
    settings.setValue(PROVIDER_KEY, config.provider)
    settings.setValue(MODEL_KEY, config.model.strip())
    settings.setValue(BASE_URL_KEY, config.base_url)
    settings.setValue(TIMEOUT_KEY, config.bounded_timeout)
    settings.setValue(BACKGROUND_KEY, bool(config.background_images))


def default_secret_store():
    """The production store: ``<OpenLP data>/portadas/secrets``, private to the current user."""
    return FileSecretStore(AppLocation.get_section_data_path('portadas') / 'secrets')


KEY_OK, KEY_CHANGED, KEY_UNBOUND = 'ok', 'changed', 'unbound'


def key_server_status(secret_store, base_url):
    """
    Whether the stored OpenAI-compatible key may be sent to ``base_url``: ``(status, saved_origin)``.

    ``status`` is ``KEY_OK`` (the key was entered for this origin), ``KEY_CHANGED`` (it was entered for another one,
    for example because an imported settings file changed the address) or ``KEY_UNBOUND`` (no origin was recorded, as
    for a key saved by an older version). Only ``KEY_OK`` allows the key to leave the machine.

    :raises ValueError: when ``base_url`` is not a valid server address.
    """
    wanted = origin_of(base_url)
    saved = secret_store.get_api_key_origin(COMPATIBLE)
    if not saved:
        return KEY_UNBOUND, None
    return (KEY_OK if saved == wanted else KEY_CHANGED), saved


def destination_key(config):
    """What the first-use notice is bound to: the provider id, plus the server origin for an own server."""
    if config.provider == COMPATIBLE:
        try:
            return f'{COMPATIBLE} {origin_of(config.base_url)}'
        except ValueError:
            return COMPATIBLE
    return config.provider


def destination_label(config):
    """Where a design request goes, for the user: the provider's name, or the host of an own server."""
    if config.provider == COMPATIBLE:
        try:
            return urlsplit(origin_of(config.base_url)).netloc
        except ValueError:
            return 'the server you configured'
    names = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'gemini': 'Google Gemini'}
    return names.get(config.provider, 'the AI provider')
