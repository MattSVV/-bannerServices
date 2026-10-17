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
"""Loads templates (``<id>/template.html`` + ``<id>/manifest.json``) from a directory."""
import json
from dataclasses import dataclass
from pathlib import Path

from ..domain.cover import SLUG_PATTERN
from ..domain.errors import DomainError
from ..domain.templating import TemplateError, TemplateManifest, validate_placeholders

BUILTIN_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'templates'
_MAX_FILE_BYTES = 512 * 1024


@dataclass(frozen=True)
class Template:
    """A loaded template: its manifest and HTML source."""
    manifest: TemplateManifest
    html: str


class TemplateCatalog:
    """A read-only catalog of templates stored one per folder under ``root`` (built-ins by default)."""

    def __init__(self, root=None):
        self.root = Path(root) if root is not None else BUILTIN_TEMPLATES_DIR

    def list(self):
        """Return the manifests of every valid template, sorted by id. Broken folders are skipped."""
        manifests = []
        for folder in sorted(self.root.iterdir()) if self.root.is_dir() else ():
            if folder.is_dir() and SLUG_PATTERN.match(folder.name):
                try:
                    manifests.append(self.load(folder.name).manifest)
                except DomainError:
                    continue
        return tuple(manifests)

    def load(self, template_id):
        """
        Load and validate one template.

        :raises DomainError: when the id is unsafe or unknown, or the files are missing or inconsistent.
        """
        if not isinstance(template_id, str) or not SLUG_PATTERN.match(template_id):
            raise TemplateError('The template id may only use lowercase letters, digits and hyphens.')
        folder = self.root / template_id
        try:
            data = json.loads(self._read(folder / 'manifest.json'))
        except (OSError, ValueError) as error:
            raise TemplateError(f'The manifest of template "{template_id}" cannot be read.') from error
        manifest = TemplateManifest.from_dict(data)
        if manifest.id != template_id:
            raise TemplateError(f'The manifest id "{manifest.id}" does not match its folder "{template_id}".')
        try:
            html = self._read(folder / 'template.html')
        except OSError as error:
            raise TemplateError(f'The template.html of "{template_id}" cannot be read.') from error
        validate_placeholders(html, manifest.required)
        return Template(manifest, html)

    @staticmethod
    def _read(path):
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise OSError('file too large')
        return path.read_text(encoding='utf-8')
