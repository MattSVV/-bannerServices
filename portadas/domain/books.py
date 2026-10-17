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
"""Canonical Spanish (Reina-Valera) names of the 66 Bible books, with chapter counts and lookup."""
import re
import unicodedata
from dataclasses import dataclass

from .errors import ScriptureError

# name, chapter count, abbreviations. For numbered books the abbreviations are written without the number.
_CATALOG = (
    ('Génesis', 50, 'Gn,Gen,Gé'),
    ('Éxodo', 40, 'Ex,Éx,Exo'),
    ('Levítico', 27, 'Lv,Lev'),
    ('Números', 36, 'Nm,Num,Nú'),
    ('Deuteronomio', 34, 'Dt,Deut'),
    ('Josué', 24, 'Jos'),
    ('Jueces', 21, 'Jue,Jc'),
    ('Rut', 4, 'Rt'),
    ('1 Samuel', 31, 'Sa,S,Sam'),
    ('2 Samuel', 24, 'Sa,S,Sam'),
    ('1 Reyes', 22, 'R,Re,Rey'),
    ('2 Reyes', 25, 'R,Re,Rey'),
    ('1 Crónicas', 29, 'Cr,Cro,Crón'),
    ('2 Crónicas', 36, 'Cr,Cro,Crón'),
    ('Esdras', 10, 'Esd'),
    ('Nehemías', 13, 'Neh,Ne'),
    ('Ester', 10, 'Est'),
    ('Job', 42, ''),
    ('Salmos', 150, 'Sal,Sl,Salmo,Ps'),
    ('Proverbios', 31, 'Pr,Prov,Pro'),
    ('Eclesiastés', 12, 'Ec,Ecl'),
    ('Cantares', 8, 'Cnt,Cant,Cantar,Cantar de los Cantares'),
    ('Isaías', 66, 'Is,Isa'),
    ('Jeremías', 52, 'Jer,Jr'),
    ('Lamentaciones', 5, 'Lm,Lam'),
    ('Ezequiel', 48, 'Ez,Eze'),
    ('Daniel', 12, 'Dn,Dan'),
    ('Oseas', 14, 'Os'),
    ('Joel', 3, 'Jl'),
    ('Amós', 9, 'Am'),
    ('Abdías', 1, 'Abd,Ab'),
    ('Jonás', 4, 'Jon'),
    ('Miqueas', 7, 'Miq,Mi'),
    ('Nahúm', 3, 'Nah,Na'),
    ('Habacuc', 3, 'Hab,Hb'),
    ('Sofonías', 3, 'Sof,Sf'),
    ('Hageo', 2, 'Hag,Hg'),
    ('Zacarías', 14, 'Zac,Zc'),
    ('Malaquías', 4, 'Mal,Ml'),
    ('Mateo', 28, 'Mt,Mat'),
    ('Marcos', 16, 'Mr,Mc,Mar'),
    ('Lucas', 24, 'Lc,Luc'),
    ('Juan', 21, 'Jn,Jua'),
    ('Hechos', 28, 'Hch,Hec'),
    ('Romanos', 16, 'Ro,Rom,Rm'),
    ('1 Corintios', 16, 'Co,Cor'),
    ('2 Corintios', 13, 'Co,Cor'),
    ('Gálatas', 6, 'Gá,Gal,Ga'),
    ('Efesios', 6, 'Ef,Efe'),
    ('Filipenses', 4, 'Fil,Flp,Filip'),
    ('Colosenses', 4, 'Col'),
    ('1 Tesalonicenses', 5, 'Ts,Tes'),
    ('2 Tesalonicenses', 3, 'Ts,Tes'),
    ('1 Timoteo', 6, 'Ti,Tim'),
    ('2 Timoteo', 4, 'Ti,Tim'),
    ('Tito', 3, 'Tit,Tt'),
    ('Filemón', 1, 'Flm,Filem,Fm'),
    ('Hebreos', 13, 'Heb,He'),
    ('Santiago', 5, 'Stg,Sant,Snt'),
    ('1 Pedro', 5, 'P,Pe,Ped'),
    ('2 Pedro', 3, 'P,Pe,Ped'),
    ('1 Juan', 5, 'Jn,Jua'),
    ('2 Juan', 1, 'Jn,Jua'),
    ('3 Juan', 1, 'Jn,Jua'),
    ('Judas', 1, 'Jud,Jd'),
    ('Apocalipsis', 22, 'Ap,Apoc'),
)

_ROMAN_PREFIX = re.compile(r'^(i{1,3})\s+(?=[a-z])')
_DIGIT_PREFIX = re.compile(r'^([123])\s*(?:\.?\s*[º°])?\s*\.?\s*(?=[a-z])')
_MIN_PREFIX_LENGTH = 3


class BookError(ScriptureError):
    """A book name could not be resolved."""


@dataclass(frozen=True)
class Book:
    """A Bible book: canonical display name and number of chapters."""
    name: str
    chapters: int


def _fold(text):
    """Lower-case, accent-free, single-spaced form used for matching."""
    decomposed = unicodedata.normalize('NFD', text)
    stripped = ''.join(char for char in decomposed if not unicodedata.combining(char))
    return ' '.join(stripped.casefold().replace('.', ' ').split())


def _normalise_key(text):
    """Fold ``text`` and turn leading ``I``/``1º``/``1`` ordinals into a plain ``1 `` prefix."""
    folded = _fold(text)
    roman = _ROMAN_PREFIX.match(folded)
    if roman:
        return f'{len(roman.group(1))} {folded[roman.end():]}'
    digit = _DIGIT_PREFIX.match(folded)
    if digit:
        return f'{digit.group(1)} {folded[digit.end():]}'
    return folded


def _build():
    books, aliases = [], {}
    for name, chapters, abbreviations in _CATALOG:
        book = Book(name, chapters)
        books.append(book)
        number = f'{name.split(" ")[0]} ' if name[0].isdigit() else ''
        for alias in [name.split(' ', 1)[-1] if number else name, *abbreviations.split(',')]:
            if alias:
                aliases[_normalise_key(number + alias)] = book
        aliases[_normalise_key(name)] = book
    return tuple(books), aliases


BOOKS, _ALIASES = _build()


def find_book(text):
    """
    Resolve a typed book name (any case, accents optional, common abbreviations) to its canonical ``Book``.

    :raises BookError: when the name is unknown or an abbreviation matches several books.
    """
    key = _normalise_key(text)
    if key in _ALIASES:
        return _ALIASES[key]
    if len(key) >= _MIN_PREFIX_LENGTH:
        matches = {book for alias, book in _ALIASES.items() if alias.startswith(key)}
        if len(matches) == 1:
            return matches.pop()
        if matches:
            names = ', '.join(sorted(book.name for book in matches))
            raise BookError(f'Ambiguous book name "{text.strip()}": it could be {names}.')
    elif key and any(alias.startswith(key) for alias in _ALIASES):
        raise BookError(f'Ambiguous book name "{text.strip()}": please type more letters.')
    raise BookError(f'Unknown book "{text.strip()}".')
