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
"""The production designer factory: settings and secret store in, a ready ``CoverDesigner`` out."""
import pytest
from contrib.plugins.portadas.application.ai_config import AiConfig
from contrib.plugins.portadas.application.ports import DesignError, DesignRequest, SecretStoreError
from contrib.plugins.portadas.lib.ai_designer import make_designer

from .ai_support import KEY


class Store:
    def __init__(self, key=None, error=None):
        self.key, self.error, self.asked = key, error, []

    def get_api_key(self, provider):
        self.asked.append(provider)
        if self.error:
            raise self.error
        return self.key


def config(**overrides):
    values = dict(provider='openai', model='', base_url='', timeout=60)
    values.update(overrides)
    return AiConfig(**values)


def test_the_key_of_the_configured_provider_goes_to_the_adapter():
    seen = {}
    store = Store(KEY)

    def create(cfg, key):
        seen.update(cfg=cfg, key=key)
        return 'D'

    result = make_designer(config(provider='gemini'), store, create=create)

    assert result == 'D' and seen['key'] == KEY and seen['cfg'].provider == 'gemini'
    assert store.asked == ['gemini']


def test_no_saved_key_surfaces_the_adapter_message_without_any_request():
    designer = make_designer(config(), Store(None))

    with pytest.raises(DesignError, match='No API key is saved for OpenAI'):
        designer.design(DesignRequest('system', 'user'))


def test_an_unreadable_key_store_becomes_a_presentable_error():
    with pytest.raises(DesignError, match='saved API key could not be read'):
        make_designer(config(), Store(error=SecretStoreError('/home/x/secrets is broken')))


@pytest.mark.parametrize('url', ['', 'http://example.com/v1', 'ftp://x'])
def test_a_bad_compatible_server_address_is_refused_before_any_call(url):
    with pytest.raises(DesignError):
        make_designer(config(provider='openai_compatible', base_url=url), Store(None))


def test_a_local_compatible_server_works_without_a_key():
    designer = make_designer(config(provider='openai_compatible', base_url='http://localhost:11434/v1'), Store(None))

    assert designer is not None
