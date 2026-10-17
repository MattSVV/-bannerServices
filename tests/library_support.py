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
"""Shared by the library tab tests: a fake plugin and form, an ``Item`` whose dialogs the test controls, fixtures."""
from datetime import datetime, timedelta, timezone

import pytest
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.lib.mediaitem import PortadasMediaItem
from openlp.core.lib.plugin import StringContent
from PyQt5 import QtWidgets

from .fakes import make_services, png_bytes

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


class FakePlugin:
    """What ``MediaManagerItem`` needs from a plugin."""
    name = 'portadas'
    icon_path = 'images/image'
    name_strings = {'singular': 'Cover', 'plural': 'Covers'}

    def get_string(self, kind):
        if kind == StringContent.VisibleName:
            return {'title': 'Covers'}
        return {'title': str(kind), 'tooltip': f'{kind} tooltip'}


class FakeForm:
    """Stands in for ``CoverEditForm``: records what the media item asked and 'saves' when told to."""

    def __init__(self, save_as=None):
        self.save_as = save_as
        self.loaded = 'not called'
        self.saved_cover = None

    def load_cover(self, cover=None):
        self.loaded = cover

    def exec(self):
        if self.save_as is None:
            return QtWidgets.QDialog.Rejected
        self.saved_cover = self.save_as
        return QtWidgets.QDialog.Accepted


class Item(PortadasMediaItem):
    """The media item with message boxes and file choosers under the test's control."""

    def __init__(self, *args, **kwargs):
        self.errors = []
        self.confirm_answer = True
        self.export_path = None
        self.form = FakeForm()
        super().__init__(*args, **kwargs)

    def show_error(self, title, message):
        self.errors.append((title, message))

    def confirm_delete(self, count):
        self.confirm_asked = count
        return self.confirm_answer

    def choose_export_path(self, default_name):
        self.suggested_name = default_name
        return self.export_path

    def create_edit_form(self):
        return self.form


def make_cover(cover_id, title, minutes=0, **fields):
    return Cover.from_raw(title, id=cover_id, created_at=NOW + timedelta(minutes=minutes), **fields)


@pytest.fixture
def services(tmp_path):
    services = make_services(tmp_path)
    for cover in (make_cover('one', 'Resistir', 1, title_accent='al diablo'), make_cover('two', 'Fe', 3),
                  make_cover('three', 'Esperanza viva', 2, subtitle='Una serie')):
        services.repository.save(cover, png_bytes(16, 9))
    return services


@pytest.fixture
def item(qtbot, openlp_env, services):
    media_item = Item(None, FakePlugin())
    media_item.services = services
    qtbot.addWidget(media_item)
    media_item.initialise()
    return media_item


def titles(item):
    return [item.list_view.item(row).text() for row in range(item.list_view.count())]


def select(item, *row_numbers):
    item.list_view.setCurrentRow(row_numbers[0])  # selects only that row...
    for row in row_numbers[1:]:
        item.list_view.item(row).setSelected(True)  # ...then extend the selection
