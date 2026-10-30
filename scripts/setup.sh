#!/usr/bin/env bash
# Creates a virtual environment in .venv and installs everything needed to run
# the compiler, the web studio and the full test suite.
# Usage (from anywhere):  bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium || echo "Chromium not installed: browser tests (tests/ui) will not run."
echo
echo "Setup complete. Activate the environment with:  source .venv/bin/activate"
