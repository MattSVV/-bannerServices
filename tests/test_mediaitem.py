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
"""The library tab: listing, searching, editing, deleting and exporting covers."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from contrib.plugins.portadas.application.ports import RepositoryError
from contrib.plugins.portadas.domain.cover import Cover
from contrib.plugins.portadas.lib.mediaitem import PortadasMediaItem
from openlp.core.lib.plugin import StringContent
from PyQt5 import QtCore, QtWidgets

from .fakes import InMemoryRepository, make_services, png_bytes

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


# --- listing --------------------------------------------------------------------------------------------------------

def test_the_list_shows_saved_covers_newest_first_with_thumbnails(item):
    assert titles(item) == ['Fe', 'Esperanza viva', 'Resistir al diablo']
    row = item.list_view.item(0)
    assert row.data(QtCore.Qt.UserRole) == 'two'
    assert not row.icon().isNull()
    assert (item.services.thumbnail_dir / 'two.png').exists()


def test_an_empty_library_shows_an_empty_list(qtbot, openlp_env, tmp_path):
    media_item = Item(None, FakePlugin())
    media_item.services = make_services(tmp_path)
    qtbot.addWidget(media_item)

    media_item.initialise()

    assert titles(media_item) == []


def test_a_cover_whose_image_is_missing_is_still_listed_without_a_thumbnail(item, services):
    (services.repository.png_dir / 'two.png').unlink()

    item.load_list()

    assert 'Fe' in titles(item)
    assert item.list_view.item(0).icon().isNull()


def test_a_failing_repository_is_reported_not_raised(item, services, monkeypatch):
    def broken():
        raise RepositoryError('store unavailable')
    monkeypatch.setattr(services.repository, 'list', broken)

    item.load_list()

    assert item.errors and 'store unavailable' in item.errors[0][1]


def test_the_list_reload_keeps_the_selection(item):
    select(item, 1)

    item.load_list()

    assert item.list_view.currentItem().data(QtCore.Qt.UserRole) == 'three'


# --- search ---------------------------------------------------------------------------------------------------------

def test_the_filter_box_filters_by_title_ignoring_case_and_accents(item):
    item.filter_edit.setText('ESPERANZA')
    assert [not item.list_view.item(r).isHidden() for r in range(3)] == [False, True, False]

    item.filter_edit.setText('feé')
    assert all(item.list_view.item(r).isHidden() for r in range(3))

    item.filter_edit.setText('fe')
    assert [not item.list_view.item(r).isHidden() for r in range(3)] == [True, False, False]

    item.filter_edit.setText('')
    assert not any(item.list_view.item(r).isHidden() for r in range(3))


def test_the_filter_matches_the_accent_title_too(item):
    item.filter_edit.setText('diablo')

    assert [not item.list_view.item(r).isHidden() for r in range(3)] == [False, False, True]


# --- new / edit ----------------------------------------------------------------------------------------------------

def test_new_opens_the_editor_empty_and_reloads_and_selects_the_saved_cover(item, services):
    created = make_cover('four', 'Nueva', 10)
    services.repository.save(created, png_bytes())
    item.form = FakeForm(save_as=created)

    item.on_new_click()

    assert item.form.loaded is None
    assert titles(item)[0] == 'Nueva'
    assert item.list_view.currentItem().data(QtCore.Qt.UserRole) == 'four'


def test_cancelling_the_editor_changes_nothing(item):
    before = titles(item)

    item.on_new_click()

    assert titles(item) == before


def test_edit_loads_the_selected_cover_into_the_editor(item, services):
    select(item, 2)

    item.on_edit_click()

    assert item.form.loaded == services.repository.get('one')


def test_edit_of_a_vanished_cover_reports_an_error(item, services):
    select(item, 0)
    del services.repository.covers['two']

    item.on_edit_click()

    assert item.errors and 'two' in item.errors[0][1]
    assert item.form.loaded == 'not called'


def test_an_edit_refreshes_the_thumbnail(item, services):
    old_thumbnail = services.thumbnail_dir / 'two.png'
    assert old_thumbnail.exists()
    select(item, 0)
    item.form = FakeForm(save_as=services.repository.get('two'))
    services.repository.save(services.repository.get('two'), png_bytes(8, 8, b'\x00\xff\x00'))

    item.on_edit_click()

    assert (services.thumbnail_dir / 'two.png').exists()
    assert not item.list_view.item(0).icon().isNull()


# --- delete ----------------------------------------------------------------------------------------------------------

def test_delete_asks_for_confirmation_and_calls_the_repository(item, services):
    select(item, 0, 2)

    item.on_delete_click()

    assert item.confirm_asked == 2
    assert sorted(services.repository.deleted) == ['one', 'two']
    assert titles(item) == ['Esperanza viva']
    assert not (services.thumbnail_dir / 'two.png').exists()


def test_delete_declined_deletes_nothing(item, services):
    item.confirm_answer = False
    select(item, 0)

    item.on_delete_click()

    assert services.repository.deleted == []
    assert len(titles(item)) == 3


def test_a_delete_failure_is_reported_and_the_rest_continues(item, services, monkeypatch):
    real_delete = services.repository.delete

    def flaky(cover_id):
        if cover_id == 'two':
            raise RepositoryError('cannot delete')
        real_delete(cover_id)
    monkeypatch.setattr(services.repository, 'delete', flaky)
    select(item, 0, 1)

    item.on_delete_click()

    assert item.errors and 'cannot delete' in item.errors[0][1]
    assert services.repository.deleted == ['three']


# --- export ----------------------------------------------------------------------------------------------------------

def test_export_copies_the_png_through_the_repository(item, services, tmp_path):
    select(item, 0)
    item.export_path = tmp_path / 'out' / 'Fe.png'
    item.export_path.parent.mkdir()

    item.on_export_click()

    assert item.suggested_name == 'Fe.png'
    assert services.repository.exported == [('two', item.export_path, False)]
    assert item.export_path.read_bytes() == (services.repository.png_dir / 'two.png').read_bytes()


def test_export_to_an_existing_file_overwrites_because_the_dialog_confirmed(item, services, tmp_path):
    select(item, 0)
    item.export_path = tmp_path / 'Fe.png'
    item.export_path.write_bytes(b'old')

    item.on_export_click()

    assert services.repository.exported == [('two', item.export_path, True)]
    assert item.export_path.read_bytes() != b'old'


def test_cancelling_the_export_dialog_exports_nothing(item, services):
    select(item, 0)
    item.export_path = None

    item.on_export_click()

    assert services.repository.exported == []


def test_an_export_failure_is_reported(item, services, tmp_path, monkeypatch):
    def broken(cover_id, dest, overwrite=False):
        raise RepositoryError('read-only folder')
    monkeypatch.setattr(services.repository, 'export_png', broken)
    select(item, 0)
    item.export_path = tmp_path / 'x.png'

    item.on_export_click()

    assert item.errors and 'read-only folder' in item.errors[0][1]


def test_the_suggested_export_name_is_a_safe_file_name(item, services, tmp_path):
    services.repository.save(make_cover('odd', 'A/B: "C" ?', 20), png_bytes())
    item.load_list()
    select(item, 0)
    item.export_path = None

    item.on_export_click()

    assert item.suggested_name == 'A B C.png'


# --- toolbar, context menu, lifecycle ---------------------------------------------------------------------------------

def test_the_standard_and_custom_actions_are_present(item):
    toolbar_actions = set(item.toolbar.actions.keys())
    assert {'portadasNewAction', 'portadasEditAction', 'portadasDeleteAction', 'portadasPreviewAction',
            'portadasLiveAction', 'portadasServiceAction', 'portadasExportAction'} <= toolbar_actions
    menu_texts = [action.text() for action in item.list_view.actions()]
    assert any('PNG' in text for text in menu_texts)
    assert item.can_preview and item.can_make_live and item.can_add_to_service
    assert item.single_service_item is False


def test_shutdown_closes_the_services(item, services):
    item.shutdown()

    assert services.renderer.closed


def test_production_services_are_built_lazily_in_the_data_dir(qtbot, openlp_env, tmp_path, monkeypatch):
    from contrib.plugins.portadas.lib import mediaitem as module
    built = {}

    def fake_build(data_dir):
        built['dir'] = Path(data_dir)
        return make_services(tmp_path)
    monkeypatch.setattr(module, 'build_services', fake_build)
    monkeypatch.setattr(module.AppLocation, 'get_section_data_path', lambda section: tmp_path / section)
    media_item = Item(None, FakePlugin())
    qtbot.addWidget(media_item)

    media_item.initialise()

    assert built['dir'] == tmp_path / 'portadas'
    assert isinstance(media_item.services.repository, InMemoryRepository)
