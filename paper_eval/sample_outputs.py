"""
Writes a plain-text sample output for every benchmark (S1-S7 and K1-K10):
the source program and its input, the raw three-address code, the optimized
SSA code, what each optimization pass did, the sizes of each representation,
and the program output before optimization, after optimization and after
decoding the CLIR bytecode (reference interpreters).

Usage (from the project root):  python3 paper_eval/sample_outputs.py
Output:                          results/sample_outputs/<ID>_<file>.txt
"""

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.binary_compression import BytecodeDecoder                    # noqa: E402
from paper_eval.pipeline import compile_source, raw_text, opt_text     # noqa: E402
from paper_eval.interp import run_tac, run_cfg, observe                # noqa: E402
from paper_eval.common import all_benchmarks, load, clir               # noqa: E402

OUT = os.path.join(ROOT, "results", "sample_outputs")


def show(result):
    status, value = result
    if status != "ok":
        return f"[{status}] {value}"
    printed = [repr(v) if isinstance(v, str) else str(v)
               for v in value if not (isinstance(v, tuple) and v[:1] == ("ret",))]
    ret = [v[1] for v in value if isinstance(v, tuple) and v[:1] == ("ret",)]
    text = "[" + ", ".join(printed) + "]" if printed else "(nothing printed)"
    return text + (f"   (return value {ret[0]})" if ret and ret[0] is not None else "")


def main():
    os.makedirs(OUT, exist_ok=True)
    for bid, fname, focus, _ in all_benchmarks():
        src, inputs = load(fname)
        c = compile_source(src)
        raw_b, opt_b = raw_text(c), opt_text(c)
        package, _ = clir(c)

        expected = observe(run_tac, c.raw_module(), inputs)
        optimized = observe(run_cfg, c.cfg_module("opt_cfg"), inputs)
        decoded = observe(run_cfg, BytecodeDecoder.decode_module_cfgs(package), inputs)

        stats = Counter()
        for u in c.units:
            stats.update({k: v for k, v in u.optimizer.stats.items() if isinstance(v, int)})

        n_raw, n_opt = len(c.raw), len(c.opt)
        bar = "-" * 72
        lines = [
            f"Sample output for {bid}: {fname} ({focus.replace('$', '').replace(chr(92), '')})",
            "Produced by paper_eval/sample_outputs.py (the same compiler pipeline as main.py)",
            "=" * 72,
            "\nSOURCE PROGRAM\n" + bar, src.rstrip(),
            f"\nPROGRAM INPUT: {' '.join(map(str, inputs)) if inputs else '(none)'}",
            f"\nRAW THREE-ADDRESS CODE ({n_raw} instructions)\n" + bar, raw_b.decode(),
            f"\nOPTIMIZED SSA CODE ({n_opt} instructions)\n" + bar, opt_b.decode(),
            "\nOPTIMIZATION PASSES (summed over all functions)\n" + bar,
        ]
        lines += [f"  {k:32s} {v}" for k, v in stats.items()]
        lines += [
            "\nSIZES\n" + bar,
            f"  instructions:    {n_raw} -> {n_opt}  (reduction {100 * (n_raw - n_opt) / n_raw:.1f}%)",
            f"  raw TAC text:    {len(raw_b):7d} bytes",
            f"  optimized text:  {len(opt_b):7d} bytes",
            f"  CLIR bytecode:   {len(package):7d} bytes",
            "\nPROGRAM OUTPUT (reference interpreters; one item per PRINT instruction,\n"
            "printf prints its format string and its value as separate items)\n" + bar,
            f"  raw TAC:          {show(expected)}",
            f"  optimized SSA:    {show(optimized)}",
            f"  decoded CLIR:     {show(decoded)}",
            f"  all identical:    {expected == optimized == decoded}",
        ]
        out = os.path.join(OUT, f"{bid}_{os.path.splitext(fname)[0]}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
