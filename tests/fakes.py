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
"""Test doubles shared by the UI tests: an in-memory repository and a renderer the test can drive by hand."""
import struct
import zlib
from pathlib import Path

from contrib.plugins.portadas.application.create_cover import CreateCoverFromTemplate
from contrib.plugins.portadas.application.icon_catalog import IconCatalog
from contrib.plugins.portadas.application.ports import (
    CoverNotFound,
    CoverRenderer,
    CoverRepository,
    ExportExists,
    RenderError,
    RenderResult,
)
from contrib.plugins.portadas.application.template_catalog import TemplateCatalog
from contrib.plugins.portadas.lib.ai_notice import FileNoticeStore
from contrib.plugins.portadas.lib.services import PortadasServices


def png_bytes(width=2, height=2, color=b'\xff\x00\x00'):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    raw = b''.join(b'\x00' + color * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class FakeRenderer(CoverRenderer):
    """``render`` answers at once; ``render_async`` waits until the test calls ``finish`` / ``fail``."""

    def __init__(self, overflow=(), fail=None):
        self.overflow = tuple(overflow)
        self.fail_with = fail
        self.sync_calls = []
        self.pending = []
        self.closed = False

    def render(self, html, base_dir, size=(1920, 1080)):
        self.sync_calls.append(html)
        if self.fail_with:
            raise RenderError(self.fail_with)
        return RenderResult(png_bytes(32, 18), self.overflow)

    def render_async(self, html, base_dir, on_done, on_error, size=(1920, 1080)):
        self.pending.append((html, on_done, on_error))

    def finish(self, overflow=None):
        html, on_done, _ = self.pending.pop(0)
        on_done(RenderResult(png_bytes(32, 18), self.overflow if overflow is None else tuple(overflow)))
        return html

    def fail(self, message='boom'):
        _, _, on_error = self.pending.pop(0)
        on_error(RenderError(message))

    def finish_all(self):
        while self.pending:
            self.finish()

    def close(self):
        self.closed = True


class InMemoryRepository(CoverRepository):
    """Keeps covers in a dict and writes each PNG under ``png_dir`` so thumbnails and services can read it."""

    def __init__(self, png_dir):
        self.png_dir = Path(png_dir)
        self.png_dir.mkdir(parents=True, exist_ok=True)
        self.covers = {}
        self.deleted = []
        self.exported = []

    def save(self, cover, png):
        self.covers[cover.id] = cover
        (self.png_dir / f'{cover.id}.png').write_bytes(png)

    def get(self, cover_id):
        try:
            return self.covers[cover_id]
        except KeyError:
            raise CoverNotFound(f'There is no cover "{cover_id}".') from None

    def list(self):
        return sorted(self.covers.values(), key=lambda cover: cover.created_at, reverse=True)

    def delete(self, cover_id):
        if cover_id not in self.covers:
            raise CoverNotFound(f'There is no cover "{cover_id}".')
        del self.covers[cover_id]
        self.deleted.append(cover_id)

    def export_png(self, cover_id, dest_path, overwrite=False):
        if Path(dest_path).exists() and not overwrite:
            raise ExportExists('exists')
        Path(dest_path).write_bytes(self.png_path(cover_id).read_bytes())
        self.exported.append((cover_id, Path(dest_path), overwrite))

    def png_path(self, cover_id):
        path = self.png_dir / f'{cover_id}.png'
        if cover_id not in self.covers or not path.exists():
            raise CoverNotFound(f'There is no image for cover "{cover_id}".')
        return path


def make_services(tmp_path, renderer=None, repository=None):
    renderer = renderer or FakeRenderer()
    repository = repository or InMemoryRepository(tmp_path / 'store')
    templates, icons = TemplateCatalog(), IconCatalog()
    return PortadasServices(repository=repository,
                            creator=CreateCoverFromTemplate(templates, icons, renderer, repository),
                            renderer=renderer, templates=templates, icons=icons,
                            thumbnail_dir=tmp_path / 'thumbnails',
                            notice_store=FileNoticeStore(tmp_path / 'ai-notice.json'))
