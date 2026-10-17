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
"""The editor's AI design mode: a fake designer drives the busy state, cancel, errors and the saved template."""
import threading

import pytest
from contrib.plugins.portadas.application.ports import CoverDesigner, DesignError, DesignProposal
from contrib.plugins.portadas.domain.cover import IconKind

from .ai_support import GOOD_HTML, GOOD_SVG, KEY
from .fakes import make_services
from .test_edit_form import Form


class FakeDesigner(CoverDesigner):
    """Blocks in ``design`` until the test opens the gate, then answers (or raises) as scripted."""

    def __init__(self, proposal=None, error=None, gated=True):
        self.proposal = proposal or DesignProposal(GOOD_HTML, GOOD_SVG, 'warm')
        self.error = error
        self.gate = threading.Event()
        if not gated:
            self.gate.set()
        self.requests = []
        self.entered = threading.Event()

    def design(self, request):
        self.requests.append(request)
        self.entered.set()
        assert self.gate.wait(10), 'the test never released the designer'
        if self.error is not None:
            raise self.error
        return self.proposal


@pytest.fixture
def designer():
    return FakeDesigner()


@pytest.fixture
def services(tmp_path, designer):
    services = make_services(tmp_path)
    services.designer_factory = lambda: designer
    return services


@pytest.fixture
def form(qtbot, openlp_env, services):
    dialog = Form(None, services)
    qtbot.addWidget(dialog)
    dialog.load_cover(None)
    dialog.title_main_edit.setText('Resistir')
    dialog.key_verse_edit.setText('Santiago 4:7')
    services.renderer.pending.clear()
    return dialog


def start_design(form, qtbot, designer, hint='warm and golden'):
    form.hint_edit.setText(hint)
    form.design_button.click()
    assert designer.entered.wait(5)


def finish_design(form, qtbot, designer):
    designer.gate.set()
    qtbot.waitUntil(lambda: form._design_job is None, timeout=5000)


def test_the_ai_controls_exist_and_cancel_is_hidden_when_idle(form):
    assert form.design_button.isEnabled()
    assert form.cancel_design_button.isHidden()
    assert form.hint_edit.maxLength() == 300


def test_design_shows_a_busy_state_then_applies_the_template_and_icon(form, qtbot, designer, services):
    start_design(form, qtbot, designer)

    assert not form.design_button.isEnabled()
    assert not form.hint_edit.isEnabled()
    assert not form.cancel_design_button.isHidden()
    assert not form.save_button.isEnabled()
    assert 'Designing' in form.status_label.text()

    finish_design(form, qtbot, designer)

    assert form.design_button.isEnabled() and form.cancel_design_button.isHidden()
    assert 'background:#123456' in form.values()['custom_template_html'].replace(' ', '')
    assert form.icon().kind is IconKind.INLINE_SVG
    assert 'warm and golden' in designer.requests[0].user_prompt
    assert 'Resistir' in designer.requests[0].user_prompt
    assert not form.ai_note_label.isHidden()
    form.preview_timer.stop()
    qtbot.waitUntil(lambda: bool(services.renderer.pending) or form._preview_dirty, timeout=2000)


def test_a_second_click_while_designing_is_ignored(form, qtbot, designer):
    start_design(form, qtbot, designer)
    form.on_design()
    form.on_design()

    finish_design(form, qtbot, designer)

    assert len(designer.requests) == 1


def test_cancel_drops_the_outcome_and_restores_the_controls(form, qtbot, designer):
    start_design(form, qtbot, designer)

    form.cancel_design_button.click()
    designer.gate.set()
    qtbot.wait(150)

    assert form._design_job is None
    assert form.values()['custom_template_html'] is None
    assert form.design_button.isEnabled() and form.hint_edit.isEnabled()
    assert form.cancel_design_button.isHidden()
    assert 'cancel' in form.status_label.text().lower()


def test_a_provider_error_is_shown_and_redacted(form, qtbot, designer):
    designer.error = DesignError(f'The provider said no ({KEY}).')
    start_design(form, qtbot, designer)

    finish_design(form, qtbot, designer)

    assert KEY not in form.status_label.text()
    assert 'provider said no' in form.status_label.text()
    assert form.values()['custom_template_html'] is None
    assert form.design_button.isEnabled()


@pytest.mark.parametrize('message', [
    'No API key is saved for openai. Add one in Settings > Configure OpenLP > Covers.',
    'The AI call took too long and was stopped.',
    'The AI design could not be made safe after one correction (script). Try again or change the style hint.',
])
def test_known_failures_reach_the_status_line(form, qtbot, designer, message):
    designer.error = DesignError(message)
    start_design(form, qtbot, designer)

    finish_design(form, qtbot, designer)

    assert message in form.status_label.text()


def test_an_unexpected_error_does_not_leak_its_text(form, qtbot, designer):
    designer.error = RuntimeError(f'secret {KEY}')
    start_design(form, qtbot, designer)

    finish_design(form, qtbot, designer)

    assert KEY not in form.status_label.text() and 'secret' not in form.status_label.text()
    assert 'RuntimeError' in form.status_label.text()


def test_a_designer_factory_error_is_shown_without_starting_a_job(form, services):
    def broken():
        raise DesignError('The server address is empty.')
    services.designer_factory = broken

    form.on_design()

    assert form._design_job is None
    assert 'server address is empty' in form.status_label.text()
    assert form.design_button.isEnabled()


def test_without_a_designer_factory_the_mode_explains_itself(form, services):
    services.designer_factory = None

    form.on_design()

    assert form._design_job is None
    assert 'not available' in form.status_label.text()


def test_an_invalid_cover_is_not_sent_to_the_provider(form, designer):
    form.title_main_edit.setText('')

    form.on_design()

    assert form._design_job is None and designer.requests == []
    assert form.status_label.text()


def test_closing_the_dialog_while_designing_ignores_the_late_result(form, qtbot, designer):
    start_design(form, qtbot, designer)

    form.reject()
    designer.gate.set()
    qtbot.wait(200)
    form._design_done(None)  # a callback that still arrives is dropped without touching the widgets
    form._design_failed('late failure')

    assert form._design_job is None
    assert form.values()['custom_template_html'] is None


def test_save_is_blocked_while_designing(form, qtbot, designer, services):
    start_design(form, qtbot, designer)

    form.on_save()

    assert services.repository.covers == {}
    finish_design(form, qtbot, designer)


def test_saving_persists_the_custom_template(form, qtbot, designer, services):
    start_design(form, qtbot, designer)
    finish_design(form, qtbot, designer)
    form.preview_timer.stop()
    form._busy = False

    form.on_save()

    saved = next(iter(services.repository.covers.values()))
    assert 'background:#123456' in saved.custom_template_html.replace(' ', '')
    assert saved.icon.kind is IconKind.INLINE_SVG


def test_a_stored_ai_cover_loads_its_template_and_can_go_back_to_a_template(form, services):
    from contrib.plugins.portadas.domain.cover import Cover
    cover = Cover.from_raw('Titulo', id='ai1', custom_template_html=GOOD_HTML)

    form.load_cover(cover)

    assert form.values()['custom_template_html'] == cover.custom_template_html
    assert not form.ai_note_label.isHidden()
    form.use_template_button.click()
    assert form.values()['custom_template_html'] is None
    assert form.ai_note_label.isHidden()


def test_picking_a_template_after_a_design_drops_the_design(form, qtbot, designer):
    start_design(form, qtbot, designer)
    finish_design(form, qtbot, designer)
    assert form.values()['custom_template_html'] is not None

    form.template_list.setCurrentRow(1)

    assert form.values()['custom_template_html'] is None
