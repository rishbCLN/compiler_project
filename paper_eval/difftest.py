"""
Differential testing: the observable behavior (printed values and return
value) of the optimized program must equal that of the raw TAC.

Three optimizer variants are run on the same 1000 random programs:
  released   the five passes of the first release, folding / and % with
             Python's floor rule (the defect reported in the first draft);
  corrected  the same five passes with C's truncating / and %;
  all        all passes, including SCCP and copy propagation.
A further 500 random programs read input() and run with all passes.

A divergence counts as a division divergence if it disappears when both
programs are run with the floor rule for / and %.

    python3 paper_eval/difftest.py           -> results/difftest.json
"""

import random

from common import save
from core.optimizer import IROptimizer
from paper_eval.generator import generate
from paper_eval.interp import run_tac, run_cfg, observe, floor_semantics
from paper_eval.pipeline import compile_source, ReleasedFolderOptimizer

PROGRAMS = 1000
INPUT_PROGRAMS = 500
SEED_BASE = 1_000_000          # disjoint from ablation (2_000_000) and scaling (3_000_000)
INPUT_SEED_BASE = 4_000_000

VARIANTS = {
    "released": dict(passes=IROptimizer.BASE_PASSES, optimizer_cls=ReleasedFolderOptimizer),
    "corrected": dict(passes=IROptimizer.BASE_PASSES),
    "all": dict(passes=None),
}


def program(seed: int, with_input: bool = False):
    rng = random.Random(seed)
    src = generate(seed, n_statements=rng.randint(4, 48), with_input=with_input)
    inputs = [rng.randint(-100, 100) for _ in range(2000)] if with_input else []
    return src, inputs


def check(src, inputs, variant):
    c = compile_source(src, **VARIANTS[variant])
    expected = observe(run_tac, c.raw_module(), inputs)
    if expected[0] != "ok":
        return "invalid", len(c.raw)
    ssa = observe(run_cfg, c.cfg_module("ssa_cfg"), inputs)
    if ssa != expected:
        return "ssa_differs", len(c.raw)
    got = observe(run_cfg, c.cfg_module("opt_cfg"), inputs)
    if got == expected:
        return "agree", len(c.raw)
    # Folded divisions used one rule and run-time divisions another, so
    # rerun both programs with the floor rule throughout.
    with floor_semantics():
        floor_expected = observe(run_tac, c.raw_module(), inputs)
        floor_got = observe(run_cfg, c.cfg_module("opt_cfg"), inputs)
    return ("differ_division" if floor_got == floor_expected else "differ_other"), len(c.raw)


def campaign(seeds, with_input, variants):
    summary = {}
    sizes = []
    for variant in variants:
        counts = {"agree": 0, "differ_division": 0, "differ_other": 0, "ssa_differs": 0, "invalid": 0}
        failing = []
        for seed in seeds:
            src, inputs = program(seed, with_input)
            status, n = check(src, inputs, variant)
            counts[status] += 1
            if status != "agree" and len(failing) < 20:
                failing.append(seed)
            if variant == variants[0]:
                sizes.append(n)
        counts["programs"] = len(seeds)
        counts["agreement_percent"] = 100.0 * counts["agree"] / len(seeds)
        counts["example_failing_seeds"] = failing
        summary[variant] = counts
        print(f"{variant:10} {counts}")
    return summary, sizes


def main():
    seeds = [SEED_BASE + k for k in range(PROGRAMS)]
    no_input, sizes = campaign(seeds, False, list(VARIANTS))
    input_seeds = [INPUT_SEED_BASE + k for k in range(INPUT_PROGRAMS)]
    with_input, input_sizes = campaign(input_seeds, True, ["all"])
    save("difftest.json", {
        "programs": PROGRAMS,
        "raw_instructions": {"min": min(sizes), "max": max(sizes), "total": sum(sizes)},
        "variants": no_input,
        "input_programs": INPUT_PROGRAMS,
        "input_raw_instructions": {"min": min(input_sizes), "max": max(input_sizes),
                                   "total": sum(input_sizes)},
        "with_input": with_input,
    })


if __name__ == "__main__":
    main()
