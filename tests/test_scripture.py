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
"""Spanish scripture reference parsing and formatting."""
import pytest
from contrib.plugins.portadas.domain.books import BOOKS, find_book
from contrib.plugins.portadas.domain.errors import DomainError
from contrib.plugins.portadas.domain.scripture import ScriptureError, format_reference, parse_reference

# Every reading and key verse of the reference design (Portada@2x.png), as the design prints them.
REFERENCE_DESIGN_STRINGS = [
    'Efesios 6:11-12',
    '2 Corintios 10:4-5',
    'Salmos 139:23-24',
    'Levítico 9:6',
    'Romanos 8:1 · 12:1-2',
    'Proverbios 4:23 · 3:3-8',
    '1 Juan 1:9',
    'Salmos 119:5, 9',
    'Filipenses 4:6-7',
    'Hebreos 11:6 · 10:24-25',
    'Efesios 6:11',
]


@pytest.mark.parametrize('text', REFERENCE_DESIGN_STRINGS)
def test_reference_design_strings_round_trip_exactly(text):
    assert str(parse_reference(text)) == text
    assert format_reference(text) == text


def test_catalog_has_66_books_and_1189_chapters():
    assert len(BOOKS) == 66
    assert sum(book.chapters for book in BOOKS) == 1189
    assert len({book.name for book in BOOKS}) == 66


def test_parse_exposes_structure():
    reference = parse_reference('Romanos 8:1 · 12:1-2')

    assert reference.book.name == 'Romanos'
    assert [part.chapter for part in reference.parts] == [8, 12]
    assert [(v.start, v.end) for v in reference.parts[1].verses] == [(1, 2)]


def test_verse_list_keeps_order_and_collapses_equal_ranges():
    assert format_reference('salmos 119:5,9') == 'Salmos 119:5, 9'
    assert format_reference('Salmos 119:5-5') == 'Salmos 119:5'


def test_whole_chapter_and_chapter_range():
    assert format_reference('Salmos 23') == 'Salmos 23'
    assert format_reference('Salmos 23-24') == 'Salmos 23-24'
    assert parse_reference('Salmos 23').parts[0].verses == ()


def test_new_chapter_with_comma_is_a_new_part():
    assert format_reference('Romanos 8:1, 12:1') == 'Romanos 8:1 · 12:1'


@pytest.mark.parametrize('separator', ['·', ' · ', ';', '•'])
def test_part_separators_are_normalised(separator):
    assert format_reference(f'Romanos 8:1{separator}12:1-2') == 'Romanos 8:1 · 12:1-2'


def test_en_dash_and_extra_spaces_are_accepted():
    assert format_reference('  Efesios   6 : 11 – 12 ') == 'Efesios 6:11-12'


@pytest.mark.parametrize('typed, canonical', [
    ('levitico 9:6', 'Levítico'),
    ('LEVÍTICO 9:6', 'Levítico'),
    ('Lv 9:6', 'Levítico'),
    ('Sal 23', 'Salmos'),
    ('Salmo 23', 'Salmos'),
    ('Ef 6:11', 'Efesios'),
    ('1 Co 13:4', '1 Corintios'),
    ('1Co 13:4', '1 Corintios'),
    ('2 cor 10:4', '2 Corintios'),
    ('I Juan 1:9', '1 Juan'),
    ('1º Juan 1:9', '1 Juan'),
    ('Ro 8:1', 'Romanos'),
    ('Fil 4:6', 'Filipenses'),
    ('Flm 1:4', 'Filemón'),
    ('Heb 11:6', 'Hebreos'),
    ('Pr 4:23', 'Proverbios'),
    ('Jn 3:16', 'Juan'),
    ('Jon 1:1', 'Jonás'),
    ('Gen 1:1', 'Génesis'),
    ('Ap 22:21', 'Apocalipsis'),
    ('Hch 2:1', 'Hechos'),
    ('Deuteronomio 6:4', 'Deuteronomio'),
    ('Apocalip 1:1', 'Apocalipsis'),
])
def test_book_names_are_accent_case_and_abbreviation_insensitive(typed, canonical):
    assert parse_reference(typed).book.name == canonical


def test_every_canonical_name_resolves_to_itself():
    for book in BOOKS:
        assert find_book(book.name) is book
        assert find_book(book.name.upper()) is book


@pytest.mark.parametrize('text, fragment', [
    ('', 'empty'),
    ('   ', 'empty'),
    ('Efesios', 'chapter'),
    ('Nolibro 1:1', 'Unknown book'),
    ('Jo 1:1', 'Ambiguous'),
    ('Efesios 7:1', 'has only 6 chapters'),
    ('Salmos 151', 'has only 150 chapters'),
    ('Efesios 0:1', 'positive'),
    ('Efesios 6:0', 'positive'),
    ('Efesios 6:12-11', 'before'),
    ('Salmos 24-23', 'before'),
    ('Efesios 6:1-', 'Invalid'),
    ('Efesios 6:a', 'Invalid'),
    ('Efesios 6:1-7:2', 'Invalid'),
    ('Salmos 23:1 ·', 'Invalid'),
    ('123 Juan 1:9', 'book name'),
    ('Judas 2:1', 'has only 1 chapter'),
])
def test_invalid_references_raise_presentable_errors(text, fragment):
    with pytest.raises(ScriptureError) as error:
        parse_reference(text)

    assert fragment.lower() in str(error.value).lower()
    assert isinstance(error.value, DomainError)


def test_unknown_book_error_is_ambiguity_aware():
    with pytest.raises(ScriptureError, match='Ambiguous'):
        find_book('Ma')


def test_too_many_digits_are_rejected():
    with pytest.raises(ScriptureError):
        parse_reference('Salmos 1:' + '9' * 12)


def test_references_are_hashable_and_equal_by_value():
    assert parse_reference('Efesios 6:11') == parse_reference('ef 6:11')
    assert len({parse_reference('Efesios 6:11'), parse_reference('ef 6:11')}) == 1
