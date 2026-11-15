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
``CoverRepository`` on the file system: ``<root>/<id>.json`` and a PNG per cover.

* every save writes the image under a NEW name, ``<id>.<version>.png`` (the version is a hex number that only grows),
  and records it in the JSON (``"image"``). OpenLP's display loads images by file URL and may serve a cached picture
  for a URL it has seen, so a re-rendered cover must never reuse a path. Covers saved before this layout have
  ``<id>.png`` and no ``"image"``; they keep working, and their next save migrates them;
* the newest ``KEPT_IMAGE_VERSIONS`` images stay (service items already in the order point at them); older ones are
  deleted after a save, and a delete that fails (on Windows a file in use) is logged and retried by the next save;
* the recorded name is validated against a strict pattern before it touches a path, like ids;
* ids are validated against a strict pattern before they touch a path, so ``..``, separators, NUL bytes and absolute
  paths cannot reach outside ``root``;
* writes go to a temporary file in the same folder and are moved into place with ``os.replace``; a failed save
  restores the previous state. Both temporary files are written before either is moved, and the JSON is moved last:
  it is the commit marker. A crash between the two moves leaves a new PNG next to the old JSON (the previous cover
  with its newer image) or, for a new cover, a PNG without JSON, which ``list`` and ``get`` do not see as a cover;
* stored files are opened without following symlinks, without blocking on named pipes and with a size limit;
* unreadable entries are skipped by ``list`` with a logged warning;
* messages in exceptions are safe to show to the user (no paths); details go to the log.
"""
import json
import logging
import os
import re
import stat
import time
import uuid
from pathlib import Path

from ..application.cover_mapper import CoverDataError, cover_from_json, cover_to_json
from ..application.ports import (
    KEPT_IMAGE_VERSIONS,
    CoverCorrupt,
    CoverNotFound,
    CoverRepository,
    ExportExists,
    InvalidCoverId,
    RepositoryError,
)
from ..domain.cover import Cover

log = logging.getLogger(__name__)

MAX_JSON_BYTES = 512 * 1024  # a cover may carry an AI template (up to 150 KB) and an inline icon (up to 140 KB)
MAX_PNG_BYTES = 50 * 1024 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
_VERSION = re.compile(r'[0-9a-f]{1,32}')
# Windows refuses these file names (with any extension), so they are never valid ids.
_RESERVED = {'con', 'prn', 'aux', 'nul'} | {f'com{n}' for n in range(1, 10)} | {f'lpt{n}' for n in range(1, 10)}
_NO_FOLLOW = getattr(os, 'O_NOFOLLOW', 0)
_NO_BLOCK = getattr(os, 'O_NONBLOCK', 0)  # opening a FIFO for reading would otherwise wait for a writer


def _version_of(cover_id, name):
    """The version number inside ``<cover_id>.<hex>.png``; ``None`` for any other name (ids never contain a dot)."""
    prefix = f'{cover_id}.'
    if not isinstance(name, str) or not name.startswith(prefix) or not name.endswith('.png'):
        return None
    token = name[len(prefix):-len('.png')]
    return int(token, 16) if _VERSION.fullmatch(token) else None


def _check_id(cover_id):
    if not isinstance(cover_id, str) or not _ID.fullmatch(cover_id) or cover_id.lower() in _RESERVED:
        raise InvalidCoverId('The cover id is not valid.')
    return cover_id


def _read_regular(path, limit):
    """Read a regular file without following a symlink, refusing files larger than ``limit``."""
    descriptor = os.open(path, os.O_RDONLY | _NO_FOLLOW | _NO_BLOCK)
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


def _reason(error):
    """The system's own wording for ``error`` (``No space left on device``), which never contains a path."""
    return getattr(error, 'strerror', None) or 'input/output error'


def _stage(path, data):
    """Write ``data`` to a new temporary file next to ``path`` and return the temporary path."""
    temp = path.parent / f'.{path.name}.{uuid.uuid4().hex[:8]}.tmp'
    try:
        with open(temp, 'xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return temp


def _atomic_write(path, data):
    """Write ``data`` to ``path`` through a temporary file in the same folder, then ``os.replace``."""
    temp = _stage(path, data)
    try:
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

    def _legacy_png(self, cover_id):
        return self.root / f'{_check_id(cover_id)}.png'

    def _png(self, cover_id):
        """The current image: the file name recorded in the JSON, or the legacy ``<id>.png`` without one."""
        name = self._recorded_image(cover_id)
        return self.root / name if name else self._legacy_png(cover_id)

    def _recorded_image(self, cover_id):
        """The validated image name stored in the JSON; ``None`` when absent, unreadable or not one we generate."""
        try:
            name = json.loads(_read_regular(self._json(cover_id), MAX_JSON_BYTES).decode('utf-8')).get('image')
        except (OSError, ValueError, AttributeError, RecursionError):
            return None
        if isinstance(name, str) and _version_of(cover_id, name) is not None:
            return name
        return None

    def _versions(self, cover_id):
        """``[(version, path)]`` of a cover's images, oldest first; the legacy ``<id>.png`` counts as version -1."""
        found = []
        if self.root.is_dir():
            for path in self.root.iterdir():
                version = _version_of(cover_id, path.name)
                if version is not None and _is_regular(path):
                    found.append((version, path))
        legacy = self._legacy_png(cover_id)
        if _is_regular(legacy):
            found.append((-1, legacy))
        return sorted(found)

    def save(self, cover, png_bytes):
        if not isinstance(cover, Cover):
            raise RepositoryError('Only covers can be saved.')
        json_path = self._json(cover.id)
        if not isinstance(png_bytes, bytes) or not png_bytes.startswith(PNG_SIGNATURE):
            raise RepositoryError('The image is not a PNG.')
        if len(png_bytes) > MAX_PNG_BYTES:
            raise RepositoryError('The image is too large.')
        staged = []
        png_path = None
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            newest = max((version for version, _ in self._versions(cover.id)), default=-1)
            version = max(time.time_ns(), newest + 1)  # only grows, even when the clock steps back
            png_path = self.root / f'{cover.id}.{version:x}.png'
            png_written = False
            try:
                staged.append(_stage(png_path, png_bytes))
                staged.append(_stage(json_path, cover_to_json(cover, image=png_path.name).encode('utf-8')))
                os.replace(staged[0], png_path)
                png_written = True
                os.replace(staged[1], json_path)  # the commit marker
            except BaseException:
                for temp in staged:
                    temp.unlink(missing_ok=True)
                if png_written:  # the previous image was never touched: only the new one has to go
                    self._discard(png_path)
                raise
        except OSError as error:
            log.warning('Could not save cover "%s": %s', cover.id, error)
            raise RepositoryError(f'The cover could not be saved: {_reason(error)}.') from error
        except UnicodeError:  # text that cannot be written as UTF-8 (a lone surrogate)
            log.warning('Could not save cover "%s": its text cannot be encoded.', cover.id)
            raise RepositoryError('The cover could not be saved: it contains a character that cannot be stored.'
                                  ) from None
        self._prune(cover.id, png_path)

    @staticmethod
    def _discard(path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            log.exception('Could not remove %s after a failed save', path.name)

    def _prune(self, cover_id, current):
        """Delete the images older than the newest few. A failure is logged and retried by the next save."""
        try:
            versions = self._versions(cover_id)
        except OSError as error:
            log.warning('Could not prune the old images of cover "%s": %s', cover_id, error)
            return
        for _, path in versions[:-KEPT_IMAGE_VERSIONS]:
            if path == current:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError as error:  # on Windows the file may still be open in the display
                log.warning('Could not prune the old image %s of cover "%s": %s', path.name, cover_id, error)

    def get(self, cover_id):
        json_path = self._json(cover_id)
        try:
            return self._load(cover_id)
        except FileNotFoundError:
            if not os.path.lexists(json_path):
                raise CoverNotFound(f'There is no cover "{cover_id}".') from None
            raise CoverCorrupt(f'The cover "{cover_id}" is incomplete.') from None
        except (OSError, CoverDataError, ValueError) as error:
            log.warning('Cover "%s" cannot be read: %s', cover_id, error)
            raise CoverCorrupt(f'The cover "{cover_id}" cannot be read: it is damaged or unreadable.') from error

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
            except Exception as error:  # noqa: BLE001 - one damaged entry must never hide every other cover
                log.warning('Skipping unreadable cover "%s": %s', path.stem, error)
        covers.sort(key=lambda cover: cover.id)  # stable: ties on the timestamp keep id order
        covers.sort(key=lambda cover: cover.created_at, reverse=True)
        return covers

    def delete(self, cover_id):
        json_path = self._json(cover_id)
        try:
            versions = self._versions(cover_id)
        except OSError as error:
            log.warning('Could not delete cover "%s": %s', cover_id, error)
            raise RepositoryError(f'The cover could not be deleted: {_reason(error)}.') from error
        if not os.path.lexists(json_path) and not versions:
            raise CoverNotFound(f'There is no cover "{cover_id}".')
        failure = None
        try:
            json_path.unlink(missing_ok=True)  # first, so a half-finished delete never lists a cover without image
        except OSError as error:
            failure = error
        else:
            for _, path in versions:  # every version, so none is left behind; the first failure is reported
                try:
                    path.unlink(missing_ok=True)
                except OSError as error:
                    failure = failure or error
        if failure is not None:
            log.warning('Could not delete cover "%s": %s', cover_id, failure)
            raise RepositoryError(f'The cover could not be deleted: {_reason(failure)}.') from failure

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
            log.warning('Could not export cover "%s": %s', cover_id, error)
            raise RepositoryError(f'The cover could not be exported: {_reason(error)}.') from error
