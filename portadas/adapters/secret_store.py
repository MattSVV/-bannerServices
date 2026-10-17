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
import ctypes
import json
import logging
import os
import stat
import tempfile
from pathlib import Path

from ..application.ai_config import PROVIDERS
from ..application.ports import SecretStore, SecretStoreError
from ..security.redaction import register_secret

log = logging.getLogger(__name__)

FILE_NAME = 'api-keys'
SCHEMA_VERSION = 1
MAX_KEY_LENGTH = 512
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
        keys = self._read()
        keys[provider] = key
        register_secret(key)
        self._write(keys)

    def delete_api_key(self, provider):
        _check_provider(provider)
        keys = self._read()
        if keys.pop(provider, None) is not None:
            self._write(keys)

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
            log.warning('The API key file could not be read and was ignored.')
            return {}
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
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.platform == 'posix':
            os.chmod(self.directory, 0o700)


def _check_provider(provider):
    if provider not in PROVIDERS:
        raise ValueError('Unknown AI provider.')


def _check_key(key):
    key = (key or '').strip() if isinstance(key, str) else ''
    if not key or len(key) > MAX_KEY_LENGTH or any(char.isspace() or ord(char) < 0x20 for char in key):
        raise ValueError('The API key is empty or contains spaces or line breaks.')
    return key
