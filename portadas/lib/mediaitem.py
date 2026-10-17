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
"""
Library tab of the Portadas plugin.

Lists the saved covers (thumbnail and title, newest first), lets the user create, edit, delete and export them, and
builds image service items so the base class handles Preview, Go Live, Add to Service and drag and drop.
"""
import logging
import re
import unicodedata
from pathlib import Path

from openlp.core.common.applocation import AppLocation
from openlp.core.common.i18n import translate
from openlp.core.common.settings import Settings
from openlp.core.lib import ServiceItemContext, build_icon, check_item_selected, create_thumb, validate_thumb
from openlp.core.lib.mediamanageritem import MediaManagerItem
from openlp.core.lib.serviceitem import ItemCapabilities
from openlp.core.lib.ui import create_widget_action
from openlp.core.ui.icons import UiIcons
from PyQt5 import QtCore, QtGui, QtWidgets

from ..application.ports import RepositoryError
from .editform import CoverEditForm
from .services import build_services

log = logging.getLogger(__name__)

LIST_ICON_SIZE = QtCore.QSize(88, 50)
_UNSAFE_FILE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def display_title(cover):
    """The title shown in the list and in the service: the main title followed by the accent title."""
    return ' '.join(part for part in (cover.title_main, cover.title_accent) if part)


def file_name_for(cover, suffix='.png'):
    """A file name made from the cover's title that is safe on every platform."""
    name = ' '.join(_UNSAFE_FILE_CHARS.sub(' ', display_title(cover)).split()).strip(' .')
    return (name or cover.id) + suffix


def _fold(text):
    """Lower-case ``text`` and drop accents, so that 'Esperanza' matches 'esperánza'."""
    decomposed = unicodedata.normalize('NFD', text.casefold())
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def register_shortcut_defaults():
    """
    OpenLP lists the default keyboard shortcuts of its own plugins in ``core/common/settings.py``. A community plugin
    has to register those of its list view itself, or creating the list view's actions raises ``KeyError``. This runs
    when the media item is created, because ``QKeySequence`` needs a ``QApplication``.
    """
    Settings.extend_default_settings({
        'shortcuts/listViewPortadasDeleteItem': [QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Delete)],
        'shortcuts/listViewPortadasPreviewItem': [QtGui.QKeySequence(QtCore.Qt.Key_Return),
                                                  QtGui.QKeySequence(QtCore.Qt.Key_Enter)],
        'shortcuts/listViewPortadasLiveItem': [QtGui.QKeySequence(QtCore.Qt.SHIFT + QtCore.Qt.Key_Return),
                                               QtGui.QKeySequence(QtCore.Qt.SHIFT + QtCore.Qt.Key_Enter)],
        'shortcuts/listViewPortadasServiceItem': [QtGui.QKeySequence(QtCore.Qt.Key_Plus),
                                                  QtGui.QKeySequence(QtCore.Qt.Key_Equal)],
    })


class PortadasMediaItem(MediaManagerItem):
    """Media manager item listing the saved covers."""
    log.info('Portadas media item loaded')

    def __init__(self, parent, plugin):
        self.icon_path = 'images/image'
        self.services = None  # built on ``initialise`` (production) or injected (tests)
        register_shortcut_defaults()
        super().__init__(parent, plugin)

    # --- setup ----------------------------------------------------------------------------------------------------
    def setup_item(self):
        # One service item per cover, like custom slides: selecting several covers adds several items.
        self.single_service_item = False
        self.quick_preview_allowed = True
        self.has_search = True

    def required_icons(self):
        super().required_icons()
        self.has_import_icon = False
        self.has_file_icon = False
        self.add_to_service_item = False

    def retranslate_ui(self):
        super().retranslate_ui()
        self.retranslate_export_text()
        if hasattr(self, 'filter_edit'):
            self.filter_edit.setPlaceholderText(translate('PortadasPlugin.MediaItem', 'Filter by title...'))

    def add_end_header_bar(self):
        self.retranslate_export_text()
        self.export_action = self.toolbar.add_toolbar_action(
            'portadasExportAction', text=self.export_text, icon=UiIcons().download, tooltip=self.export_tooltip,
            triggers=self.on_export_click)

    def retranslate_export_text(self):
        self.export_text = translate('PortadasPlugin.MediaItem', 'Export PNG...')
        self.export_tooltip = translate('PortadasPlugin.MediaItem', 'Save the selected cover as a PNG image.')

    def add_custom_context_actions(self):
        create_widget_action(self.list_view, separator=True)
        create_widget_action(self.list_view, text=self.export_text, icon=UiIcons().download,
                             triggers=self.on_export_click)

    def add_list_view_to_toolbar(self):
        super().add_list_view_to_toolbar()
        self.filter_edit = QtWidgets.QLineEdit(self)
        self.filter_edit.setObjectName('portadasFilterEdit')
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setPlaceholderText(translate('PortadasPlugin.MediaItem', 'Filter by title...'))
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.page_layout.insertWidget(self.page_layout.indexOf(self.list_view), self.filter_edit)

    def initialise(self):
        """Build the services (first call only), then list the covers."""
        self.ensure_services()
        self.list_view.setIconSize(LIST_ICON_SIZE)
        self.load_list()

    def ensure_services(self):
        if self.services is None:
            self.services = build_services(AppLocation.get_section_data_path(self.settings_section))
        return self.services

    def shutdown(self):
        """Release the renderer. Called when the plugin is finalised."""
        if self.services is not None:
            self.services.close()

    def on_focus(self):
        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    # --- user feedback (overridable so tests never open a modal window) -----------------------------------------------
    def show_error(self, title, message):
        QtWidgets.QMessageBox.critical(self, title, message)

    def confirm_delete(self, count):
        answer = QtWidgets.QMessageBox.question(
            self, translate('PortadasPlugin.MediaItem', 'Delete covers'),
            translate('PortadasPlugin.MediaItem', 'Are you sure you want to delete the {count} selected cover(s)? '
                      'This cannot be undone.').format(count=count),
            defaultButton=QtWidgets.QMessageBox.No)
        return answer == QtWidgets.QMessageBox.Yes

    def choose_export_path(self, default_name):
        """Ask where to save the PNG. The dialog itself asks before overwriting. Returns a ``Path`` or ``None``."""
        name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, translate('PortadasPlugin.MediaItem', 'Export PNG'), default_name,
            translate('PortadasPlugin.MediaItem', 'PNG image (*.png)'))
        if not name:
            return None
        path = Path(name)
        return path if path.suffix else path.with_suffix('.png')

    def create_edit_form(self):
        return CoverEditForm(self, self.ensure_services())

    # --- the list ---------------------------------------------------------------------------------------------------
    def load_list(self, covers=None, target_group=None):
        """Fill the list from the repository (newest first), keeping the selected cover selected."""
        self.save_auto_select_id()
        self.list_view.clear()
        if covers is None:
            try:
                covers = self.ensure_services().repository.list()
            except RepositoryError as error:
                self.show_error(translate('PortadasPlugin.MediaItem', 'Covers'), str(error))
                covers = []
        for cover in covers:
            list_item = QtWidgets.QListWidgetItem(display_title(cover))
            list_item.setData(QtCore.Qt.UserRole, cover.id)
            list_item.setToolTip(self._tooltip(cover))
            icon = self._thumbnail_icon(cover.id)
            if icon is not None:
                list_item.setIcon(icon)
            self.list_view.addItem(list_item)
            if cover.id == self.auto_select_id:
                self.list_view.setCurrentItem(list_item)
        self.auto_select_id = -1
        self.apply_filter()
        log.info('Portadas library loaded: %d cover(s)', self.list_view.count())

    @staticmethod
    def _tooltip(cover):
        lines = [display_title(cover)]
        if cover.subtitle:
            lines.append(cover.subtitle)
        return '\n'.join(lines)

    def apply_filter(self, text=None):
        """Hide the covers whose title does not contain the filter text (case and accents ignored)."""
        needle = _fold(self.filter_edit.text() if text is None else text).strip()
        for row in range(self.list_view.count()):
            list_item = self.list_view.item(row)
            list_item.setHidden(bool(needle) and needle not in _fold(list_item.text()))

    def _thumbnail_path(self, cover_id):
        return self.services.thumbnail_dir / f'{cover_id}.png'

    def _thumbnail_icon(self, cover_id):
        """The cached thumbnail of a cover as an icon, created or refreshed from its PNG; ``None`` without image."""
        try:
            png_path = self.services.repository.png_path(cover_id)
        except RepositoryError:
            return None
        thumbnail = self._ensure_thumbnail(cover_id, png_path)
        return None if thumbnail is None else build_icon(thumbnail)

    def _ensure_thumbnail(self, cover_id, png_path):
        thumbnail = self._thumbnail_path(cover_id)
        try:
            if not validate_thumb(png_path, thumbnail):
                thumbnail.parent.mkdir(parents=True, exist_ok=True)
                create_thumb(png_path, thumbnail, size=LIST_ICON_SIZE)
        except OSError as error:
            log.warning('Could not create the thumbnail of cover "%s": %s', cover_id, error)
            return None
        return thumbnail if thumbnail.exists() else None

    def _forget_thumbnail(self, cover_id):
        try:
            self._thumbnail_path(cover_id).unlink(missing_ok=True)
        except OSError as error:
            log.warning('Could not remove the thumbnail of cover "%s": %s', cover_id, error)

    def _selected_ids(self):
        return [self.list_view.item(row).data(QtCore.Qt.UserRole) for row in range(self.list_view.count())
                if self.list_view.item(row).isSelected()]

    # --- actions ------------------------------------------------------------------------------------------------------
    def on_new_click(self):
        self._edit(None)

    def on_edit_click(self):
        if not check_item_selected(self.list_view, translate('PortadasPlugin.MediaItem',
                                                             'You must select a cover to edit.')):
            return
        cover_id = self.list_view.currentItem().data(QtCore.Qt.UserRole)
        try:
            cover = self.services.repository.get(cover_id)
        except RepositoryError as error:
            self.show_error(translate('PortadasPlugin.MediaItem', 'Edit cover'), str(error))
            self.load_list()
            return
        self._edit(cover)

    def _edit(self, cover):
        form = self.create_edit_form()
        try:
            form.load_cover(cover)
            accepted = form.exec() == QtWidgets.QDialog.Accepted and form.saved_cover is not None
            saved = form.saved_cover
        finally:
            form.deleteLater()  # the dialog is parented to this item: without this every edit would leak one
        if accepted:
            self._forget_thumbnail(saved.id)
            self.auto_select_id = saved.id
            self.load_list()

    def on_delete_click(self):
        if not check_item_selected(self.list_view, translate('PortadasPlugin.MediaItem',
                                                             'You must select a cover to delete.')):
            return
        cover_ids = self._selected_ids()
        if not cover_ids or not self.confirm_delete(len(cover_ids)):
            return
        for cover_id in cover_ids:
            try:
                self.services.repository.delete(cover_id)
            except RepositoryError as error:
                self.show_error(translate('PortadasPlugin.MediaItem', 'Delete cover'), str(error))
                continue
            self._forget_thumbnail(cover_id)
        self.auto_select_id = -1
        self.load_list()

    def on_export_click(self):
        if not check_item_selected(self.list_view, translate('PortadasPlugin.MediaItem',
                                                             'You must select a cover to export.')):
            return
        cover_id = self.list_view.currentItem().data(QtCore.Qt.UserRole)
        try:
            cover = self.services.repository.get(cover_id)
            destination = self.choose_export_path(file_name_for(cover))
            if destination is None:
                return
            # The file dialog already asked the user to confirm replacing an existing file.
            self.services.repository.export_png(cover_id, destination, overwrite=destination.exists())
        except RepositoryError as error:
            self.show_error(translate('PortadasPlugin.MediaItem', 'Export PNG'), str(error))

    # --- service integration ----------------------------------------------------------------------------------------
    def generate_slide_data(self, service_item, *, item=None, remote=False, context=ServiceItemContext.Service,
                            **kwargs):
        """
        Build an image service item from the selected cover: the stored PNG is the slide, so the service file bundles
        the image and the cover still opens after it is deleted from the library.

        :param service_item: The service item to fill.
        :param item: The list item (or model index) of the cover; defaults to the current one.
        :param remote: Triggered from a remote; no dialog is shown then.
        :param context: Why the item is being built (unused).
        :returns: True when the service item is ready, False when there is nothing to add.
        """
        cover_id = self._get_id_of_item_to_generate(item, None)
        if not cover_id:
            return False
        try:
            cover = self.services.repository.get(cover_id)
            png_path = self.services.repository.png_path(cover_id)
        except RepositoryError as error:
            if not remote:
                self.show_error(translate('PortadasPlugin.MediaItem', 'Cover not found'), str(error))
            return False
        if not service_item.slides:  # appending to an existing item keeps its title
            service_item.title = display_title(cover)
        for capability in (ItemCapabilities.CanMaintain, ItemCapabilities.CanPreview, ItemCapabilities.CanLoop,
                           ItemCapabilities.CanAppend, ItemCapabilities.CanEditTitle,
                           ItemCapabilities.HasThumbnails, ItemCapabilities.ProvidesOwnTheme):
            service_item.add_capability(capability)
        service_item.theme = -1  # a cover is a finished image: no theme background behind it
        service_item.add_from_image(png_path, file_name_for(cover), self._ensure_thumbnail(cover_id, png_path))
        return True
