"""
Comparison with general-purpose compressors.

Every benchmark is written in three representations: the raw TAC text, the
optimized text (the same optimized program as the CLIR package, printed one
instruction per line) and the CLIR package. Each representation is
compressed with Brotli, Zstandard, xz and DEFLATE in three settings:

  framed      the usual containers: Brotli stream, Zstandard frame, .xz file,
              raw DEFLATE;
  headerless  without container overhead: Zstandard magic-less frame without
              checksum, content size or dictionary id, raw LZMA2 instead of
              .xz (Brotli and raw DEFLATE have no container to remove);
  dictionary  Zstandard (headerless) with a 4 KiB dictionary trained on 300
              random programs, and DEFLATE with the same bytes as preset
              dictionary. The Python Brotli binding offers no custom
              dictionaries. The dictionary is shared by all files and is not
              counted per file.

The main comparison is CLIR against the best of Brotli, Zstandard and xz on
the optimized text, so that both sides encode the same optimized program.
The 64 programs of the scaling study are compared in the same way.

    python3 paper_eval/compare.py            -> results/compare.json
"""

import random

from common import (save, all_benchmarks, load, clir, deflate_raw, brotli_c, zstd_frame,
                    zstd_headerless, xz_container, lzma2_raw, check_roundtrips,
                    library_versions, reduction)
from paper_eval.generator import generate
from paper_eval.pipeline import compile_source, raw_text, opt_text
from scaling import SIZE_CLASSES, SEEDS_PER_CLASS, SEED_BASE as SCALING_SEED_BASE

DICT_SIZE = 4096
TRAINING_PROGRAMS = 300
TRAINING_SEED_BASE = 5_000_000
REPRESENTATIONS = ("raw_text", "opt_text", "clir")


def representations(c):
    return {"raw_text": raw_text(c), "opt_text": opt_text(c), "clir": clir(c)[0]}


def train_dictionaries():
    import zstandard
    samples = {r: [] for r in REPRESENTATIONS}
    for k in range(TRAINING_PROGRAMS):
        seed = TRAINING_SEED_BASE + k
        rng = random.Random(seed)
        c = compile_source(generate(seed, n_statements=rng.randint(4, 48), with_input=k % 2 == 1))
        for r, data in representations(c).items():
            samples[r].append(data)
    return {r: zstandard.train_dictionary(DICT_SIZE, samples[r]) for r in REPRESENTATIONS}


def compress_all(data, zstd_dict):
    zdict = zstd_dict.as_bytes()
    check_roundtrips(data, zstd_dict, zdict)
    return {
        "input": len(data),
        "framed": {"brotli": len(brotli_c(data)), "zstd": len(zstd_frame(data)),
                   "xz": len(xz_container(data)), "deflate": len(deflate_raw(data))},
        "headerless": {"brotli": len(brotli_c(data)), "zstd": len(zstd_headerless(data)),
                       "lzma2": len(lzma2_raw(data)), "deflate": len(deflate_raw(data))},
        "dictionary": {"zstd": len(zstd_headerless(data, zstd_dict)),
                       "deflate": len(deflate_raw(data, zdict))},
    }


def best_of_three(sizes, setting):
    keys = ("brotli", "zstd", "xz") if setting == "framed" else ("brotli", "zstd", "lzma2")
    return min(sizes[setting][k] for k in keys)


def summarize(row):
    clir_bytes = row["clir"]["input"]
    out = {}
    for rep in ("raw_text", "opt_text"):
        out[rep] = {
            "best_framed": best_of_three(row[rep], "framed"),
            "best_headerless": best_of_three(row[rep], "headerless"),
            "best_dictionary": min(row[rep]["dictionary"].values()),
        }
        out[rep]["clir_vs_best_framed"] = reduction(out[rep]["best_framed"], clir_bytes)
        out[rep]["clir_vs_best_headerless"] = reduction(out[rep]["best_headerless"], clir_bytes)
        out[rep]["clir_vs_best_dictionary"] = reduction(out[rep]["best_dictionary"], clir_bytes)
    out["clir_best_compressed"] = min(min(row["clir"]["headerless"].values()),
                                      min(row["clir"]["dictionary"].values()))
    return out


def main():
    dictionaries = train_dictionaries()
    rows = []
    for bid, fname, focus, group in all_benchmarks():
        src, _ = load(fname)
        c = compile_source(src)
        row = {"id": bid, "set": group}
        for rep, data in representations(c).items():
            row[rep] = compress_all(data, dictionaries[rep])
        row["summary"] = summarize(row)
        s = row["summary"]["opt_text"]
        print(f"{bid:4} CLIR {row['clir']['input']:4}  opt text {row['opt_text']['input']:5} "
              f"best framed {s['best_framed']:4} ({s['clir_vs_best_framed']:+.1f}%)  "
              f"headerless {s['best_headerless']:4} ({s['clir_vs_best_headerless']:+.1f}%)  "
              f"dict {s['best_dictionary']:4} ({s['clir_vs_best_dictionary']:+.1f}%)")
        rows.append(row)

    scaling = []
    for ci, n in enumerate(SIZE_CLASSES):
        for s in range(SEEDS_PER_CLASS):
            seed = SCALING_SEED_BASE + 100 * ci + s
            c = compile_source(generate(seed, n_statements=n, with_input=True))
            reps = representations(c)
            entry = {"seed": seed, "statements": n, "clir": len(reps["clir"]),
                     "clir_brotli": len(brotli_c(reps["clir"])),
                     "opt_text_best_framed": min(len(brotli_c(reps["opt_text"])),
                                                 len(zstd_frame(reps["opt_text"])),
                                                 len(xz_container(reps["opt_text"]))),
                     "opt_text_best_headerless": min(len(brotli_c(reps["opt_text"])),
                                                     len(zstd_headerless(reps["opt_text"])),
                                                     len(lzma2_raw(reps["opt_text"])))}
            scaling.append(entry)

    save("compare.json", {
        "versions": library_versions(),
        "settings": {"brotli": "quality 11, window 2^22", "zstd": "level 19",
                     "xz": "preset 9", "deflate": "level 9, raw stream",
                     "dictionary_bytes": DICT_SIZE, "training_programs": TRAINING_PROGRAMS},
        "benchmarks": rows,
        "scaling": scaling,
    })


if __name__ == "__main__":
    main()
