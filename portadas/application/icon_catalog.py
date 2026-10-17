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
"""The bundled SVG icon set (``assets/icons/<slug>.svg``)."""
from pathlib import Path

from ..domain.cover import SLUG_PATTERN
from ..domain.errors import DomainError

BUILTIN_ICONS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'icons'
_MAX_ICON_BYTES = 20000


class IconCatalog:
    """Read-only access to icons stored as ``<slug>.svg`` under ``root`` (built-ins by default)."""

    def __init__(self, root=None):
        self.root = Path(root) if root is not None else BUILTIN_ICONS_DIR

    def ids(self):
        """Return the sorted slugs of the available icons."""
        if not self.root.is_dir():
            return ()
        return tuple(sorted(path.stem for path in self.root.glob('*.svg') if SLUG_PATTERN.match(path.stem)))

    def svg(self, icon_id):
        """
        Return the SVG markup of an icon.

        :raises DomainError: when the id is unsafe, unknown or the file is unusable.
        """
        if not isinstance(icon_id, str) or not SLUG_PATTERN.match(icon_id):
            raise DomainError('The icon name may only use lowercase letters, digits and hyphens.')
        path = self.root / f'{icon_id}.svg'
        try:
            if path.stat().st_size > _MAX_ICON_BYTES:
                raise DomainError(f'The icon "{icon_id}" is too large.')
            return path.read_text(encoding='utf-8').strip()
        except OSError as error:
            raise DomainError(f'Unknown icon "{icon_id}".') from error
