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
"""
Entry point of the Portadas plugin.

OpenLP imports this file as ``contrib.plugins.portadas.portadasplugin`` and instantiates every
direct subclass of ``Plugin``, so internal imports must be relative to stay independent of that name.
"""
import logging

from openlp.core.common.i18n import translate
from openlp.core.common.settings import Settings
from openlp.core.lib import build_icon
from openlp.core.lib.plugin import Plugin, PluginStatus, StringContent
from openlp.core.state import State
from openlp.core.ui.icons import UiIcons

from .lib.ai_settings import default_secret_store  # noqa: F401 - importing it registers the AI setting defaults
from .lib.i18n import install_for_openlp
from .lib.mediaitem import PortadasMediaItem
from .lib.settingstab import PortadasSettingsTab
from .security.redaction import install_log_redaction

log = logging.getLogger(__name__)

# Every record of the plugin is cleaned of API keys before OpenLP's handlers see it.
install_log_redaction(__name__.rpartition('.')[0] or __name__)  # the package this plugin is loaded as

# OpenLP reads '<name>/status' while a plugin is instantiated, so the default must exist at import time.
Settings.extend_default_settings({'portadas/status': PluginStatus.Inactive})


class PortadasPlugin(Plugin):
    """Creates sermon cover slides and keeps them in their own library tab."""
    log.info('Portadas plugin loaded')

    def __init__(self):
        install_for_openlp()  # before the base class asks for any text
        super().__init__('portadas', PortadasMediaItem, PortadasSettingsTab)
        self.weight = -6
        self.icon_path = UiIcons().picture
        self.icon = build_icon(self.icon_path)
        State().add_service('portadas', self.weight, is_plugin=True)
        State().update_pre_conditions('portadas', self.check_pre_conditions())

    def finalise(self):
        """Release the renderer, then remove the library tab."""
        if self.media_item:
            self.media_item.shutdown()
        super().finalise()

    @staticmethod
    def about():
        return translate('PortadasPlugin', '<strong>Portadas Plugin</strong>'
                         '<br />Creates sermon cover slides from templates and adds them to the service.')

    def set_plugin_text_strings(self):
        """Define all translatable texts of the plugin."""
        self.text_strings[StringContent.Name] = {
            'singular': translate('PortadasPlugin', 'Cover', 'name singular'),
            'plural': translate('PortadasPlugin', 'Covers', 'name plural')
        }
        self.text_strings[StringContent.VisibleName] = {
            'title': translate('PortadasPlugin', 'Covers', 'container title')
        }
        tooltips = {
            'load': '',
            'import': '',
            'new': translate('PortadasPlugin', 'Create a new cover.'),
            'edit': translate('PortadasPlugin', 'Edit the selected cover.'),
            'delete': translate('PortadasPlugin', 'Delete the selected cover.'),
            'preview': translate('PortadasPlugin', 'Preview the selected cover.'),
            'live': translate('PortadasPlugin', 'Send the selected cover live.'),
            'service': translate('PortadasPlugin', 'Add the selected cover to the service.')
        }
        self.set_plugin_ui_text_strings(tooltips)
