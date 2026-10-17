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
"""
Builds the ``CoverDesigner`` the editor's AI mode uses, from the saved AI settings and the secret store.

It runs on the GUI thread (reading settings and one small key file) and never makes a request: the blocking call
happens later on a worker thread. Every failure is a ``DesignError`` whose message is presentable and key-free.
"""
import dataclasses
import logging

from openlp.core.common.i18n import translate

from ..adapters.ai import create_designer
from ..application.ai_config import COMPATIBLE, validate_base_url
from ..application.ports import DesignError, SecretStoreError
from .ai_settings import default_secret_store, load_ai_config

log = logging.getLogger(__name__)


def make_designer(config=None, secret_store=None, create=create_designer):
    """
    :param config: an ``AiConfig``; defaults to the saved settings.
    :param secret_store: a ``SecretStore``; defaults to the per-user file store.
    :param create: the adapter factory (replaced in tests).
    :raises DesignError: for an invalid server address or an unreadable key store. A missing key is reported by the
        designer itself when the request is made, because OpenAI-compatible local servers need none.
    """
    config = config or load_ai_config()
    if config.provider == COMPATIBLE:
        try:
            config = dataclasses.replace(config, base_url=validate_base_url(config.base_url))
        except ValueError as error:
            raise DesignError(str(error)) from None
    store = secret_store or default_secret_store()
    try:
        api_key = store.get_api_key(config.provider)
    except (SecretStoreError, ValueError):
        log.warning('The saved API key could not be read.')
        raise DesignError(translate('PortadasPlugin.EditForm', 'The saved API key could not be read. Enter it again '
                                    'in Settings > Configure OpenLP > Covers.')) from None
    return create(config, api_key)
