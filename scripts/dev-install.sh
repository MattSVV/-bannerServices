#!/usr/bin/env bash
# Link the plugin package into OpenLP's community plugins dir. Idempotent; never overwrites real files.
#
# Env overrides:
#   OPENLP_DATA_DIR  OpenLP data dir (default $HOME/.local/share/openlp)
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
source_dir="$repo/portadas"
data_dir="${OPENLP_DATA_DIR:-$HOME/.local/share/openlp}"
plugins_dir="$data_dir/contrib/plugins"
target="$plugins_dir/portadas"

mkdir -p "$plugins_dir"

if [ -L "$target" ]; then
  if [ "$(readlink "$target")" = "$source_dir" ]; then
    echo "already linked: $target -> $source_dir"
    exit 0
  fi
  echo "updating link: $target (was $(readlink "$target"))"
  ln -sfn "$source_dir" "$target"
elif [ -e "$target" ]; then
  echo "error: $target exists and is not a symlink; refusing to overwrite" >&2
  exit 1
else
  ln -s "$source_dir" "$target"
  echo "linked: $target -> $source_dir"
fi
