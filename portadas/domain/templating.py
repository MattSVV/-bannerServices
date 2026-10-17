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
Safe placeholder engine for cover templates.

A template is plain HTML with ``{{name}}`` placeholders. There is no expression language, no loops and no code
execution: substitution is a single regex pass, so text inserted for one placeholder is never scanned again.

Placeholders
    ``{{label}}``, ``{{title_main}}``, ``{{title_accent}}``, ``{{subtitle}}``, ``{{key_verse}}``, ``{{readings_label}}``
        user text, escaped with ``html.escape(quote=True)``; line breaks in the subtitle become ``<br>``.
    ``{{readings}}``
        ``<li>`` items built here (one per reading, escaped); put it inside a ``<ul>``.
    ``{{icon}}``
        an already sanitised SVG string, inserted verbatim (the caller is responsible for its safety).
    ``{{empty_fields}}``
        space-separated hook classes naming every empty field, e.g. ``no-subtitle no-readings``.

CSS hook convention
    Put ``class="{{empty_fields}}"`` on ``<body>`` and hide optional blocks with rules such as
    ``body.no-subtitle .subtitle { display: none; }``. The hook names are ``no-`` plus the placeholder name with
    underscores turned into hyphens (``no-title-accent``, ``no-key-verse``). Placing a placeholder directly inside
    its element, without whitespace, also lets ``:empty`` work as a fallback.
"""
import html
import re
from dataclasses import dataclass

from .cover import SLUG_PATTERN
from .errors import DomainError

CONTENT_PLACEHOLDERS = (
    'label', 'title_main', 'title_accent', 'subtitle', 'key_verse', 'readings_label', 'readings', 'icon')
TEXT_PLACEHOLDERS = ('label', 'title_main', 'title_accent', 'subtitle', 'key_verse', 'readings_label')
EMPTY_FIELDS = 'empty_fields'
ALL_PLACEHOLDERS = CONTENT_PLACEHOLDERS + (EMPTY_FIELDS,)
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080

_VALID = re.compile(r'\{\{\s*([A-Za-z0-9_]+)\s*\}\}')


class TemplateError(DomainError):
    """A template, manifest or placeholder rule was violated."""


def find_placeholders(template):
    """
    Return the distinct placeholder names used by ``template``, in order of first use.

    :raises TemplateError: on unknown names or malformed ``{{ ... }}`` syntax.
    """
    names = []
    for match in _VALID.finditer(template):
        name = match.group(1)
        before, after = template[match.start() - 1:match.start()], template[match.end():match.end() + 1]
        if before == '{' or after == '}':
            raise TemplateError('Malformed placeholder: use exactly two braces, like {{title_main}}.')
        if name not in ALL_PLACEHOLDERS:
            raise TemplateError(f'Unknown placeholder "{name}".')
        if name not in names:
            names.append(name)
    if '{{' in _VALID.sub('', template):
        raise TemplateError('Malformed placeholder: every "{{" must close as a known name followed by "}}".')
    return tuple(names)


def validate_placeholders(template, required=()):
    """Check the syntax and that every ``required`` placeholder is present. Returns the names used."""
    for name in required:
        if name not in ALL_PLACEHOLDERS:
            raise TemplateError(f'Unknown placeholder "{name}".')
    names = find_placeholders(template)
    for name in required:
        if name not in names:
            raise TemplateError(f'The template is missing the required placeholder "{name}".')
    return names


def _escape(value):
    return html.escape(value, quote=True)


def render(template, *, text=None, readings=(), icon_svg='', required=()):
    """
    Substitute every placeholder in a single pass and return the HTML.

    :param text: raw (unescaped) strings for ``label``, ``title_main``, ``title_accent``, ``subtitle`` and
        ``key_verse``; missing or blank values render empty.
    :param readings: display strings, rendered as ``<li>`` items.
    :param icon_svg: sanitised SVG markup for ``{{icon}}``.
    :param required: placeholders that must be non-empty (and are checked to exist in the template).
    """
    text = text or {}
    validate_placeholders(template, required)
    values = {name: (text.get(name) or '').strip() for name in TEXT_PLACEHOLDERS}
    values['readings'] = '\n'.join(f'<li>{_escape(item)}</li>' for item in readings)
    values['icon'] = icon_svg or ''
    for name in required:
        if not values[name]:
            raise TemplateError(f'The "{name}" is required.')
    rendered = {name: _escape(values[name]).replace('\n', '<br>') for name in TEXT_PLACEHOLDERS}
    rendered['readings'] = values['readings']
    rendered['icon'] = values['icon']
    rendered[EMPTY_FIELDS] = ' '.join(
        'no-' + name.replace('_', '-') for name in CONTENT_PLACEHOLDERS if not values[name])
    return _VALID.sub(lambda match: rendered[match.group(1)], template)


def render_cover(template, cover, icon_svg='', required=()):
    """Render ``template`` with the fields of a ``Cover`` and an already sanitised icon SVG."""
    text = {
        'label': cover.label, 'title_main': cover.title_main, 'title_accent': cover.title_accent,
        'subtitle': cover.subtitle, 'key_verse': str(cover.key_verse) if cover.key_verse else None,
        'readings_label': cover.readings_label}
    return render(template, text=text, readings=[str(reading) for reading in cover.readings],
                  icon_svg=icon_svg, required=required)


@dataclass(frozen=True)
class TemplateManifest:
    """Metadata of a template: identity, which placeholders it needs, and its fixed canvas."""
    id: str
    name: str
    description: str
    required: tuple
    optional: tuple
    width: int = CANVAS_WIDTH
    height: int = CANVAS_HEIGHT

    @classmethod
    def from_dict(cls, data):
        """Build and validate a manifest from parsed ``manifest.json`` data."""
        try:
            canvas = data['canvas']
            manifest = cls(id=data['id'], name=data['name'], description=data['description'],
                           required=_names(data['required'], 'required'), optional=_names(data['optional'], 'optional'),
                           width=canvas['width'], height=canvas['height'])
        except KeyError as error:
            raise TemplateError(f'The manifest is missing {error}.') from error
        except (TypeError, AttributeError) as error:
            raise TemplateError('The manifest has an invalid structure.') from error
        manifest._validate()
        return manifest

    def _validate(self):
        if not isinstance(self.id, str) or not SLUG_PATTERN.match(self.id):
            raise TemplateError('The template id may only use lowercase letters, digits and hyphens.')
        if not isinstance(self.name, str) or not self.name.strip():
            raise TemplateError('The template needs a name.')
        if not isinstance(self.description, str):
            raise TemplateError('The template description must be text.')
        if not self.required:
            raise TemplateError('A template must require at least one placeholder.')
        for name in self.required + self.optional:
            if name not in CONTENT_PLACEHOLDERS:
                raise TemplateError(f'Unknown placeholder "{name}".')
        if set(self.required) & set(self.optional):
            raise TemplateError('A placeholder cannot be both required and optional.')
        if (self.width, self.height) != (CANVAS_WIDTH, CANVAS_HEIGHT):
            raise TemplateError(f'The canvas must be {CANVAS_WIDTH}x{CANVAS_HEIGHT}.')


def _names(value, what):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TemplateError(f'The manifest "{what}" must be a list of placeholder names.')
    return tuple(value)
