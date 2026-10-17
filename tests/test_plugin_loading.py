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
"""The plugin is importable under the module name OpenLP uses for community plugins."""
import importlib

from openlp.core.lib.plugin import Plugin


def test_community_module_name(community_module_name):
    assert community_module_name == 'contrib.plugins.portadas.portadasplugin'


def test_plugin_module_defines_portadas_plugin(contrib_data_dir, community_module_name):
    module = importlib.import_module(community_module_name)

    plugin_class = module.PortadasPlugin

    assert issubclass(plugin_class, Plugin)
    assert plugin_class in Plugin.__subclasses__()


def test_plugin_registers_default_status_setting(contrib_data_dir, community_module_name):
    # OpenLP reads '<name>/status' while the plugin is instantiated, so a default must exist at import time.
    from openlp.core.common.settings import Settings
    from openlp.core.lib.plugin import PluginStatus

    importlib.import_module(community_module_name)

    assert Settings.__default_settings__['portadas/status'] == PluginStatus.Inactive
