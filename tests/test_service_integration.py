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
"""Covers in the OpenLP service: the library tab builds image service items; the service file bundles the PNG."""
import json
import shutil
from unittest.mock import MagicMock

import pytest
from contrib.plugins.portadas.application.ports import CoverNotFound
from openlp.core.common import sha256_file_hash
from openlp.core.common.applocation import AppLocation
from openlp.core.common.json import OpenLPJSONDecoder, OpenLPJSONEncoder
from openlp.core.common.registry import Registry
from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem, ServiceItemType
from openlp.core.state import State

from .fakes import png_bytes
from .library_support import select


@pytest.fixture
def controllers(openlp_env):
    """Fake service manager and slide controllers, registered the way OpenLP does."""
    mocks = {name: MagicMock(name=name) for name in ('service_manager', 'preview_controller', 'live_controller')}
    for name, mock in mocks.items():
        Registry().register(name, mock)
    return mocks


def build(item, row=0):
    select(item, row)
    service_item = ServiceItem(item.plugin)
    service_item.add_icon()
    assert item.generate_slide_data(service_item)
    return service_item


def test_generate_slide_data_builds_an_image_service_item(item, services):
    service_item = build(item, 2)  # 'Resistir al diablo'

    assert service_item.service_item_type is ServiceItemType.Image
    assert service_item.name == 'portadas'
    assert service_item.title == 'Resistir al diablo'
    assert len(service_item.slides) == 1
    slide = service_item.slides[0]
    assert slide['path'] == services.repository.png_path('one')
    assert slide['title'] == 'Resistir al diablo.png'
    assert slide['file_hash'] == sha256_file_hash(services.repository.png_path('one'))
    assert slide['thumbnail'] == services.thumbnail_dir / 'one.png'
    assert slide['thumbnail'].exists()
    assert service_item.theme == -1


@pytest.mark.parametrize('capability', [
    ItemCapabilities.CanPreview, ItemCapabilities.CanLoop, ItemCapabilities.CanAppend, ItemCapabilities.CanMaintain,
    ItemCapabilities.CanEditTitle, ItemCapabilities.HasThumbnails, ItemCapabilities.ProvidesOwnTheme])
def test_the_service_item_has_the_image_capabilities(item, capability):
    assert build(item).is_capable(capability)


def test_text_only_capabilities_are_not_claimed(item):
    service_item = build(item)

    assert not service_item.is_capable(ItemCapabilities.CanSoftBreak)
    assert not service_item.is_capable(ItemCapabilities.CanEdit)


def test_nothing_selected_builds_nothing(item):
    item.list_view.setCurrentRow(-1)
    service_item = ServiceItem(item.plugin)

    assert item.generate_slide_data(service_item) is False
    assert service_item.slides == []


def test_a_list_item_or_model_index_can_be_passed_explicitly(item):
    service_item = ServiceItem(item.plugin)
    assert item.generate_slide_data(service_item, item=item.list_view.item(1))
    assert service_item.title == 'Esperanza viva'

    second = ServiceItem(item.plugin)
    assert item.generate_slide_data(second, item=item.list_view.indexFromItem(item.list_view.item(0)))
    assert second.title == 'Fe'


def test_a_cover_that_vanished_reports_an_error_unless_remote(item, services):
    select(item, 0)
    del services.repository.covers['two']

    assert item.generate_slide_data(ServiceItem(item.plugin)) is False
    assert item.errors and 'two' in item.errors[0][1]

    item.errors.clear()
    assert item.generate_slide_data(ServiceItem(item.plugin), remote=True) is False
    assert item.errors == []


def test_a_missing_png_is_handled(item, services):
    select(item, 0)
    (services.repository.png_dir / 'two.png').unlink()

    with pytest.raises(CoverNotFound):
        services.repository.png_path('two')
    assert item.generate_slide_data(ServiceItem(item.plugin)) is False


def test_appending_to_an_existing_item_keeps_its_title(item):
    existing = build(item, 0)
    select(item, 1)

    assert item.generate_slide_data(existing)

    assert existing.title == 'Fe'
    assert len(existing.slides) == 2


# --- through the base class: Preview, Live, Add to service, drag and drop ----------------------------------------

def test_preview_sends_the_cover_to_the_preview_controller(item, controllers):
    select(item, 0)

    item.on_preview_click()

    sent = controllers['preview_controller'].add_service_item.call_args.args[0]
    assert sent.title == 'Fe' and sent.service_item_type is ServiceItemType.Image


def test_go_live_sends_the_cover_to_the_live_controller(item, controllers):
    select(item, 1)

    item.on_live_click()

    sent = controllers['live_controller'].add_service_item.call_args.args[0]
    assert sent.title == 'Esperanza viva'


def test_add_to_service_adds_one_service_item_per_selected_cover(item, controllers):
    controllers['service_manager'].get_drop_position.return_value = -1
    select(item, 0, 2)

    item.on_add_click()

    added = [call.args[0].title for call in controllers['service_manager'].add_service_item.call_args_list]
    assert added == ['Fe', 'Resistir al diablo']


def test_dragging_a_cover_carries_the_plugin_name_the_service_manager_looks_up(item):
    """OpenLP's list widget puts ``mime_data_text`` on the drag; the service manager asks that plugin to add."""
    assert item.list_view.mime_data_text == item.plugin.name == 'portadas'


def test_the_plugin_adds_to_the_service_when_the_service_manager_signals_a_drop(item, controllers):
    """``Plugin.process_add_service_event`` (what a drop triggers) ends in ``on_add_click``."""
    from openlp.core.lib.plugin import Plugin
    controllers['service_manager'].get_drop_position.return_value = 3
    select(item, 0)

    Plugin.process_add_service_event(MagicMock(media_item=item), replace=False)

    controllers['service_manager'].add_service_item.assert_called_once()


# --- the service file ----------------------------------------------------------------------------------------------

def test_a_saved_service_still_opens_after_the_cover_is_deleted(item, services, tmp_path, monkeypatch):
    """
    Mimic ServiceManager: write the item's JSON and the files it lists under their hash names, delete the cover,
    then rebuild the item from the "service file" alone.
    """
    monkeypatch.setattr(AppLocation, 'get_data_path', staticmethod(lambda: tmp_path))
    monkeypatch.setattr(AppLocation, 'get_section_data_path', staticmethod(lambda section: tmp_path))
    monkeypatch.setattr(State, 'check_preconditions', lambda self, name: False)  # no media plugin in this test
    original = build(item, 2)
    stored_json = json.dumps({'serviceitem': original.get_service_repr(lite_save=False)}, cls=OpenLPJSONEncoder)
    service_dir = tmp_path / 'service-extracted'
    service_dir.mkdir()
    png = original.slides[0]['path']
    file_hash = original.slides[0]['file_hash']
    shutil.copy(png, service_dir / f'{file_hash}.png')
    (service_dir / 'thumbnails').mkdir()
    shutil.copy(original.slides[0]['thumbnail'], service_dir / 'thumbnails' / 'one.png')

    services.repository.delete('one')
    png.unlink()
    assert not png.exists()

    reopened = ServiceItem()
    reopened.set_from_service(json.loads(stored_json, cls=OpenLPJSONDecoder), service_dir, version=3)

    assert reopened.name == 'portadas'
    assert reopened.title == 'Resistir al diablo'
    assert reopened.service_item_type is ServiceItemType.Image
    reopened_png = reopened.slides[0]['path']
    assert reopened_png.exists() and reopened_png.parent == service_dir
    assert reopened_png.read_bytes() == png_bytes(16, 9)  # the image travelled inside the service
    assert reopened.is_capable(ItemCapabilities.CanPreview)


def test_the_service_manager_writes_the_png_and_its_thumbnail_into_the_service_file(item, tmp_path):
    """``ServiceManager.get_write_file_list`` is what decides which files go into the .osz."""
    from openlp.core.ui.servicemanager import ServiceManager
    original = build(item, 2)
    manager = MagicMock()
    manager.service_items = [{'service_item': original}]

    write_list, missing = ServiceManager.get_write_file_list(manager)

    names = {str(target) for _, target in write_list}
    assert f'{original.slides[0]["file_hash"]}.png' in names
    assert missing == []
    assert 'thumbnails/one.png' in names
