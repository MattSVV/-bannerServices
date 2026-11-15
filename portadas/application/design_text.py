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
Suggested cover text: when the AI may write it, and how what it wrote is checked.

The AI writes text only when the user left every free-text field empty and gave at least one Bible reference. What it
answers is untrusted: it is accepted only as plain text that passes the same limits as typed text, and it is never put
into the template.
"""
from dataclasses import dataclass

from ..domain.cover import Cover
from ..domain.errors import DomainError

# A cover needs a main title. In suggest mode the editor builds the cover to design with this stand-in; it is never
# sent to the AI, shown to the user or stored.
STAND_IN_TITLE = 'Title to be suggested'
_MARKUP = ('<', '>')
_FIELDS = ('title_main', 'title_accent', 'subtitle')


@dataclass(frozen=True)
class SuggestedText:
    """Validated, normalised suggested text. ``title_main`` is never empty."""
    title_main: str
    title_accent: str = None
    subtitle: str = None


class SuggestionRejected(ValueError):
    """The text the AI suggested cannot be used. The message is presentable and never echoes the text."""


def _blank(value):
    return not str(value or '').strip()


def wants_text_suggestion(title_main, title_accent, subtitle, key_verse, readings):
    """True when the AI should also suggest text: no free text at all, and a key verse or a reading is present."""
    if not all(_blank(value) for value in (title_main, title_accent, subtitle)):
        return False
    return not _blank(key_verse) or any(not _blank(item) for item in readings or ())


def check_suggested_text(raw):
    """
    The plain text of a reply's ``suggested_text`` object, or :raises SuggestionRejected: when it is unusable.

    Every field must be text without markup (``<`` or ``>``), control or invisible characters, and within the length
    limits of a typed field; the main title must not be empty.
    """
    if not isinstance(raw, dict):
        raise SuggestionRejected('The AI did not suggest any text.')
    values = {}
    for name in _FIELDS:
        value = raw.get(name)
        if value is not None and not isinstance(value, str):
            raise SuggestionRejected('The suggested text is not plain text.')
        if value is not None and any(mark in value for mark in _MARKUP):
            raise SuggestionRejected('The suggested text contains markup.')
        values[name] = value
    try:
        cover = Cover.from_raw(values['title_main'], title_accent=values['title_accent'], subtitle=values['subtitle'])
    except DomainError as error:
        raise SuggestionRejected(f'The suggested text is not valid: {error}') from None
    return SuggestedText(cover.title_main, cover.title_accent, cover.subtitle)
