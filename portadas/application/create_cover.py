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
"""Use cases that turn raw user input into a rendered, stored cover."""
from dataclasses import dataclass

from ..domain.cover import Cover, CoverError, IconKind
from ..domain.templating import render_cover
from ..security.html_policy import sanitize_svg


@dataclass(frozen=True)
class CreatedCover:
    """A stored cover plus the fields that did not fit (see ``RenderResult.overflow``)."""
    cover: Cover
    overflow: tuple = ()


class CreateCoverFromTemplate:
    """
    Builds a ``Cover`` from raw input, fills a template with it, renders it and stores the result.

    :param templates: a ``TemplateCatalog``.
    :param icons: an ``IconCatalog``.
    :param renderer: a ``CoverRenderer``.
    :param repository: a ``CoverRepository``.
    """

    def __init__(self, templates, icons, renderer, repository):
        self.templates = templates
        self.icons = icons
        self.renderer = renderer
        self.repository = repository

    def build_cover(self, title_main, **fields):
        """Validate raw input (see ``Cover.from_raw``). :raises DomainError: with a presentable message."""
        return Cover.from_raw(title_main, **fields)

    def compose(self, cover):
        """
        Return ``(html, base_dir)`` ready for a ``CoverRenderer``: the template filled with the cover's text and
        icon. Useful for asynchronous previews. :raises DomainError: for an unknown template or unusable icon.
        """
        template = self.templates.load(cover.template_id)
        html = render_cover(template.html, cover, self._icon_svg(cover.icon),
                            required=template.manifest.required)
        return html, self.templates.root / cover.template_id

    def preview(self, title_main, **fields):
        """Validate and render without storing. Returns ``(cover, RenderResult)``."""
        cover = self.build_cover(title_main, **fields)
        html, base_dir = self.compose(cover)
        return cover, self.renderer.render(html, base_dir)

    def execute(self, title_main, **fields):
        """
        Validate, render and store a cover; passing an existing ``id`` replaces that cover.

        :returns: a ``CreatedCover``.
        :raises DomainError: for invalid input, :raises RenderError: when rendering fails,
            :raises RepositoryError: when storing fails. Nothing is stored unless all steps succeed.
        """
        cover, result = self.preview(title_main, **fields)
        self.repository.save(cover, result.png_bytes)
        return CreatedCover(cover, tuple(result.overflow))

    def _icon_svg(self, icon):
        if icon.kind is IconKind.BUILTIN:
            return self.icons.svg(icon.value)
        if icon.kind is IconKind.INLINE_SVG:
            result = sanitize_svg(icon.value)
            if not result.accepted:
                reasons = '; '.join(violation.message for violation in result.violations)
                raise CoverError(f'The icon SVG was rejected: {reasons}')
            return result.html
        raise CoverError('Uploaded icons are not supported yet.')
