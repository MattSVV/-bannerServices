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
Spanish translation of the plugin, following OpenLP's language setting.

OpenLP loads translations from the ``.qm`` files in its own ``i18n`` folder, which a community plugin cannot extend,
and the Qt tools that compile ``.ts`` into ``.qm`` are not part of OpenLP's runtime. The plugin therefore ships its
Spanish texts as a plain Python catalog (``i18n_es``) and serves them through a ``QTranslator`` subclass. Qt asks every
installed translator for each ``translate()`` call, so the existing ``openlp.core.common.i18n.translate`` calls work
unchanged. English stays the source language: nothing is installed unless OpenLP's language is Spanish.

Error texts raised by the domain, application and adapter layers are plain English strings (those layers know nothing
about Qt). ``localize`` turns them into Spanish at the places where the UI shows them.
"""
import logging
import re

from PyQt5 import QtCore

from . import i18n_es

log = logging.getLogger(__name__)

_state = {'language': 'en', 'translator': None, 'patterns': None}
_MAX_DEPTH = 4


def catalog_language(code):
    """The catalog language (``'es'`` or ``'en'``) for an OpenLP language code such as ``es``, ``es_CL`` or ``[es]``."""
    primary = re.split(r'[_\-.@]', str(code or '').strip('[] ').lower())[0]
    return 'es' if primary == 'es' else 'en'


def set_language(language):
    """Choose the language ``localize`` answers in (``'es'`` or ``'en'``)."""
    _state['language'] = catalog_language(language)


def current_language():
    return _state['language']


class CatalogTranslator(QtCore.QTranslator):
    """Answers Qt's ``translate()`` lookups from the Spanish catalog; unknown texts fall through to the source text."""

    def translate(self, context, source_text, disambiguation=None, n=-1):
        # ``None`` (a null string) tells Qt this translator has no answer. An empty string would blank the widget.
        return i18n_es.UI.get(context, {}).get(source_text) or None

    def isEmpty(self):
        return False


def install_translator(language):
    """
    Install the Spanish translator when ``language`` is Spanish and return it; otherwise return ``None``.

    Calling it again replaces the translator installed earlier, so it is safe on every plugin start.
    """
    uninstall_translator()
    set_language(language)
    if current_language() != 'es':
        return None
    translator = CatalogTranslator()
    QtCore.QCoreApplication.installTranslator(translator)
    _state['translator'] = translator
    log.info('Portadas: Spanish translation installed.')
    return translator


def uninstall_translator():
    translator = _state['translator']
    if translator is not None:
        QtCore.QCoreApplication.removeTranslator(translator)
    _state['translator'] = None
    set_language('en')


def install_for_openlp():
    """Install the translator for the language OpenLP runs in (its ``core/language`` setting). Never raises."""
    try:
        from openlp.core.common.i18n import LanguageManager
        return install_translator(LanguageManager.get_language())
    except Exception as error:  # a language problem must never stop the plugin from loading
        log.warning('Portadas: could not read the OpenLP language (%s); using English.', type(error).__name__)
        return install_translator('en')


# --- error texts -----------------------------------------------------------------------------------------------------

def _compiled():
    """The message templates as ``(regex, spanish, takes_tail)``, most specific first."""
    if _state['patterns'] is None:
        patterns = []
        for text, spanish in i18n_es.MESSAGES.items():
            if '{}' not in text:
                continue
            body = '(.*?)'.join(re.escape(part) for part in text.split('{}'))
            tail = not text.endswith('{}') and text.endswith('.')
            patterns.append((len(text.replace('{}', '')), re.compile(f'{body}(?: (?P<tail>.+))?$' if tail else
                                                                      f'{body}$', re.DOTALL), spanish))
        patterns.sort(key=lambda item: -item[0])
        _state['patterns'] = [(regex, spanish) for _, regex, spanish in patterns]
    return _state['patterns']


def localize(text, _depth=0):
    """
    The Spanish form of one of the plugin's English error texts when OpenLP runs in Spanish, otherwise ``text``.

    A text that is not in the catalog (a provider's own words, a Spanish text already) is returned unchanged. Values
    interpolated into a message (counts, names) are kept, and an unrecognised sentence after a known one is kept too.
    """
    if _state['language'] != 'es' or not isinstance(text, str) or not text or _depth > _MAX_DEPTH:
        return text
    exact = i18n_es.MESSAGES.get(text)
    if exact is not None and '{}' not in text:
        return exact
    for regex, spanish in _compiled():
        match = regex.match(text)
        if match is None:
            continue
        values = [localize(value, _depth + 1) for value in match.groups()[:spanish_fields(regex)]]
        result = re.sub(r'%(\d)', lambda found, values=values: values[int(found.group(1)) - 1], spanish)
        tail = match.groupdict().get('tail')
        return f'{result} {localize(tail, _depth + 1)}' if tail else result
    return text


def spanish_fields(regex):
    """How many ``{}`` fields a compiled template has (its groups, without the optional tail)."""
    return regex.groups - (1 if 'tail' in regex.groupindex else 0)
