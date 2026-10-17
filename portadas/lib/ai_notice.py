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
Remembers which AI destinations the user agreed to send cover text to.

Why not a plain OpenLP setting: OpenLP's *Import settings* writes any key of a ``.conf`` file into the settings store,
so a flag kept there could be pre-accepted by a file the user was handed. This record is a private file next to the
covers, which a settings import cannot write. It holds destination strings (a provider id, or the origin of an
OpenAI-compatible server, see ``destination_key``), so changing the provider or the server asks again.
"""
import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

MAX_DESTINATIONS = 20  # the oldest agreement is forgotten first
MAX_DESTINATION_CHARS = 300


class FileNoticeStore:
    """The accepted destinations, in a small JSON file. A missing, unreadable or damaged file means none."""

    def __init__(self, path):
        self.path = Path(path)

    def accepted(self, destination):
        return destination in self._read()

    def accept(self, destination):
        """Remember ``destination``. A write failure is logged and ignored: the user is simply asked again."""
        if not isinstance(destination, str) or not destination or len(destination) > MAX_DESTINATION_CHARS:
            return
        destinations = [item for item in self._read() if item != destination] + [destination]
        temp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(prefix='.ai-notice-', dir=self.path.parent)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                json.dump({'accepted': destinations[-MAX_DESTINATIONS:]}, handle)
            os.replace(temp_name, self.path)
            temp_name = None
        except OSError:
            log.warning('The AI data notice answer could not be saved.')
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    def _read(self):
        try:
            with open(self.path, 'rb') as handle:
                data = json.loads(handle.read(65536).decode('utf-8'))
            items = data['accepted']
        except (OSError, ValueError, KeyError, TypeError):  # ValueError covers bad JSON and bad UTF-8
            return []
        return [item for item in items if isinstance(item, str)] if isinstance(items, list) else []
