#!/usr/bin/env bash
# Runs the unit and regression tests.  Add --all to include the browser tests.
# Usage:  bash scripts/run_tests.sh [--all]
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
if [ "${1:-}" = "--all" ]; then
  python3 -m pytest -q
else
  python3 -m pytest tests --ignore=tests/ui -q
fi
