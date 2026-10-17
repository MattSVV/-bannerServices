#!/usr/bin/env python3
"""Build the release zip of the Portadas plugin.

The zip holds only the ``portadas/`` package (plus the licence as ``portadas/LICENSE``), so unzipping it into
``<DataDir>/contrib/plugins/`` installs the plugin. Entries are sorted and carry a fixed timestamp and mode, so the
same sources always give the same bytes. A ``<zip>.sha256`` file in ``sha256sum`` format is written next to it.

Usage: scripts/package.py [--out DIR] [--repo DIR]
"""
import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

PACKAGE = 'portadas'
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # earliest time a zip can hold
EXCLUDED_DIRS = {'__pycache__', 'tests'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo'}


def read_version(repo):
    text = (repo / 'pyproject.toml').read_text(encoding='utf-8')
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit('error: no version in pyproject.toml')
    return match.group(1)


def package_files(repo):
    """Sorted (archive name, source path) pairs for everything that belongs in the release."""
    root = repo / PACKAGE
    if not root.is_dir():
        raise SystemExit(f'error: {root} is not a directory')
    entries = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise SystemExit(f'error: refusing to package a symlink: {relative}')
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS or part.startswith('.') for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        entries[f'{PACKAGE}/{relative.as_posix()}'] = path
    licence = repo / 'LICENSE'
    if licence.is_file():
        entries[f'{PACKAGE}/LICENSE'] = licence
    return sorted(entries.items())


def build(repo, out):
    version = read_version(repo)
    entries = package_files(repo)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'openlp-portadas-{version}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in entries:
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3  # unix, so the mode above is honoured
            archive.writestr(info, source.read_bytes(), compresslevel=9)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum = out / f'{target.name}.sha256'
    checksum.write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    return target, checksum, len(entries)


def main(argv=None):
    default_repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', type=Path, default=default_repo, help='repository root (default: this repo)')
    parser.add_argument('--out', type=Path, default=None, help='output directory (default: <repo>/dist)')
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    target, checksum, count = build(repo, (args.out or repo / 'dist').resolve())
    print(f'built {target} ({count} files)')
    print(f'wrote {checksum}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
