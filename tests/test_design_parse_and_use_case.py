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
"""Parsing a designer's reply and the ``DesignCoverWithAI`` use case, with fake designers (no network)."""
import json
import time

import pytest
from contrib.plugins.portadas.application.design_cover import DesignCoverWithAI
from contrib.plugins.portadas.application.design_parse import parse_design_reply
from contrib.plugins.portadas.application.ports import CoverDesigner, DesignError, DesignProposal, UnusableReply
from contrib.plugins.portadas.domain.cover import Cover, IconKind

GOOD_HTML = ('<html><head><style>body{background:#123456;color:#fff}.title-main{font-size:90px}</style></head>'
             '<body class="{{empty_fields}}"><div class="title-main">{{title_main}}</div>'
             '<div class="icon">{{icon}}</div></body></html>')
GOOD_SVG = '<svg viewBox="0 0 8 8" fill="none" stroke="currentColor"><path d="M1 1 L7 7"/></svg>'


def reply(html=GOOD_HTML, icon=GOOD_SVG, notes='warm sunrise'):
    return json.dumps({'html': html, 'icon_svg': icon, 'notes': notes})


# --- parsing ------------------------------------------------------------------------------------------------------

def test_a_plain_json_reply_is_parsed():
    proposal = parse_design_reply(reply())

    assert proposal == DesignProposal(GOOD_HTML, GOOD_SVG, 'warm sunrise')


@pytest.mark.parametrize('wrap', ['```json\n{}\n```', '```\n{}\n```', 'Here you go:\n```json\n{}\n```\nEnjoy!',
                                  'Sure! {}', '  \n{}\n  '])
def test_fences_and_chatter_around_the_json_are_tolerated(wrap):
    assert parse_design_reply(wrap.replace('{}', reply())).template_html == GOOD_HTML


def test_a_missing_or_null_icon_and_notes_are_fine():
    proposal = parse_design_reply(json.dumps({'html': GOOD_HTML, 'icon_svg': None}))

    assert proposal.icon_svg is None and proposal.notes == ''
    assert parse_design_reply(json.dumps({'html': GOOD_HTML, 'icon_svg': '  '})).icon_svg is None


def test_notes_are_shortened():
    assert len(parse_design_reply(reply(notes='n' * 5000)).notes) <= 1000


@pytest.mark.parametrize('text', ['', 'no json here', '{"html": ', '[1, 2]', '{"icon_svg": "<svg/>"}', '{"html": 5}',
                                  '{"html": ""}', '{"html": "<b/>", "icon_svg": 5}', None, 42])
def test_unusable_replies_raise_a_design_error(text):
    with pytest.raises(DesignError):
        parse_design_reply(text)


def test_a_truncated_reply_says_so():
    with pytest.raises(DesignError, match='cut off|valid'):
        parse_design_reply('{"html": "<div>' + 'a' * 100)


# --- the use case --------------------------------------------------------------------------------------------------

class FakeDesigner(CoverDesigner):
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def design(self, request):
        self.requests.append(request)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, DesignProposal) else parse_design_reply(item)


def cover():
    return Cover.from_raw('Resistir', id='c1', subtitle='Una serie')


def test_a_good_design_is_returned_sanitised_with_its_icon():
    designer = FakeDesigner(reply())

    designed = DesignCoverWithAI(designer).design(cover(), 'warm')

    assert designed.template_html.startswith('<!DOCTYPE html>') and '{{title_main}}' in designed.template_html
    assert designed.icon.kind is IconKind.INLINE_SVG and designed.icon.value.startswith('<svg')
    assert designed.notes == 'warm sunrise' and designed.repaired is False
    assert len(designer.requests) == 1 and 'warm' in designer.requests[0].user_prompt


def test_apply_to_puts_the_design_on_the_cover():
    designed = DesignCoverWithAI(FakeDesigner(reply())).design(cover())

    result = designed.apply_to(cover())

    assert result.custom_template_html == designed.template_html and result.icon == designed.icon
    assert result.title_main == 'Resistir' and result.id == 'c1'


def test_a_design_without_an_icon_keeps_the_cover_icon():
    original = cover()
    designed = DesignCoverWithAI(FakeDesigner(reply(icon=None))).design(original)

    assert designed.icon is None
    assert designed.apply_to(original).icon == original.icon


def test_malicious_html_ends_up_sanitised():
    evil = GOOD_HTML.replace('<div class="icon">', '<script>alert(1)</script><iframe src="https://evil.test"></iframe>'
                             '<img src="https://evil.test/x.png"><div class="icon" onclick="x()">')

    designed = DesignCoverWithAI(FakeDesigner(reply(html=evil))).design(cover())

    for needle in ('<script', 'iframe', 'evil.test', 'onclick', 'alert'):
        assert needle not in designed.template_html


def test_a_hostile_icon_is_sanitised_or_dropped_never_passed_through():
    evil_svg = '<svg viewBox="0 0 8 8"><script>alert(1)</script><image href="https://evil.test/a.png"/>' \
               '<path d="M1 1"/></svg>'

    designed = DesignCoverWithAI(FakeDesigner(reply(icon=evil_svg))).design(cover())

    assert designed.icon is None or ('script' not in designed.icon.value and 'evil.test' not in designed.icon.value)


def test_a_rejected_template_gets_exactly_one_repair_round_with_the_violations():
    bad = GOOD_HTML.replace('{{title_main}}', 'Texto fijo')  # hard-coded text and no title placeholder
    designer = FakeDesigner(reply(html=bad), reply())

    designed = DesignCoverWithAI(designer).design(cover(), 'warm')

    assert designed.repaired is True and len(designer.requests) == 2
    repair = designer.requests[1]
    assert repair.system_prompt == designer.requests[0].system_prompt
    assert repair.user_prompt.startswith(designer.requests[0].user_prompt)
    assert 'rejected' in repair.user_prompt and 'title_main' in repair.user_prompt
    assert 'Texto fijo' in repair.user_prompt  # the previous answer is sent back


def test_two_rejections_end_in_a_clear_error_after_one_repair():
    bad = reply(html=GOOD_HTML.replace('{{title_main}}', 'Texto fijo'))
    designer = FakeDesigner(bad, bad, bad)

    with pytest.raises(DesignError, match='could not be made safe'):
        DesignCoverWithAI(designer).design(cover())

    assert len(designer.requests) == 2 and len(designer.replies) == 1


def test_an_unparseable_first_reply_is_repaired_too():
    designer = FakeDesigner('sorry, I cannot do JSON', reply())

    designed = DesignCoverWithAI(designer).design(cover())

    assert designed.repaired is True and 'valid JSON' in designer.requests[1].user_prompt


def test_an_unusable_icon_is_repaired_and_then_dropped_without_losing_the_template():
    bad_icon = '<svg><text>hello</text></svg>'
    designer = FakeDesigner(reply(icon=bad_icon), reply(icon=bad_icon))

    designed = DesignCoverWithAI(designer).design(cover())

    assert designed.icon is None and designed.repaired is True and designed.template_html
    assert 'icon' in designer.requests[1].user_prompt


def test_provider_errors_propagate_without_a_repair_round():
    designer = FakeDesigner(DesignError('The provider is busy.'))

    with pytest.raises(DesignError, match='busy'):
        DesignCoverWithAI(designer).design(cover())

    assert len(designer.requests) == 1


def test_a_provider_error_during_the_repair_round_propagates():
    bad = reply(html='<div>Texto fijo</div>')
    designer = FakeDesigner(bad, DesignError('The provider is busy.'))

    with pytest.raises(DesignError, match='busy'):
        DesignCoverWithAI(designer).design(cover())


def test_a_non_proposal_from_the_designer_is_an_error():
    class Broken(CoverDesigner):
        def design(self, request):
            return 'not a proposal'

    with pytest.raises(DesignError):
        DesignCoverWithAI(Broken()).design(cover())


def test_two_unusable_replies_in_a_row_end_in_a_clear_error():
    designer = FakeDesigner('nope', 'still nope')

    with pytest.raises(DesignError, match='could not be made safe'):
        DesignCoverWithAI(designer).design(cover())

    assert len(designer.requests) == 2


def test_a_designed_cover_renders_with_our_text(tmp_path):
    from contrib.plugins.portadas.application.create_cover import CreateCoverFromTemplate
    from contrib.plugins.portadas.application.icon_catalog import IconCatalog
    from contrib.plugins.portadas.application.template_catalog import TemplateCatalog

    from .fakes import FakeRenderer, InMemoryRepository
    creator = CreateCoverFromTemplate(TemplateCatalog(), IconCatalog(), FakeRenderer(), InMemoryRepository(tmp_path))
    original = Cover.from_raw('Resistir <b>ya</b>', id='c9')
    designed = DesignCoverWithAI(FakeDesigner(reply())).design(original)

    html, _ = creator.compose(designed.apply_to(original))

    assert 'Resistir &lt;b&gt;ya&lt;/b&gt;' in html and '<svg' in html and '{{' not in html


def test_a_bad_icon_then_a_failed_repair_keeps_the_good_first_template():
    bad_icon = '<svg><text>hello</text></svg>'
    designer = FakeDesigner(reply(icon=bad_icon), reply(html='<div>Texto fijo</div>'))

    designed = DesignCoverWithAI(designer).design(cover())

    assert designed.template_html and designed.icon is None and designed.repaired is False
    assert len(designer.requests) == 2


def test_a_hostile_deeply_nested_reply_is_a_rejection_not_a_crash():
    deep = reply(html='<div>' * 5000 + '{{title_main}}' + '</div>' * 5000)
    designer = FakeDesigner(deep, deep)

    with pytest.raises(DesignError, match='could not be made safe'):
        DesignCoverWithAI(designer).design(cover())


# --- T15a / SEC-002: linear parsing and a reply cap ------------------------------------------------------------------

def test_a_fence_followed_by_a_huge_run_of_spaces_is_parsed_in_linear_time():
    started = time.perf_counter()
    with pytest.raises(UnusableReply):
        parse_design_reply('```' + ' ' * 200_000)

    assert time.perf_counter() - started < 1.0


@pytest.mark.parametrize('hostile', ['```a' * 60_000, '``` \n' * 40_000, '```' + '\n' * 200_000 + 'x'])
def test_other_fence_shaped_inputs_stay_fast(hostile):
    started = time.perf_counter()
    with pytest.raises(UnusableReply):
        parse_design_reply(hostile)

    assert time.perf_counter() - started < 1.0


def test_a_reply_beyond_the_cap_is_refused_before_parsing():
    with pytest.raises(UnusableReply, match='too long'):
        parse_design_reply(reply() + ' ' * 600_000)


def test_the_second_fence_is_still_found_after_an_empty_one():
    text = 'intro\n```\n```\nthen\n```json\n' + reply() + '\n```\nbye'

    assert parse_design_reply(text).template_html == GOOD_HTML


# --- suggested text -------------------------------------------------------------------------------------------------

from contrib.plugins.portadas.application.design_text import STAND_IN_TITLE  # noqa: E402

SUGGESTION = {'title_main': 'Firmes ante la prueba', 'title_accent': 'con fe', 'subtitle': 'Una serie\nsobre firmeza'}


def suggest_reply(suggested=SUGGESTION, **extra):
    return json.dumps({'html': GOOD_HTML, 'icon_svg': GOOD_SVG, 'notes': 'n', 'suggested_text': suggested, **extra})


def verses_only_cover():
    return Cover.from_raw(STAND_IN_TITLE, id='c1', key_verse='Santiago 4:7', readings=['Efesios 6:11-12'])


def test_the_suggested_text_object_is_kept_by_the_parser_and_other_values_are_dropped():
    assert parse_design_reply(suggest_reply()).suggested_text == SUGGESTION
    assert parse_design_reply(suggest_reply(suggested='text')).suggested_text is None
    assert parse_design_reply(reply()).suggested_text is None


def test_in_suggest_mode_a_valid_suggestion_is_returned_cleaned_and_the_design_is_kept():
    designer = FakeDesigner(suggest_reply({'title_main': '  Firmes   ante la prueba ', 'title_accent': '',
                                           'subtitle': 'Una serie\n\nsobre firmeza'}))

    designed = DesignCoverWithAI(designer).design(verses_only_cover(), None, suggest_text=True)

    assert designed.suggested_text.title_main == 'Firmes ante la prueba'
    assert designed.suggested_text.title_accent is None
    assert designed.suggested_text.subtitle == 'Una serie\nsobre firmeza'
    assert designed.suggestion_problem == '' and designed.template_html
    assert 'suggested_text' in designer.requests[0].system_prompt


def test_the_cover_keeps_the_typed_text_when_the_design_is_applied():
    designed = DesignCoverWithAI(FakeDesigner(suggest_reply())).design(verses_only_cover(), None, suggest_text=True)

    applied = designed.apply_to(verses_only_cover())

    assert applied.title_main == STAND_IN_TITLE  # the editor, not the cover, decides where suggested text goes
    assert applied.custom_template_html == designed.template_html


def test_without_suggest_mode_any_suggested_text_is_ignored():
    designed = DesignCoverWithAI(FakeDesigner(suggest_reply())).design(cover(), 'warm')

    assert designed.suggested_text is None and designed.suggestion_problem == ''


@pytest.mark.parametrize('suggested', [
    {'title_main': 'x' * 81},
    {'title_main': 'Bien', 'subtitle': 'x' * 241},
    {'title_main': 'Bien', 'title_accent': 'y' * 81},
    {'title_main': 'Con\x00control'},
    {'title_main': 'Con​invisible'},
    {'title_main': '<b>Marca</b>'},
    {'title_main': 'Bien', 'subtitle': 'a > b'},
    {'title_main': ''},
    {'title_main': '   ', 'subtitle': 'Solo subtítulo'},
    {'title_accent': 'Sin título'},
    {'title_main': 5},
    {'title_main': 'Bien', 'subtitle': ['no', 'texto']},
], ids=lambda value: str(value)[:40])
def test_an_invalid_suggestion_is_rejected_with_a_message_and_the_design_still_applies(suggested):
    designed = DesignCoverWithAI(FakeDesigner(suggest_reply(suggested))).design(
        verses_only_cover(), None, suggest_text=True)

    assert designed.suggested_text is None
    assert designed.suggestion_problem
    assert designed.template_html and designed.icon is not None


@pytest.mark.parametrize('raw', [None, 'text', ['a']])
def test_a_missing_or_non_object_suggestion_in_suggest_mode_is_reported(raw):
    designed = DesignCoverWithAI(FakeDesigner(suggest_reply(raw))).design(
        verses_only_cover(), None, suggest_text=True)

    assert designed.suggested_text is None and designed.suggestion_problem


def test_the_suggestion_of_the_repair_round_is_the_one_used():
    bad_html = GOOD_HTML.replace('{{title_main}}', 'Texto fijo')  # hard-coded text and no title placeholder
    designer = FakeDesigner(suggest_reply({'title_main': 'Primero'}, html=bad_html), suggest_reply())

    designed = DesignCoverWithAI(designer).design(verses_only_cover(), None, suggest_text=True)

    assert designed.repaired and designed.suggested_text.title_main == 'Firmes ante la prueba'
    assert 'suggested_text' in designer.requests[1].system_prompt
