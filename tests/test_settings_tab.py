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
"""The AI settings tab: load/save of non-secret values, the masked API key and the injected connection test."""
import threading

import pytest
from contrib.plugins.portadas.application.ai_config import DEFAULT_MODELS, DEFAULT_TIMEOUT, AiConfig
from contrib.plugins.portadas.application.ports import SecretStore, SecretStoreError
from contrib.plugins.portadas.lib.ai_settings import load_ai_config, save_ai_config
from contrib.plugins.portadas.lib.settingstab import SAVED_PLACEHOLDER, PortadasSettingsTab
from contrib.plugins.portadas.security import redaction

FAKE = 'sk-FAKE-tab-key-0123456789abcdef'
NEW = 'sk-FAKE-new-key-0123456789abcdef'


class MemoryStore(SecretStore):
    def __init__(self, keys=None, fail_on_set=False, origins=None):
        self.keys = dict(keys or {})
        self.origins = dict(origins or {})
        self.fail_on_set = fail_on_set

    def get_api_key_origin(self, provider):
        return self.origins.get(provider)

    def get_api_key(self, provider):
        return self.keys.get(provider)

    def set_api_key(self, provider, key, origin=None):
        if self.fail_on_set:
            raise SecretStoreError('The API key could not be saved.')
        if len(key.split()) != 1:  # like the real store
            raise ValueError('unusable key')
        self.keys[provider] = key.strip()
        self.origins.pop(provider, None)
        if origin:
            self.origins[provider] = origin

    def delete_api_key(self, provider):
        self.keys.pop(provider, None)
        self.origins.pop(provider, None)


class Tab(PortadasSettingsTab):
    """The tab with its message box replaced so a test never blocks on a modal window."""
    warnings = None

    def show_warning(self, text):
        self.warnings = (self.warnings or []) + [text]


@pytest.fixture(autouse=True)
def clean_secrets():
    redaction.clear_secrets()
    yield
    redaction.clear_secrets()


@pytest.fixture
def make_tab(qtbot, openlp_env):
    def make(store=None, **kwargs):
        tab = Tab(None, 'portadas', 'Covers', None, secret_store=store if store is not None else MemoryStore(),
                  **kwargs)
        qtbot.addWidget(tab)
        return tab
    return make


def all_settings_text(settings):
    return ' '.join(f'{key}={settings.value(key)}' for key in settings.allKeys())


def test_defaults_are_loaded(make_tab):
    tab = make_tab()

    assert tab.provider_combo.currentData() == 'openai'
    assert tab.model_edit.text() == ''
    assert tab.model_edit.placeholderText() == DEFAULT_MODELS['openai']
    assert tab.timeout_spin.value() == DEFAULT_TIMEOUT
    assert not tab.background_check.isChecked()
    assert not tab.base_url_edit.isEnabled()
    assert tab.api_key_edit.echoMode() == tab.api_key_edit.Password
    assert tab.api_key_edit.text() == ''
    assert 'No API key' in tab.key_status_label.text()


def test_model_placeholder_follows_the_provider(make_tab):
    tab = make_tab()

    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('anthropic'))

    assert tab.model_edit.placeholderText() == DEFAULT_MODELS['anthropic']


def test_base_url_is_only_enabled_for_openai_compatible(make_tab):
    tab = make_tab()

    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    assert tab.base_url_edit.isEnabled()

    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('gemini'))
    assert not tab.base_url_edit.isEnabled()


def test_save_writes_only_non_secret_values_to_settings(make_tab, openlp_env):
    store = MemoryStore()
    tab = make_tab(store)
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.model_edit.setText('qwen2.5:7b')
    tab.base_url_edit.setText('http://localhost:11434/v1')
    tab.timeout_spin.setValue(90)
    tab.background_check.setChecked(True)
    tab.api_key_edit.setText(f'  {NEW}  ')

    tab.save()

    assert load_ai_config(openlp_env) == AiConfig('openai_compatible', 'qwen2.5:7b', 'http://localhost:11434/v1', 90,
                                                  True)
    assert store.keys == {'openai_compatible': NEW}
    assert NEW not in all_settings_text(openlp_env)
    assert 'sk-' not in all_settings_text(openlp_env)
    assert tab.api_key_edit.text() == ''  # the typed key does not linger in the widget


def test_a_stored_key_is_masked_and_survives_a_save_without_typing(make_tab):
    store = MemoryStore({'openai': FAKE})
    tab = make_tab(store)

    assert tab.api_key_edit.text() == ''
    assert tab.api_key_edit.placeholderText() == SAVED_PLACEHOLDER
    assert SAVED_PLACEHOLDER.startswith('••••') and 'saved' in SAVED_PLACEHOLDER
    assert FAKE not in tab.key_status_label.text()
    assert tab.clear_key_button.isEnabled()

    tab.save()

    assert store.keys == {'openai': FAKE}


def test_the_key_status_follows_the_selected_provider(make_tab):
    tab = make_tab(MemoryStore({'openai': FAKE}))

    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('gemini'))

    assert tab.api_key_edit.placeholderText() != SAVED_PLACEHOLDER
    assert not tab.clear_key_button.isEnabled()


def test_clear_deletes_the_key_on_save_but_not_on_cancel(make_tab):
    store = MemoryStore({'openai': FAKE})
    tab = make_tab(store)

    tab.clear_key_button.click()
    assert 'will be removed' in tab.key_status_label.text()
    tab.cancel()
    assert store.keys == {'openai': FAKE}
    assert tab.api_key_edit.placeholderText() == SAVED_PLACEHOLDER

    tab.clear_key_button.click()
    tab.save()
    assert store.keys == {}
    assert 'No API key' in tab.key_status_label.text()


def test_a_key_is_stored_under_the_provider_that_was_selected(make_tab):
    store = MemoryStore()
    tab = make_tab(store)
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('anthropic'))
    tab.api_key_edit.setText(NEW)

    tab.save()

    assert store.keys == {'anthropic': NEW}


def test_an_unusable_key_is_reported_and_not_stored(make_tab):
    store = MemoryStore()
    tab = make_tab(store)
    tab.api_key_edit.setText('two words')

    tab.save()

    assert store.keys == {}
    assert tab.warnings and 'two words' not in ' '.join(tab.warnings)


def test_a_store_failure_is_reported_without_the_key(make_tab, openlp_env):
    tab = make_tab(MemoryStore(fail_on_set=True))
    tab.api_key_edit.setText(NEW)
    tab.timeout_spin.setValue(45)

    tab.save()

    assert tab.warnings and NEW not in ' '.join(tab.warnings)
    assert load_ai_config(openlp_env).timeout == 45  # the other settings are still saved


@pytest.mark.parametrize('url', ['http://example.com/v1', 'ftp://x', 'https://u:p@example.com', ''])
def test_an_invalid_base_url_is_flagged_and_not_saved(make_tab, openlp_env, url):
    tab = make_tab()
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(url)

    assert not tab.base_url_error_label.isHidden()
    tab.save()

    assert load_ai_config(openlp_env).base_url == ''
    assert tab.warnings


def test_a_valid_base_url_clears_the_error(make_tab):
    tab = make_tab()
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText('nope')
    tab.base_url_edit.setText('https://openrouter.ai/api/v1')

    assert tab.base_url_error_label.isHidden()


def test_loading_again_shows_the_saved_values(make_tab, openlp_env):
    save_ai_config(openlp_env, AiConfig('gemini', 'gemini-x', '', 120, True))
    tab = make_tab()

    assert tab.provider_combo.currentData() == 'gemini'
    assert tab.model_edit.text() == 'gemini-x'
    assert tab.timeout_spin.value() == 120
    assert tab.background_check.isChecked()


def test_a_corrupt_stored_provider_falls_back_to_the_default(make_tab, openlp_env):
    openlp_env.setValue('portadas/ai provider', 'evilcorp')
    openlp_env.setValue('portadas/ai timeout', 'abc')

    config = load_ai_config(openlp_env)

    assert config.provider == 'openai' and config.timeout == DEFAULT_TIMEOUT


def wait_for_result(qtbot, tab, text='Testing...'):
    qtbot.waitUntil(lambda: tab.test_button.isEnabled() and tab.test_result_label.text() != text, timeout=5000)


def test_test_connection_uses_the_real_adapter_by_default(make_tab, qtbot):
    tab = make_tab()  # no key stored: the adapter answers without any network call

    tab.test_button.click()
    wait_for_result(qtbot, tab)

    assert 'No API key' in tab.test_result_label.text()


def test_the_button_is_disabled_and_a_hint_shown_while_the_test_runs(make_tab, qtbot):
    release = threading.Event()

    def slow(config, api_key):
        release.wait(5)
        return 'Connected.'

    tab = make_tab(test_connection=slow)

    tab.test_button.click()

    assert not tab.test_button.isEnabled() and tab.test_result_label.text() == 'Testing...'
    release.set()
    wait_for_result(qtbot, tab)
    assert tab.test_result_label.text() == 'Connected.'


def test_reloading_the_tab_drops_a_test_in_flight(make_tab, qtbot):
    release = threading.Event()
    tab = make_tab(test_connection=lambda config, api_key: release.wait(5) and 'late')

    tab.test_button.click()
    tab.load()
    release.set()
    qtbot.wait(150)

    assert tab.test_button.isEnabled() and tab.test_result_label.text() == ''


def test_test_connection_calls_the_injected_callable_with_the_typed_key(make_tab, qtbot):
    calls = []

    def probe(config, api_key):
        calls.append((config, api_key))
        return 'Connected.'

    tab = make_tab(MemoryStore({'openai': FAKE}), test_connection=probe)
    tab.model_edit.setText('m1')
    tab.test_button.click()
    wait_for_result(qtbot, tab)
    tab.api_key_edit.setText(NEW)
    tab.test_button.click()
    wait_for_result(qtbot, tab)

    assert [call[0].model for call in calls] == ['m1', 'm1']
    assert [call[1] for call in calls] == [FAKE, NEW]  # the stored key, then the one being typed
    assert tab.test_result_label.text() == 'Connected.'


def test_test_connection_errors_are_shown_redacted(make_tab, qtbot):
    def probe(config, api_key):
        raise RuntimeError(f'401 for key {api_key}')

    tab = make_tab(MemoryStore({'openai': FAKE}), test_connection=probe)

    tab.test_button.click()
    wait_for_result(qtbot, tab)

    assert FAKE not in tab.test_result_label.text()
    assert '401' in tab.test_result_label.text()


def test_cancel_discards_unsaved_edits(make_tab):
    tab = make_tab()
    tab.model_edit.setText('typed')
    tab.api_key_edit.setText(NEW)

    tab.cancel()

    assert tab.model_edit.text() == '' and tab.api_key_edit.text() == ''


def test_the_widgets_use_translated_titles(make_tab):
    tab = make_tab()

    assert tab.tab_title == 'portadas'
    assert tab.group_box.title()
    assert tab.timeout_spin.minimum() < tab.timeout_spin.maximum()
