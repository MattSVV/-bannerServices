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
"""JSON (de)serialisation of covers, kept out of the domain."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from contrib.plugins.portadas.application.cover_mapper import (
    SCHEMA_VERSION,
    CoverDataError,
    cover_from_dict,
    cover_from_json,
    cover_to_dict,
    cover_to_json,
)
from contrib.plugins.portadas.domain.cover import Cover, IconKind, IconRef
from contrib.plugins.portadas.domain.errors import DomainError

FULL = dict(title_main='Resistir', title_accent='al diablo', label='MENSAJE', subtitle='uno\ndos',
            key_verse='Efesios 6:11', readings=['Efesios 6:11-12', 'Romanos 8:1 · 12:1-2'],
            icon=IconRef(IconKind.BUILTIN, 'heart'), template_id='minimal', readings_label='LECTURAS',
            id='abc123', created_at=datetime(2026, 10, 16, 12, 30, tzinfo=timezone(timedelta(hours=-5))))


def test_a_full_cover_round_trips():
    cover = Cover.from_raw(**FULL)

    assert cover_from_dict(cover_to_dict(cover)) == cover
    assert cover_from_json(cover_to_json(cover)) == cover


def test_a_minimal_cover_round_trips():
    cover = Cover.from_raw('Solo titulo', id='min1')

    assert cover_from_json(cover_to_json(cover)) == cover


@pytest.mark.parametrize('icon', [
    IconRef(IconKind.BUILTIN, 'dove'), IconRef(IconKind.UPLOADED, 'logo.png'),
    IconRef(IconKind.INLINE_SVG, '<svg xmlns="http://www.w3.org/2000/svg"></svg>')])
def test_every_icon_kind_round_trips(icon):
    cover = Cover.from_raw('Titulo', icon=icon, id='ic1')

    assert cover_from_json(cover_to_json(cover)).icon == icon


def test_the_dict_is_plain_json_with_a_schema_version():
    data = cover_to_dict(Cover.from_raw(**FULL))

    assert data['schema_version'] == SCHEMA_VERSION == 1
    assert data['key_verse'] == 'Efesios 6:11'
    assert data['readings'] == ['Efesios 6:11-12', 'Romanos 8:1 · 12:1-2']
    assert data['icon'] == {'kind': 'builtin', 'value': 'heart'}
    assert data['created_at'] == '2026-10-16T12:30:00-05:00'
    json.dumps(data)


def test_unicode_is_written_readably():
    assert 'Resistir · fe' in cover_to_json(Cover.from_raw('Resistir · fe', id='u1'))


def good():
    return cover_to_dict(Cover.from_raw(**FULL))


def test_an_unknown_schema_version_is_rejected():
    data = good()
    data['schema_version'] = 2

    with pytest.raises(CoverDataError, match='version'):
        cover_from_dict(data)


@pytest.mark.parametrize('key', ['schema_version', 'id', 'title_main', 'icon', 'template_id', 'created_at'])
def test_missing_required_keys_are_rejected(key):
    data = good()
    del data[key]

    with pytest.raises(CoverDataError):
        cover_from_dict(data)


@pytest.mark.parametrize('change', [
    {'title_main': 5}, {'title_main': ''}, {'id': '../x'}, {'readings': 'Efesios 6:11'}, {'readings': [1]},
    {'readings': ['not a reference']}, {'key_verse': 'nonsense 99:99'}, {'icon': 'heart'},
    {'icon': {'kind': 'magic', 'value': 'x'}}, {'icon': {'kind': 'builtin'}},
    {'icon': {'kind': 'builtin', 'value': '../x'}},
    {'created_at': 'yesterday'}, {'created_at': '2026-10-16T12:30:00'}, {'created_at': 5}, {'template_id': 'Bad Id'},
    {'subtitle': ['x']}, {'label': None}])
def test_invalid_values_are_rejected(change):
    data = good()
    data.update(change)

    with pytest.raises(CoverDataError):
        cover_from_dict(data)


@pytest.mark.parametrize('payload', [[], 'text', 3, None])
def test_a_non_object_is_rejected(payload):
    with pytest.raises(CoverDataError):
        cover_from_dict(payload)


@pytest.mark.parametrize('text', ['', '{', 'not json', '[1]', '{"schema_version": 1}'])
def test_broken_json_is_rejected(text):
    with pytest.raises(CoverDataError):
        cover_from_json(text)


def test_data_errors_are_domain_errors():
    assert issubclass(CoverDataError, DomainError)


def test_unknown_extra_keys_are_ignored():
    data = good()
    data['future_field'] = 1

    assert cover_from_dict(data) == Cover.from_raw(**FULL)
