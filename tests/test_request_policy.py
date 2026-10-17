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
"""The request policy of the renderer: which URLs a cover page may load."""
import os

import pytest
from contrib.plugins.portadas.security.request_policy import is_url_allowed


@pytest.fixture
def roots(tmp_path):
    assets = tmp_path / 'assets'
    base = tmp_path / 'base'
    for folder in (assets, base):
        folder.mkdir()
        (folder / 'ok.png').write_bytes(b'x')
    (tmp_path / 'secret.txt').write_text('secret')
    return {'assets': assets, 'base': base, 'tmp': tmp_path, 'roots': (assets, base)}


def file_url(path):
    return 'file://' + str(path)


def test_data_urls_are_allowed(roots):
    assert is_url_allowed('data:image/png;base64,AAAA', roots['roots'])


@pytest.mark.parametrize('url', [
    'http://example.com/x.png', 'https://example.com/x.png', 'ftp://example.com/x', '//example.com/x.png',
    'qrc:/qtwebchannel/qwebchannel.js', 'blob:null/1234', 'filesystem:file:///tmp/x', 'javascript:alert(1)',
    'view-source:file:///etc/passwd', 'chrome://gpu', 'about:blank', 'ws://localhost:1/', '', 'not a url', None, 42])
def test_everything_but_data_and_local_files_is_blocked(roots, url):
    assert not is_url_allowed(url, roots['roots'])


def test_files_inside_an_allowed_root_are_allowed(roots):
    assert is_url_allowed(file_url(roots['assets'] / 'ok.png'), roots['roots'])
    assert is_url_allowed(file_url(roots['base'] / 'ok.png'), roots['roots'])


def test_a_missing_file_inside_a_root_is_allowed_so_the_page_sees_a_normal_404(roots):
    assert is_url_allowed(file_url(roots['base'] / 'missing.png'), roots['roots'])


def test_files_outside_every_root_are_blocked(roots):
    assert not is_url_allowed(file_url(roots['tmp'] / 'secret.txt'), roots['roots'])
    assert not is_url_allowed('file:///etc/passwd', roots['roots'])


def test_a_root_itself_is_not_a_file(roots):
    assert not is_url_allowed(file_url(roots['assets']), roots['roots'])


def test_a_sibling_directory_sharing_the_root_prefix_is_blocked(roots):
    evil = roots['tmp'] / 'assets-evil'
    evil.mkdir()
    (evil / 'x.png').write_bytes(b'x')

    assert not is_url_allowed(file_url(evil / 'x.png'), roots['roots'])


@pytest.mark.parametrize('suffix', [
    '/../secret.txt', '/%2e%2e/secret.txt', '/%2E%2E/secret.txt', '/..%2fsecret.txt', '/sub/../../secret.txt'])
def test_dot_dot_traversal_is_blocked(roots, suffix):
    (roots['assets'] / 'sub').mkdir()

    assert not is_url_allowed(file_url(roots['assets']) + suffix, roots['roots'])


def test_a_nul_byte_is_blocked(roots):
    assert not is_url_allowed(file_url(roots['assets']) + '/ok.png%00.txt', roots['roots'])


def test_a_symlink_inside_a_root_pointing_outside_is_blocked(roots):
    link = roots['assets'] / 'link.txt'
    os.symlink(roots['tmp'] / 'secret.txt', link)

    assert not is_url_allowed(file_url(link), roots['roots'])


def test_a_symlinked_directory_inside_a_root_pointing_outside_is_blocked(roots):
    link = roots['assets'] / 'dir'
    os.symlink(roots['tmp'], link, target_is_directory=True)

    assert not is_url_allowed(file_url(link / 'secret.txt'), roots['roots'])


def test_a_file_url_with_a_remote_host_is_blocked(roots):
    assert not is_url_allowed('file://evil.example.com' + str(roots['assets'] / 'ok.png'), roots['roots'])


def test_localhost_is_accepted_as_the_host_of_a_file_url(roots):
    assert is_url_allowed('file://localhost' + str(roots['assets'] / 'ok.png'), roots['roots'])


def test_query_and_fragment_do_not_change_the_decision(roots):
    assert is_url_allowed(file_url(roots['assets'] / 'ok.png') + '?x=1#frag', roots['roots'])
    assert not is_url_allowed(file_url(roots['tmp'] / 'secret.txt') + '?x=1#frag', roots['roots'])


def test_scheme_matching_is_case_insensitive(roots):
    assert is_url_allowed('FILE://' + str(roots['assets'] / 'ok.png'), roots['roots'])
    assert is_url_allowed('DATA:text/plain,hi', roots['roots'])
    assert not is_url_allowed('HTTP://example.com/', roots['roots'])


def test_with_no_roots_only_data_urls_pass(roots):
    assert not is_url_allowed(file_url(roots['assets'] / 'ok.png'), ())
    assert is_url_allowed('data:text/plain,hi', ())
