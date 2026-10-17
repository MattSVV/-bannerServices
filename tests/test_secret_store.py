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
"""The file based secret store: round trip, permissions, refused files, atomic writes and the DPAPI path."""
import ctypes
import json
import logging
import os
import stat

import pytest
from contrib.plugins.portadas.adapters import secret_store as module
from contrib.plugins.portadas.adapters.secret_store import DpapiCipher, FileSecretStore
from contrib.plugins.portadas.application.ports import SecretStoreError
from contrib.plugins.portadas.security import redaction

FAKE = 'sk-FAKE-test-key-0123456789abcdef'
posix_only = pytest.mark.skipif(os.name != 'posix', reason='POSIX permission bits')


@pytest.fixture(autouse=True)
def clean_secrets():
    redaction.clear_secrets()
    yield
    redaction.clear_secrets()


@pytest.fixture
def store(tmp_path):
    return FileSecretStore(tmp_path / 'secrets')


def test_round_trip_per_provider(store):
    assert store.get_api_key('openai') is None

    store.set_api_key('openai', FAKE)
    store.set_api_key('gemini', 'AIzaFAKE-gemini-key-0123456789')

    assert store.get_api_key('openai') == FAKE
    assert store.get_api_key('gemini') == 'AIzaFAKE-gemini-key-0123456789'
    assert store.get_api_key('anthropic') is None


def test_delete_removes_only_that_provider(store):
    store.set_api_key('openai', FAKE)
    store.set_api_key('gemini', 'gem-key-123456')

    store.delete_api_key('openai')
    store.delete_api_key('anthropic')  # deleting a missing key is not an error

    assert store.get_api_key('openai') is None
    assert store.get_api_key('gemini') == 'gem-key-123456'


def test_a_second_store_object_reads_what_the_first_wrote(tmp_path):
    FileSecretStore(tmp_path / 's').set_api_key('openai', FAKE)

    assert FileSecretStore(tmp_path / 's').get_api_key('openai') == FAKE


@pytest.mark.parametrize('provider', ['', 'nope', '../x', 'OpenAI'])
def test_unknown_providers_are_refused(store, provider):
    with pytest.raises(ValueError):
        store.set_api_key(provider, FAKE)
    with pytest.raises(ValueError):
        store.get_api_key(provider)


@pytest.mark.parametrize('key', ['', '   ', 'two words', 'new\nline', 'x' * 600, 'tab\tkey'])
def test_unusable_keys_are_refused(store, key):
    with pytest.raises(ValueError):
        store.set_api_key('openai', key)


def test_keys_are_stripped(store):
    store.set_api_key('openai', f'  {FAKE}\n')

    assert store.get_api_key('openai') == FAKE


@posix_only
def test_directory_is_0700_and_file_is_0600(store):
    store.set_api_key('openai', FAKE)

    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


@posix_only
def test_a_loose_directory_is_tightened(tmp_path):
    directory = tmp_path / 'secrets'
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)

    FileSecretStore(directory).set_api_key('openai', FAKE)

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


@posix_only
@pytest.mark.parametrize('mode', [0o644, 0o640, 0o604, 0o660, 0o666])
def test_group_or_world_accessible_files_are_refused(store, caplog, mode):
    store.set_api_key('openai', FAKE)
    os.chmod(store.path, mode)

    with caplog.at_level(logging.WARNING):
        assert store.get_api_key('openai') is None

    assert 'group- or world-accessible' in caplog.text
    assert FAKE not in caplog.text


@posix_only
def test_a_symlinked_secrets_file_is_refused(store, tmp_path, caplog):
    store.set_api_key('openai', FAKE)
    real = tmp_path / 'elsewhere'
    os.replace(store.path, real)
    os.chmod(real, 0o600)
    store.path.symlink_to(real)

    with caplog.at_level(logging.WARNING):
        assert store.get_api_key('openai') is None

    assert 'symbolic link' in caplog.text
    assert FAKE not in caplog.text


@posix_only
def test_a_file_owned_by_someone_else_is_refused(store, monkeypatch, caplog):
    store.set_api_key('openai', FAKE)
    monkeypatch.setattr(os, 'geteuid', lambda: os.stat(store.path).st_uid + 1)

    with caplog.at_level(logging.WARNING):
        assert store.get_api_key('openai') is None

    assert 'not owned' in caplog.text


@posix_only
def test_writing_over_an_insecure_file_replaces_it_with_a_private_one(store):
    store.set_api_key('openai', FAKE)
    os.chmod(store.path, 0o666)

    store.set_api_key('openai', FAKE)

    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert store.get_api_key('openai') == FAKE


@pytest.mark.parametrize('content', [b'not json', b'[]', b'{"version": 99, "keys": {}}', b'{"version": 1, "keys": []}',
                                     b'{"version": 1, "keys": {"openai": 5}}', b''])
def test_a_corrupt_file_reads_as_no_key(store, caplog, content):
    store.set_api_key('openai', FAKE)
    store.path.write_bytes(content)
    os.chmod(store.path, 0o600)

    with caplog.at_level(logging.WARNING):
        assert store.get_api_key('openai') is None

    assert FAKE not in caplog.text


def test_the_write_is_atomic(store, monkeypatch):
    store.set_api_key('openai', FAKE)

    def failing_replace(src, dst):
        raise OSError('disk full')
    monkeypatch.setattr(module.os, 'replace', failing_replace)

    with pytest.raises(SecretStoreError) as error:
        store.set_api_key('openai', 'sk-NEW-key-0123456789abcdef')

    assert FAKE not in str(error.value) and 'NEW' not in str(error.value)
    monkeypatch.undo()
    assert store.get_api_key('openai') == FAKE  # the old content is intact
    assert sorted(item.name for item in store.directory.iterdir()) == ['.lock', store.path.name]  # no temp file left


def test_the_file_is_not_world_readable_even_while_it_is_being_written(store, monkeypatch):
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(stat.S_IMODE(os.stat(src).st_mode))
        real_replace(src, dst)
    monkeypatch.setattr(module.os, 'replace', spy)

    store.set_api_key('openai', FAKE)

    if os.name == 'posix':
        assert seen == [0o600]


def test_stored_and_read_keys_are_registered_for_log_redaction(store):
    store.set_api_key('openai', FAKE)
    assert redaction.redact(f'leak {FAKE}') == 'leak [redacted]'

    redaction.clear_secrets()
    assert store.get_api_key('openai') == FAKE
    assert redaction.redact(f'leak {FAKE}') == 'leak [redacted]'


def test_the_plain_file_is_json_and_keeps_keys_out_of_other_places(store, tmp_path):
    store.set_api_key('openai', FAKE)

    assert json.loads(store.path.read_text(encoding='utf-8')) == {'version': 1, 'keys': {'openai': FAKE}}
    assert [path for path in tmp_path.rglob('*') if path.is_file() and FAKE in path.read_text(errors='ignore')] \
        == [store.path]


# --- Windows DPAPI path, exercised with a fake crypt API -----------------------------------------------------------

class FakeCrypt32:
    """Stands in for ``crypt32``: 'encrypts' by XOR so the test can tell the plaintext from the stored bytes."""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.buffers = []

    def _transform(self, name, data_in, data_out, flags):
        self.calls.append((name, flags))
        if self.fail:
            return 0
        blob = data_in.contents
        raw = bytes(b ^ 0x5A for b in ctypes.string_at(blob.pbData, blob.cbData))
        buffer = ctypes.create_string_buffer(raw, len(raw))
        self.buffers.append(buffer)
        out = data_out.contents
        out.cbData = len(raw)
        out.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        return 1

    def CryptProtectData(self, data_in, descr, entropy, reserved, prompt, flags, data_out):
        return self._transform('protect', data_in, data_out, flags)

    def CryptUnprotectData(self, data_in, descr, entropy, reserved, prompt, flags, data_out):
        return self._transform('unprotect', data_in, data_out, flags)


class FakeKernel32:
    def __init__(self):
        self.freed = 0

    def LocalFree(self, pointer):
        self.freed += 1
        return None


def test_dpapi_cipher_round_trip_with_a_mocked_crypt_api():
    crypt, kernel = FakeCrypt32(), FakeKernel32()
    cipher = DpapiCipher(crypt32=crypt, kernel32=kernel)

    sealed = cipher.protect(b'secret payload')

    assert sealed != b'secret payload'
    assert cipher.unprotect(sealed) == b'secret payload'
    assert [name for name, _ in crypt.calls] == ['protect', 'unprotect']
    assert all(flags & 0x1 for _, flags in crypt.calls)  # CRYPTPROTECT_UI_FORBIDDEN: never prompt
    assert kernel.freed == 2  # the buffers DPAPI allocated are released


def test_dpapi_failures_become_a_secret_store_error():
    cipher = DpapiCipher(crypt32=FakeCrypt32(fail=True), kernel32=FakeKernel32())

    with pytest.raises(SecretStoreError):
        cipher.protect(b'x')
    with pytest.raises(SecretStoreError):
        cipher.unprotect(b'x')


def test_the_store_encrypts_the_file_content_when_given_a_cipher(tmp_path):
    cipher = DpapiCipher(crypt32=FakeCrypt32(), kernel32=FakeKernel32())
    store = FileSecretStore(tmp_path / 'secrets', cipher=cipher)

    store.set_api_key('openai', FAKE)

    assert FAKE.encode() not in store.path.read_bytes()
    assert FileSecretStore(tmp_path / 'secrets', cipher=cipher).get_api_key('openai') == FAKE


def test_an_undecryptable_file_reads_as_no_key(tmp_path, caplog):
    store = FileSecretStore(tmp_path / 'secrets', cipher=DpapiCipher(crypt32=FakeCrypt32(), kernel32=FakeKernel32()))
    store.set_api_key('openai', FAKE)
    broken = FileSecretStore(tmp_path / 'secrets', cipher=DpapiCipher(crypt32=FakeCrypt32(fail=True),
                                                                      kernel32=FakeKernel32()))

    with caplog.at_level(logging.WARNING):
        assert broken.get_api_key('openai') is None

    assert FAKE not in caplog.text


def test_default_cipher_depends_on_the_platform(tmp_path, monkeypatch):
    assert FileSecretStore(tmp_path / 'a', platform='posix').cipher is None
    monkeypatch.setattr(module, 'DpapiCipher', lambda: 'dpapi')
    assert FileSecretStore(tmp_path / 'b', platform='nt').cipher == 'dpapi'


# --- T12b: concurrency, corrupt files, symlinked directory, key validation --------------------------------------------

def test_concurrent_writers_do_not_lose_each_others_keys(store):
    import threading
    providers = ['openai', 'anthropic', 'gemini', 'openai_compatible']
    barrier = threading.Barrier(len(providers))
    errors = []

    def write(provider):
        try:
            barrier.wait(5)
            store.set_api_key(provider, f'key-for-{provider}-0123456789')
        except Exception as error:  # noqa: BLE001 - reported by the assertion below
            errors.append(error)

    threads = [threading.Thread(target=write, args=(name,)) for name in providers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert not errors and not any(thread.is_alive() for thread in threads)
    assert {name: store.get_api_key(name) for name in providers} == {name: f'key-for-{name}-0123456789'
                                                                    for name in providers}


def test_a_corrupt_file_is_kept_as_a_backup_instead_of_being_silently_overwritten(store):
    store.set_api_key('openai', FAKE)
    store.path.write_text('{ this is not json', encoding='utf-8')
    os.chmod(store.path, 0o600)

    store.set_api_key('gemini', 'gem-key-123456')

    backup = store.directory / 'api-keys.corrupt'
    assert backup.read_text(encoding='utf-8') == '{ this is not json'
    assert store.get_api_key('gemini') == 'gem-key-123456'


def test_a_symlinked_secrets_directory_is_refused_and_its_target_left_alone(tmp_path):
    target = tmp_path / 'elsewhere'
    target.mkdir(mode=0o755)
    link = tmp_path / 'secrets'
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(SecretStoreError):
        FileSecretStore(link).set_api_key('openai', FAKE)

    assert stat.S_IMODE(os.stat(target).st_mode) == 0o755 and not any(target.iterdir())


@pytest.mark.parametrize('key', ['sk-ключ-with-non-ascii-0123', 'abc', 'x' * 501, 'sk-\x7f-0123456789'])
def test_keys_the_adapters_would_refuse_are_not_saved(store, key):
    with pytest.raises(ValueError):
        store.set_api_key('openai', key)


# --- T12c: an untrusted file is backed up, not dropped; a failing chmod is a SecretStoreError ------------------------

@posix_only
def test_changing_keys_over_an_untrusted_file_keeps_it_as_a_private_backup(store):
    store.set_api_key('openai', FAKE)
    store.set_api_key('gemini', 'gem-key-123456')
    os.chmod(store.path, 0o644)

    store.set_api_key('anthropic', 'ant-key-123456')

    backup = store.directory / 'api-keys.corrupt'
    saved = json.loads(backup.read_text(encoding='utf-8'))['keys']
    assert saved == {'openai': FAKE, 'gemini': 'gem-key-123456'}  # the other providers' keys are not lost
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600  # and the backup is not left readable by others
    assert store.get_api_key('anthropic') == 'ant-key-123456'
    assert store.get_api_key('openai') is None  # the untrusted content is not merged into the new file


@posix_only
def test_deleting_a_key_over_an_untrusted_file_also_keeps_a_backup(store):
    store.set_api_key('openai', FAKE)
    os.chmod(store.path, 0o666)

    store.delete_api_key('openai')

    assert FAKE in (store.directory / 'api-keys.corrupt').read_text(encoding='utf-8')


@posix_only
def test_a_directory_that_cannot_be_made_private_is_a_secret_store_error(store, monkeypatch):
    def refuse(path, mode):
        raise PermissionError('not ours')

    monkeypatch.setattr(os, 'chmod', refuse)

    with pytest.raises(SecretStoreError):
        store.set_api_key('openai', FAKE)
    with pytest.raises(SecretStoreError):
        store.delete_api_key('openai')
