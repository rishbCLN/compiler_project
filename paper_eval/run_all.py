"""
Runs every evaluation script in order and regenerates paper/tables and the
data figures in paper/figures.

    python3 paper_eval/run_all.py
"""

import os
import runpy
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ["measure", "difftest", "ablation", "scaling", "compare", "baselines",
         "make_tables", "make_figures"]


def main():
    sys.path.insert(0, HERE)
    for step in STEPS:
        t = time.time()
        print(f"== {step}")
        runpy.run_path(os.path.join(HERE, f"{step}.py"), run_name="__main__")
        print(f"   {time.time() - t:.1f} s")


if __name__ == "__main__":
    main()
