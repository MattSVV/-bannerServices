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
"""The release packaging script (``scripts/package.py``): contents, exclusions, determinism, checksum, import."""
import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'scripts' / 'package.py'


def run_script(out_dir, *extra, repo=None):
    args = [sys.executable, str(SCRIPT), '--out', str(out_dir), *extra]
    if repo is not None:
        args += ['--repo', str(repo)]
    return subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp('dist')
    result = run_script(out)
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def the_zip(out):
    zips = list(out.glob('*.zip'))
    assert len(zips) == 1
    return zips[0]


def test_the_zip_is_versioned_from_pyproject(built):
    version = next(line for line in (REPO / 'pyproject.toml').read_text().splitlines()
                   if line.startswith('version')).split('"')[1]

    assert the_zip(built).name == f'openlp-portadas-{version}.zip'


def test_the_zip_holds_only_the_plugin_package(built):
    with zipfile.ZipFile(the_zip(built)) as archive:
        names = archive.namelist()

    assert all(name.startswith('portadas/') for name in names)
    assert 'portadas/portadasplugin.py' in names
    assert 'portadas/__init__.py' in names
    assert 'portadas/LICENSE' in names
    assert 'portadas/templates/minimal/template.html' in names
    assert 'portadas/assets/fonts/Outfit-Variable.ttf' in names
    assert 'portadas/assets/icons/cross.svg' in names


def test_the_zip_excludes_tests_caches_and_dev_files(built):
    with zipfile.ZipFile(the_zip(built)) as archive:
        names = archive.namelist()

    assert not [n for n in names if '__pycache__' in n or n.endswith(('.pyc', '.pyo'))]
    assert not [n for n in names if n.startswith(('tests', 'scripts', 'docs', 'odd', '.'))]
    assert not [n for n in names if '/.' in n]


def test_entries_are_sorted_with_fixed_timestamps_and_modes(built):
    with zipfile.ZipFile(the_zip(built)) as archive:
        infos = archive.infolist()

    assert [i.filename for i in infos] == sorted(i.filename for i in infos)
    assert {i.date_time for i in infos} == {(1980, 1, 1, 0, 0, 0)}
    assert {(i.external_attr >> 16) & 0o777 for i in infos} == {0o644}


def test_the_build_is_reproducible(built, tmp_path):
    again = run_script(tmp_path)

    assert again.returncode == 0, again.stderr
    assert the_zip(tmp_path).read_bytes() == the_zip(built).read_bytes()


def test_the_checksum_file_matches_the_zip(built):
    archive = the_zip(built)
    checksum = Path(str(archive) + '.sha256')

    digest, name = checksum.read_text().split()
    assert name == archive.name
    assert digest == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_caches_in_the_source_tree_never_reach_the_zip(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'portadas' / '__pycache__').mkdir(parents=True)
    (repo / 'portadas' / '__pycache__' / 'x.cpython-312.pyc').write_bytes(b'x')
    (repo / 'portadas' / 'a.pyc').write_bytes(b'x')
    (repo / 'portadas' / '.hidden').write_text('x')
    (repo / 'portadas' / 'portadasplugin.py').write_text('x = 1\n')
    (repo / 'LICENSE').write_text('license\n')
    (repo / 'pyproject.toml').write_text('[project]\nname = "x"\nversion = "9.9.9"\n')
    out = tmp_path / 'out'

    result = run_script(out, repo=repo)

    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(out / 'openlp-portadas-9.9.9.zip') as archive:
        assert archive.namelist() == ['portadas/LICENSE', 'portadas/portadasplugin.py']


def test_a_missing_package_fails_loudly(tmp_path):
    result = run_script(tmp_path / 'out', repo=tmp_path)

    assert result.returncode != 0
    assert not list((tmp_path / 'out').glob('*.zip'))


def test_the_extracted_zip_imports_as_a_community_plugin(built, tmp_path):
    data_dir = tmp_path / 'DataDir'
    plugins = data_dir / 'contrib' / 'plugins'
    plugins.mkdir(parents=True)
    with zipfile.ZipFile(the_zip(built)) as archive:
        archive.extractall(plugins)
    code = (
        'import sys; sys.path.insert(0, sys.argv[1]);'
        'import contrib.plugins.portadas.portadasplugin as m;'
        'from openlp.core.lib.plugin import Plugin;'
        'assert issubclass(m.PortadasPlugin, Plugin);'
        'print(m.__file__)'
    )
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')

    result = subprocess.run([sys.executable, '-c', code, str(data_dir)], capture_output=True, text=True, timeout=60,
                            env=env, cwd=tmp_path, check=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith(str(plugins))
