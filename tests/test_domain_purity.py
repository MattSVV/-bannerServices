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
"""The domain layer is pure Python: stdlib and relative imports only."""
import ast
import sys
from pathlib import Path

import pytest

DOMAIN = Path(__file__).resolve().parent.parent / 'portadas' / 'domain'


@pytest.mark.parametrize('path', sorted(DOMAIN.glob('*.py')), ids=lambda path: path.name)
def test_domain_module_imports_only_stdlib_or_relative(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.append(node.module)

    offenders = [name for name in modules if name.split('.')[0] not in sys.stdlib_module_names]

    assert offenders == []
