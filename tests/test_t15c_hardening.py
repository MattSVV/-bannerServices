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
"""T15c: plain text for messages and tooltips, no web-API search, and a first-use notice before data leaves."""
import pytest
from contrib.plugins.portadas.lib.ai_settings import DATA_NOTICE_KEY
from contrib.plugins.portadas.lib.editform import CoverEditForm
from contrib.plugins.portadas.lib.mediaitem import PortadasMediaItem
from contrib.plugins.portadas.lib.settingstab import PortadasSettingsTab
from PyQt5 import QtCore, QtWidgets

from .fakes import make_services
from .library_support import item, make_cover, services  # noqa: F401 - fixtures
from .test_edit_form import Form
from .test_edit_form_ai import FakeDesigner

RICH = '<b>Click</b> <img src="http://evil.example/x.png"> <a href="http://evil.example">here</a>'


@pytest.fixture
def boxes(monkeypatch):
    """Every QMessageBox shown: its text format and text. ``exec`` is replaced so nothing blocks."""
    shown = []

    def fake_exec(box):
        shown.append((box.textFormat(), box.text()))
        return QtWidgets.QMessageBox.Yes

    monkeypatch.setattr(QtWidgets.QMessageBox, 'exec', fake_exec)
    return shown


# --- plain text -----------------------------------------------------------------------------------------------------

def test_the_editor_error_box_is_plain_text(qtbot, openlp_env, tmp_path, boxes):
    form = Form(None, make_services(tmp_path))
    qtbot.addWidget(form)

    CoverEditForm.show_error(form, 'Title', RICH)

    assert boxes == [(QtCore.Qt.PlainText, RICH)]


def test_the_library_boxes_are_plain_text(item, boxes):  # noqa: F811
    PortadasMediaItem.show_error(item, 'Title', RICH)
    assert PortadasMediaItem.confirm_delete(item, 2) is True

    assert [text_format for text_format, _ in boxes] == [QtCore.Qt.PlainText, QtCore.Qt.PlainText]


def test_the_settings_warning_is_plain_text(qtbot, openlp_env, boxes):
    tab = PortadasSettingsTab(None, 'portadas', 'Covers', None)
    qtbot.addWidget(tab)

    PortadasSettingsTab.show_warning(tab, RICH)

    assert boxes == [(QtCore.Qt.PlainText, RICH)]


def test_the_key_status_never_renders_markup(qtbot, openlp_env):
    tab = PortadasSettingsTab(None, 'portadas', 'Covers', None)
    qtbot.addWidget(tab)

    assert tab.key_status_label.textFormat() == QtCore.Qt.PlainText


def test_a_cover_tooltip_cannot_render_markup(item):  # noqa: F811
    item.load_list([make_cover('evil', RICH.replace('\n', ' ')[:70], 1, subtitle='<h1>big</h1>')])

    tip = item.list_view.item(0).toolTip()

    assert '<h1>' not in tip and '<img' not in tip and '&lt;' in tip
    assert QtCore.Qt.mightBeRichText(tip)  # rich text on purpose: Qt has no plain mode for tooltips, so it is escaped


# --- search ---------------------------------------------------------------------------------------------------------

def test_the_library_does_not_advertise_a_search_it_does_not_implement(item):  # noqa: F811
    assert item.has_search is False
    with pytest.raises(NotImplementedError):
        item.search('x')  # the upstream default: with has_search on, the web API would turn this into a 500


# --- first-use notice -----------------------------------------------------------------------------------------------

class AskingForm(Form):
    answers = None

    def confirm_data_use(self, destination):
        self.asked = getattr(self, 'asked', []) + [destination]
        return self.answers.pop(0) if self.answers else True


@pytest.fixture
def ai_form(qtbot, openlp_env, tmp_path):
    designer = FakeDesigner(gated=False)
    svc = make_services(tmp_path)
    svc.designer_factory = lambda: designer
    form = AskingForm(None, svc)
    qtbot.addWidget(form)
    form.load_cover(None)
    form.title_main_edit.setText('Resistir')
    form.key_verse_edit.setText('Santiago 4:7')
    form.designer = designer
    return form


def settings_flag(openlp_env):
    return bool(openlp_env.value(DATA_NOTICE_KEY))


def test_the_first_design_asks_before_sending_and_remembers_the_yes(ai_form, qtbot, openlp_env):
    ai_form.answers = [True]
    assert settings_flag(openlp_env) is False

    ai_form.design_button.click()
    qtbot.waitUntil(lambda: ai_form._design_job is None, timeout=5000)

    assert len(ai_form.asked) == 1 and len(ai_form.designer.requests) == 1
    assert settings_flag(openlp_env) is True

    ai_form.design_button.click()
    qtbot.waitUntil(lambda: ai_form._design_job is None and len(ai_form.designer.requests) == 2, timeout=5000)

    assert len(ai_form.asked) == 1  # not asked again


def test_declining_sends_nothing_and_asks_again_next_time(ai_form, openlp_env):
    ai_form.answers = [False, False]

    ai_form.design_button.click()
    ai_form.design_button.click()

    assert ai_form.designer.requests == [] and ai_form._design_job is None
    assert len(ai_form.asked) == 2 and settings_flag(openlp_env) is False
    assert ai_form.design_button.isEnabled()


def test_the_notice_names_where_the_text_goes_and_is_a_real_box_by_default(qtbot, openlp_env, tmp_path, boxes):
    form = CoverEditForm(None, make_services(tmp_path), thumbnails=False)
    qtbot.addWidget(form)

    assert CoverEditForm.confirm_data_use(form, 'llm.example.org') is True

    (text_format, text), = boxes
    assert text_format == QtCore.Qt.PlainText and 'llm.example.org' in text
