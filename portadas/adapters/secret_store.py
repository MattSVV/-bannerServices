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
Per-user API key storage in a private file, outside OpenLP's settings.

Threat model (see ``docs/security.md``): the key must not end up in QSettings (so OpenLP's settings export and backups
never contain it), in logs, or in a file other local users can read. On POSIX the file is ``0600`` in a ``0700``
directory, written atomically, and refused when it is a symlink, owned by someone else or accessible to group or world.
That protects against other users of the machine, not against malware running as the same user: nothing stored for an
unattended program can. On Windows the content is additionally encrypted with DPAPI, bound to the signed-in user. The OS
keyring is not used because it is not in the dependency budget.
"""
import contextlib
import ctypes
import json
import logging
import os
import stat
import tempfile
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: the process lock below is all there is
    fcntl = None

from ..application.ai_config import KEY_PATTERN, PROVIDERS
from ..application.ports import SecretStore, SecretStoreError
from ..security.redaction import register_secret

log = logging.getLogger(__name__)

FILE_NAME = 'api-keys'
SCHEMA_VERSION = 1
LOCK_FILE_NAME = '.lock'
CORRUPT_SUFFIX = '.corrupt'
LOCK_WAIT_SECONDS = 5.0  # the longest a writer waits for another one
_PROCESS_LOCK = threading.RLock()  # serialises the read-modify-write cycles of this process
CRYPTPROTECT_UI_FORBIDDEN = 0x1  # never show a prompt: this runs inside a settings dialog


class _DataBlob(ctypes.Structure):
    """The Windows ``DATA_BLOB`` structure: a length and a pointer to bytes."""
    _fields_ = [('cbData', ctypes.c_uint32), ('pbData', ctypes.POINTER(ctypes.c_char))]


class DpapiCipher:
    """
    Encrypts bytes with the Windows Data Protection API (``CryptProtectData``), so only the same Windows user can
    decrypt them. ``crypt32`` and ``kernel32`` are injectable so the logic runs under test on any platform.
    """

    def __init__(self, crypt32=None, kernel32=None):
        if crypt32 is None:
            crypt32 = ctypes.windll.crypt32  # only exists on Windows
            kernel32 = ctypes.windll.kernel32
        self.crypt32 = crypt32
        self.kernel32 = kernel32

    def protect(self, data):
        return self._call(self.crypt32.CryptProtectData, data)

    def unprotect(self, data):
        return self._call(self.crypt32.CryptUnprotectData, data)

    def _call(self, function, data):
        buffer = ctypes.create_string_buffer(data, len(data))
        source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        result = _DataBlob()
        ok = function(ctypes.pointer(source), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN,
                      ctypes.pointer(result))
        if not ok:
            raise SecretStoreError('Windows could not protect or unprotect the stored API keys.')
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            self.kernel32.LocalFree(result.pbData)  # DPAPI allocated the output buffer; we must free it


class FileSecretStore(SecretStore):
    """
    Stores ``{"version": 1, "keys": {provider: key}}`` in ``<directory>/api-keys``.

    :param directory: the (private) directory; OpenLP's ``AppLocation.get_section_data_path('portadas') / 'secrets'``.
    :param cipher: encrypts the whole file when given; defaults to DPAPI on Windows and to none elsewhere.
    :param platform: ``os.name``, injectable for tests.
    """

    def __init__(self, directory, cipher=None, platform=None):
        self.directory = Path(directory)
        self.path = self.directory / FILE_NAME
        self.platform = platform or os.name
        self.cipher = cipher if cipher is not None else (DpapiCipher() if self.platform == 'nt' else None)

    # --- port
    def get_api_key(self, provider):
        _check_provider(provider)
        key = self._read().get(provider)
        if key:
            register_secret(key)
        return key or None

    def set_api_key(self, provider, key):
        _check_provider(provider)
        key = _check_key(key)
        with self._exclusive():
            keys = self._read_for_update()
            keys[provider] = key
            register_secret(key)
            self._write(keys)

    def delete_api_key(self, provider):
        _check_provider(provider)
        with self._exclusive():
            keys = self._read_for_update()
            if keys.pop(provider, None) is not None:
                self._write(keys)

    # --- one writer at a time
    @contextlib.contextmanager
    def _exclusive(self):
        """
        The read-modify-write cycle of a change: one thread, and on POSIX one process, at a time. Without it two
        writers read the same old file and the second rename silently drops the first one's key.
        """
        with _PROCESS_LOCK:
            self._prepare_directory()
            descriptor = None
            try:
                if fcntl is not None:
                    descriptor = os.open(self.directory / LOCK_FILE_NAME, os.O_RDWR | os.O_CREAT, 0o600)
                    self._flock(descriptor)
                yield
            except OSError:
                log.error('The API key file could not be locked.')
                raise SecretStoreError('The API key could not be saved. Check the permissions of the OpenLP data '
                                       'folder.') from None
            finally:
                if descriptor is not None:
                    os.close(descriptor)  # closing releases the flock

    @staticmethod
    def _flock(descriptor):
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SecretStoreError('The API keys are being changed by another OpenLP window. Try again in a '
                                           'moment.') from None
                time.sleep(0.01)

    # --- file handling
    def _read(self):
        """Return ``{provider: key}``; an absent, untrusted or unreadable file reads as empty (and is logged)."""
        try:
            info = os.lstat(self.path)
        except FileNotFoundError:
            return {}
        except OSError:
            log.warning('The API key file could not be inspected.')
            return {}
        problem = self._trust_problem(info)
        if problem:
            log.warning('The API key file was ignored: %s.', problem)
            return {}
        keys = self._parse()
        if keys is None:
            log.warning('The API key file could not be read and was ignored.')
            return {}
        return keys

    def _read_for_update(self):
        """
        The keys to modify. Like ``_read``, but an existing file that cannot be parsed or decrypted is first moved to
        ``api-keys.corrupt`` (one backup, the latest) instead of being overwritten without a trace.
        """
        try:
            info = os.lstat(self.path)
        except FileNotFoundError:
            return {}
        except OSError:
            raise SecretStoreError('The stored API keys could not be inspected.') from None
        if self._trust_problem(info):
            return self._read()  # untrusted files are ignored, and the write replaces them with a private one
        keys = self._parse()
        if keys is None:
            backup = self.path.with_name(FILE_NAME + CORRUPT_SUFFIX)
            try:
                os.replace(self.path, backup)
            except OSError:
                raise SecretStoreError('The stored API keys are unreadable and could not be backed up.') from None
            log.warning('The API key file could not be read; it was kept as %s and a new one is started.',
                        backup.name)
            return {}
        return keys

    def _parse(self):
        """The ``{provider: key}`` of a trusted file, or ``None`` when its content cannot be used."""
        try:
            raw = self.path.read_bytes()
            if self.cipher is not None:
                raw = self.cipher.unprotect(raw)
            data = json.loads(raw.decode('utf-8'))
            keys = data['keys']
            if data['version'] != SCHEMA_VERSION or not isinstance(keys, dict) or not all(
                    isinstance(value, str) for value in keys.values()):
                raise ValueError('unexpected structure')
        except (OSError, ValueError, KeyError, TypeError, SecretStoreError):
            return None
        return {name: value for name, value in keys.items() if name in PROVIDERS}

    def _trust_problem(self, info):
        if stat.S_ISLNK(info.st_mode):
            return 'it is a symbolic link'
        if not stat.S_ISREG(info.st_mode):
            return 'it is not a regular file'
        if self.platform == 'posix':
            if info.st_uid != os.geteuid():
                return 'it is not owned by the current user'
            if info.st_mode & 0o077:
                return 'it is group- or world-accessible (run chmod 600 on it)'
        return None

    def _write(self, keys):
        """Write atomically: a private temp file in the same directory, flushed to disk, then renamed over the old."""
        payload = json.dumps({'version': SCHEMA_VERSION, 'keys': keys}, sort_keys=True).encode('utf-8')
        temp_name = None
        try:
            self._prepare_directory()
            if self.cipher is not None:
                payload = self.cipher.protect(payload)
            # mkstemp creates the file with mode 0600 and O_EXCL, so it is never readable by others, not even briefly.
            descriptor, temp_name = tempfile.mkstemp(prefix='.api-keys-', dir=self.directory)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
            temp_name = None
        except OSError:
            log.error('The API key file could not be written.')
            raise SecretStoreError('The API key could not be saved. Check the permissions of the OpenLP data '
                                   'folder.') from None
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    def _prepare_directory(self):
        if self.directory.is_symlink():  # chmod would follow the link and change a directory that is not ours
            raise SecretStoreError('The folder for the API keys is a symbolic link, which is not accepted.')
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise SecretStoreError('The API key could not be saved. Check the permissions of the OpenLP data '
                                   'folder.') from None
        if self.platform == 'posix':
            os.chmod(self.directory, 0o700)


def _check_provider(provider):
    if provider not in PROVIDERS:
        raise ValueError('Unknown AI provider.')


def _check_key(key):
    key = (key or '').strip() if isinstance(key, str) else ''
    if not KEY_PATTERN.match(key):  # the same rule the adapters apply, so a saved key is always a usable one
        raise ValueError('The API key is empty, too short or long, or contains spaces or unsupported characters.')
    return key
