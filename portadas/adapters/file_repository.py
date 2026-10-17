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
``CoverRepository`` on the file system: ``<root>/<id>.png`` and ``<root>/<id>.json`` per cover.

* ids are validated against a strict pattern before they touch a path, so ``..``, separators, NUL bytes and absolute
  paths cannot reach outside ``root``;
* writes go to a temporary file in the same folder and are moved into place with ``os.replace``; a failed save
  restores the previous state;
* stored files are opened without following symlinks and with a size limit;
* unreadable entries are skipped by ``list`` with a logged warning.
"""
import logging
import os
import re
import stat
import uuid
from pathlib import Path

from ..application.cover_mapper import CoverDataError, cover_from_json, cover_to_json
from ..application.ports import (
    CoverCorrupt,
    CoverNotFound,
    CoverRepository,
    ExportExists,
    InvalidCoverId,
    RepositoryError,
)
from ..domain.cover import Cover

log = logging.getLogger(__name__)

MAX_JSON_BYTES = 256 * 1024
MAX_PNG_BYTES = 50 * 1024 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
# Windows refuses these file names (with any extension), so they are never valid ids.
_RESERVED = {'con', 'prn', 'aux', 'nul'} | {f'com{n}' for n in range(1, 10)} | {f'lpt{n}' for n in range(1, 10)}
_NO_FOLLOW = getattr(os, 'O_NOFOLLOW', 0)


def _check_id(cover_id):
    if not isinstance(cover_id, str) or not _ID.fullmatch(cover_id) or cover_id.lower() in _RESERVED:
        raise InvalidCoverId('The cover id is not valid.')
    return cover_id


def _read_regular(path, limit):
    """Read a regular file without following a symlink, refusing files larger than ``limit``."""
    descriptor = os.open(path, os.O_RDONLY | _NO_FOLLOW)
    with os.fdopen(descriptor, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError('not a regular file')
        if info.st_size > limit:
            raise OSError('file too large')
        return handle.read(limit + 1)


def _is_regular(path):
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def _atomic_write(path, data):
    """Write ``data`` to ``path`` through a temporary file in the same folder, then ``os.replace``."""
    temp = path.parent / f'.{path.name}.{uuid.uuid4().hex[:8]}.tmp'
    try:
        with open(temp, 'xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


class FileCoverRepository(CoverRepository):
    """Stores covers under ``root`` (OpenLP's ``AppLocation.get_section_data_path('portadas')`` in production)."""

    def __init__(self, root):
        self.root = Path(root)

    def _json(self, cover_id):
        return self.root / f'{_check_id(cover_id)}.json'

    def _png(self, cover_id):
        return self.root / f'{_check_id(cover_id)}.png'

    def save(self, cover, png_bytes):
        if not isinstance(cover, Cover):
            raise RepositoryError('Only covers can be saved.')
        json_path, png_path = self._json(cover.id), self._png(cover.id)
        if not isinstance(png_bytes, bytes) or not png_bytes.startswith(PNG_SIGNATURE):
            raise RepositoryError('The image is not a PNG.')
        if len(png_bytes) > MAX_PNG_BYTES:
            raise RepositoryError('The image is too large.')
        previous_png = None
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            existed = json_path.exists()
            if existed and _is_regular(png_path):
                previous_png = _read_regular(png_path, MAX_PNG_BYTES)
            png_written = False
            try:
                _atomic_write(png_path, png_bytes)
                png_written = True
                _atomic_write(json_path, cover_to_json(cover).encode('utf-8'))
            except BaseException:
                if png_written:
                    self._restore_png(png_path, previous_png)
                raise
        except OSError as error:
            raise RepositoryError(f'The cover could not be saved: {error.strerror or error}') from error

    @staticmethod
    def _restore_png(png_path, previous_png):
        try:
            if previous_png is None:
                png_path.unlink(missing_ok=True)
            else:
                _atomic_write(png_path, previous_png)
        except OSError:
            log.exception('Could not roll back %s after a failed save', png_path.name)

    def get(self, cover_id):
        json_path = self._json(cover_id)
        try:
            return self._load(cover_id)
        except FileNotFoundError:
            if not os.path.lexists(json_path):
                raise CoverNotFound(f'There is no cover "{cover_id}".') from None
            raise CoverCorrupt(f'The cover "{cover_id}" is incomplete.') from None
        except (OSError, CoverDataError, ValueError) as error:
            raise CoverCorrupt(f'The cover "{cover_id}" cannot be read: {error}') from error

    def _load(self, cover_id):
        raw = _read_regular(self._json(cover_id), MAX_JSON_BYTES)
        if len(raw) > MAX_JSON_BYTES:
            raise ValueError('file too large')
        cover = cover_from_json(raw.decode('utf-8'))
        if cover.id != cover_id:
            raise ValueError('the id inside the file does not match its name')
        if not _is_regular(self._png(cover_id)):
            raise FileNotFoundError('the image file is missing')
        return cover

    def list(self):
        if not self.root.is_dir():
            return []
        covers = []
        for path in sorted(self.root.iterdir()):
            if path.suffix != '.json' or not _ID.fullmatch(path.stem) or path.stem.lower() in _RESERVED:
                continue
            try:
                covers.append(self._load(path.stem))
            except (OSError, CoverDataError, ValueError) as error:
                log.warning('Skipping unreadable cover "%s": %s', path.stem, error)
        covers.sort(key=lambda cover: cover.id)  # stable: ties on the timestamp keep id order
        covers.sort(key=lambda cover: cover.created_at, reverse=True)
        return covers

    def delete(self, cover_id):
        json_path, png_path = self._json(cover_id), self._png(cover_id)
        if not os.path.lexists(json_path) and not os.path.lexists(png_path):
            raise CoverNotFound(f'There is no cover "{cover_id}".')
        try:
            json_path.unlink(missing_ok=True)  # first, so a half-finished delete never lists a cover without image
            png_path.unlink(missing_ok=True)
        except OSError as error:
            raise RepositoryError(f'The cover could not be deleted: {error.strerror or error}') from error

    def png_path(self, cover_id):
        path = self._png(cover_id)
        if not _is_regular(path):
            raise CoverNotFound(f'There is no image for cover "{cover_id}".')
        return path

    def export_png(self, cover_id, dest_path, overwrite=False):
        source = self.png_path(cover_id)
        dest = Path(dest_path)
        try:
            data = _read_regular(source, MAX_PNG_BYTES)
            if dest.is_dir():
                raise RepositoryError('The export destination is a folder.')
            if overwrite:
                _atomic_write(dest, data)
                return
            try:
                with open(dest, 'xb') as handle:  # exclusive create: refuses existing files and symlinks
                    handle.write(data)
            except FileExistsError:
                raise ExportExists(f'"{dest.name}" already exists.') from None
            except OSError:
                dest.unlink(missing_ok=True)
                raise
        except OSError as error:
            raise RepositoryError(f'The cover could not be exported: {error.strerror or error}') from error
