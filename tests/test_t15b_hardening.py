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
"""T15b: the low-severity findings of the T15 security review (SEC-004 to SEC-007) and the T12c verifier lows."""
import logging
import nturl2path
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from contrib.plugins.portadas.adapters import qt_renderer
from contrib.plugins.portadas.adapters.file_repository import FileCoverRepository
from contrib.plugins.portadas.adapters.qt_renderer import QtCoverRenderer
from contrib.plugins.portadas.adapters.secret_store import FileSecretStore
from contrib.plugins.portadas.application import design_prompt
from contrib.plugins.portadas.application.design_prompt import build_repair_prompt
from contrib.plugins.portadas.application.ports import DesignError, RenderError, RepositoryError
from contrib.plugins.portadas.domain.cover import Cover, CoverError
from contrib.plugins.portadas.security import request_policy
from contrib.plugins.portadas.security.html_policy import sanitize_svg, sanitize_template
from contrib.plugins.portadas.security.request_policy import is_url_allowed

from .ai_support import KEY, FakeResponse
from .fakes import make_services, png_bytes
from .test_ai_adapters import REQUEST, make, ok
from .test_edit_form import Form

REPO = Path(__file__).resolve().parent.parent
GOOD_BODY = '<div class="title-main">{{title_main}}</div>'


def timed(function, *args):
    started = time.perf_counter()
    result = function(*args)
    return result, time.perf_counter() - started


# --- SEC-004: the request filter is total and fails closed -----------------------------------------------------------

class FakeUrl:
    def __init__(self, text):
        self.text = text

    def toString(self, _options=None):
        return self.text


class FakeInfo:
    def __init__(self, text):
        self.url, self.blocked = FakeUrl(text), None

    def requestUrl(self):
        return self.url

    def block(self, flag):
        self.blocked = flag


def test_the_interceptor_blocks_when_the_policy_raises(qapp, monkeypatch):
    def boom(url, roots):
        raise RuntimeError('unexpected')

    monkeypatch.setattr(qt_renderer, 'is_url_allowed', boom)
    info = FakeInfo('file:///etc/passwd')

    qt_renderer._Interceptor(['/tmp']).interceptRequest(info)

    assert info.blocked is True


def test_the_interceptor_still_lets_allowed_requests_through(qapp, monkeypatch):
    monkeypatch.setattr(qt_renderer, 'is_url_allowed', lambda url, roots: True)
    info = FakeInfo('data:image/png;base64,AAAA')

    qt_renderer._Interceptor(['/tmp']).interceptRequest(info)

    assert info.blocked is None


@pytest.mark.parametrize('error', [OSError('boom'), ValueError('boom'), UnicodeError('boom')])
@pytest.mark.parametrize('place', ['realpath', 'url2pathname'])
def test_is_url_allowed_is_total(tmp_path, monkeypatch, error, place):
    def boom(*args):
        raise error

    if place == 'realpath':
        monkeypatch.setattr(request_policy.os.path, 'realpath', boom)
    else:
        monkeypatch.setattr(request_policy, 'url2pathname', boom)

    assert is_url_allowed(f'file://{tmp_path}/a.png', [tmp_path]) is False


def test_a_colon_after_the_drive_is_refused_on_windows_paths(monkeypatch):
    monkeypatch.setattr(request_policy, 'url2pathname', nturl2path.url2pathname)
    monkeypatch.setattr(request_policy, '_inside_any', lambda path, roots: True)  # the path check is not the subject

    assert is_url_allowed('file:///C:/assets/icon.png', ['C:\\assets']) is True
    assert is_url_allowed('file:///C:/assets/icon.png:stream', ['C:\\assets']) is False
    assert is_url_allowed('file:///C:/assets/icon.png::$DATA', ['C:\\assets']) is False


# --- SEC-005: no quadratic CPU ---------------------------------------------------------------------------------------

def test_many_distinct_css_problems_cost_linear_time_and_fail_closed():
    css = ''.join(f'a{{p{i}:c}}' for i in range(14000))
    template = f'<style>{css}</style>{GOOD_BODY}'

    result, seconds = timed(sanitize_template, template)

    assert seconds < 2.0
    assert any('too many problems' in violation.message for violation in result.violations)
    assert 'p0:c' not in (result.html or '') and len(result.violations) < 500


def test_skipped_elements_with_unmatched_end_tags_are_linear():
    template = '<x>' * 45000 + '</y>' * 13000

    _, seconds = timed(sanitize_template, template)

    assert seconds < 2.0


def hostile_reply(size):
    text, char = '>>>', '<'
    while len(text) + 3 <= size:
        text, char = char * 2 + text + char, '>' if char == '<' else '<'
    return text


def test_a_hostile_previous_answer_is_stripped_in_linear_time():
    prompt, seconds = timed(build_repair_prompt, 'ORIGINAL', hostile_reply(design_prompt.MAX_PREVIOUS_CHARS), ['x'])
    body = prompt.split('<<<PREVIOUS_ANSWER\n', 1)[1].split('\nPREVIOUS_ANSWER>>>', 1)[0]

    assert seconds < 0.5
    assert '<<<' not in body and '>>>' not in body


def test_the_previous_answer_is_bounded():
    assert design_prompt.MAX_PREVIOUS_CHARS <= 30000


# --- SEC-006: lone surrogates ----------------------------------------------------------------------------------------

@pytest.mark.parametrize('field', ['title_main', 'subtitle', 'label', 'title_accent'])
def test_a_cover_field_with_a_lone_surrogate_is_refused(field):
    values = {'title_main': 'Bueno', field: 'x\ud800y'}

    with pytest.raises(CoverError):
        Cover.from_raw(values.pop('title_main'), **values)


def test_a_template_with_a_lone_surrogate_is_rejected():
    for text in (f'{GOOD_BODY}<p title="a\ud800">x</p>', f'<style>.a{{font-family:"a\udc00"}}</style>{GOOD_BODY}',
                 f'{GOOD_BODY}\ud83d'):
        assert not sanitize_template(text).accepted


def test_an_svg_with_a_lone_surrogate_attribute_is_rejected():
    assert not sanitize_svg('<svg viewBox="0 0 8 8"><path d="M0 0 L1 1 \ud800"/></svg>').accepted


def test_the_renderer_turns_an_unencodable_page_into_a_render_error(qapp):
    renderer = QtCoverRenderer()

    with pytest.raises(RenderError):
        renderer.render_async('<p>\ud800</p>', REPO / 'portadas' / 'templates' / 'noche-dorada', print, print)


def test_the_repository_turns_an_unencodable_cover_into_a_repository_error(tmp_path):
    cover = Cover.from_raw('Bueno', id='abc')
    object.__setattr__(cover, 'title_main', 'x\ud800y')

    with pytest.raises(RepositoryError):
        FileCoverRepository(tmp_path).save(cover, png_bytes())


def test_the_editor_is_not_left_busy_when_starting_a_preview_fails(qtbot, openlp_env, tmp_path):
    services = make_services(tmp_path)
    form = Form(None, services)
    qtbot.addWidget(form)
    form.title_main_edit.setText('Bueno')

    def boom(*args, **kwargs):
        raise UnicodeError('unencodable')

    services.renderer.render_async = boom
    try:
        form._start_preview()
    except UnicodeError:
        pass

    assert form._busy is False


# --- SEC-007: redaction follows the package name ---------------------------------------------------------------------

def test_the_redaction_hooks_the_package_the_plugin_is_loaded_under(tmp_path):
    plugins = tmp_path / 'data' / 'contrib' / 'plugins'
    plugins.mkdir(parents=True)
    os.symlink(REPO / 'portadas', plugins / 'renamedpkg')
    code = (
        'import sys, logging; sys.path.insert(0, sys.argv[1]);'
        'import contrib.plugins.renamedpkg.portadasplugin;'
        'from contrib.plugins.renamedpkg.security.redaction import register_secret;'
        'register_secret("exact-secret-value");'
        'out = []\n'
        'class H(logging.Handler):\n'
        '    def emit(self, record): out.append(self.format(record))\n'
        'logging.getLogger().addHandler(H()); child = logging.getLogger("contrib.plugins.renamedpkg.adapters.x");'
        'child.setLevel(logging.INFO); child.info("leak exact-secret-value");'
        'print(out)'
    )

    result = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'data')], capture_output=True, text=True,
                            timeout=60, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), cwd=tmp_path, check=False)

    assert result.returncode == 0, result.stderr
    assert 'exact-secret-value' not in result.stdout and '[redacted]' in result.stdout


# --- T12c lows --------------------------------------------------------------------------------------------------------

def test_a_backup_name_taken_by_a_folder_does_not_block_every_save(tmp_path, caplog):
    store = FileSecretStore(tmp_path / 's')
    store.set_api_key('openai', KEY)
    (store.directory / 'api-keys.corrupt').mkdir()
    store.path.write_text('not json')  # untrusted content: it must be moved aside before a new file is written

    with caplog.at_level(logging.WARNING):
        store.set_api_key('openai', 'sk-NEW-0123456789abcdef')

    assert store.get_api_key('openai') == 'sk-NEW-0123456789abcdef'
    backups = [path for path in store.directory.iterdir() if path.name.startswith('api-keys.corrupt-')]
    assert len(backups) == 1 and backups[0].read_text() == 'not json'


def test_a_real_http_error_is_not_masked_by_a_deadline_that_fires_right_after():
    designer, _, _ = make('openai', FakeResponse(401, {}))
    attempt = designer._attempt

    def late_deadline(watch, *args):
        try:
            return attempt(watch, *args)
        finally:
            watch.reason = 'deadline'  # the watcher fired just after the answer had been read

    designer._attempt = late_deadline

    with pytest.raises(DesignError, match='API key'):
        designer.design(REQUEST)


def test_a_deadline_still_wins_when_the_answer_was_not_complete():
    designer, _, _ = make('openai', ok('openai'))

    def broken_read(watch, *args):
        try:
            raise ConnectionError('socket shut down by the watcher')
        finally:
            watch.reason = 'deadline'

    designer._attempt = broken_read

    with pytest.raises(DesignError, match='in time'):
        designer.design(REQUEST)
