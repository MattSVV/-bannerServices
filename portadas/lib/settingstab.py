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
The "Covers" page of OpenLP's settings dialog: AI provider, model, server address, timeout and API key.

Only non-secret values go to ``Settings``. The key goes to the ``SecretStore`` and is never shown again: the field
stays empty and a "saved" hint appears instead. A typed key is stored only by the Save key button, and only after the
same connection test as Test connection succeeded with it; OK never stores a typed key. The show button reveals just the
text being typed. A saved key is only deleted when the user presses Clear and then OK.
"""
import logging
from urllib.parse import urlsplit

from openlp.core.common.i18n import translate
from openlp.core.lib.settingstab import SettingsTab
from PyQt5 import QtCore, QtWidgets

from ..adapters.ai import test_connection as ai_test_connection
from ..application.ai_config import (
    COMPATIBLE,
    DEFAULT_MODELS,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
    PROVIDERS,
    AiConfig,
    origin_of,
    validate_base_url,
)
from ..application.ports import DesignError, SecretStoreError
from ..security.redaction import redact, register_secret
from .ai_settings import (
    KEY_OK,
    KEY_UNBOUND,
    default_secret_store,
    key_block_message,
    key_server_status,
    load_ai_config,
    save_ai_config,
)
from .background import run_in_background
from .dialogs import message_box
from .i18n import localize

log = logging.getLogger(__name__)

SAVED_PLACEHOLDER = '•••• saved'


def _host_of(origin):
    return urlsplit(origin).netloc


def provider_labels():
    return {
        'openai': translate('PortadasPlugin.SettingsTab', 'OpenAI'),
        'anthropic': translate('PortadasPlugin.SettingsTab', 'Anthropic'),
        'gemini': translate('PortadasPlugin.SettingsTab', 'Google Gemini'),
        'openai_compatible': translate('PortadasPlugin.SettingsTab', 'OpenAI-compatible server'),
    }


class PortadasSettingsTab(SettingsTab):
    """
    :param secret_store: a ``SecretStore``; defaults to the per-user file store.
    :param test_connection: ``callable(config, api_key) -> str`` run by the Test connection button. It returns a
        message to show or raises. ``api_key`` is the key being typed, else the stored one, else ``None``. It runs on
        a worker thread (``lib/background.py``), so it may block up to the request timeout. The default asks the
        configured provider (``adapters.ai.test_connection``).
    """

    def __init__(self, parent, title, visible_title=None, icon_path=None, secret_store=None, test_connection=None):
        self._secret_store = secret_store
        self.test_connection = test_connection or ai_test_connection
        self._test_job = None
        self._key_saved = {}  # provider -> a key is stored
        self._pending_clear = set()  # providers whose key is deleted when the user presses OK
        super().__init__(parent, title, visible_title, icon_path)

    @property
    def secret_store(self):
        if self._secret_store is None:
            self._secret_store = default_secret_store()
        return self._secret_store

    # --- construction
    def setup_ui(self):
        self.setObjectName('PortadasTab')
        super().setup_ui()
        self.group_box = QtWidgets.QGroupBox(self.left_column)
        form = QtWidgets.QFormLayout(self.group_box)
        self.provider_combo = QtWidgets.QComboBox(self.group_box)
        self.provider_combo.setObjectName('provider_combo')
        for provider in PROVIDERS:
            self.provider_combo.addItem(provider_labels()[provider], provider)
        self.provider_label = QtWidgets.QLabel(self.group_box)
        form.addRow(self.provider_label, self.provider_combo)
        self.model_edit = QtWidgets.QLineEdit(self.group_box)
        self.model_edit.setObjectName('model_edit')
        self.model_label = QtWidgets.QLabel(self.group_box)
        form.addRow(self.model_label, self.model_edit)
        self.base_url_edit = QtWidgets.QLineEdit(self.group_box)
        self.base_url_edit.setObjectName('base_url_edit')
        self.base_url_label = QtWidgets.QLabel(self.group_box)
        form.addRow(self.base_url_label, self.base_url_edit)
        self.base_url_error_label = QtWidgets.QLabel(self.group_box)
        self.base_url_error_label.setStyleSheet('color: #b00020;')
        self.base_url_error_label.setWordWrap(True)
        self.base_url_error_label.hide()
        form.addRow('', self.base_url_error_label)
        self.timeout_spin = QtWidgets.QSpinBox(self.group_box)
        self.timeout_spin.setRange(MIN_TIMEOUT, MAX_TIMEOUT)
        self.timeout_label = QtWidgets.QLabel(self.group_box)
        form.addRow(self.timeout_label, self.timeout_spin)
        # API key: never displayed, only replaced or cleared.
        self.api_key_edit = QtWidgets.QLineEdit(self.group_box)
        self.api_key_edit.setObjectName('api_key_edit')
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_edit.setClearButtonEnabled(False)
        self.show_key_button = QtWidgets.QPushButton(self.group_box)
        self.show_key_button.setObjectName('show_key_button')
        self.show_key_button.setCheckable(True)
        self.save_key_button = QtWidgets.QPushButton(self.group_box)
        self.save_key_button.setObjectName('save_key_button')
        self.clear_key_button = QtWidgets.QPushButton(self.group_box)
        key_row = QtWidgets.QHBoxLayout()
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(self.show_key_button)
        key_row.addWidget(self.save_key_button)
        key_row.addWidget(self.clear_key_button)
        self.api_key_label = QtWidgets.QLabel(self.group_box)
        form.addRow(self.api_key_label, key_row)
        self.key_status_label = QtWidgets.QLabel(self.group_box)
        self.key_status_label.setTextFormat(QtCore.Qt.PlainText)  # it shows host names taken from the saved address
        form.addRow('', self.key_status_label)
        self.test_button = QtWidgets.QPushButton(self.group_box)
        self.test_result_label = QtWidgets.QLabel(self.group_box)
        self.test_result_label.setWordWrap(True)
        self.test_result_label.setTextFormat(QtCore.Qt.PlainText)  # provider messages are never rich text
        form.addRow(self.test_button, self.test_result_label)
        self.left_layout.addWidget(self.group_box)
        self.left_layout.addStretch()
        self.right_layout.addStretch()
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        self.base_url_edit.textChanged.connect(self.refresh_base_url)
        self.clear_key_button.clicked.connect(self.on_clear_key)
        self.show_key_button.toggled.connect(self.on_show_key_toggled)
        self.save_key_button.clicked.connect(self.on_save_key)
        self.test_button.clicked.connect(self.on_test_connection)
        log.info('Portadas settings tab created')

    def retranslate_ui(self):
        context = 'PortadasPlugin.SettingsTab'
        self.group_box.setTitle(translate(context, 'AI cover designs'))
        self.provider_label.setText(translate(context, 'Provider:'))
        self.model_label.setText(translate(context, 'Model:'))
        self.base_url_label.setText(translate(context, 'Server address:'))
        self.base_url_edit.setPlaceholderText(translate(context, 'https://host/v1 or http://localhost:11434/v1'))
        self.timeout_label.setText(translate(context, 'Request timeout:'))
        self.timeout_spin.setSuffix(translate(context, ' s'))
        self.api_key_label.setText(translate(context, 'API key:'))
        self.clear_key_button.setText(translate(context, 'Clear'))
        self.show_key_button.setText(translate(context, 'Show'))
        self.show_key_button.setToolTip(translate(context, 'Show or hide the key you are typing. A saved key is never '
                                                  'shown.'))
        self.save_key_button.setText(translate(context, 'Save key'))
        self.save_key_button.setToolTip(translate(context, 'Tests the typed key with the provider and saves it only if '
                                                  'the test succeeds.'))
        self.test_button.setText(translate(context, 'Test connection'))

    # --- state
    def selected_provider(self):
        return self.provider_combo.currentData()

    def on_provider_changed(self, _index=0):
        self.api_key_edit.clear()  # a key typed for one provider must never be saved for another
        self._cancel_test()  # a test still running would otherwise save its key under the new provider
        self._hide_key()
        self.refresh_provider_fields()

    def refresh_provider_fields(self):
        provider = self.selected_provider()
        self.model_edit.setPlaceholderText(DEFAULT_MODELS[provider])
        compatible = provider == COMPATIBLE
        self.base_url_edit.setEnabled(compatible)
        self.base_url_label.setEnabled(compatible)
        self.refresh_base_url()
        self.refresh_key_state()

    def refresh_base_url(self, _text=None):
        message = ''
        if self.selected_provider() == COMPATIBLE:
            try:
                validate_base_url(self.base_url_edit.text())
            except ValueError as error:
                message = localize(str(error))
        self.base_url_error_label.setText(message)
        self.base_url_error_label.setVisible(bool(message))
        self.refresh_key_state()

    def refresh_key_state(self):
        context = 'PortadasPlugin.SettingsTab'
        provider = self.selected_provider()
        saved = self._key_saved.get(provider, False)
        pending = provider in self._pending_clear
        self.api_key_edit.setPlaceholderText(
            SAVED_PLACEHOLDER if saved and not pending else translate(context, 'Paste your API key'))
        if pending:
            status = translate(context, 'The saved key will be removed when you press OK.')
        elif saved:
            status = self._saved_key_status(provider) or translate(
                context, 'An API key is saved. Type a new one to replace it.')
        else:
            status = translate(context, 'No API key saved.')
        self.key_status_label.setText(status)
        self.clear_key_button.setEnabled(saved and not pending)

    def _server_state(self, provider):
        """``(host, status, saved_host)`` of the compatible server in the field, or ``None`` when not applicable."""
        if provider != COMPATIBLE:
            return None
        text = self.base_url_edit.text()
        try:
            host = _host_of(origin_of(text))
            status, saved = key_server_status(self.secret_store, text)
        except ValueError:
            return None
        return host, status, _host_of(saved) if saved else None

    def _saved_key_status(self, provider):
        """The status line of a saved key for an OpenAI-compatible server: where it will go, or why it will not."""
        state = self._server_state(provider)
        if state is None:
            return ''
        context = 'PortadasPlugin.SettingsTab'
        host, status, saved_host = state
        if status == KEY_OK:
            return translate(context, 'An API key is saved. It is only sent to {host}. Type a new one to replace it.'
                             ).format(host=host)
        if status == KEY_UNBOUND:
            return translate(context, 'The saved key is not tied to a server. Enter the key again for {host}.'
                             ).format(host=host)
        return translate(context, 'The saved key was entered for {saved}. Enter the key again for {host}.').format(
            saved=saved_host, host=host)

    def on_clear_key(self):
        self._pending_clear.add(self.selected_provider())
        self.api_key_edit.clear()
        self._hide_key()
        self.refresh_key_state()

    def on_show_key_toggled(self, shown):
        """Reveal or mask the text being typed. A stored key is never in the field, so it is never revealed."""
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Normal if shown else QtWidgets.QLineEdit.Password)

    def _hide_key(self):
        self.show_key_button.setChecked(False)  # also resets the echo mode through the toggled signal
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)

    def current_config(self):
        return AiConfig(provider=self.selected_provider(), model=self.model_edit.text().strip(),
                        base_url=self.base_url_edit.text().strip(), timeout=self.timeout_spin.value())

    # --- SettingsTab API
    def load(self):
        config = load_ai_config(self.settings)
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(config.provider)))
        self.provider_combo.blockSignals(False)
        self.model_edit.setText(config.model)
        self.base_url_edit.blockSignals(True)
        self.base_url_edit.setText(config.base_url)
        self.base_url_edit.blockSignals(False)
        self.timeout_spin.setValue(config.timeout)
        self.api_key_edit.clear()
        self._hide_key()
        self._cancel_test()
        self.test_result_label.clear()
        self._pending_clear.clear()
        self._key_saved = {provider: bool(self._stored_key(provider)) for provider in PROVIDERS}
        self.refresh_provider_fields()

    def _stored_key(self, provider):
        try:
            return self.secret_store.get_api_key(provider)
        except (SecretStoreError, ValueError):
            return None

    def save(self):
        warnings = []
        config = self.current_config()
        previous = load_ai_config(self.settings)
        base_url = previous.base_url
        if config.base_url or config.provider == COMPATIBLE:
            try:
                base_url = validate_base_url(config.base_url)
            except ValueError as error:
                if config.provider == COMPATIBLE:
                    warnings.append(translate('PortadasPlugin.SettingsTab',
                                              'The server address was not saved: {error}').format(
                                                  error=localize(str(error))))
        save_ai_config(self.settings, AiConfig(config.provider, config.model, base_url, config.timeout))
        self._apply_key_removal(config.provider, warnings)
        if self.api_key_edit.text().strip():
            warnings.append(translate('PortadasPlugin.SettingsTab', 'The API key you typed was not saved. Press Save '
                                      'key to test it and save it.'))
        self.api_key_edit.clear()  # the typed key must not linger in the widget
        self._hide_key()
        self.refresh_key_state()
        if warnings:
            self.show_warning('\n'.join(warnings))

    def _apply_key_removal(self, provider, warnings):
        """OK deletes a key the user cleared. It never stores a typed key: that is what Save key is for."""
        if provider not in self._pending_clear:
            return
        try:
            self.secret_store.delete_api_key(provider)
            self._key_saved[provider] = False
            self._pending_clear.discard(provider)
        except SecretStoreError as error:
            warnings.append(redact(localize(str(error))))

    @staticmethod
    def _origin_for_save(provider, base_url):
        """The server a typed key is bound to: the address that was tested for an OpenAI-compatible server."""
        if provider != COMPATIBLE:
            return None
        try:
            return origin_of(base_url)
        except ValueError:
            return None  # no valid address: the key stays unverified and must be entered again

    def show_warning(self, text):
        message_box(self, QtWidgets.QMessageBox.Warning, translate('PortadasPlugin.SettingsTab', 'Covers settings'),
                    text)

    # --- test connection and save key
    def on_test_connection(self):
        provider = self.selected_provider()
        typed = self.api_key_edit.text().strip()
        api_key = typed or self._stored_key(provider)
        state = self._server_state(provider)
        self._cancel_test()
        if api_key and not typed and state is not None and state[1] != KEY_OK:
            # The stored key belongs to another server (an imported settings file may have changed the address).
            self.test_result_label.setText(key_block_message(state[1], state[0]))
            return
        self._start_probe(api_key, state)

    def on_save_key(self):
        """Test the typed key like Test connection does and store it only when the test succeeds."""
        provider = self.selected_provider()
        typed = self.api_key_edit.text().strip()
        self._cancel_test()
        if not typed:
            self.test_result_label.setText(translate('PortadasPlugin.SettingsTab', 'Type an API key first.'))
            return
        config = self.current_config()
        if provider == COMPATIBLE:
            try:
                validate_base_url(config.base_url)
            except ValueError as error:
                self.test_result_label.setText(localize(str(error)))
                return
        register_secret(typed)  # redact it from any provider message shown from now on
        origin = self._origin_for_save(provider, config.base_url)
        self._start_probe(typed, self._server_state(provider),
                          on_success=lambda message: self._store_tested_key(provider, typed, origin, message))

    def _store_tested_key(self, provider, key, origin, message):
        context = 'PortadasPlugin.SettingsTab'
        try:
            self.secret_store.set_api_key(provider, key, origin=origin)
        except ValueError:
            self.test_result_label.setText(translate(context, 'The API key was not saved: it is empty, too short or '
                                                     'long, or contains spaces or unsupported characters.'))
            return
        except SecretStoreError as error:
            self.test_result_label.setText(redact(localize(str(error))))
            return
        self._key_saved[provider] = True
        self._pending_clear.discard(provider)
        self.api_key_edit.clear()
        self._hide_key()
        self.refresh_key_state()
        self.test_result_label.setText(redact(localize(message)) + ' ' + translate(context, 'The API key was saved.'))

    def _start_probe(self, api_key, state, on_success=None):
        config, probe = self.current_config(), self.test_connection
        self._set_testing(True)
        if state is not None:
            self.test_result_label.setText(translate('PortadasPlugin.SettingsTab', 'Testing {host}...').format(
                host=state[0]))
        else:
            self.test_result_label.setText(translate('PortadasPlugin.SettingsTab', 'Testing...'))
        self._test_job = run_in_background(lambda: self._probe(probe, config, api_key),
                                           lambda message: self._test_done(message, on_success), self._test_failed)

    def _set_testing(self, testing):
        """Save key and Test connection are never available while a test is running."""
        self.test_button.setEnabled(not testing)
        self.save_key_button.setEnabled(not testing)

    @staticmethod
    def _probe(probe, config, api_key):
        """Runs on the worker thread. Any failure is shown to the user, so it becomes a presentable message."""
        try:
            return str(probe(config, api_key))
        except DesignError:
            raise
        except Exception as error:  # a provider error must be shown, never crash the settings dialog
            log.warning('The connection test failed (%s).', type(error).__name__)
            raise DesignError(redact(str(error)) or type(error).__name__) from None

    def _test_done(self, message, on_success=None):
        self._test_job = None
        self._set_testing(False)
        if on_success is not None:
            on_success(message)
            return
        self.test_result_label.setText(redact(localize(message)))

    def _test_failed(self, message):
        self._test_job = None
        self._set_testing(False)
        self.test_result_label.setText(redact(localize(message)))

    def _cancel_test(self):
        if self._test_job is not None:
            self._test_job.cancel()
            self._test_job = None
        self._set_testing(False)
