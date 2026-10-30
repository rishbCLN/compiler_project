#!/usr/bin/env bash
# Re-runs every experiment of the manuscript, regenerates its tables and data
# figures, writes the sample outputs and checks the manuscript.
# Usage:  bash scripts/reproduce_results.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
pip install -q -r paper_eval/requirements.txt
python3 paper_eval/run_all.py
python3 paper_eval/sample_outputs.py
python3 paper_eval/check_paper.py
echo
echo "Done. Results: paper_eval/results/  Tables and figures: paper/tables, paper/figures  Samples: results/sample_outputs/"
echo "Sizes and counts are deterministic; timings differ from machine to machine."
