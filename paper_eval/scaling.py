"""
Scaling study: 64 random programs that read input, eight size classes
(4 to 512 top-level statements) with eight seeds each. For every program the
script records the encoded sizes, both Huffman coders with their headers, the
entropy of the CLIR package, and the compilation time (minimum of 3 runs).

    python3 paper_eval/scaling.py            -> results/scaling.json
"""

import time

from common import (save, clir, columnar, entropy_bits_per_byte, freq_huffman_header,
                    deflate_raw, brotli_c)
from core.binary_compression import HuffmanCompressor, FrequencyTableHuffman
from paper_eval.generator import generate
from paper_eval.pipeline import compile_source, raw_text, opt_text

SIZE_CLASSES = [4, 8, 16, 32, 64, 128, 256, 512]
SEEDS_PER_CLASS = 8
SEED_BASE = 3_000_000
TIME_RUNS = 3


def measure(seed, n_statements):
    src = generate(seed, n_statements=n_statements, with_input=True)
    best = None
    for _ in range(TIME_RUNS):
        t0 = time.perf_counter()
        c = compile_source(src)
        package, _ = clir(c)
        elapsed = time.perf_counter() - t0
        if best is None or elapsed < best[0]:
            best = (elapsed, c.times_ms)
    elapsed, stage_ms = best
    huff = HuffmanCompressor.analyze(package)
    freq = FrequencyTableHuffman.compress(package)
    stored, container, coded = columnar(c)
    return {
        "seed": seed, "statements": n_statements,
        "raw_instructions": len(c.raw), "opt_instructions": len(c.opt),
        "raw_text_bytes": len(raw_text(c)), "opt_text_bytes": len(opt_text(c)),
        "clir_bytes": len(package),
        "huffman_bytes": huff["total_bytes"], "huffman_header_bytes": huff["header_bytes"],
        "huffman_symbols": huff["distinct_symbols"],
        "freq_huffman_bytes": len(freq), "freq_huffman_header_bytes": freq_huffman_header(package),
        "entropy_bits_per_byte": entropy_bits_per_byte(package),
        "deflate_clir": len(deflate_raw(package)),
        "brotli_clir": len(brotli_c(package)),
        "columnar_bytes": len(stored), "columnar_container_bytes": len(container),
        "columnar_huffman_applied": coded,
        "time_ms": elapsed * 1000, "stage_ms": stage_ms,
        "throughput_instr_per_s": len(c.raw) / elapsed,
    }


def break_even(rows, total_key, header_key):
    """Observed threshold and the model n* = header / (1 - H/8), applied
    program by program."""
    larger = [r["clir_bytes"] for r in rows if r[total_key] >= r["clir_bytes"]]
    smaller = [r["clir_bytes"] for r in rows if r[total_key] < r["clir_bytes"]]
    correct = 0
    for r in rows:
        gain = 1 - r["entropy_bits_per_byte"] / 8
        n_star = r[header_key] / gain if gain > 0 else float("inf")
        predicted_helps = r["clir_bytes"] > n_star
        correct += predicted_helps == (r[total_key] < r["clir_bytes"])
    return {"largest_package_not_helped": max(larger) if larger else None,
            "smallest_package_helped": min(smaller) if smaller else None,
            "programs_helped": len(smaller), "model_correct": correct, "programs": len(rows)}


def main():
    rows = []
    for ci, n in enumerate(SIZE_CLASSES):
        for s in range(SEEDS_PER_CLASS):
            row = measure(SEED_BASE + 100 * ci + s, n)
            rows.append(row)
        cls = rows[-SEEDS_PER_CLASS:]
        print(n, "raw", sorted(r["raw_instructions"] for r in cls)[SEEDS_PER_CLASS // 2],
              "clir", sorted(r["clir_bytes"] for r in cls)[SEEDS_PER_CLASS // 2],
              "huff", sorted(r["huffman_bytes"] for r in cls)[SEEDS_PER_CLASS // 2],
              "freq", sorted(r["freq_huffman_bytes"] for r in cls)[SEEDS_PER_CLASS // 2])
    save("scaling.json", {
        "size_classes": SIZE_CLASSES, "seeds_per_class": SEEDS_PER_CLASS, "programs": rows,
        "break_even_canonical": break_even(rows, "huffman_bytes", "huffman_header_bytes"),
        "break_even_frequency_table": break_even(rows, "freq_huffman_bytes", "freq_huffman_header_bytes"),
    })


if __name__ == "__main__":
    main()
