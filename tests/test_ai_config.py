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
"""Pure AI settings rules: providers, default models and the base URL policy."""
import pytest
from contrib.plugins.portadas.application.ai_config import (
    DEFAULT_MODELS,
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
    PROVIDERS,
    AiConfig,
    validate_base_url,
)


def test_every_provider_has_a_default_model():
    assert set(PROVIDERS) == {'openai', 'anthropic', 'gemini', 'openai_compatible'}
    assert all(DEFAULT_MODELS[provider] for provider in PROVIDERS)


def test_effective_model_falls_back_to_the_provider_default():
    assert AiConfig('anthropic', '', '', 60).effective_model == DEFAULT_MODELS['anthropic']
    assert AiConfig('anthropic', '  my-model ', '', 60).effective_model == 'my-model'


@pytest.mark.parametrize('url', [
    'https://api.example.com/v1', 'https://openrouter.ai/api/v1', 'http://localhost:11434/v1',
    'http://127.0.0.1:11434', 'http://[::1]:8080/v1', 'HTTP://LOCALHOST/v1'])
def test_valid_base_urls_are_accepted(url):
    assert validate_base_url(url) == url.strip()


@pytest.mark.parametrize('url', [
    '', 'ftp://example.com', 'http://example.com/v1', 'http://localhost.evil.com', 'https://', 'https:///path',
    'https://user:pw@example.com', 'https://example.com/a b', 'javascript:alert(1)', 'file:///etc/passwd',
    'https://example.com/#frag', 'https://exa mple.com', 'http://127.0.0.1.evil.com', 'https://' + 'a' * 600])
def test_invalid_base_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_timeout_bounds_are_sane():
    assert MIN_TIMEOUT <= DEFAULT_TIMEOUT <= MAX_TIMEOUT
    assert AiConfig('openai', '', '', 9999).bounded_timeout == MAX_TIMEOUT
    assert AiConfig('openai', '', '', 0).bounded_timeout == MIN_TIMEOUT
