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
"""The cover editor dialog: filling, validation, live preview, icon upload and saving."""
import pytest
from contrib.plugins.portadas.domain.cover import Cover, IconKind, IconRef
from contrib.plugins.portadas.lib.editform import CoverEditForm
from PyQt5 import QtCore, QtWidgets

from .fakes import FakeRenderer, make_services, png_bytes

SVG = '<svg viewBox="0 0 8 8" fill="none" stroke="currentColor"><path d="M1 1 L7 7"/></svg>'


class Form(CoverEditForm):
    """The dialog with its message boxes and file chooser replaced, so no test ever blocks on a modal window."""

    def __init__(self, *args, **kwargs):
        self.errors = []
        self.chosen_file = None
        kwargs.setdefault('thumbnails', False)
        super().__init__(*args, **kwargs)
        self.preview_delay_ms = 0

    def show_error(self, title, message):
        self.errors.append((title, message))

    def choose_icon_file(self):
        return self.chosen_file

    def confirm_data_use(self, destination):
        return True


@pytest.fixture
def services(tmp_path):
    return make_services(tmp_path)


@pytest.fixture
def form(qtbot, openlp_env, services):
    dialog = Form(None, services)
    qtbot.addWidget(dialog)
    return dialog


def sample_cover(**overrides):
    values = dict(title_main='Resistir', title_accent='al diablo', label='MENSAJE', subtitle='Una serie\nsobre firmeza',
                  key_verse='Santiago 4:7', readings=['Efesios 6:11-12', 'Santiago 4:7'], readings_label='LECTURAS',
                  template_id='luz-clara', icon=IconRef(IconKind.BUILTIN, 'dove'), id='abc123')
    values.update(overrides)
    return Cover.from_raw(**values)


def settle(form, qtbot):
    """Let the debounce timer fire; the fake renderer then holds the render until the test finishes it."""
    qtbot.waitUntil(lambda: bool(form.services.renderer.pending) or not form.preview_timer.isActive(), timeout=2000)


# --- filling and round trip ---------------------------------------------------------------------------------------

def test_the_form_fills_from_a_cover_and_round_trips(form):
    cover = sample_cover()

    form.load_cover(cover)
    values = form.values()

    assert form.title_main_edit.text() == 'Resistir'
    assert form.title_accent_edit.text() == 'al diablo'
    assert form.label_edit.text() == 'MENSAJE'
    assert form.subtitle_edit.toPlainText() == 'Una serie\nsobre firmeza'
    assert form.key_verse_edit.text() == 'Santiago 4:7'
    assert form.readings_label_edit.text() == 'LECTURAS'
    assert form.readings_edit.toPlainText() == 'Efesios 6:11-12\nSantiago 4:7'
    assert form.template_id() == 'luz-clara'
    assert form.icon() == cover.icon
    rebuilt = Cover.from_raw(**values)
    assert rebuilt.id == cover.id
    assert rebuilt.created_at == cover.created_at
    assert {f: getattr(rebuilt, f) for f in ('title_main', 'title_accent', 'label', 'subtitle', 'key_verse',
                                               'readings', 'icon', 'template_id', 'readings_label')} == \
        {f: getattr(cover, f) for f in ('title_main', 'title_accent', 'label', 'subtitle', 'key_verse',
                                        'readings', 'icon', 'template_id', 'readings_label')}


def test_a_new_cover_starts_with_defaults_and_no_id(form):
    form.load_cover(None)
    values = form.values()

    assert values['id'] is None
    assert form.label_edit.text() == 'MENSAJE'
    assert form.template_id() == 'noche-dorada'
    assert form.icon().kind is IconKind.BUILTIN


def test_the_pickers_list_every_template_and_bundled_icon(form, services):
    assert form.template_list.count() == len(services.templates.list()) >= 3
    assert form.icon_list.count() >= len(services.icons.ids()) >= 10


# --- inline validation --------------------------------------------------------------------------------------------

def test_a_bad_reading_shows_an_inline_error_for_its_line(form):
    form.load_cover(None)
    form.title_main_edit.setText('Resistir')

    form.readings_edit.setPlainText('Efesios 6:11\nNoExisteLibro 3:1\nSantiago 4:7')

    assert 'Line 2' in form.readings_error.text()
    assert not form.readings_error.isHidden()


def test_a_bad_key_verse_shows_an_inline_error(form):
    form.load_cover(None)

    form.key_verse_edit.setText('Xyz 99:99')

    assert not form.key_verse_error.isHidden()
    assert form.key_verse_error.text()


def test_valid_references_clear_the_errors(form):
    form.load_cover(None)
    form.key_verse_edit.setText('Xyz 99:99')
    form.key_verse_edit.setText('Juan 3:16')

    assert form.key_verse_error.isHidden()


def test_too_many_readings_is_reported(form):
    form.load_cover(None)

    form.readings_edit.setPlainText('\n'.join(['Juan 3:16'] * 13))

    assert not form.readings_error.isHidden()


def test_save_refuses_invalid_input_and_explains_why(form, services):
    form.load_cover(None)
    form.key_verse_edit.setText('Xyz 99:99')
    form.title_main_edit.setText('Resistir')

    form.on_save()

    assert form.errors and 'Key verse' in form.errors[0][1]
    assert services.repository.covers == {}
    assert form.result() != QtWidgets.QDialog.Accepted


def test_save_requires_a_main_title(form):
    form.load_cover(None)

    form.on_save()

    assert form.errors and 'main title' in form.errors[0][1]


# --- live preview -------------------------------------------------------------------------------------------------

def test_editing_triggers_a_single_debounced_render(form, qtbot):
    form.preview_delay_ms = 50
    form.load_cover(None)
    form.title_main_edit.setText('R')
    form.title_main_edit.setText('Re')
    form.title_main_edit.setText('Resistir')

    assert form.services.renderer.pending == []  # nothing yet: the debounce is still running
    qtbot.waitUntil(lambda: len(form.services.renderer.pending) == 1, timeout=2000)
    qtbot.wait(120)

    assert len(form.services.renderer.pending) == 1
    assert 'Resistir' in form.services.renderer.pending[0][0]


def test_the_default_debounce_is_about_400_ms(openlp_env, services):
    assert CoverEditForm(None, services).preview_delay_ms == 400


def test_the_preview_shows_the_rendered_image_and_save_waits_for_it(form, qtbot):
    form.load_cover(sample_cover())
    settle(form, qtbot)

    assert not form.save_button.isEnabled()  # rendering

    form.services.renderer.finish()

    assert form.save_button.isEnabled()
    assert form.preview_label.pixmap() is not None and not form.preview_label.pixmap().isNull()


def test_edits_during_a_render_are_coalesced_and_the_stale_result_is_dropped(form, qtbot):
    form.load_cover(sample_cover())
    settle(form, qtbot)
    first = form.services.renderer.pending
    assert len(first) == 1

    form.title_main_edit.setText('Cambio rapido')
    qtbot.wait(60)
    assert len(form.services.renderer.pending) == 1  # one render at a time: the new one waits

    form.services.renderer.finish()  # the stale render completes and is ignored
    assert not form.save_button.isEnabled()  # a newer render started
    qtbot.waitUntil(lambda: len(form.services.renderer.pending) == 1, timeout=2000)
    assert 'Cambio rapido' in form.services.renderer.pending[0][0]
    form.services.renderer.finish()
    assert form.save_button.isEnabled()


def test_overflow_warnings_appear_next_to_the_affected_fields(form, qtbot):
    form.load_cover(sample_cover())
    settle(form, qtbot)

    form.services.renderer.finish(overflow=('title_main', 'subtitle'))

    assert not form.warning_labels['title_main'].isHidden()
    assert not form.warning_labels['subtitle'].isHidden()
    assert form.warning_labels['key_verse'].isHidden()

    form.title_main_edit.setText('Corto')
    settle(form, qtbot)
    form.services.renderer.finish(overflow=())
    assert form.warning_labels['title_main'].isHidden()


def test_a_render_error_is_shown_without_crashing(form, qtbot):
    form.load_cover(sample_cover())
    settle(form, qtbot)

    form.services.renderer.fail('the render exploded')

    assert 'the render exploded' in form.status_label.text()
    assert form.save_button.isEnabled()


def test_no_render_starts_for_invalid_input(form, qtbot):
    form.load_cover(None)  # empty main title

    qtbot.wait(80)

    assert form.services.renderer.pending == []


# --- saving -------------------------------------------------------------------------------------------------------

def test_save_calls_the_use_case_and_keeps_the_id_of_an_edit(form, services, qtbot):
    cover = sample_cover()
    services.repository.save(cover, png_bytes())
    form.load_cover(cover)
    settle(form, qtbot)
    services.renderer.finish()
    form.title_main_edit.setText('Resistir mejor')
    settle(form, qtbot)
    services.renderer.finish()

    form.on_save()

    saved = services.repository.covers['abc123']
    assert saved.title_main == 'Resistir mejor'
    assert saved.created_at == cover.created_at
    assert list(services.repository.covers) == ['abc123']
    assert form.saved_cover.id == 'abc123'
    assert form.result() == QtWidgets.QDialog.Accepted
    assert form.errors == []


def test_save_of_a_new_cover_creates_a_new_id(form, services):
    form.load_cover(None)
    form.title_main_edit.setText('Nuevo')

    form.on_save()

    assert len(services.repository.covers) == 1
    assert form.saved_cover.id in services.repository.covers


def test_a_render_failure_while_saving_is_shown_in_a_message_box(openlp_env, qtbot, tmp_path):
    services = make_services(tmp_path, renderer=FakeRenderer(fail='render failed'))
    dialog = Form(None, services)
    qtbot.addWidget(dialog)
    dialog.load_cover(None)
    dialog.title_main_edit.setText('Nuevo')

    dialog.on_save()

    assert dialog.errors and 'render failed' in dialog.errors[0][1]
    assert services.repository.covers == {}
    assert dialog.result() != QtWidgets.QDialog.Accepted


def test_a_storage_failure_while_saving_is_shown_in_a_message_box(form, services, monkeypatch):
    from contrib.plugins.portadas.application.ports import RepositoryError

    def broken_save(cover, png):
        raise RepositoryError('disk full')
    monkeypatch.setattr(services.repository, 'save', broken_save)
    form.load_cover(None)
    form.title_main_edit.setText('Nuevo')

    form.on_save()

    assert form.errors and 'disk full' in form.errors[0][1]


def test_cancel_rejects_and_saves_nothing(form, services):
    form.load_cover(None)
    form.title_main_edit.setText('Nuevo')

    form.reject()

    assert services.repository.covers == {}
    assert form.saved_cover is None


# --- templates and icons ------------------------------------------------------------------------------------------

def test_picking_a_template_changes_the_cover_and_restarts_the_preview(form, qtbot):
    form.load_cover(sample_cover(template_id='noche-dorada'))
    settle(form, qtbot)
    form.services.renderer.finish()

    target = next(i for i in range(form.template_list.count())
                  if form.template_list.item(i).data(QtCore.Qt.UserRole) == 'minimal')
    form.template_list.setCurrentRow(target)

    assert form.template_id() == 'minimal'
    qtbot.waitUntil(lambda: len(form.services.renderer.pending) >= 1, timeout=2000)


def test_picking_a_bundled_icon_changes_the_icon(form):
    form.load_cover(None)
    row = next(i for i in range(form.icon_list.count())
               if form.icon_list.item(i).data(QtCore.Qt.UserRole) == IconRef(IconKind.BUILTIN, 'cross'))

    form.icon_list.setCurrentRow(row)

    assert form.icon() == IconRef(IconKind.BUILTIN, 'cross')


def test_uploading_a_clean_svg_selects_it_as_the_icon(form, tmp_path):
    path = tmp_path / 'mine.svg'
    path.write_text(SVG, encoding='utf-8')
    form.chosen_file = path
    form.load_cover(None)

    form.on_upload_icon()

    assert form.icon().kind is IconKind.INLINE_SVG
    assert form.icon().value.startswith('<svg')
    assert form.errors == []


def test_uploading_a_malicious_svg_is_rejected(form, tmp_path):
    path = tmp_path / 'evil.svg'
    path.write_text('<svg onload="alert(1)"><script>alert(1)</script><path d="M0 0"/></svg>', encoding='utf-8')
    form.chosen_file = path
    form.load_cover(None)
    before = form.icon()

    form.on_upload_icon()

    assert form.errors and 'rejected' in form.errors[0][1]
    assert form.icon() == before


def test_uploading_a_png_embeds_it_safely(form, tmp_path):
    from PyQt5 import QtGui
    path = tmp_path / 'logo.png'
    image = QtGui.QImage(600, 300, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('#aa3300'))
    assert image.save(str(path), 'PNG')
    form.chosen_file = path
    form.load_cover(None)

    form.on_upload_icon()

    assert form.errors == []
    assert form.icon().kind is IconKind.INLINE_SVG
    assert 'data:image/png;base64,' in form.icon().value


def test_uploading_something_that_is_not_an_image_is_rejected(form, tmp_path):
    path = tmp_path / 'fake.png'
    path.write_bytes(b'this is not a png')
    form.chosen_file = path
    form.load_cover(None)

    form.on_upload_icon()

    assert form.errors


def test_uploading_a_wrong_extension_is_rejected(form, tmp_path):
    path = tmp_path / 'icon.exe'
    path.write_bytes(b'MZ')
    form.chosen_file = path
    form.load_cover(None)

    form.on_upload_icon()

    assert form.errors


def test_cancelling_the_file_chooser_changes_nothing(form):
    form.chosen_file = None
    form.load_cover(None)
    before = form.icon()

    form.on_upload_icon()

    assert form.errors == [] and form.icon() == before


def test_an_uploaded_icon_survives_a_save_and_reload(form, services, tmp_path):
    path = tmp_path / 'mine.svg'
    path.write_text(SVG, encoding='utf-8')
    form.chosen_file = path
    form.load_cover(None)
    form.title_main_edit.setText('Con icono')
    form.on_upload_icon()

    form.on_save()

    stored = next(iter(services.repository.covers.values()))
    assert stored.icon.kind is IconKind.INLINE_SVG
    form.load_cover(stored)
    assert form.icon() == stored.icon


def test_template_thumbnails_render_lazily_one_at_a_time_and_are_cached(openlp_env, qtbot, tmp_path):
    services = make_services(tmp_path)
    dialog = Form(None, services, thumbnails=True)
    qtbot.addWidget(dialog)
    dialog.load_cover(sample_cover())
    settle(dialog, qtbot)
    assert all(dialog.template_list.item(row).icon().isNull() for row in range(dialog.template_list.count()))

    services.renderer.finish()  # the preview is done: the thumbnails follow, one render at a time

    while services.renderer.pending:
        assert len(services.renderer.pending) == 1
        assert not dialog.save_button.isEnabled()
        services.renderer.finish()
    assert set(services.template_thumbnails) == {m.id for m in services.templates.list()}
    assert all(not dialog.template_list.item(row).icon().isNull() for row in range(dialog.template_list.count()))
    assert dialog.save_button.isEnabled()

    again = Form(None, services, thumbnails=True)
    qtbot.addWidget(again)
    assert all(not again.template_list.item(row).icon().isNull() for row in range(again.template_list.count()))
    again.load_cover(sample_cover())
    settle(again, qtbot)
    services.renderer.finish()
    assert services.renderer.pending == []  # cached: no thumbnail renders this time
