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
"""The file-system cover repository: round trips, ordering, traversal safety, corruption and atomic writes."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import pytest
from contrib.plugins.portadas.adapters import file_repository
from contrib.plugins.portadas.adapters.file_repository import FileCoverRepository
from contrib.plugins.portadas.application.ports import (
    CoverCorrupt,
    CoverNotFound,
    CoverRepository,
    ExportExists,
    InvalidCoverId,
    RepositoryError,
)
from contrib.plugins.portadas.domain.cover import Cover

PNG = b'\x89PNG\r\n\x1a\n' + b'fake image payload'
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_cover(cover_id='c1', minutes=0, **extra):
    return Cover.from_raw('Resistir', id=cover_id, created_at=T0 + timedelta(minutes=minutes), **extra)


@pytest.fixture
def repo(tmp_path):
    return FileCoverRepository(tmp_path / 'store')


def test_it_implements_the_port(repo):
    assert isinstance(repo, CoverRepository)


def test_save_then_get_round_trips_and_writes_png_and_json(repo, tmp_path):
    cover = make_cover(key_verse='Efesios 6:11', readings=['Efesios 6:11-12'])

    repo.save(cover, PNG)

    assert repo.get('c1') == cover
    assert (tmp_path / 'store' / 'c1.png').read_bytes() == PNG
    stored = json.loads((tmp_path / 'store' / 'c1.json').read_text(encoding='utf-8'))
    assert stored['schema_version'] == 1 and stored['title_main'] == 'Resistir'
    assert repo.png_path('c1') == tmp_path / 'store' / 'c1.png'
    assert sorted(path.name for path in (tmp_path / 'store').iterdir()) == ['c1.json', 'c1.png']


def test_saving_again_replaces_the_cover(repo):
    repo.save(make_cover(), PNG)
    newer = Cover.from_raw('Otro titulo', id='c1', created_at=T0)

    repo.save(newer, PNG + b'2')

    assert repo.get('c1').title_main == 'Otro titulo'
    assert repo.png_path('c1').read_bytes() == PNG + b'2'
    assert len(repo.list()) == 1


def test_list_is_newest_first_with_id_as_tie_breaker(repo):
    for cover_id, minutes in (('old', 0), ('new', 10), ('mid', 5), ('b-tie', 5), ('a-tie', 5)):
        repo.save(make_cover(cover_id, minutes), PNG)

    assert [cover.id for cover in repo.list()] == ['new', 'a-tie', 'b-tie', 'mid', 'old']


def test_list_of_an_empty_or_missing_store_is_empty(tmp_path):
    assert FileCoverRepository(tmp_path / 'nothing-here').list() == []
    assert FileCoverRepository(tmp_path).list() == []


def test_delete_removes_both_files(repo, tmp_path):
    repo.save(make_cover(), PNG)

    repo.delete('c1')

    assert repo.list() == []
    assert list((tmp_path / 'store').iterdir()) == []


def test_unknown_covers_are_not_found(repo):
    for action in (repo.get, repo.delete, repo.png_path):
        with pytest.raises(CoverNotFound):
            action('nope')
    with pytest.raises(CoverNotFound):
        repo.export_png('nope', repo.root.parent / 'out.png')


BAD_IDS = ['../x', '../../etc/passwd', '/etc/passwd', 'a/b', 'a\\b', 'a\x00b', '', '.', '..', 'x' * 65, 'con', 'NUL',
           'Aux', 'com1', 'LPT9', 'é', ' a', 'a ', 'a.png', 'a.json', 'a b', None, 5]


@pytest.mark.parametrize('bad', BAD_IDS, ids=repr)
def test_unsafe_ids_are_refused_by_every_operation(repo, tmp_path, bad):
    for action in (repo.get, repo.delete, repo.png_path):
        with pytest.raises(InvalidCoverId):
            action(bad)
    with pytest.raises(InvalidCoverId):
        repo.export_png(bad, tmp_path / 'out.png')


@pytest.mark.parametrize('bad', ['con', 'NUL', 'com1', 'Lpt2'])
def test_save_refuses_reserved_device_names(repo, bad):
    with pytest.raises(InvalidCoverId):
        repo.save(make_cover(bad), PNG)
    assert repo.list() == []


def test_traversal_cannot_read_a_file_outside_the_store(repo, tmp_path):
    (tmp_path / 'secret.json').write_text('{"title_main": "secret"}', encoding='utf-8')
    (tmp_path / 'secret.png').write_bytes(PNG)
    repo.save(make_cover(), PNG)

    for sneaky in ('../secret', '..%2fsecret', '../store/../secret'):
        with pytest.raises(InvalidCoverId):
            repo.get(sneaky)
        with pytest.raises(InvalidCoverId):
            repo.delete(sneaky)
    assert (tmp_path / 'secret.json').exists() and (tmp_path / 'secret.png').exists()


def test_traversal_cannot_export_a_file_outside_the_store(repo, tmp_path):
    (tmp_path / 'secret.png').write_bytes(b'top secret')

    with pytest.raises(InvalidCoverId):
        repo.export_png('../secret', tmp_path / 'stolen.png')
    assert not (tmp_path / 'stolen.png').exists()


def test_symlinked_files_are_not_followed(repo, tmp_path, caplog):
    repo.save(make_cover(), PNG)
    outside = tmp_path / 'outside.json'
    outside.write_text((tmp_path / 'store' / 'c1.json').read_text(encoding='utf-8'), encoding='utf-8')
    os.symlink(outside, tmp_path / 'store' / 'evil.json')
    os.symlink(tmp_path / 'store' / 'c1.png', tmp_path / 'store' / 'evil.png')

    with caplog.at_level(logging.WARNING):
        assert [cover.id for cover in repo.list()] == ['c1']
    with pytest.raises(RepositoryError):
        repo.get('evil')


def corrupt(repo, name, content):
    repo.root.mkdir(parents=True, exist_ok=True)
    mode = 'wb' if isinstance(content, bytes) else 'w'
    with open(repo.root / f'{name}.json', mode) as handle:
        handle.write(content)
    (repo.root / f'{name}.png').write_bytes(PNG)


@pytest.mark.parametrize('content', [
    '{not json', '', '[]', '"text"', b'\xff\xfe\x00bad', '{"schema_version": 99}', '{"schema_version": 1}',
    '{"x": "' + 'y' * 600000 + '"}'],
    ids=['syntax', 'empty', 'list', 'string', 'binary', 'future', 'incomplete', 'huge'])
def test_corrupt_files_are_skipped_with_a_warning_and_never_crash_list(repo, caplog, content):
    repo.save(make_cover('good'), PNG)
    corrupt(repo, 'broken', content)

    with caplog.at_level(logging.WARNING):
        covers = repo.list()

    assert [cover.id for cover in covers] == ['good']
    assert any('broken' in record.getMessage() for record in caplog.records)


def test_get_of_a_corrupt_cover_raises_a_clear_error(repo):
    corrupt(repo, 'broken', '{not json')

    with pytest.raises(CoverCorrupt):
        repo.get('broken')


def test_a_cover_without_its_png_is_skipped(repo, caplog):
    repo.save(make_cover('lonely'), PNG)
    repo.png_path('lonely').unlink()

    with caplog.at_level(logging.WARNING):
        assert repo.list() == []
    assert any('lonely' in record.getMessage() for record in caplog.records)


def test_a_json_whose_id_differs_from_its_file_name_is_skipped(repo, tmp_path, caplog):
    repo.save(make_cover('real'), PNG)
    (tmp_path / 'store' / 'fake.json').write_text((tmp_path / 'store' / 'real.json').read_text(encoding='utf-8'),
                                                  encoding='utf-8')
    (tmp_path / 'store' / 'fake.png').write_bytes(PNG)

    with caplog.at_level(logging.WARNING):
        assert [cover.id for cover in repo.list()] == ['real']


def test_unrelated_files_and_directories_are_ignored(repo, tmp_path):
    repo.save(make_cover(), PNG)
    (tmp_path / 'store' / 'notes.txt').write_text('hi', encoding='utf-8')
    (tmp_path / 'store' / 'sub.json').mkdir()
    (tmp_path / 'store' / '..json').write_text('{}', encoding='utf-8')
    (tmp_path / 'store' / '.c1.json.abc.tmp').write_text('{}', encoding='utf-8')

    assert [cover.id for cover in repo.list()] == ['c1']


@pytest.mark.parametrize('payload', [b'', b'not a png', None, 'text', b'\x89PNG'])
def test_save_refuses_data_that_is_not_a_png(repo, payload):
    with pytest.raises(RepositoryError):
        repo.save(make_cover(), payload)
    assert repo.list() == []


def test_save_refuses_a_huge_png(repo, monkeypatch):
    monkeypatch.setattr(file_repository, 'MAX_PNG_BYTES', 20)

    with pytest.raises(RepositoryError):
        repo.save(make_cover(), PNG + b'x' * 20)


def test_save_requires_a_cover(repo):
    with pytest.raises(RepositoryError):
        repo.save({'id': 'x'}, PNG)


def fail_second_replace(monkeypatch, fail_on):
    real = os.replace
    calls = []

    def replace(source, target):
        calls.append(str(target))
        if len(calls) == fail_on:
            raise OSError('disk full')
        return real(source, target)

    monkeypatch.setattr(file_repository.os, 'replace', replace)


def test_a_failure_while_saving_the_json_leaves_no_half_written_new_cover(repo, monkeypatch):
    fail_second_replace(monkeypatch, 2)

    with pytest.raises(RepositoryError):
        repo.save(make_cover(), PNG)

    assert repo.list() == []
    assert list(repo.root.iterdir()) == []


def test_a_failed_overwrite_keeps_the_previous_cover_intact(repo, monkeypatch):
    original = make_cover()
    repo.save(original, PNG)
    fail_second_replace(monkeypatch, 2)

    with pytest.raises(RepositoryError):
        repo.save(Cover.from_raw('Nuevo', id='c1', created_at=T0), PNG + b'new')

    monkeypatch.undo()
    assert repo.get('c1') == original
    assert sorted(path.name for path in repo.root.iterdir()) == ['c1.json', 'c1.png']


def test_a_failure_writing_the_png_leaves_nothing_behind(repo, monkeypatch):
    fail_second_replace(monkeypatch, 1)

    with pytest.raises(RepositoryError):
        repo.save(make_cover(), PNG)

    assert list(repo.root.iterdir()) == []


def test_export_copies_the_png(repo, tmp_path):
    repo.save(make_cover(), PNG)

    repo.export_png('c1', tmp_path / 'out.png')

    assert (tmp_path / 'out.png').read_bytes() == PNG


def test_export_accepts_a_string_path(repo, tmp_path):
    repo.save(make_cover(), PNG)

    repo.export_png('c1', str(tmp_path / 'out.png'))

    assert (tmp_path / 'out.png').read_bytes() == PNG


def test_export_refuses_to_overwrite_unless_asked(repo, tmp_path):
    repo.save(make_cover(), PNG)
    (tmp_path / 'out.png').write_bytes(b'precious')

    with pytest.raises(ExportExists):
        repo.export_png('c1', tmp_path / 'out.png')
    assert (tmp_path / 'out.png').read_bytes() == b'precious'

    repo.export_png('c1', tmp_path / 'out.png', overwrite=True)
    assert (tmp_path / 'out.png').read_bytes() == PNG
    assert sorted(path.name for path in tmp_path.iterdir() if path.name.startswith('.')) == []


def test_export_never_follows_a_symlink_at_the_destination_without_overwrite(repo, tmp_path):
    repo.save(make_cover(), PNG)
    target = tmp_path / 'target.txt'
    target.write_text('keep', encoding='utf-8')
    os.symlink(target, tmp_path / 'link.png')

    with pytest.raises(ExportExists):
        repo.export_png('c1', tmp_path / 'link.png')
    assert target.read_text(encoding='utf-8') == 'keep'


def test_export_to_a_missing_folder_or_a_directory_fails_cleanly(repo, tmp_path):
    repo.save(make_cover(), PNG)

    with pytest.raises(RepositoryError):
        repo.export_png('c1', tmp_path / 'missing' / 'out.png')
    with pytest.raises(RepositoryError):
        repo.export_png('c1', tmp_path, overwrite=True)


# --- T07b regressions -------------------------------------------------------------------------------------------------

def call_bounded(function, seconds=5):
    """Run ``function`` in a daemon thread, so a regression that blocks on a FIFO fails instead of hanging."""
    import threading
    outcome = {}

    def target():
        try:
            outcome['value'] = function()
        except BaseException as error:  # noqa: B902 - handed back to the test thread
            outcome['error'] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), 'the repository call blocked on a named pipe'
    if 'error' in outcome:
        raise outcome['error']
    return outcome['value']


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='needs POSIX named pipes')
def test_a_named_pipe_in_the_store_never_blocks_get_or_list(repo):
    repo.save(make_cover('ok'), PNG)
    os.mkfifo(repo.root / 'pipe.json')

    with pytest.raises(CoverCorrupt):
        call_bounded(lambda: repo.get('pipe'))
    assert [cover.id for cover in call_bounded(repo.list)] == ['ok']


def test_a_failed_save_keeps_a_pre_existing_orphan_png(repo, monkeypatch):
    repo.root.mkdir(parents=True, exist_ok=True)
    (repo.root / 'c1.png').write_bytes(PNG + b'orphan')
    fail_second_replace(monkeypatch, 2)

    with pytest.raises(RepositoryError):
        repo.save(make_cover(), PNG)

    assert (repo.root / 'c1.png').read_bytes() == PNG + b'orphan'
    assert not (repo.root / 'c1.json').exists()


def test_a_failed_save_leaves_no_temporary_files(repo, monkeypatch):
    fail_second_replace(monkeypatch, 1)

    with pytest.raises(RepositoryError):
        repo.save(make_cover(), PNG)

    assert list(repo.root.iterdir()) == []


def test_user_facing_errors_do_not_leak_paths(repo, tmp_path, caplog):
    corrupt(repo, 'broken', '{not json')
    (repo.root / 'dir.json').mkdir()

    for cover_id in ('broken', 'dir'):
        with caplog.at_level(logging.WARNING), pytest.raises(CoverCorrupt) as caught:
            repo.get(cover_id)
        assert str(tmp_path) not in str(caught.value)
        assert '/' not in str(caught.value)
    assert any('dir' in record.getMessage() for record in caplog.records)


def test_save_failures_do_not_leak_paths(repo, tmp_path, monkeypatch):
    def refuse(*_):
        raise PermissionError(13, 'Permission denied', str(repo.root / 'c1.png'))

    monkeypatch.setattr(file_repository.os, 'replace', refuse)

    with pytest.raises(RepositoryError) as caught:
        repo.save(make_cover(), PNG)

    assert str(tmp_path) not in str(caught.value)


def test_the_json_is_the_commit_marker_of_a_save(repo, monkeypatch):
    """A crash between the two renames leaves a PNG without JSON: the cover does not exist yet, nothing is listed."""
    order = []
    real = os.replace

    def spy(source, target):
        order.append(os.path.basename(target))
        return real(source, target)

    monkeypatch.setattr(file_repository.os, 'replace', spy)
    repo.save(make_cover(), PNG)

    assert order == ['c1.png', 'c1.json']


# --- T12b: one damaged entry never hides the others ------------------------------------------------------------------

def test_a_cover_with_a_hostile_deeply_nested_template_does_not_break_the_list(repo):
    repo.save(make_cover('ok', 1), PNG)
    repo.save(make_cover('deep', 2), PNG)
    path = repo.root / 'deep.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['custom_template_html'] = '<div>' * 5000 + '{{title_main}}' + '</div>' * 5000
    path.write_text(json.dumps(data), encoding='utf-8')

    covers = repo.list()

    assert [cover.id for cover in covers] == ['deep', 'ok']
    assert covers[0].custom_template_html is None  # the template was dropped, the cover stays usable


def test_an_unexpected_error_while_reading_one_entry_skips_only_that_entry(repo, monkeypatch, caplog):
    repo.save(make_cover('ok', 1), PNG)
    repo.save(make_cover('bad', 2), PNG)
    real = file_repository.cover_from_json

    def flaky(text):
        cover = real(text)
        if cover.id == 'bad':
            raise RecursionError('boom')
        return cover

    monkeypatch.setattr(file_repository, 'cover_from_json', flaky)

    with caplog.at_level(logging.WARNING):
        assert [cover.id for cover in repo.list()] == ['ok']
    assert 'bad' in caplog.text
