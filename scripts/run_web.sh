#!/usr/bin/env bash
# Starts the web studio.  Usage:  bash scripts/run_web.sh [port]   (default 8000)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
PORT="${1:-8000}"
echo "Open http://127.0.0.1:${PORT} in your browser (Ctrl+C to stop)."
python3 main.py --web --port "$PORT"
