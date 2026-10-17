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
"""The ``Cover`` value object: the validated text and choices that make up one sermon cover."""
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .errors import DomainError
from .scripture import MAX_REFERENCE_CHARS, Reference, parse_reference

DEFAULT_LABEL = 'MENSAJE'
DEFAULT_READINGS_LABEL = 'LECTURAS'
DEFAULT_TEMPLATE_ID = 'noche-dorada'
MAX_LABEL = 40
MAX_TITLE = 80
MAX_SUBTITLE = 240
MAX_READINGS = 12
MAX_RAW_READINGS = 30  # raw reading lines accepted by ``from_raw`` before any parsing
MAX_CUSTOM_TEMPLATE = 150000  # an AI-designed template stored with the cover (sanitised HTML)
MAX_INLINE_SVG = 140000  # room for an uploaded PNG (96 KB, base64) wrapped in an SVG

_SAFE_ID = re.compile(r'\A[A-Za-z0-9_-]{1,64}\Z')
SLUG_PATTERN = re.compile(r'\A[a-z0-9][a-z0-9-]{0,39}\Z')
_UPLOAD_NAME = re.compile(r'\A[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')


class CoverError(DomainError):
    """A cover violates a domain rule."""


class IconKind(Enum):
    """Where an icon comes from."""
    BUILTIN = 'builtin'
    UPLOADED = 'uploaded'
    INLINE_SVG = 'inline_svg'


@dataclass(frozen=True)
class IconRef:
    """A reference to an icon: a bundled icon slug, an uploaded file name, or inline SVG markup."""
    kind: IconKind
    value: str

    def __post_init__(self):
        if not isinstance(self.kind, IconKind):
            raise CoverError('The icon kind is not valid.')
        if not isinstance(self.value, str) or not self.value:
            raise CoverError('The icon needs a value.')
        if self.kind is IconKind.BUILTIN and not SLUG_PATTERN.match(self.value):
            raise CoverError('The built-in icon name may only use lowercase letters, digits and hyphens.')
        if self.kind is IconKind.UPLOADED and not _UPLOAD_NAME.match(self.value):
            raise CoverError('The uploaded icon file name is not valid.')
        if self.kind is IconKind.INLINE_SVG and len(self.value) > MAX_INLINE_SVG:
            raise CoverError(f'The inline SVG icon must be at most {MAX_INLINE_SVG} characters.')


DEFAULT_ICON = IconRef(IconKind.BUILTIN, 'shield-heart')


def _clean_line(value, what, limit, required=False):
    """Collapse whitespace of a single-line field; return ``None`` when blank and optional."""
    text = ' '.join((value or '').split())
    _reject_invisible(text, what)
    if not text:
        if required:
            raise CoverError(f'The {what} is required.')
        return None
    if len(text) > limit:
        raise CoverError(f'The {what} must be at most {limit} characters.')
    return text


def _reject_invisible(text, what):
    for char in text:
        if char != '\n' and unicodedata.category(char) in ('Cc', 'Cf', 'Cs', 'Zl', 'Zp'):
            raise CoverError(f'The {what} contains a control or invisible formatting character.')


def _clean_multiline(value, what, limit):
    """Trim every line of a multi-line field and drop blank lines; return ``None`` when nothing is left."""
    raw = (value or '').replace('\r\n', '\n').replace('\r', '\n')
    _reject_invisible(raw, what)
    text = '\n'.join(line for line in (' '.join(line.split()) for line in raw.split('\n')) if line)
    if not text:
        return None
    if len(text) > limit:
        raise CoverError(f'The {what} must be at most {limit} characters.')
    return text


def _as_reference(value, what):
    if isinstance(value, Reference):
        return value
    if len(value) > MAX_REFERENCE_CHARS:
        raise CoverError(f'{what}: a reference must be at most {MAX_REFERENCE_CHARS} characters.')
    try:
        return parse_reference(value)
    except DomainError as error:
        raise CoverError(f'{what}: {error}') from error


@dataclass(frozen=True)
class Cover:
    """One sermon cover. Construction validates every invariant; use ``from_raw`` for untrusted user strings."""
    id: str
    title_main: str
    label: str = DEFAULT_LABEL
    title_accent: str = None
    subtitle: str = None
    key_verse: Reference = None
    readings: tuple = ()
    icon: IconRef = DEFAULT_ICON
    template_id: str = DEFAULT_TEMPLATE_ID
    readings_label: str = DEFAULT_READINGS_LABEL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    custom_template_html: str = None  # AI design; ``template_id`` then only anchors relative asset URLs

    def __post_init__(self):
        if not isinstance(self.id, str) or not _SAFE_ID.match(self.id):
            raise CoverError('The cover id may only use letters, digits, "-" and "_" (1 to 64 characters).')
        if not isinstance(self.template_id, str) or not SLUG_PATTERN.match(self.template_id):
            raise CoverError('The template id may only use lowercase letters, digits and hyphens.')
        self._check_text('label', self.label, MAX_LABEL, required=True)
        self._check_text('readings label', self.readings_label, MAX_LABEL, required=True)
        self._check_text('main title', self.title_main, MAX_TITLE, required=True)
        self._check_text('accent title', self.title_accent, MAX_TITLE)
        self._check_text('subtitle', self.subtitle, MAX_SUBTITLE, multiline=True)
        if self.key_verse is not None and not isinstance(self.key_verse, Reference):
            raise CoverError('The key verse must be a validated reference.')
        if not isinstance(self.readings, tuple) or not all(isinstance(item, Reference) for item in self.readings):
            raise CoverError('The readings must be a tuple of validated references.')
        if len(self.readings) > MAX_READINGS:
            raise CoverError(f'A cover can have at most {MAX_READINGS} readings.')
        if not isinstance(self.icon, IconRef):
            raise CoverError('The icon must be an IconRef.')
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise CoverError('The creation time needs a timezone.')
        if self.custom_template_html is not None and (
                not isinstance(self.custom_template_html, str) or not self.custom_template_html.strip()
                or len(self.custom_template_html) > MAX_CUSTOM_TEMPLATE):
            raise CoverError(f'The custom template must be text of at most {MAX_CUSTOM_TEMPLATE} characters.')

    @staticmethod
    def _check_text(what, value, limit, required=False, multiline=False):
        if value is None and not required:
            return
        if multiline:
            cleaned = _clean_multiline(value, what, limit)
        else:
            cleaned = _clean_line(value, what, limit, required)
        if cleaned != value:
            raise CoverError(f'The {what} must be trimmed and free of blank lines or repeated spaces.')

    @classmethod
    def from_raw(cls, title_main, *, label=None, readings_label=None, title_accent=None, subtitle=None,
                 key_verse=None, readings=(), icon=DEFAULT_ICON, template_id=DEFAULT_TEMPLATE_ID, id=None,
                 created_at=None, custom_template_html=None):
        """
        Build a cover from raw user input: whitespace is normalised, blank optionals become ``None`` and
        references are parsed. Raises ``CoverError`` with a presentable message on any rule violation.
        """
        if isinstance(readings, str):
            readings = readings.splitlines()
        lines = [(number, item) for number, item in enumerate(readings, 1)
                 if isinstance(item, Reference) or (item or '').strip()]
        if len(lines) > MAX_RAW_READINGS:
            raise CoverError(f'A cover can have at most {MAX_RAW_READINGS} readings.')
        verse = key_verse if isinstance(key_verse, Reference) or (key_verse or '').strip() else None
        return cls(
            id=uuid.uuid4().hex if id is None else id,
            title_main=_clean_line(title_main, 'main title', MAX_TITLE, required=True),
            label=_clean_line(label, 'label', MAX_LABEL) or DEFAULT_LABEL,
            readings_label=_clean_line(readings_label, 'readings label', MAX_LABEL) or DEFAULT_READINGS_LABEL,
            title_accent=_clean_line(title_accent, 'accent title', MAX_TITLE),
            subtitle=_clean_multiline(subtitle, 'subtitle', MAX_SUBTITLE),
            key_verse=None if verse is None else _as_reference(verse, 'Key verse'),
            readings=tuple(_as_reference(item, f'Reading {number}') for number, item in lines),
            icon=icon, template_id=template_id,
            created_at=datetime.now(timezone.utc) if created_at is None else created_at,
            custom_template_html=custom_template_html)
