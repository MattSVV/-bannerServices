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
Which URLs a cover page may load while it is being rendered.

The renderer feeds every sub-resource request of the page to ``is_url_allowed``. Only ``data:`` URLs and ``file:``
URLs that resolve (symlinks and ``..`` included) to a file strictly inside one of the allowed roots pass; every other
scheme, a ``file:`` URL with a remote host, and anything unparsable is blocked. The function is pure and
thread-safe, because QtWebEngine calls its interceptor on the IO thread.
"""
import os
import re
from urllib.parse import urlsplit
from urllib.request import url2pathname

_LOCAL_HOSTS = ('', 'localhost')
_DRIVE = re.compile(r'\A[A-Za-z]:')


def is_url_allowed(url, roots):
    """
    Decide whether the renderer may load ``url``.

    :param url: the fully encoded request URL.
    :param roots: directories (``str`` or ``Path``) whose files a ``file:`` URL may reach.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        return _allowed(url, roots)
    except (OSError, ValueError, UnicodeError):  # a filter that raises must never mean "allowed"
        return False


def _allowed(url, roots):
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme == 'data':
        return True
    if scheme != 'file' or parts.netloc.lower() not in _LOCAL_HOSTS:
        return False
    path = url2pathname(parts.path)
    if not path or '\x00' in path:
        return False
    if _DRIVE.match(path) and ':' in path[2:]:  # Windows: ``file.png:stream`` names an NTFS alternate data stream
        return False
    return _inside_any(os.path.realpath(path), roots)


def _inside_any(real_path, roots):
    target = os.path.normcase(real_path)
    for root in roots:
        base = os.path.normcase(os.path.realpath(os.fspath(root)))
        try:
            if target != base and os.path.commonpath([target, base]) == base:
                return True
        except ValueError:  # different drives on Windows
            continue
    return False
