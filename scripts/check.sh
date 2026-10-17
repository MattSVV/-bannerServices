#!/usr/bin/env bash
# Quality gate: lint + full test suite with coverage. Exits non-zero on any failure.
#
# Env overrides:
#   PYTHON        interpreter with OpenLP + pytest + pytest-cov + ruff (default ../openlp/.venv/bin/python)
#   COVERAGE_MIN  minimum % for portadas/domain, application and security (default 90)
#   TESTS_TIMEOUT hard limit in seconds for the whole test run (default 600; the suite normally takes under a minute)
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-../openlp/.venv/bin/python}"
COVERAGE_MIN="${COVERAGE_MIN:-90}"
TESTS_TIMEOUT="${TESTS_TIMEOUT:-600}"

echo "==> lint (ruff)"
"$PYTHON" -m ruff check .

echo "==> tests (pytest, coverage >= ${COVERAGE_MIN}% on domain/application/security)"
# `timeout` is the last resort when even pytest-timeout cannot run (exit status 124 means it fired).
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" timeout --kill-after=10 "$TESTS_TIMEOUT" "$PYTHON" -m pytest -q \
  --cov --cov-report=term-missing --cov-fail-under="$COVERAGE_MIN"

echo "==> all checks passed"
