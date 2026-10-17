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
The cover editor: fields, template and icon pickers, and a live preview.

The dialog only talks to the application layer through ``PortadasServices``: ``creator`` (the use case) validates,
composes and stores; ``renderer`` draws the preview. One render runs at a time. Edits restart a debounce timer; when
a render finishes after the user kept typing, its result is dropped and a fresh render starts, so the preview never
shows stale content for long and renders never pile up.
"""
import logging
import uuid
from pathlib import Path

from openlp.core.common.i18n import translate
from PyQt5 import QtCore, QtGui, QtWidgets

from ..application.icon_upload import icon_from_png_bytes, icon_from_svg_text
from ..application.ports import RenderError, RepositoryError
from ..domain.cover import DEFAULT_ICON, DEFAULT_TEMPLATE_ID, MAX_RAW_READINGS, MAX_READINGS, IconKind, IconRef
from ..domain.errors import DomainError
from ..domain.scripture import MAX_REFERENCE_CHARS, parse_reference
from ..security.html_policy import sanitize_svg
from .iconimage import MAX_PNG_FILE_BYTES, prepare_png_icon, svg_pixmap

log = logging.getLogger(__name__)

PREVIEW_DELAY_MS = 400
THUMB_SIZE = QtCore.QSize(160, 90)
ICON_SIZE = QtCore.QSize(48, 48)
MAX_SVG_FILE_BYTES = 200 * 1024  # an SVG file is read up to this size; the icon rules reject larger ones anyway

# Placeholder names reported by the renderer -> the form field that holds that text.
OVERFLOW_FIELDS = ('label', 'title_main', 'title_accent', 'subtitle', 'key_verse', 'readings_label', 'readings')


class CoverEditForm(QtWidgets.QDialog):
    """Create or edit one cover. After ``exec()`` returned ``Accepted``, ``saved_cover`` holds the stored cover."""

    def __init__(self, parent, services, thumbnails=True):
        super().__init__(parent)
        self.services = services
        self.preview_delay_ms = PREVIEW_DELAY_MS
        self.saved_cover = None
        self._cover_id = None
        self._created_at = None
        self._loading = False
        self._busy = False
        self._saving = False
        self._closed = False
        self._preview_dirty = False
        self._preview_image = None
        self._custom_icon_item = None
        self._thumb_queue = []
        self._want_thumbnails = thumbnails
        self.warning_labels = {}
        self._setup_ui()
        self._fill_pickers()
        self.preview_timer = QtCore.QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._preview_due)
        self.retranslate_ui()

    # --- construction ----------------------------------------------------------------------------------------------
    def _setup_ui(self):
        self.setObjectName('PortadasCoverEditForm')
        self.resize(1180, 720)
        layout = QtWidgets.QHBoxLayout(self)
        form_column = QtWidgets.QVBoxLayout()
        layout.addLayout(form_column, 5)
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form_column.addLayout(self.form_layout)

        self.label_edit = QtWidgets.QLineEdit()
        self.title_main_edit = QtWidgets.QLineEdit()
        self.title_accent_edit = QtWidgets.QLineEdit()
        self.subtitle_edit = QtWidgets.QPlainTextEdit()
        self.subtitle_edit.setFixedHeight(60)
        self.key_verse_edit = QtWidgets.QLineEdit()
        self.readings_label_edit = QtWidgets.QLineEdit()
        self.readings_edit = QtWidgets.QPlainTextEdit()
        self.readings_edit.setFixedHeight(90)
        self.key_verse_error = self._message_label('errorLabel')
        self.readings_error = self._message_label('errorLabel')
        self.form_labels = {}
        for name, widget in (('label', self.label_edit), ('title_main', self.title_main_edit),
                             ('title_accent', self.title_accent_edit), ('subtitle', self.subtitle_edit),
                             ('key_verse', self.key_verse_edit), ('readings_label', self.readings_label_edit),
                             ('readings', self.readings_edit)):
            self.form_labels[name] = QtWidgets.QLabel()
            self.warning_labels[name] = self._message_label('warningLabel')
            box = QtWidgets.QVBoxLayout()
            box.setSpacing(2)
            box.addWidget(widget)
            if name == 'key_verse':
                box.addWidget(self.key_verse_error)
            if name == 'readings':
                box.addWidget(self.readings_error)
            box.addWidget(self.warning_labels[name])
            self.form_layout.addRow(self.form_labels[name], box)
            widget.setObjectName(f'{name}_edit')
            widget.textChanged.connect(self._edited)

        self.template_label = QtWidgets.QLabel()
        self.template_list = QtWidgets.QListWidget()
        self.template_list.setViewMode(QtWidgets.QListView.IconMode)
        self.template_list.setFlow(QtWidgets.QListView.LeftToRight)
        self.template_list.setWrapping(False)
        self.template_list.setMovement(QtWidgets.QListView.Static)
        self.template_list.setIconSize(THUMB_SIZE)
        self.template_list.setFixedHeight(THUMB_SIZE.height() + 52)
        self.template_list.setObjectName('template_list')
        self.template_list.currentItemChanged.connect(self._edited)
        form_column.addWidget(self.template_label)
        form_column.addWidget(self.template_list)

        self.icon_label = QtWidgets.QLabel()
        self.icon_list = QtWidgets.QListWidget()
        self.icon_list.setViewMode(QtWidgets.QListView.IconMode)
        self.icon_list.setMovement(QtWidgets.QListView.Static)
        self.icon_list.setResizeMode(QtWidgets.QListView.Adjust)
        self.icon_list.setIconSize(ICON_SIZE)
        self.icon_list.setFixedHeight(ICON_SIZE.height() * 2 + 30)
        self.icon_list.setObjectName('icon_list')
        self.icon_list.currentItemChanged.connect(self._edited)
        self.upload_button = QtWidgets.QPushButton()
        self.upload_button.setObjectName('upload_button')
        self.upload_button.clicked.connect(self.on_upload_icon)
        form_column.addWidget(self.icon_label)
        form_column.addWidget(self.icon_list)
        form_column.addWidget(self.upload_button, 0, QtCore.Qt.AlignLeft)

        preview_column = QtWidgets.QVBoxLayout()
        layout.addLayout(preview_column, 6)
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setObjectName('preview_label')
        self.preview_label.setMinimumSize(480, 270)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.preview_label.setStyleSheet('background: #1b1b1b; color: #cccccc;')
        self.status_label = QtWidgets.QLabel()
        self.status_label.setObjectName('status_label')
        self.status_label.setWordWrap(True)
        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save |
                                                     QtWidgets.QDialogButtonBox.Cancel)
        self.save_button = self.button_box.button(QtWidgets.QDialogButtonBox.Save)
        self.save_button.setObjectName('save_button')
        self.button_box.accepted.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
        preview_column.addWidget(self.preview_label, 1)
        preview_column.addWidget(self.status_label)
        preview_column.addWidget(self.button_box)

    @staticmethod
    def _message_label(object_name):
        label = QtWidgets.QLabel()
        label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setStyleSheet('color: #b00020;' if object_name == 'errorLabel' else 'color: #9a6700;')
        label.setVisible(False)
        return label

    def retranslate_ui(self):
        """Set every user-visible string."""
        t = translate
        self.setWindowTitle(t('PortadasPlugin.EditForm', 'Cover'))
        titles = {
            'label': t('PortadasPlugin.EditForm', 'Label:'),
            'title_main': t('PortadasPlugin.EditForm', 'Main title:'),
            'title_accent': t('PortadasPlugin.EditForm', 'Accent title:'),
            'subtitle': t('PortadasPlugin.EditForm', 'Subtitle:'),
            'key_verse': t('PortadasPlugin.EditForm', 'Key verse:'),
            'readings_label': t('PortadasPlugin.EditForm', 'Readings heading:'),
            'readings': t('PortadasPlugin.EditForm', 'Readings (one per line):'),
        }
        for name, text in titles.items():
            self.form_labels[name].setText(text)
        self.template_label.setText(t('PortadasPlugin.EditForm', 'Template:'))
        self.icon_label.setText(t('PortadasPlugin.EditForm', 'Icon:'))
        self.upload_button.setText(t('PortadasPlugin.EditForm', 'Upload...'))
        self.upload_button.setToolTip(t('PortadasPlugin.EditForm', 'Use your own SVG or PNG file as the icon.'))
        self.save_button.setText(t('PortadasPlugin.EditForm', 'Save'))
        self.button_box.button(QtWidgets.QDialogButtonBox.Cancel).setText(t('PortadasPlugin.EditForm', 'Cancel'))
        self.key_verse_edit.setPlaceholderText(t('PortadasPlugin.EditForm', 'For example: Santiago 4:7'))
        self.readings_edit.setPlaceholderText(t('PortadasPlugin.EditForm', 'For example: Efesios 6:11-12'))
        self.preview_label.setText(t('PortadasPlugin.EditForm', 'The preview appears here.'))

    def _fill_pickers(self):
        for manifest in self.services.templates.list():
            item = QtWidgets.QListWidgetItem(manifest.name)
            item.setData(QtCore.Qt.UserRole, manifest.id)
            item.setToolTip(manifest.description)
            cached = self.services.template_thumbnails.get(manifest.id)
            if cached:
                item.setIcon(self._thumbnail_icon(cached))
            self.template_list.addItem(item)
        for icon_id in self.services.icons.ids():
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, IconRef(IconKind.BUILTIN, icon_id))
            item.setToolTip(icon_id.replace('-', ' '))
            try:
                item.setIcon(QtGui.QIcon(svg_pixmap(self.services.icons.svg(icon_id))))
            except DomainError:
                continue
            self.icon_list.addItem(item)

    # --- loading and reading values --------------------------------------------------------------------------------
    def load_cover(self, cover=None):
        """Fill the form from ``cover`` (``None`` for a new cover) and start the preview."""
        self._loading = True
        try:
            self._cover_id = None if cover is None else cover.id
            self._created_at = None if cover is None else cover.created_at
            self.label_edit.setText('' if cover is None else cover.label)
            self.readings_label_edit.setText('' if cover is None else cover.readings_label)
            self.title_main_edit.setText('' if cover is None else cover.title_main)
            self.title_accent_edit.setText('' if cover is None or cover.title_accent is None else cover.title_accent)
            self.subtitle_edit.setPlainText('' if cover is None or cover.subtitle is None else cover.subtitle)
            self.key_verse_edit.setText('' if cover is None or cover.key_verse is None else str(cover.key_verse))
            self.readings_edit.setPlainText('' if cover is None else '\n'.join(str(item) for item in cover.readings))
            if cover is None:
                self.label_edit.setText(self._default('label'))
                self.readings_label_edit.setText(self._default('readings_label'))
            self._select_template(DEFAULT_TEMPLATE_ID if cover is None else cover.template_id)
            self._select_icon(DEFAULT_ICON if cover is None else cover.icon)
        finally:
            self._loading = False
        self._validate_inline()
        self._schedule_preview()

    @staticmethod
    def _default(field):
        from ..domain.cover import DEFAULT_LABEL, DEFAULT_READINGS_LABEL
        return {'label': DEFAULT_LABEL, 'readings_label': DEFAULT_READINGS_LABEL}[field]

    def values(self):
        """The raw user input, as the keyword arguments of the use case (``Cover.from_raw``)."""
        return {
            'title_main': self.title_main_edit.text(), 'label': self.label_edit.text(),
            'title_accent': self.title_accent_edit.text(), 'subtitle': self.subtitle_edit.toPlainText(),
            'key_verse': self.key_verse_edit.text(), 'readings': self.readings_edit.toPlainText().splitlines(),
            'readings_label': self.readings_label_edit.text(), 'icon': self.icon(),
            'template_id': self.template_id(), 'id': self._cover_id, 'created_at': self._created_at,
        }

    def template_id(self):
        item = self.template_list.currentItem()
        return DEFAULT_TEMPLATE_ID if item is None else item.data(QtCore.Qt.UserRole)

    def icon(self):
        item = self.icon_list.currentItem()
        return DEFAULT_ICON if item is None else item.data(QtCore.Qt.UserRole)

    def _select_template(self, template_id):
        for row in range(self.template_list.count()):
            if self.template_list.item(row).data(QtCore.Qt.UserRole) == template_id:
                self.template_list.setCurrentRow(row)
                return
        self.template_list.setCurrentRow(-1)

    def _select_icon(self, icon_ref):
        if icon_ref.kind is IconKind.BUILTIN:
            for row in range(self.icon_list.count()):
                if self.icon_list.item(row).data(QtCore.Qt.UserRole) == icon_ref:
                    self.icon_list.setCurrentRow(row)
                    return
        self._set_custom_icon(icon_ref)

    def _set_custom_icon(self, icon_ref):
        """Show a non-bundled icon (an upload) as the first entry of the picker and select it."""
        if icon_ref.kind is IconKind.INLINE_SVG:
            # A stored icon may have been edited by hand: keep only what passes the icon rules, or fall back.
            safe = sanitize_svg(icon_ref.value, allow_png_image=True)
            if not safe.accepted:
                log.warning('The cover icon was rejected by the icon rules; using the default icon.')
                self._set_status(translate('PortadasPlugin.EditForm', 'The cover icon is not valid and was replaced '
                                           'by the default icon.'), error=True)
                self._select_icon(DEFAULT_ICON)
                return
            icon_ref = IconRef(IconKind.INLINE_SVG, safe.html)
        if self._custom_icon_item is None:
            self._custom_icon_item = QtWidgets.QListWidgetItem()
            self._custom_icon_item.setText(translate('PortadasPlugin.EditForm', 'Uploaded'))
            self.icon_list.insertItem(0, self._custom_icon_item)
        self._custom_icon_item.setData(QtCore.Qt.UserRole, icon_ref)
        self._custom_icon_item.setIcon(QtGui.QIcon(svg_pixmap(icon_ref.value)))
        self.icon_list.setCurrentItem(self._custom_icon_item)

    # --- validation ------------------------------------------------------------------------------------------------
    def _edited(self, *_):
        if self._loading:
            return
        self._validate_inline()
        self._schedule_preview()

    def _validate_inline(self):
        """Show errors for the key verse and each reading line as the user types. Returns True when none."""
        verse_error = self._reference_error(self.key_verse_edit.text())
        self._show(self.key_verse_error, verse_error)
        errors = []
        lines = [(number, line) for number, line in enumerate(self.readings_edit.toPlainText().splitlines(), 1)
                 if line.strip()]
        for number, line in lines:
            problem = self._reference_error(line)
            if problem:
                errors.append(translate('PortadasPlugin.EditForm', 'Line {number}: {problem}').format(
                    number=number, problem=problem))
        if len(lines) > min(MAX_READINGS, MAX_RAW_READINGS):
            errors.append(translate('PortadasPlugin.EditForm', 'A cover can have at most {count} readings.').format(
                count=MAX_READINGS))
        self._show(self.readings_error, '\n'.join(errors))
        return not verse_error and not errors

    @staticmethod
    def _reference_error(text):
        text = text.strip()
        if not text:
            return ''
        if len(text) > MAX_REFERENCE_CHARS:
            return translate('PortadasPlugin.EditForm', 'A reference must be at most {count} characters.').format(
                count=MAX_REFERENCE_CHARS)
        try:
            parse_reference(text)
        except DomainError as error:
            return str(error)
        return ''

    @staticmethod
    def _show(label, text):
        label.setText(text)
        label.setVisible(bool(text))

    def _first_problem(self):
        """Return ``(cover, None)`` for valid input or ``(None, message)`` with the rule that is broken."""
        try:
            return self.services.creator.build_cover(**self.values()), None
        except DomainError as error:
            return None, str(error)

    # --- live preview ----------------------------------------------------------------------------------------------
    def _schedule_preview(self):
        self.preview_timer.start(self.preview_delay_ms)

    def _preview_due(self):
        if self._closed:
            return
        self._preview_dirty = True
        self._pump()

    def _pump(self):
        """Start the next render if none is running: the preview first, then the lazy template thumbnails."""
        if self._busy or self._saving or self._closed:
            return
        if self._preview_dirty:
            self._preview_dirty = False
            self._start_preview()
        elif self._thumb_queue:
            self._start_thumbnail(self._thumb_queue.pop(0))
        self._update_buttons()

    def _start_preview(self):
        cover, problem = self._first_problem()
        if cover is None or not self._validate_inline():
            self._set_status(problem or translate('PortadasPlugin.EditForm', 'Fix the marked fields to see the '
                                                  'preview.'), error=True)
            return
        try:
            html, base_dir = self.services.creator.compose(cover)
            self._busy = True
            self._set_status(translate('PortadasPlugin.EditForm', 'Rendering the preview...'))
            self.services.renderer.render_async(html, base_dir, self._preview_done, self._preview_failed)
        except (DomainError, RenderError) as error:
            self._busy = False
            self._set_status(str(error), error=True)

    def _preview_done(self, result):
        if self._closed:  # the dialog is gone: its widgets may already be deleted
            return
        self._busy = False
        if self._preview_dirty:  # the user kept editing: this image is stale, draw the new one instead
            self._pump()
            return
        self._show_image(result.png_bytes)
        self._set_status(translate('PortadasPlugin.EditForm', 'Preview up to date.'))
        for name in OVERFLOW_FIELDS:
            self._show(self.warning_labels[name], translate(
                'PortadasPlugin.EditForm', 'This text does not fit; shorten it or choose another template.')
                if name in result.overflow else '')
        if self._want_thumbnails and not self._thumb_queue and self._missing_thumbnails():
            self._thumb_queue = self._missing_thumbnails()
        self._pump()
        self._update_buttons()

    def _preview_failed(self, error):
        if self._closed:
            return
        self._busy = False
        self._set_status(translate('PortadasPlugin.EditForm', 'The preview could not be rendered: {error}').format(
            error=error), error=True)
        self._pump()
        self._update_buttons()

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        self.status_label.setStyleSheet('color: #b00020;' if error else '')

    def _show_image(self, png_bytes):
        pixmap = QtGui.QPixmap()
        if pixmap.loadFromData(png_bytes, 'PNG'):
            self._preview_image = pixmap
            self._scale_preview()

    def _scale_preview(self):
        if self._preview_image is not None:
            self.preview_label.setPixmap(self._preview_image.scaled(
                self.preview_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._scale_preview()

    def _update_buttons(self):
        self.save_button.setEnabled(not self._busy and not self._saving)

    # --- template thumbnails (lazy, one render at a time, cached for the session) ----------------------------------
    def _missing_thumbnails(self):
        return [self.template_list.item(row).data(QtCore.Qt.UserRole) for row in range(self.template_list.count())
                if self.template_list.item(row).data(QtCore.Qt.UserRole) not in self.services.template_thumbnails]

    def _start_thumbnail(self, template_id):
        try:
            sample = self.services.creator.build_cover(
                translate('PortadasPlugin.EditForm', 'Sample title'), template_id=template_id,
                title_accent=translate('PortadasPlugin.EditForm', 'in two colours'),
                subtitle=translate('PortadasPlugin.EditForm', 'A short subtitle'), key_verse='Juan 3:16',
                readings=['Salmo 23:1-6'], icon=DEFAULT_ICON)
            html, base_dir = self.services.creator.compose(sample)
            self._busy = True
            self.services.renderer.render_async(
                html, base_dir, lambda result: self._thumbnail_done(template_id, result),
                lambda error: self._thumbnail_done(template_id, None))
        except (DomainError, RenderError) as error:
            self._busy = False
            log.warning('No thumbnail for template "%s": %s', template_id, error)
            self.services.template_thumbnails[template_id] = b''

    def _thumbnail_done(self, template_id, result):
        self.services.template_thumbnails[template_id] = result.png_bytes if result is not None else b''
        if self._closed:  # keep the cached image, but never touch the deleted widgets
            return
        self._busy = False
        for row in range(self.template_list.count()):
            item = self.template_list.item(row)
            if item.data(QtCore.Qt.UserRole) == template_id and result is not None:
                item.setIcon(self._thumbnail_icon(result.png_bytes))
        self._pump()
        self._update_buttons()

    @staticmethod
    def _thumbnail_icon(png_bytes):
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(png_bytes, 'PNG')
        return QtGui.QIcon(pixmap.scaled(THUMB_SIZE, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    # --- icon upload -----------------------------------------------------------------------------------------------
    def choose_icon_file(self):
        """Ask for an SVG or PNG file. Returns a ``Path`` or ``None`` when cancelled. Overridable in tests."""
        name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, translate('PortadasPlugin.EditForm', 'Choose an icon'), '',
            translate('PortadasPlugin.EditForm', 'Icons (*.svg *.png)'))
        return Path(name) if name else None

    def on_upload_icon(self):
        """Let the user pick an SVG or PNG file and use it as the icon, after the safety checks."""
        path = self.choose_icon_file()
        if path is None:
            return
        try:
            icon = self._icon_from_file(Path(path))
        except (DomainError, OSError) as error:
            self.show_error(translate('PortadasPlugin.EditForm', 'Icon rejected'), str(error))
            return
        self._set_custom_icon(icon)

    @staticmethod
    def _icon_from_file(path):
        suffix = path.suffix.lower()
        if suffix == '.svg':
            with open(path, 'rb') as handle:
                raw = handle.read(MAX_SVG_FILE_BYTES + 1)
            if len(raw) > MAX_SVG_FILE_BYTES:
                raise DomainError(translate('PortadasPlugin.EditForm', 'The SVG file is too large.'))
            return icon_from_svg_text(raw.decode('utf-8', 'replace'))
        if suffix == '.png':
            if path.stat().st_size > MAX_PNG_FILE_BYTES:
                raise DomainError(translate('PortadasPlugin.EditForm', 'The image file is too large.'))
            return icon_from_png_bytes(prepare_png_icon(path))
        raise DomainError(translate('PortadasPlugin.EditForm', 'Choose an SVG or PNG file.'))

    # --- saving ----------------------------------------------------------------------------------------------------
    def show_error(self, title, message):
        """Show an error to the user. Overridable in tests."""
        QtWidgets.QMessageBox.critical(self, title, message)

    def on_save(self):
        """Validate, render and store the cover through the use case; close the dialog on success."""
        if self._busy or self._saving:
            return
        if self._cover_id is None:
            self._cover_id = uuid.uuid4().hex  # one id per dialog: a repeated save replaces the cover, never copies it
        self._saving = True
        self.preview_timer.stop()
        self._update_buttons()
        try:
            cover, problem = self._first_problem()
            if cover is None:
                self.show_error(translate('PortadasPlugin.EditForm', 'The cover is not valid'), problem)
                return
            try:
                created = self.services.creator.execute(**self.values())
            except (DomainError, RenderError, RepositoryError) as error:
                self.show_error(translate('PortadasPlugin.EditForm', 'The cover could not be saved'), str(error))
                return
            self.saved_cover = created.cover
            self.accept()
        finally:
            self._saving = False
            if not self._closed:
                self._update_buttons()
                if self._preview_dirty:
                    self._pump()

    def done(self, result):
        """Stop the timer so a late tick never starts a render for a closed dialog; ignore Cancel while saving."""
        if self._saving and result != QtWidgets.QDialog.Accepted:
            return
        self._closed = True
        self.preview_timer.stop()
        self._preview_dirty = False
        self._thumb_queue = []
        super().done(result)
