"""
Per-pass ablation: total instructions after optimization over 200 random
programs without input and 200 that read input, with one pass disabled at a
time, with the five passes of the first release (base), with base plus copy
propagation or SCCP, and with no pass at all (the SSA form itself).

    python3 paper_eval/ablation.py           -> results/ablation.json
"""

import random

from common import save
from core.optimizer import IROptimizer
from paper_eval.generator import generate
from paper_eval.pipeline import compile_source

PROGRAMS = 200
SEED_BASE = 2_000_000
INPUT_SEED_BASE = 2_500_000

ALL = IROptimizer.ALL_PASSES
BASE = IROptimizer.BASE_PASSES
CONFIGS = {"all": ALL, "base": BASE, "base+copy_prop": BASE + ("copy_prop",),
           "base+sccp": BASE + ("sccp",), "none": ()}
for p in ALL:
    CONFIGS[f"no_{p}"] = tuple(q for q in ALL if q != p)

STATS = ("constant_folds", "sccp_constants", "sccp_branches_resolved", "copies_propagated",
         "gvn_eliminations", "dead_instructions_removed", "dead_blocks_removed")


def run(seed_base, with_input):
    totals = {name: 0 for name in CONFIGS}
    stats = {name: {k: 0 for k in STATS} for name in CONFIGS}
    vn_programs = {name: 0 for name in CONFIGS}
    raw_total = phi_total = 0
    for k in range(PROGRAMS):
        seed = seed_base + k
        rng = random.Random(seed)
        src = generate(seed, n_statements=rng.randint(4, 48), with_input=with_input)
        for name, passes in CONFIGS.items():
            c = compile_source(src, passes=passes)
            totals[name] += len(c.opt)
            for key in STATS:
                stats[name][key] += c.stat(key)
            if c.stat("gvn_eliminations") > 0:
                vn_programs[name] += 1
            if name == "all":
                raw_total += len(c.raw)
                phi_total += c.phi_count
    out = {"programs": PROGRAMS, "raw_instructions": raw_total, "ssa_phis": phi_total,
           "instructions": totals, "stats": stats, "programs_with_vn_hits": vn_programs}
    print({k: v for k, v in totals.items()}, "raw", raw_total)
    return out


def main():
    save("ablation.json", {"no_input": run(SEED_BASE, False), "with_input": run(INPUT_SEED_BASE, True)})


if __name__ == "__main__":
    main()
