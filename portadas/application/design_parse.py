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
"""Turns the text a model answered into a ``DesignProposal``. Tolerates code fences and chatter around the JSON."""
import json
import re

from .ports import DesignProposal, UnusableReply

MAX_NOTES = 1000
_FENCE = re.compile(r'```[A-Za-z0-9_-]*\s*\n?(.*?)```', re.DOTALL)


def parse_design_reply(text):
    """
    Parse ``{"html": ..., "icon_svg": ..., "notes": ...}`` out of ``text``.

    :raises UnusableReply: when no JSON object with a text ``html`` can be found. The message never echoes the reply.
    """
    if not isinstance(text, str) or not text.strip():
        raise UnusableReply('The AI answered with an empty reply.')
    data = _load_object(text)
    html = data.get('html', data.get('template_html'))
    if not isinstance(html, str) or not html.strip():
        raise UnusableReply('The AI reply is not valid JSON with an "html" template.')
    icon = data.get('icon_svg')
    if icon is not None and not isinstance(icon, str):
        raise UnusableReply('The AI reply is not valid JSON: "icon_svg" must be text or null.')
    notes = data.get('notes')
    return DesignProposal(html, icon if icon and icon.strip() else None,
                          notes.strip()[:MAX_NOTES] if isinstance(notes, str) else '')


def _load_object(text):
    candidates = [text.strip()]
    candidates += [match.group(1).strip() for match in _FENCE.finditer(text)]
    start, end = text.find('{'), text.rfind('}')
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (ValueError, RecursionError):
            continue
        if isinstance(data, dict):
            return data
    if text.count('{') > text.count('}'):
        raise UnusableReply('The AI reply was cut off before the JSON was complete; try again or choose a model with '
                          'a larger output limit.')
    raise UnusableReply('The AI reply is not valid JSON.')
