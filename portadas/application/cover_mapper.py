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
"""Turns a ``Cover`` into JSON-compatible data and back. The domain stays free of any storage format."""
import json
from datetime import datetime

from ..domain.cover import Cover, IconKind, IconRef
from ..domain.errors import DomainError

SCHEMA_VERSION = 1


class CoverDataError(DomainError):
    """Stored cover data is malformed, incomplete or of an unsupported schema version."""


def cover_to_dict(cover):
    """Return the plain-data form of ``cover`` (strings, lists and dicts only), tagged with the schema version."""
    return {
        'schema_version': SCHEMA_VERSION,
        'id': cover.id,
        'template_id': cover.template_id,
        'label': cover.label,
        'title_main': cover.title_main,
        'title_accent': cover.title_accent,
        'subtitle': cover.subtitle,
        'key_verse': None if cover.key_verse is None else str(cover.key_verse),
        'readings': [str(reading) for reading in cover.readings],
        'readings_label': cover.readings_label,
        'icon': {'kind': cover.icon.kind.value, 'value': cover.icon.value},
        'created_at': cover.created_at.isoformat(),
    }


def cover_to_json(cover):
    """Return ``cover`` as readable UTF-8 JSON text."""
    return json.dumps(cover_to_dict(cover), ensure_ascii=False, indent=2) + '\n'


def cover_from_json(text):
    """Parse JSON text into a ``Cover``. :raises CoverDataError: on any problem."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError, TypeError) as error:
        raise CoverDataError('The cover file is not valid JSON.') from error
    return cover_from_dict(data)


def cover_from_dict(data):
    """Rebuild a ``Cover`` from ``cover_to_dict`` data. :raises CoverDataError: on any problem."""
    if not isinstance(data, dict):
        raise CoverDataError('The cover data must be a JSON object.')
    if data.get('schema_version') != SCHEMA_VERSION:
        raise CoverDataError(f'Unsupported cover schema version: {data.get("schema_version")!r}.')
    try:
        return Cover.from_raw(
            _text(data, 'title_main'), id=_text(data, 'id'), template_id=_text(data, 'template_id'),
            label=_text(data, 'label'), readings_label=_text(data, 'readings_label', required=False),
            title_accent=_text(data, 'title_accent', required=False), subtitle=_text(data, 'subtitle', required=False),
            key_verse=_text(data, 'key_verse', required=False), readings=_readings(data),
            icon=_icon(data), created_at=_timestamp(data))
    except CoverDataError:
        raise
    except DomainError as error:
        raise CoverDataError(f'The cover data breaks a rule: {error}') from error


def _text(data, key, required=True):
    if key not in data:
        if required:
            raise CoverDataError(f'The cover data is missing "{key}".')
        return None
    value = data[key]
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise CoverDataError(f'The cover field "{key}" must be text.')
    return value


def _readings(data):
    value = data.get('readings', [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CoverDataError('The cover readings must be a list of text.')
    return value


def _icon(data):
    value = data.get('icon')
    if not isinstance(value, dict) or not isinstance(value.get('kind'), str) or not isinstance(value.get('value'), str):
        raise CoverDataError('The cover icon must be an object with a kind and a value.')
    try:
        return IconRef(IconKind(value['kind']), value['value'])
    except ValueError as error:  # unknown kind (DomainError is a ValueError too, and keeps its own message)
        if isinstance(error, DomainError):
            raise
        raise CoverDataError(f'Unknown icon kind "{value["kind"]}".') from error


def _timestamp(data):
    value = data.get('created_at')
    if not isinstance(value, str):
        raise CoverDataError('The cover data is missing "created_at".')
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise CoverDataError('The cover creation time is not a valid timestamp.') from error
    if moment.tzinfo is None:
        raise CoverDataError('The cover creation time needs a timezone.')
    return moment
