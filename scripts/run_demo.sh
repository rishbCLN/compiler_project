#!/usr/bin/env bash
# Compiles benchmarks with the command-line interface.
# Usage:  bash scripts/run_demo.sh            (all 17 benchmarks)
#         bash scripts/run_demo.sh <file>     (one program)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
if [ $# -gt 0 ]; then
  python3 main.py --input "$1"
else
  for f in benchmarks/*.lang benchmarks/*.c benchmarks/kernels/*.c; do
    echo "==================== $f ===================="
    python3 main.py --input "$f"
  done
fi
