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
"""Library tab of the Portadas plugin. Skeleton: shows an empty list."""
import logging

from openlp.core.lib.mediamanageritem import MediaManagerItem

log = logging.getLogger(__name__)


class PortadasMediaItem(MediaManagerItem):
    """Media manager item listing the saved covers."""
    log.info('Portadas media item loaded')

    def __init__(self, parent, plugin):
        self.icon_path = 'images/image'
        super().__init__(parent, plugin)

    def required_icons(self):
        """No actions yet: the skeleton only shows an empty list."""
        super().required_icons()
        self.has_new_icon = False
        self.has_edit_icon = False
        self.has_delete_icon = False
        self.can_preview = False
        self.can_make_live = False
        self.can_add_to_service = False
