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
"""Spanish translation: catalog completeness, message localization and a real widget in Spanish."""
import ast
import json
import re
from pathlib import Path

import pytest
from contrib.plugins.portadas.lib import i18n, i18n_es
from contrib.plugins.portadas.lib.editform import CoverEditForm
from contrib.plugins.portadas.lib.settingstab import PortadasSettingsTab
from PyQt5 import QtCore, QtWidgets

from .fakes import make_services

PACKAGE = Path(__file__).resolve().parent.parent / 'portadas'
UI_FILES = sorted((PACKAGE / 'lib').glob('*.py')) + [PACKAGE / 'portadasplugin.py']
MESSAGE_FILES = [path for path in sorted(PACKAGE.rglob('*.py'))
                 if path not in UI_FILES and 'security' not in path.parts]

# Technical or developer-facing texts that are never shown to a user as they are: they stay in English.
NOT_USER_FACING = {
    'not a regular file', 'file too large', 'unexpected structure', 'the id inside the file does not match its name',
    'the image file is missing', 'Unknown AI provider.', 'The size must be a (width, height) pair.',
    'No QApplication is running.', 'The cover HTML is missing or larger than 2 MB.',
    'The render was interrupted before it finished.', 'The template was rejected: {}',
}
NOT_USER_FACING_PREFIXES = ('The image may not have more than', 'Each side of the image must be')
INTERNAL_EXCEPTIONS = {'OSError', 'FileNotFoundError', 'CssSyntaxError', 'TemplateRejected'}
HELPER_FUNCTIONS = {'_status_message', '_too_slow', 'unusable'}


def _template(node):
    """The message of a string node with every interpolated value replaced by ``{}`` (None if not static)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return ''.join(part.value if isinstance(part, ast.Constant) else '{}' for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _template(node.left), _template(node.right)
        if left is not None:
            return left + (right if right is not None else '{}')
    return None


def _call_name(node):
    func = node.func
    return func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')


def ui_strings():
    """``{(context, source)}`` of every ``translate()`` call in the Qt layer; fails on one it cannot read."""
    found, problems = set(), []
    for path in UI_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        constants = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants.setdefault(target.id, set()).add(node.value.value)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _call_name(node) in ('translate', 't') and len(node.args) >= 2):
                continue
            context, source = node.args[0], node.args[1]
            if isinstance(context, ast.Name) and len(constants.get(context.id, ())) == 1:
                context = ast.Constant(next(iter(constants[context.id])))
            if (isinstance(context, ast.Constant) and isinstance(source, ast.Constant)
                    and isinstance(source.value, str)):
                found.add((context.value, source.value))
            else:
                problems.append(f'{path.name}:{node.lineno}')
    assert not problems, f'translate() calls whose context or text is not a literal: {problems}'
    return found


def user_messages():
    """The templates of the error texts the domain, application and adapters raise for the user to read."""
    found = set()
    for path in MESSAGE_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            texts = []
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                if _call_name(node.exc) not in INTERNAL_EXCEPTIONS:
                    texts.append(node.exc.args[0])
            elif isinstance(node, ast.Call) and _call_name(node) == 'unusable' and node.args:
                texts.append(node.args[0])
            elif isinstance(node, ast.FunctionDef) and node.name in HELPER_FUNCTIONS:
                inner = {id(part) for child in ast.walk(node) if isinstance(child, ast.JoinedStr)
                         for part in child.values}
                texts.extend(child for child in ast.walk(node) if id(child) not in inner and (
                    isinstance(child, ast.JoinedStr) or (isinstance(child, ast.Constant)
                                                         and isinstance(child.value, str) and len(child.value) > 12)))
            for text in texts:
                template = _template(text)
                if template is not None and template.strip('{} ') and template not in NOT_USER_FACING \
                        and not template.startswith(NOT_USER_FACING_PREFIXES):
                    found.add(template)
    return found


# --- the catalog is complete -------------------------------------------------------------------------------------

def test_every_user_facing_string_has_a_spanish_entry():
    missing = sorted(key for key in ui_strings() if not i18n_es.UI.get(key[0], {}).get(key[1], '').strip())

    assert not missing, f'Strings without a Spanish translation (add them to portadas/lib/i18n_es.py): {missing}'


def test_the_catalog_has_no_stale_ui_entries():
    used = ui_strings()
    stale = sorted((context, source) for context, entries in i18n_es.UI.items() for source in entries
                   if (context, source) not in used)

    assert not stale, f'Entries no code asks for any more: {stale}'


def test_every_error_message_has_a_spanish_entry():
    missing = sorted(message for message in user_messages() if not i18n_es.MESSAGES.get(message, '').strip())

    assert not missing, f'Messages without a Spanish translation (add them to portadas/lib/i18n_es.py): {missing}'


def test_message_entries_use_the_same_placeholders_as_their_source():
    wrong = [text for text, spanish in i18n_es.MESSAGES.items()
             if sorted(re.findall(r'%\d', spanish)) != [f'%{index}' for index in range(1, text.count('{}') + 1)]]

    assert not wrong, f'Spanish messages whose %1, %2... do not match the {{}} of the English text: {wrong}'


def test_ui_entries_keep_their_format_fields_and_markup():
    wrong = []
    for context, entries in i18n_es.UI.items():
        for source, spanish in entries.items():
            if sorted(re.findall(r'\{\w*\}', source)) != sorted(re.findall(r'\{\w*\}', spanish)) \
                    or sorted(re.findall(r'</?\w+ ?/?>', source)) != sorted(re.findall(r'</?\w+ ?/?>', spanish)):
                wrong.append((context, source))

    assert not wrong, f'Spanish texts that lost a {{field}} or an HTML tag: {wrong}'


def test_every_template_and_icon_has_a_spanish_description():
    files = (PACKAGE / 'templates').glob('*/manifest.json')
    manifests = [json.loads(path.read_text(encoding='utf-8')) for path in files]
    icons = [path.stem.replace('-', ' ') for path in (PACKAGE / 'assets' / 'icons').glob('*.svg')]

    missing = [text for text in [m['description'] for m in manifests] + icons
               if not i18n_es.MESSAGES.get(text, '').strip()]

    assert manifests and icons
    assert not missing, f'Template descriptions or icon names without a translation: {missing}'


def test_spanish_texts_are_neutral_not_regional():
    voseo = re.compile(r'\b(vos|tenés|podés|querés|hacé|elegí|escribí|probá|ingresá|pulsá|fijate)\b', re.IGNORECASE)
    every = [s for entries in i18n_es.UI.values() for s in entries.values()] + list(i18n_es.MESSAGES.values())

    assert not [s for s in every if voseo.search(s)]
    assert not [s for s in every if re.search(r'\b(computadora|celular|ordenador)\b', s, re.IGNORECASE)]


# --- localizing messages --------------------------------------------------------------------------------------------

@pytest.fixture
def spanish():
    i18n.set_language('es')
    yield
    i18n.set_language('en')


def test_messages_stay_in_english_by_default():
    assert i18n.localize('The reference is empty.') == 'The reference is empty.'


def test_a_known_message_is_translated(spanish):
    assert i18n.localize('The reference is empty.') == 'La referencia está vacía.'


def test_values_inside_a_message_are_kept_and_nouns_translated(spanish):
    text = i18n.localize('The main title must be at most 30 characters.')

    assert '30' in text
    assert 'título principal' in text
    assert 'main title' not in text


def test_a_message_with_a_provider_detail_keeps_the_detail(spanish):
    text = i18n.localize('OpenAI answered with an error (HTTP 418). The teapot refuses.')

    assert text.startswith('OpenAI')
    assert '418' in text
    assert text.endswith('The teapot refuses.')
    assert 'answered with an error' not in text


def test_an_unknown_message_is_returned_unchanged(spanish):
    assert i18n.localize('Something nobody planned for.') == 'Something nobody planned for.'
    assert i18n.localize('') == ''


def test_a_plain_spanish_text_passes_through(spanish):
    assert i18n.localize('La referencia está vacía.') == 'La referencia está vacía.'


@pytest.mark.parametrize('language,expected', [('es', 'es'), ('es_CL', 'es'), ('ES', 'es'), ('en', 'en'), ('de', 'en'),
                                               ('', 'en'), ('[es]', 'es'), (None, 'en')])
def test_the_language_follows_openlp_codes(language, expected):
    assert i18n.catalog_language(language) == expected


# --- a real widget -------------------------------------------------------------------------------------------------

@pytest.fixture
def installed(qapp):
    """Install the Spanish translator the way the plugin does and remove it afterwards."""
    translator = i18n.install_translator('es')
    assert translator is not None
    yield translator
    QtCore.QCoreApplication.removeTranslator(translator)
    i18n.set_language('en')


def test_nothing_is_installed_for_english(qapp):
    assert i18n.install_translator('en') is None
    assert i18n.install_translator('de_DE') is None


def test_the_settings_tab_is_in_spanish(qtbot, openlp_env, installed):
    tab = PortadasSettingsTab(None, 'portadas', 'Covers', None)
    qtbot.addWidget(tab)

    assert tab.provider_label.text() == 'Proveedor:'
    assert tab.test_button.text() == 'Probar conexión'
    assert tab.group_box.title() == 'Diseños de portada con IA'
    assert tab.key_status_label.text() == 'No hay ninguna clave de API guardada.'
    assert tab.provider_combo.itemText(tab.provider_combo.findData('openai_compatible')) \
        == 'Servidor compatible con OpenAI'


def test_the_editor_is_in_spanish_including_template_tooltips(qtbot, openlp_env, installed, tmp_path):
    form = CoverEditForm(None, make_services(tmp_path), thumbnails=False)
    qtbot.addWidget(form)

    assert form.windowTitle() == 'Portada'
    assert form.form_labels['key_verse'].text() == 'Versículo clave:'
    assert form.form_labels['readings'].text() == 'Lecturas (una por línea):'
    assert form.save_button.text() == 'Guardar'
    assert form.design_button.text() == 'Diseñar con IA'
    tooltips = [form.template_list.item(row).toolTip() for row in range(form.template_list.count())]
    assert tooltips and not any('background' in tip for tip in tooltips)
    assert form.icon_list.item(0).toolTip() != ''


def test_the_editor_validation_text_is_in_spanish(qtbot, openlp_env, installed, tmp_path):
    form = CoverEditForm(None, make_services(tmp_path), thumbnails=False)
    qtbot.addWidget(form)

    form.key_verse_edit.setText('Nada 1:1')

    assert form.key_verse_error.text() == 'Libro desconocido "Nada".'


def test_the_editor_stays_in_english_without_the_translator(qtbot, openlp_env, tmp_path):
    form = CoverEditForm(None, make_services(tmp_path), thumbnails=False)
    qtbot.addWidget(form)

    assert form.form_labels['key_verse'].text() == 'Key verse:'
    assert form.key_verse_error.text() == ''


def test_plugin_strings_are_in_spanish(qapp, installed):
    from contrib.plugins.portadas.portadasplugin import PortadasPlugin
    about = PortadasPlugin.about()

    assert 'Complemento Portadas' in about
    assert QtWidgets.QApplication.translate('PortadasPlugin', 'Covers', 'name plural') == 'Portadas'


@pytest.mark.parametrize('setting,system,spanish', [
    ('es', 'en_US', True), ('en', 'es_ES', False), ('de', 'es_ES', False),
    # A bracketed value is OpenLP's "Automatic" choice: the system language decides, not the code inside.
    ('[es]', 'es_ES', True), ('[es]', 'en_US', False), ('[en]', 'es_ES', True),
])
def test_the_plugin_follows_the_openlp_language_setting(qapp, openlp_env, monkeypatch, setting, system, spanish):
    monkeypatch.setattr(QtCore.QLocale, 'system', staticmethod(lambda: QtCore.QLocale(system)))
    openlp_env.setValue('core/language', setting)
    try:
        translator = i18n.install_for_openlp()

        assert (translator is not None) is spanish
        assert (QtCore.QCoreApplication.translate('PortadasPlugin', 'Cover') == 'Portada') is spanish
    finally:
        i18n.uninstall_translator()
