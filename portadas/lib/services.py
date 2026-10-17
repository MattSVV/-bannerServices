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
Composition root of the Portadas UI: wires the use case, repository and renderer the widgets talk to.

Widgets only see a ``PortadasServices``; tests build one from fakes, production builds one with ``build_services``.
"""
from dataclasses import dataclass, field
from pathlib import Path

from ..adapters.file_repository import FileCoverRepository
from ..application.create_cover import CreateCoverFromTemplate
from ..application.icon_catalog import IconCatalog
from ..application.template_catalog import TemplateCatalog


@dataclass
class PortadasServices:
    """Everything the library tab and the editor need. ``close`` releases the renderer."""
    repository: object
    creator: object
    renderer: object
    templates: object
    icons: object
    thumbnail_dir: Path
    template_thumbnails: dict = field(default_factory=dict)  # template id -> PNG bytes, rendered lazily
    notice_store: object = None  # ``FileNoticeStore``-like; None means the AI data notice is asked every time
    designer_factory: object = None  # ``callable() -> CoverDesigner`` (may raise DesignError); None disables AI mode

    def close(self):
        """Cancel renders in progress and release the renderer's resources (safe to call twice)."""
        closer = getattr(self.renderer, 'close', None)
        if closer is not None:
            closer()


def build_services(data_dir, renderer=None):
    """
    Build the production services.

    :param data_dir: where covers are stored (``AppLocation.get_section_data_path('portadas')``).
    :param renderer: a ``CoverRenderer``; defaults to ``QtCoverRenderer``, which must be created on the GUI thread
        after the ``QApplication``.
    """
    if renderer is None:
        from ..adapters.qt_renderer import QtCoverRenderer
        renderer = QtCoverRenderer()
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    templates, icons = TemplateCatalog(), IconCatalog()
    repository = FileCoverRepository(data_dir)
    from .ai_designer import make_designer
    from .ai_notice import FileNoticeStore
    return PortadasServices(repository=repository,
                            creator=CreateCoverFromTemplate(templates, icons, renderer, repository),
                            renderer=renderer, templates=templates, icons=icons,
                            thumbnail_dir=data_dir / 'thumbnails', designer_factory=make_designer,
                            notice_store=FileNoticeStore(data_dir / 'ai-notice.json'))
