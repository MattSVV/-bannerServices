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
from openlp.core.common.applocation import AppLocation
from openlp.core.common.settings import Settings

from ..adapters.secret_store import FileSecretStore
from ..application.ai_config import DEFAULT_PROVIDER, DEFAULT_TIMEOUT, MAX_TIMEOUT, MIN_TIMEOUT, PROVIDERS, AiConfig

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
