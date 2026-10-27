"""
Measures the seven sample benchmarks (S1-S7) and the ten kernels (K1-K10):
program structure, the work of every optimizer pass, the size of every
representation and encoding, correctness checks, and per-stage time.

    python3 paper_eval/measure.py            -> results/measure.json
"""

import re
import statistics
import time

from common import (  # noqa: F401  (sets sys.path)
    all_benchmarks, load, clir, columnar, entropy_bound, entropy_bits_per_byte,
    freq_huffman_header, deflate_raw, save, reduction)
from core.binary_compression import BytecodeDecoder, HuffmanCompressor, FrequencyTableHuffman, LEB128
from core.advanced_compression import ColumnarBytecodeSerializer, SSABackwardDeltaEncoder
from core.ir import Opcode, canonical_form
from core.optimizer import IROptimizer
from paper_eval.pipeline import compile_source, raw_text, ssa_text, opt_text
from paper_eval.interp import run_tac, run_cfg, observe

TIMING_RUNS = 30
VERSION_SUFFIX = re.compile(r"_(\d+|undef)\b")


def structure(c):
    blocks = sum(len(u.raw_cfg.blocks) for u in c.units)
    edges = sum(len(b.successors) for u in c.units for b in u.raw_cfg.blocks.values())
    return blocks, edges


def text_growth(c):
    """Where the optimized text's bytes go: phi lines and SSA version suffixes."""
    text = opt_text(c).decode("utf-8")
    phi_bytes = sum(len(line) + 1 for line in text.split("\n") if "= phi(" in line)
    suffix_bytes = sum(len(m.group(0)) for m in VERSION_SUFFIX.finditer(text))
    return {"phi_lines": sum(1 for line in text.split("\n") if "= phi(" in line),
            "phi_line_bytes": phi_bytes, "version_suffix_bytes": suffix_bytes}


def leb(n):
    return len(LEB128.encode_unsigned(n))


def layout(c, package, emitter, stored, container, coded):
    """Byte breakdown of the three encodings (for the layout figure)."""
    structure = leb(len(c.units))
    for u in c.units:
        blocks = sorted(u.opt_cfg.blocks.values(), key=lambda b: int(b.id[2:]))
        structure += leb(len(blocks)) + sum(leb(len(b.instructions)) for b in blocks)
    huff = HuffmanCompressor.analyze(package)
    lengths = HuffmanCompressor.code_lengths(package)
    table = HuffmanCompressor.encode_table(lengths)
    funcs, symbols = ColumnarBytecodeSerializer.unpack_module(container)
    streams = {k: sum(len(f[k]) for f in funcs) for k in ("opcodes", "flags", "deltas", "immediates")}
    prefixes = sum(leb(f["instruction_count"]) + sum(leb(len(f[k])) for k in streams) for f in funcs)
    return {
        "clir": {"header": 5, "pool": emitter.pool_bytes, "pool_entries": len(emitter.pool.entries),
                 "structure": structure, "instructions": emitter.body_bytes - structure,
                 "total": len(package)},
        "huffman": {"length": leb(len(package)), "mode": 1, "table": len(table) - 1,
                    "table_mode": table[0], "symbols": len(lengths),
                    "payload": huff["payload_bytes"], "total": huff["total_bytes"]},
        "columnar": {"flag": 1, "magic": len(ColumnarBytecodeSerializer.CONTAINER_MAGIC),
                     "functions": leb(len(funcs)), "prefixes": prefixes, **streams,
                     "names": len(symbols) + leb(len(symbols)), "coded": coded,
                     "container": len(container), "total": len(stored)},
    }


def correctness(c, inputs):
    expected = observe(run_tac, c.raw_module(), inputs)
    ssa = observe(run_cfg, c.cfg_module("ssa_cfg"), inputs)
    opt = observe(run_cfg, c.cfg_module("opt_cfg"), inputs)
    package, _ = clir(c)
    decoded = observe(run_cfg, BytecodeDecoder.decode_module_cfgs(package), inputs)
    functions, _ = BytecodeDecoder.decode_module(package)
    clir_equal = all(
        canonical_form([i for _, ins in blocks for i in ins], [b for b, _ in blocks]) ==
        canonical_form(u.opt, sorted(u.opt_cfg.blocks, key=lambda b: int(b[2:])))
        for u, (_, blocks) in zip(c.units, functions))
    columnar_equal = all(
        canonical_form(ColumnarBytecodeSerializer.decode_instructions(
            ColumnarBytecodeSerializer.deserialize_columns(
                ColumnarBytecodeSerializer.serialize_columns(
                    SSABackwardDeltaEncoder.encode_instructions(u.opt))))) == canonical_form(u.opt)
        for u in c.units)
    huffman_ok = HuffmanCompressor.decompress(HuffmanCompressor.compress(package)) == package
    phi_args = [a for u in c.units for i in u.opt if i.op == Opcode.PHI for a in i.phi_args]
    return {
        "raw_status": expected[0],
        "output": expected[1] if expected[0] == "ok" else None,
        "ssa_agrees": ssa == expected,
        "opt_agrees": opt == expected,
        "decoded_clir_agrees": decoded == expected,
        "clir_equal_up_to_renaming": clir_equal,
        "columnar_equal_up_to_renaming": columnar_equal,
        "huffman_roundtrip": huffman_ok,
        "opt_phi_arguments": len(phi_args),
    }


def timings(src):
    stage = {k: [] for k in ("front", "tac", "cfg_dom", "ssa", "opt", "clir_huffman", "columnar", "total")}
    for _ in range(TIMING_RUNS):
        t0 = time.perf_counter()
        c = compile_source(src)
        t = time.perf_counter()
        package, _ = clir(c)
        HuffmanCompressor.compress(package)
        t_clir = time.perf_counter() - t
        t = time.perf_counter()
        columnar(c)
        t_col = time.perf_counter() - t
        total = time.perf_counter() - t0
        for k, v in c.times_ms.items():
            stage[k].append(v)
        stage["clir_huffman"].append(t_clir * 1000)
        stage["columnar"].append(t_col * 1000)
        stage["total"].append(total * 1000)
    return {k: statistics.median(v) for k, v in stage.items()}


def measure_one(bid, fname, focus, group):
    src, inputs = load(fname)
    c = compile_source(src)
    base = compile_source(src, passes=IROptimizer.BASE_PASSES)
    blocks, edges = structure(c)
    raw_t, ssa_t, opt_t = raw_text(c), ssa_text(c), opt_text(c)
    package, emitter = clir(c)
    huff = HuffmanCompressor.analyze(package)
    stored, container, coded = columnar(c)
    ssa_instr = sum(len(u.ssa_cfg.linearize()) for u in c.units)

    row = {
        "id": bid, "file": fname, "focus": focus, "set": group,
        "source_bytes": len(src.encode("utf-8")),
        "functions": len(c.units),
        "inputs": len(inputs),
        "tac_instructions": len(c.raw),
        "blocks": blocks,
        "edges": edges,
        "phis": c.phi_count,
        "ssa_instructions": ssa_instr,
        "opt_instructions": len(c.opt),
        "opt_instructions_base_passes": len(base.opt),
        "opt_blocks": sum(len(u.opt_cfg.blocks) for u in c.units),
        "instruction_reduction": reduction(len(c.raw), len(c.opt)),
        "instruction_reduction_base_passes": reduction(len(c.raw), len(base.opt)),
        "passes": {k: c.stat(k) for k in (
            "constant_folds", "constant_propagations", "sccp_constants", "sccp_branches_resolved",
            "copies_propagated", "gvn_eliminations", "dead_instructions_removed",
            "dead_blocks_removed")},
        "rounds": max(u.optimizer.stats["rounds"] for u in c.units),
        "raw_text_bytes": len(raw_t),
        "ssa_text_bytes": len(ssa_t),
        "opt_text_bytes": len(opt_t),
        "opt_text_growth": text_growth(c),
        "clir_bytes": len(package),
        "clir_pool_bytes": emitter.pool_bytes,
        "clir_body_bytes": emitter.body_bytes,
        "clir_pool_entries": len(emitter.pool.entries),
        "clir_blocks": emitter.block_count,
        "clir_vs_raw_text": reduction(len(raw_t), len(package)),
        "clir_vs_opt_text": reduction(len(opt_t), len(package)),
        "huffman_bytes": huff["total_bytes"],
        "huffman_header_bytes": huff["header_bytes"],
        "huffman_payload_bytes": huff["payload_bytes"],
        "huffman_symbols": huff["distinct_symbols"],
        "freq_huffman_bytes": len(FrequencyTableHuffman.compress(package)),
        "freq_huffman_header_bytes": freq_huffman_header(package),
        "entropy_bits_per_byte": entropy_bits_per_byte(package),
        "entropy_bound_bytes": entropy_bound(package),
        "columnar_bytes": len(stored),
        "columnar_container_bytes": len(container),
        "columnar_huffman_applied": coded,
        "deflate_raw_text": len(deflate_raw(raw_t)),
        "deflate_opt_text": len(deflate_raw(opt_t)),
        "deflate_clir": len(deflate_raw(package)),
        "density": {
            "raw_text_bits_per_raw_instr": 8 * len(raw_t) / len(c.raw),
            "clir_body_bits_per_opt_instr": 8 * emitter.body_bytes / max(1, len(c.opt)),
            "clir_bits_per_raw_instr": 8 * len(package) / len(c.raw),
        },
        "layout": layout(c, package, emitter, stored, container, coded),
        "correctness": correctness(c, inputs),
        "time_ms": timings(src),
    }
    return row


def main():
    rows = []
    for bid, fname, focus, group in all_benchmarks():
        row = measure_one(bid, fname, focus, group)
        ok = row["correctness"]
        print(f"{bid:4} instr {row['tac_instructions']:3} -> {row['opt_instructions']:3} "
              f"({row['instruction_reduction']:.1f}%)  CLIR {row['clir_bytes']:4} B  "
              f"Huffman {row['huffman_bytes']:4} B  agree={ok['opt_agrees'] and ok['decoded_clir_agrees']}")
        rows.append(row)
    print("wrote", save("measure.json", {"timing_runs": TIMING_RUNS, "benchmarks": rows}))


if __name__ == "__main__":
    main()
