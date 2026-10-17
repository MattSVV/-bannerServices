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
"""Use case: ask an AI for a cover design and return only what survives the sanitizers."""
import dataclasses
import re
from dataclasses import dataclass

from ..domain.cover import IconKind, IconRef
from ..security.html_policy import sanitize_svg, sanitize_template
from .create_cover import CUSTOM_REQUIRED
from .design_parse import parse_design_reply
from .design_prompt import build_repair_prompt, build_request
from .ports import DesignError, DesignProposal, DesignRequest, UnusableReply

_EMPTY_SVG = re.compile(r'<svg[^>]*>\s*</svg>')


@dataclass(frozen=True)
class DesignedCover:
    """
    A sanitised AI design.

    :param template_html: the sanitised template document (placeholders still in it).
    :param icon: an inline-SVG ``IconRef``, or ``None`` when the AI drew none (or its drawing was unusable).
    :param notes: the AI's short remark.
    :param repaired: True when the first answer was rejected and the repair round produced this one.
    """
    template_html: str
    icon: IconRef = None
    notes: str = ''
    repaired: bool = False

    def apply_to(self, cover):
        """Return ``cover`` with this design: its custom template and, when the AI drew one, its icon."""
        return dataclasses.replace(cover, custom_template_html=self.template_html,
                                   icon=self.icon if self.icon is not None else cover.icon)


class DesignCoverWithAI:
    """
    Calls a ``CoverDesigner``, sanitises the answer and, when it is rejected, asks once more with the violations.

    :param designer: a ``CoverDesigner``. The call blocks: run ``design`` on a worker thread.
    """

    def __init__(self, designer):
        self.designer = designer

    def design(self, cover, style_hint=None):
        """
        :returns: a ``DesignedCover``.
        :raises DesignError: when the provider fails, or the template is still rejected after one repair round.
        """
        request = build_request(cover, style_hint)
        outcome = self._attempt(request)
        if outcome.template is not None and outcome.icon_ok:
            return outcome.result(repaired=False)
        repair = DesignRequest(request.system_prompt, build_repair_prompt(
            request.user_prompt, outcome.raw, outcome.problems))
        second = self._attempt(repair)
        if second.template is None:
            reasons = '; '.join(second.problems[:3])
            raise DesignError(f'The AI design could not be made safe after one correction ({reasons}). '
                              'Try again or change the style hint.')
        return second.result(repaired=True)  # an icon that is still unusable is dropped, the template is kept

    def _attempt(self, request):
        try:
            reply = self.designer.design(request)
        except UnusableReply as error:
            return _Outcome(str(error), None, None, False, '', [str(error)])
        if not isinstance(reply, DesignProposal):
            raise DesignError('The AI provider returned an unusable answer.')
        return _Outcome.of(reply)

    @staticmethod
    def parse(text):
        """Parse a raw model answer (exposed for adapters and tests)."""
        return parse_design_reply(text)


class _Outcome:
    """The sanitised parts of one proposal and the problems found."""

    def __init__(self, raw, template, icon, icon_ok, notes, problems):
        self.raw, self.template, self.icon, self.icon_ok, self.notes, self.problems = (
            raw, template, icon, icon_ok, notes, problems)

    @classmethod
    def of(cls, proposal):
        problems = []
        result = sanitize_template(proposal.template_html, CUSTOM_REQUIRED)
        template = result.html if result.accepted else None
        if template is None:
            problems += [violation.message for violation in result.violations if violation.fatal]
        icon, icon_ok = None, True
        if proposal.icon_svg:
            svg = sanitize_svg(proposal.icon_svg)  # AI icons never get the uploaded-PNG option
            if svg.accepted and _EMPTY_SVG.fullmatch(svg.html):
                icon_ok = False
                problems.append('icon_svg: the icon draws nothing (text and unsupported elements are removed)')
            elif svg.accepted:
                icon = IconRef(IconKind.INLINE_SVG, svg.html)
            else:
                icon_ok = False
                problems += ['icon_svg: ' + violation.message for violation in svg.violations if violation.fatal]
        raw = f'{{"html": {proposal.template_html!r}, "icon_svg": {proposal.icon_svg!r}}}'
        return cls(raw, template, icon, icon_ok, proposal.notes, problems or ['the answer was unusable'])

    def result(self, repaired):
        return DesignedCover(self.template, self.icon, self.notes, repaired)
