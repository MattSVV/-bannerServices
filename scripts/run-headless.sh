#!/usr/bin/env bash
# Smoke-run OpenLP headless with the plugin linked, in a throwaway XDG profile (your real profile is untouched).
# Prints the plugin-related lines of the OpenLP log. Exits non-zero if the plugin did not load or errors appear.
#
# Env overrides:
#   OPENLP_SRC   OpenLP checkout (default ../openlp)
#   LOG_COPY     if set, copy the full OpenLP log to this path
#   E2E_TIMEOUT  hard limit in seconds for the end-to-end cover flow (default 300)
#   OPENLP_LANGUAGE  OpenLP language code to run with in the throwaway profile (for example es)
#   SECONDS_RUN  max seconds to wait for the plugin to initialise (default 120)
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
openlp_src="${OPENLP_SRC:-$repo/../openlp}"
run_for="${SECONDS_RUN:-120}"

profile="$(mktemp -d)"
trap 'rm -rf "$profile"' EXIT
export XDG_CONFIG_HOME="$profile/config" XDG_DATA_HOME="$profile/data" XDG_CACHE_HOME="$profile/cache"
export QT_QPA_PLATFORM=offscreen

# Pre-seed settings so no blocking dialog appears (wizard done, versions current) and the plugin is Active.
mkdir -p "$XDG_CONFIG_HOME/OpenLP"
language_line=''
[ -z "${OPENLP_LANGUAGE:-}" ] || language_line="language=$OPENLP_LANGUAGE\n"
printf "[core]\nhas%%20run%%20wizard=true\napplication%%20version=3.1.8\n${language_line}\n[settings]\nversion=3\n\n[portadas]\nstatus=1\n" > "$XDG_CONFIG_HOME/OpenLP/OpenLP.conf"

OPENLP_DATA_DIR="$XDG_DATA_HOME/openlp" "$repo/scripts/dev-install.sh"

# Create sample covers through the plugin's own use case and the real renderer, so the library tab has something to
# list. The second one has an uploaded PNG icon and the script checks it shows up in the rendered image.
echo "--- seeding covers ---"
"$openlp_src/.venv/bin/python" "$repo/scripts/seed_cover.py" "$XDG_DATA_HOME/openlp"

# End-to-end cover flow with the production adapters, in its own data dir so the library count above stays at 2:
# every built-in template -> cover -> render -> library tab -> service item. It fails on any Portadas error record.
echo "--- end-to-end cover flow ---"
e2e_data="$profile/e2e-data"
OPENLP_DATA_DIR="$e2e_data" "$repo/scripts/dev-install.sh"
timeout --kill-after=10 "${E2E_TIMEOUT:-300}" "$openlp_src/.venv/bin/python" "$repo/scripts/e2e_flow.py" "$e2e_data"

# A fresh profile creates every plugin database on first start, which can take a minute on a slow disk.
# Run OpenLP in the background and stop it as soon as the plugin is initialised (or the timeout expires).
log="$XDG_CACHE_HOME/openlp/openlp.log"
"$openlp_src/.venv/bin/python" "$openlp_src/run_openlp.py" -l debug -e >/dev/null 2>&1 &
openlp_pid=$!
for _ in $(seq 1 "$run_for"); do
  if grep -qs 'initialising plugins portadas' "$log" || ! kill -0 "$openlp_pid" 2>/dev/null; then
    break
  fi
  sleep 1
done
sleep 2
kill "$openlp_pid" 2>/dev/null || true
wait "$openlp_pid" 2>/dev/null || true

[ -z "${LOG_COPY:-}" ] || cp "$log" "$LOG_COPY"
echo "--- plugin lines ---"
grep -i 'portadas' "$log" | cut -c1-200 || true
echo "--- OpenLP errors unrelated to Portadas (ignored: missing 'uno', display web view timeouts offscreen) ---"
grep -nE 'ERROR|CRITICAL' "$log" | grep -vi 'portadas' | cut -c1-160 || true
echo "--- Portadas errors ---"
if grep -nEi 'Failed to import|(ERROR|CRITICAL).*portadas|File ".*portadas' "$log" | cut -c1-200; then
  echo "Portadas errors found in log" >&2
  exit 1
fi
grep -qE 'Loaded plugin .*PortadasPlugin' "$log"
grep -qE 'initialising plugins portadas in a True state' "$log"
grep -qE 'Portadas settings tab created' "$log" || { echo "the settings tab was not created" >&2; exit 1; }
# The library tab must have listed the seeded covers and built a thumbnail for each.
grep -qE 'Portadas library loaded: 2 cover\(s\)' "$log" || { echo "the library tab did not list the 2 seeded covers" >&2; exit 1; }
thumbnails="$(find "$XDG_DATA_HOME/openlp/portadas/thumbnails" -name '*.png' 2>/dev/null | wc -l)"
[ "$thumbnails" -eq 2 ] || { echo "expected 2 thumbnails, found $thumbnails" >&2; exit 1; }
echo "OK: Portadas plugin loaded and initialised; library listed 2 covers with $thumbnails thumbnails; end-to-end flow passed"
