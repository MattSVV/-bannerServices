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
Spanish scripture references: parse, validate and format.

Accepted shapes (book names are accent/case-insensitive and may be abbreviated)::

    Efesios 6:11-12            verse range
    Salmos 119:5, 9            verse list (same chapter)
    Romanos 8:1 · 12:1-2       several chapter parts of one book, separated by "·" (";" and "•" also accepted)
    Salmos 23 / Salmos 23-24   whole chapter(s)

Cross-chapter ranges (``Juan 3:16-4:2``) are not supported. Verse numbers are only checked to be positive and
ordered: the catalog has chapter counts but not verse counts.
"""
import re
from dataclasses import dataclass

from .books import Book, find_book
from .errors import ScriptureError

PART_SEPARATOR = ' · '
VERSE_SEPARATOR = ', '
_MAX_NUMBER = 999
MAX_REFERENCE_CHARS = 200  # a longer reference is refused before any parsing

_DIGIT = re.compile(r'\d')
_ITEM = re.compile(r'^(?:(?P<chapter>\d+)\s*:\s*)?(?P<first>\d+)(?:\s*-\s*(?P<last>\d+))?$')
_PART_SPLIT = re.compile(r'[·;•]')


def _check_number(value, what):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ScriptureError(f'The {what} must be a positive number.')
    if value > _MAX_NUMBER:
        raise ScriptureError(f'The {what} {value} is too large.')


@dataclass(frozen=True)
class VerseRange:
    """Verses ``start``..``end`` inclusive (``start == end`` for a single verse)."""
    start: int
    end: int

    def __post_init__(self):
        _check_number(self.start, 'verse number')
        _check_number(self.end, 'verse number')
        if self.end < self.start:
            raise ScriptureError(f'Verse {self.end} comes before verse {self.start}; write the range in order.')

    def __str__(self):
        return str(self.start) if self.start == self.end else f'{self.start}-{self.end}'


@dataclass(frozen=True)
class ChapterPart:
    """One chapter with an optional list of verse ranges, or whole chapters ``chapter``..``chapter_end``."""
    chapter: int
    verses: tuple = ()
    chapter_end: int = None

    def __post_init__(self):
        _check_number(self.chapter, 'chapter number')
        if self.chapter_end is not None:
            _check_number(self.chapter_end, 'chapter number')
            if self.verses:
                raise ScriptureError('A chapter range cannot list verses.')
            if self.chapter_end < self.chapter:
                raise ScriptureError(
                    f'Chapter {self.chapter_end} comes before chapter {self.chapter}; write the range in order.')

    def __str__(self):
        if self.chapter_end is not None and self.chapter_end != self.chapter:
            return f'{self.chapter}-{self.chapter_end}'
        if not self.verses:
            return str(self.chapter)
        return f'{self.chapter}:{VERSE_SEPARATOR.join(str(verse) for verse in self.verses)}'

    @property
    def last_chapter(self):
        return self.chapter_end or self.chapter


@dataclass(frozen=True)
class Reference:
    """A validated reference: one book and at least one chapter part."""
    book: Book
    parts: tuple

    def __post_init__(self):
        if not self.parts:
            raise ScriptureError(f'Please give a chapter for {self.book.name}.')
        for part in self.parts:
            if part.last_chapter > self.book.chapters:
                raise ScriptureError(f'{self.book.name} has only {self.book.chapters} '
                                     f'chapter{"" if self.book.chapters == 1 else "s"}; '
                                     f'chapter {part.last_chapter} does not exist.')

    def __str__(self):
        return f'{self.book.name} {PART_SEPARATOR.join(str(part) for part in self.parts)}'


def _number(text):
    if len(text) > 4:
        raise ScriptureError(f'The number "{text}" is too large.')
    return int(text)


def _split_items(rest):
    """Yield the comma-separated items of each part, as ``(part_index, item_text)``."""
    for index, part in enumerate(_PART_SPLIT.split(rest)):
        items = [item.strip() for item in part.split(',')]
        if not any(items):
            raise ScriptureError('Invalid reference: empty part. Check the "·" and "," separators.')
        for item in items:
            yield index, item


def _parse_parts(rest, original):
    """Turn the text after the book name into ``ChapterPart`` objects."""
    parts = []
    current = None  # [chapter, verses] of the part being built
    last_index = -1
    for index, item in _split_items(rest):
        match = _ITEM.match(item)
        if not match:
            raise ScriptureError(f'Invalid reference "{original.strip()}": cannot read "{item}".')
        first, last = _number(match['first']), match['last'] and _number(match['last'])
        if match['chapter']:
            current = [_number(match['chapter']), [VerseRange(first, last or first)]]
            parts.append(current)
        elif current is not None and current[1] and index == last_index:
            current[1].append(VerseRange(first, last or first))
        else:
            current = [first, []]
            parts.append(current)
            if last:
                current.append(last)
        last_index = index
    return tuple(ChapterPart(chapter, tuple(verses), *rest_) for chapter, verses, *rest_ in parts)


def _is_letter(char):
    return char.isalnum() and not _DIGIT.match(char)


def _split_book(text):
    """
    Split ``text`` into ``(book, rest)`` in a single left-to-right pass (no backtracking, so linear in its length).

    The book is an optional leading digit, then a letter, then everything up to the first digit; ``rest`` starts at
    that digit (``None`` when there is none). Returns ``None`` when the text does not start with a book name.
    """
    text = text.lstrip()
    start = 0
    if text and _DIGIT.match(text[0]):
        start = 1
        while start < len(text) and text[start].isspace():
            start += 1
    if start >= len(text) or not _is_letter(text[start]):
        return None
    end = start + 1
    while end < len(text) and not _DIGIT.match(text[end]):
        end += 1
    return text[:end].rstrip(), text[end:] or None


def parse_reference(text):
    """
    Parse and validate a reference such as ``'ef 6:11-12'``.

    :raises ScriptureError: with a user-presentable message when the text is empty, malformed or out of range.
    """
    if not text or not text.strip():
        raise ScriptureError('The reference is empty.')
    if len(text) > MAX_REFERENCE_CHARS:
        raise ScriptureError(f'A reference must be at most {MAX_REFERENCE_CHARS} characters.')
    cleaned = text.replace('–', '-').replace('—', '-').replace('−', '-')
    parts = _split_book(cleaned)
    if parts is None:
        raise ScriptureError(f'Invalid reference "{text.strip()}": it must start with a book name.')
    book, rest = find_book(parts[0]), parts[1]
    if not rest:
        raise ScriptureError(f'Please give a chapter for {book.name}, for example "{book.name} 1:1".')
    return Reference(book, _parse_parts(rest, text))


def format_reference(text):
    """Return the canonical display form of a typed reference (see ``parse_reference``)."""
    return str(parse_reference(text))
