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
"""The Cover value object and its invariants."""
import dataclasses
from datetime import datetime, timezone

import pytest
from contrib.plugins.portadas.domain.cover import (
    DEFAULT_ICON,
    DEFAULT_LABEL,
    DEFAULT_TEMPLATE_ID,
    MAX_RAW_READINGS,
    MAX_READINGS,
    MAX_REFERENCE_CHARS,
    Cover,
    CoverError,
    IconKind,
    IconRef,
)
from contrib.plugins.portadas.domain.errors import DomainError
from contrib.plugins.portadas.domain.scripture import parse_reference

READINGS = [
    'Efesios 6:11-12', '2 Corintios 10:4-5', 'Salmos 139:23-24', 'Levítico 9:6', 'Romanos 8:1 · 12:1-2',
    'Proverbios 4:23 · 3:3-8', '1 Juan 1:9', 'Salmos 119:5, 9', 'Filipenses 4:6-7', 'Hebreos 11:6 · 10:24-25',
]


def reference_design_cover(**overrides):
    values = dict(
        title_main='Resistir', title_accent='al diablo',
        subtitle='Firmes en la batalla de la mente:\nun corazón guardado, limpio y lleno de fe',
        key_verse='Efesios 6:11', readings=READINGS)
    values.update(overrides)
    return Cover.from_raw(**values)


def test_reference_design_cover_round_trips_the_design_data():
    cover = reference_design_cover()

    assert cover.label == DEFAULT_LABEL == 'MENSAJE'
    assert cover.readings_label == 'LECTURAS'
    assert cover.title_main == 'Resistir'
    assert cover.title_accent == 'al diablo'
    assert str(cover.key_verse) == 'Efesios 6:11'
    assert [str(reading) for reading in cover.readings] == READINGS
    assert cover.icon == DEFAULT_ICON
    assert cover.template_id == DEFAULT_TEMPLATE_ID
    assert cover.subtitle.splitlines() == ['Firmes en la batalla de la mente:',
                                           'un corazón guardado, limpio y lleno de fe']


def test_defaults_generate_a_safe_id_and_an_aware_timestamp():
    first, second = reference_design_cover(), reference_design_cover()

    assert first.id != second.id
    assert first.created_at.tzinfo is not None


def test_cover_is_frozen():
    cover = reference_design_cover()

    with pytest.raises(dataclasses.FrozenInstanceError):
        cover.title_main = 'x'


def test_whitespace_is_collapsed_and_blank_optionals_become_none():
    cover = Cover.from_raw(title_main='  Resistir \t  hoy ', title_accent='  ', subtitle='', key_verse='  ',
                           readings='')

    assert cover.title_main == 'Resistir hoy'
    assert cover.title_accent is None
    assert cover.subtitle is None
    assert cover.key_verse is None
    assert cover.readings == ()


def test_readings_accept_multiline_text_and_skip_blank_lines():
    cover = Cover.from_raw(title_main='T', readings='Efesios 6:11\n\n  sal 23  \n')

    assert [str(reading) for reading in cover.readings] == ['Efesios 6:11', 'Salmos 23']


def test_subtitle_keeps_line_breaks_but_trims_each_line():
    cover = Cover.from_raw(title_main='T', subtitle='  one  \r\n\r\n two  ')

    assert cover.subtitle == 'one\ntwo'


def test_invalid_reading_error_names_the_line():
    with pytest.raises(CoverError, match='Reading 2'):
        Cover.from_raw(title_main='T', readings=['Efesios 6:11', 'Efesios 9:1'])


def test_invalid_key_verse_is_reported():
    with pytest.raises(CoverError, match='Key verse'):
        Cover.from_raw(title_main='T', key_verse='Nada 1:1')


@pytest.mark.parametrize('overrides, fragment', [
    (dict(title_main=''), 'title'),
    (dict(title_main='   '), 'title'),
    (dict(title_main='x' * 81), 'at most 80'),
    (dict(title_accent='x' * 81), 'at most 80'),
    (dict(subtitle='x' * 241), 'at most 240'),
    (dict(label='x' * 41), 'at most 40'),
    (dict(readings_label='x' * 41), 'at most 40'),
    (dict(title_main='bad\x00title'), 'control'),
    (dict(title_main='bad‮title'), 'control'),
    (dict(readings=['Salmos 23'] * (MAX_READINGS + 1)), 'at most'),
    (dict(template_id='../evil'), 'template'),
    (dict(id='../x'), 'id'),
    (dict(id=''), 'id'),
])
def test_invariants_raise_domain_errors(overrides, fragment):
    with pytest.raises(CoverError) as error:
        Cover.from_raw(**{'title_main': 'Resistir', **overrides})

    assert fragment in str(error.value)
    assert isinstance(error.value, DomainError)


def test_direct_construction_enforces_the_same_invariants():
    with pytest.raises(CoverError):
        Cover(id='abc', title_main='', created_at=datetime.now(timezone.utc))
    with pytest.raises(CoverError, match='timezone'):
        Cover(id='abc', title_main='T', created_at=datetime(2026, 1, 1))
    with pytest.raises(CoverError, match='readings'):
        Cover(id='abc', title_main='T', readings=('Salmos 23',), created_at=datetime.now(timezone.utc))


def test_label_blank_falls_back_to_default_in_from_raw():
    assert Cover.from_raw(title_main='T', label='  ').label == DEFAULT_LABEL
    assert Cover.from_raw(title_main='T', label='Serie').label == 'Serie'
    assert Cover.from_raw(title_main='T', readings_label='  ').readings_label == 'LECTURAS'
    assert Cover.from_raw(title_main='T', readings_label='Textos').readings_label == 'Textos'


@pytest.mark.parametrize('kind, value', [
    (IconKind.BUILTIN, 'shield-heart'),
    (IconKind.UPLOADED, 'logo-1.png'),
    (IconKind.INLINE_SVG, '<svg viewBox="0 0 1 1"></svg>'),
])
def test_valid_icons(kind, value):
    assert IconRef(kind, value).value == value


@pytest.mark.parametrize('kind, value', [
    (IconKind.BUILTIN, 'Shield Heart'),
    (IconKind.BUILTIN, ''),
    (IconKind.UPLOADED, '../etc/passwd'),
    (IconKind.UPLOADED, '.hidden'),
    (IconKind.UPLOADED, 'a/b.png'),
    (IconKind.INLINE_SVG, ''),
    (IconKind.INLINE_SVG, '<svg>' + 'x' * 30000 + '</svg>'),
])
def test_invalid_icons(kind, value):
    with pytest.raises(CoverError):
        IconRef(kind, value)


def test_icon_kind_must_be_an_icon_kind():
    with pytest.raises(CoverError):
        IconRef('builtin', 'cross')


def test_from_raw_accepts_icon_parts_and_reference_objects():
    cover = Cover.from_raw(title_main='T', icon=IconRef(IconKind.BUILTIN, 'cross'),
                           key_verse=parse_reference('Salmos 23'), readings=[parse_reference('Juan 3:16')])

    assert cover.icon.value == 'cross'
    assert str(cover.key_verse) == 'Salmos 23'
    assert str(cover.readings[0]) == 'Juan 3:16'


# T06b: raw reference input is capped before any parsing happens.

def test_raw_limits_match_the_documented_values():
    assert (MAX_REFERENCE_CHARS, MAX_RAW_READINGS) == (200, 30)


@pytest.mark.parametrize('field, value', [
    ('key_verse', 'Juan ' + ' ' * 300 + '3:16'),
    ('readings', ['Juan 3:16', 'Salmos ' + ' ' * 300 + '23']),
    ('readings', 'Juan 3:16\n' + 'Salmos' + ' ' * 300 + '23'),
])
def test_from_raw_rejects_overlong_references_with_a_domain_error(field, value):
    with pytest.raises(CoverError, match='at most 200 characters'):
        Cover.from_raw(title_main='T', **{field: value})


def test_from_raw_rejects_too_many_raw_readings_before_parsing():
    readings = ['not a reference at all'] * (MAX_RAW_READINGS + 1)

    with pytest.raises(CoverError, match='at most 30 readings'):
        Cover.from_raw(title_main='T', readings=readings)


def test_from_raw_rejects_a_flood_of_whitespace_quickly():
    import time
    started = time.perf_counter()
    with pytest.raises(DomainError):
        Cover.from_raw(title_main='T', key_verse='Juan ' + ' ' * 1_000_000 + 'x')

    assert time.perf_counter() - started < 0.5
