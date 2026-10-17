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
"""T15a / SEC-003: the key of an OpenAI-compatible server is bound to the server it was entered for."""
import json

import pytest
from contrib.plugins.portadas.adapters.secret_store import FileSecretStore
from contrib.plugins.portadas.application.ai_config import AiConfig, origin_of
from contrib.plugins.portadas.application.ports import DesignError
from contrib.plugins.portadas.lib.ai_designer import make_designer
from contrib.plugins.portadas.lib.ai_settings import BASE_URL_KEY, PROVIDER_KEY
from contrib.plugins.portadas.security import redaction

from .test_settings_tab import FAKE, NEW, MemoryStore, Tab, wait_for_result

HOME = 'https://llm.example.org/v1'
EVIL = 'https://evil.example.net/v1'


@pytest.fixture(autouse=True)
def clean_secrets():
    redaction.clear_secrets()
    yield
    redaction.clear_secrets()


def config(url=HOME, provider='openai_compatible'):
    return AiConfig(provider, '', url, 60)


# --- the origin ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('url, origin', [
    ('https://LLM.Example.org/v1', 'https://llm.example.org'),
    ('https://llm.example.org:443/other/path', 'https://llm.example.org'),
    ('https://llm.example.org:8443/v1', 'https://llm.example.org:8443'),
    ('http://localhost:11434/v1', 'http://localhost:11434'),
    ('http://localhost:80/v1', 'http://localhost'),
    ('http://[::1]:11434/v1', 'http://[::1]:11434'),
])
def test_origin_of_normalizes_scheme_host_and_port(url, origin):
    assert origin_of(url) == origin


def test_origin_of_refuses_what_the_url_policy_refuses():
    with pytest.raises(ValueError):
        origin_of('http://evil.example.net/v1')


# --- the store -------------------------------------------------------------------------------------------------------

def test_the_origin_is_stored_with_the_key_and_replaced_with_it(tmp_path):
    store = FileSecretStore(tmp_path / 's')
    store.set_api_key('openai_compatible', FAKE, origin='https://a.example.org')
    assert store.get_api_key_origin('openai_compatible') == 'https://a.example.org'

    store.set_api_key('openai_compatible', NEW)  # a key stored without an origin is unverified
    assert store.get_api_key_origin('openai_compatible') is None


def test_deleting_the_key_forgets_its_origin(tmp_path):
    store = FileSecretStore(tmp_path / 's')
    store.set_api_key('openai_compatible', FAKE, origin='https://a.example.org')

    store.delete_api_key('openai_compatible')

    assert store.get_api_key_origin('openai_compatible') is None


def test_a_file_written_before_origins_existed_reads_as_unverified(tmp_path):
    store = FileSecretStore(tmp_path / 's')
    store.set_api_key('openai_compatible', FAKE)
    data = json.loads(store.path.read_text())
    data.pop('origins', None)
    store.path.write_text(json.dumps(data))

    assert store.get_api_key('openai_compatible') == FAKE
    assert store.get_api_key_origin('openai_compatible') is None


def test_a_malformed_origins_entry_reads_as_unverified_but_keeps_the_keys(tmp_path):
    store = FileSecretStore(tmp_path / 's')
    store.set_api_key('openai_compatible', FAKE, origin='https://a.example.org')
    data = json.loads(store.path.read_text())
    data['origins'] = ['not', 'a', 'mapping']
    store.path.write_text(json.dumps(data))

    assert store.get_api_key('openai_compatible') == FAKE
    assert store.get_api_key_origin('openai_compatible') is None


# --- the designer ----------------------------------------------------------------------------------------------------

def test_the_key_goes_to_the_server_it_was_entered_for():
    seen = []
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(HOME)})

    make_designer(config(), store, create=lambda cfg, key: seen.append(key) or 'D')

    assert seen == [FAKE]


def blocked_message(store, url=HOME):
    created = []
    with pytest.raises(DesignError) as error:
        make_designer(config(url), store, create=lambda cfg, key: created.append(key))
    assert created == []  # nothing is built, so nothing is sent: neither with the key nor without it
    return str(error.value)


def test_a_key_entered_for_another_server_blocks_the_design_and_names_the_configured_host():
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(EVIL)})

    message = blocked_message(store)

    assert 'entered for another server' in message and 'llm.example.org' in message
    assert 'Settings > Configure OpenLP > Covers' in message
    assert FAKE not in message and 'evil.example.net' not in message and 'https://' not in message


def test_a_legacy_key_without_a_recorded_server_blocks_with_its_own_message():
    message = blocked_message(MemoryStore({'openai_compatible': FAKE}))

    assert 'before' in message and 'server' in message and 'llm.example.org' in message
    assert 'entered for another server' not in message and FAKE not in message
    assert 'Settings > Configure OpenLP > Covers' in message


def test_the_two_blocking_messages_are_different():
    other = blocked_message(MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(EVIL)}))
    legacy = blocked_message(MemoryStore({'openai_compatible': FAKE}))

    assert other != legacy


def test_a_stored_key_for_another_server_blocks_even_a_local_keyless_address():
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(EVIL)})

    message = blocked_message(store, 'http://localhost:11434/v1')

    assert 'localhost:11434' in message


def test_entering_the_key_again_in_the_settings_tab_unblocks_the_design(make_tab):
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(EVIL)})
    blocked_message(store)
    tab = make_tab(store)
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(HOME)
    tab.api_key_edit.setText(NEW)

    tab.save()

    seen = []
    make_designer(config(), store, create=lambda cfg, key: seen.append(key))
    assert seen == [NEW]


def test_a_server_that_needs_no_key_is_unaffected():
    created = []

    make_designer(config(), MemoryStore(), create=lambda cfg, key: created.append(key))

    assert created == [None]


def test_fixed_providers_ignore_the_origin():
    created = []
    store = MemoryStore({'openai': FAKE})

    make_designer(config('', 'openai'), store, create=lambda cfg, key: created.append(key))

    assert created == [FAKE]


# --- the settings tab and a simulated settings import ----------------------------------------------------------------

@pytest.fixture
def make_tab(qtbot, openlp_env):
    def make(store, **kwargs):
        tab = Tab(None, 'portadas', 'Covers', None, secret_store=store, **kwargs)
        qtbot.addWidget(tab)
        return tab
    return make


def test_saving_a_key_for_a_server_binds_it_to_that_server(make_tab):
    store = MemoryStore()
    tab = make_tab(store)
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(HOME)
    tab.api_key_edit.setText(NEW)

    tab.save()

    assert store.origins == {'openai_compatible': origin_of(HOME)}


def test_an_imported_settings_file_cannot_redirect_a_saved_key(make_tab, openlp_env):
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(HOME)})
    openlp_env.setValue(PROVIDER_KEY, 'openai_compatible')
    openlp_env.setValue(BASE_URL_KEY, HOME)
    # What OpenLP's "import settings" does: it writes whatever the file says.
    openlp_env.setValue(BASE_URL_KEY, EVIL)

    created = []
    with pytest.raises(DesignError):
        make_designer(secret_store=store, create=lambda cfg, key: created.append(key))

    assert created == []  # the redirected address receives neither the key nor a keyless request


@pytest.mark.parametrize('origins, wording', [
    ({'openai_compatible': origin_of(HOME)}, 'entered for another server'),
    ({}, 'before'),
], ids=['other server', 'legacy'])
def test_test_connection_is_blocked_with_the_message_and_the_configured_host(make_tab, qtbot, origins, wording):
    calls = []
    store = MemoryStore({'openai_compatible': FAKE}, origins=origins)
    tab = make_tab(store, test_connection=lambda cfg, key: calls.append(key) or 'Connected.')
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(EVIL)

    tab.test_button.click()
    qtbot.waitUntil(lambda: tab.test_button.isEnabled(), timeout=5000)

    text = tab.test_result_label.text()
    assert calls == [] and FAKE not in text
    assert wording in text and 'evil.example.net' in text and 'Settings > Configure OpenLP > Covers' in text


def test_test_connection_without_any_stored_key_still_goes_out_keyless(make_tab, qtbot):
    calls = []
    tab = make_tab(MemoryStore(), test_connection=lambda cfg, key: calls.append(key) or 'Connected.')
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText('http://localhost:11434/v1')

    tab.test_button.click()
    wait_for_result(qtbot, tab, tab.test_result_label.text())

    assert calls == [None]


def test_test_connection_names_the_destination_host_and_uses_a_typed_key(make_tab, qtbot):
    calls = []
    tab = make_tab(MemoryStore(), test_connection=lambda cfg, key: calls.append(key) or 'Connected.')
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(HOME)
    tab.api_key_edit.setText(NEW)

    tab.test_button.click()

    assert 'llm.example.org' in tab.test_result_label.text()
    wait_for_result(qtbot, tab, tab.test_result_label.text())
    assert calls == [NEW]


def test_the_key_status_names_the_server_and_flags_a_mismatch(make_tab):
    store = MemoryStore({'openai_compatible': FAKE}, origins={'openai_compatible': origin_of(HOME)})
    tab = make_tab(store)
    tab.provider_combo.setCurrentIndex(tab.provider_combo.findData('openai_compatible'))
    tab.base_url_edit.setText(HOME)
    assert 'llm.example.org' in tab.key_status_label.text()

    tab.base_url_edit.setText(EVIL)

    assert 'again' in tab.key_status_label.text() and 'llm.example.org' in tab.key_status_label.text()
