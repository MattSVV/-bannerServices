#!/usr/bin/env python3
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
End-to-end check of the cover pipeline, headless, with the production adapters (real QtWebEngine renderer, real file
repository, real library tab). For every built-in template it:

1. creates a cover through the plugin's own use case and checks the PNG is 1920x1080;
2. lists it in the library tab (the media item reads the repository);
3. builds the image service item the tab would hand to the service and checks title, slide and capabilities;
4. adds it to a real ``ServiceItem`` list the way the service manager stores it (``get_service_repr``).

It fails when any Portadas log record at ERROR level or above was emitted. Usage (with OpenLP's interpreter)::

    python scripts/e2e_flow.py <openlp-data-dir>

The plugin must already be linked at ``<openlp-data-dir>/contrib/plugins/portadas`` (``scripts/dev-install.sh``).
Nothing outside ``<openlp-data-dir>`` is touched; OpenLP's settings go to a temporary file inside it.
"""
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class _ErrorCollector(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def main(data_dir):
    data_dir = Path(data_dir)
    sys.path.insert(0, str(data_dir))
    from PyQt5 import QtCore, QtGui, QtWebEngineWidgets, QtWidgets  # noqa: F401 - WebEngine before the QApplication
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv[:1])

    from contrib.plugins.portadas.lib.mediaitem import PortadasMediaItem
    from contrib.plugins.portadas.lib.services import build_services
    from openlp.core.common.actions import ActionList
    from openlp.core.common.registry import Registry
    from openlp.core.common.settings import Settings
    from openlp.core.lib.plugin import StringContent
    from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem, ServiceItemType

    collector = _ErrorCollector()
    logging.getLogger().addHandler(collector)
    failures = []

    def check(condition, message):
        print(('ok   ' if condition else 'FAIL ') + message)
        if not condition:
            failures.append(message)

    # The bits of OpenLP's global state the library tab needs: a Registry holding a file-backed Settings.
    ActionList.instance, ActionList.shortcut_map = None, {}
    Registry.create()
    Settings.set_filename(str(data_dir / 'e2e-settings.ini'))
    settings = Settings()
    settings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings.init_default_shortcuts()
    Registry().register('settings', settings)
    Registry().register('settings_thread', settings)
    Registry().register('application', app)

    class Plugin:
        name = 'portadas'
        icon_path = 'images/image'
        name_strings = {'singular': 'Cover', 'plural': 'Covers'}

        @staticmethod
        def get_string(kind):
            if kind == StringContent.VisibleName:
                return {'title': 'Covers'}
            return {'title': str(kind), 'tooltip': f'{kind} tooltip'}

    class Item(PortadasMediaItem):
        errors = []

        def show_error(self, title, message):
            self.errors.append((title, message))

    services = build_services(data_dir / 'portadas')
    item = Item(None, Plugin())
    item.services = services
    item.initialise()

    template_ids = [manifest.id for manifest in services.templates.list()]
    check(len(template_ids) >= 3, f'the catalog offers {len(template_ids)} built-in templates')
    service = []  # what the service manager would hold
    for number, template_id in enumerate(template_ids, 1):
        title = f'Prueba {template_id}'
        created = services.creator.execute(title, title_accent='extremo a extremo', subtitle='Comprobacion',
                                           key_verse='Santiago 4:7', readings=['Efesios 6:11-12'],
                                           template_id=template_id)
        image = QtGui.QImage.fromData(services.repository.png_path(created.cover.id).read_bytes(), 'PNG')
        check((image.width(), image.height()) == (1920, 1080), f'{template_id}: rendered a 1920x1080 PNG')

        item.load_list(services.repository.list())
        titles = [item.list_view.item(row).text() for row in range(item.list_view.count())]
        check(any(title in text for text in titles), f'{template_id}: listed in the library tab')
        check(item.list_view.count() == number, f'{template_id}: library holds {number} cover(s)')

        row = next(row for row, text in enumerate(titles) if title in text)
        item.list_view.setCurrentRow(row)
        service_item = ServiceItem(item.plugin)
        service_item.add_icon()
        built = item.generate_slide_data(service_item)
        check(built, f'{template_id}: the tab built a service item')
        check(service_item.service_item_type is ServiceItemType.Image and len(service_item.slides) == 1,
              f'{template_id}: one image slide')
        check(service_item.title.startswith(title) or title in service_item.title, f'{template_id}: service title')
        check(service_item.is_capable(ItemCapabilities.CanPreview), f'{template_id}: can be previewed')
        service.append(service_item.get_service_repr(True))

    check(len(service) == len(template_ids) and all(entry['header']['name'] == 'portadas' and len(entry['data']) == 1
                                                    for entry in service),
          f'{len(service)} portadas items are in the service')
    check(not Item.errors, f'the tab showed no error box ({Item.errors})')
    portadas_errors = [r for r in collector.records if 'portadas' in r.name.lower() or 'portadas' in r.pathname.lower()]
    check(not portadas_errors, f'no Portadas error was logged ({[r.getMessage() for r in portadas_errors]})')

    item.shutdown()
    services.close()
    del app
    if failures:
        print(f'E2E FAILED: {len(failures)} check(s)', file=sys.stderr)
        return 1
    print(f'E2E OK: {len(template_ids)} templates -> cover -> render -> library -> service')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
