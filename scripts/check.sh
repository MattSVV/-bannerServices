#!/usr/bin/env bash
# Quality gate: lint + full test suite with coverage. Exits non-zero on any failure.
#
# Env overrides:
#   PYTHON        interpreter with OpenLP + pytest + pytest-cov + ruff (default ../openlp/.venv/bin/python)
#   COVERAGE_MIN  minimum % for portadas/domain, application and security (default 90)
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-../openlp/.venv/bin/python}"
COVERAGE_MIN="${COVERAGE_MIN:-90}"

echo "==> lint (ruff)"
"$PYTHON" -m ruff check .

echo "==> tests (pytest, coverage >= ${COVERAGE_MIN}% on domain/application/security)"
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$PYTHON" -m pytest -q \
  --cov --cov-report=term-missing --cov-fail-under="$COVERAGE_MIN"

echo "==> all checks passed"
