# Evaluation scripts

These scripts produce every number, table row and data figure of the article
in `paper/`. They only read the compiler in `core/`; they never modify it.

## Setup

```
python3 -m pip install -r paper_eval/requirements.txt
python3 paper_eval/run_all.py
```

`baselines.py` also needs `clang`, `javac` and `java` on the `PATH`. Without
them it keeps the cached `results/baselines.json`. The results in the
repository were produced with the versions recorded in `results/compare.json`
(`versions`) and `results/baselines.json` (`tools`).

## Scripts

| Script | Writes | Used by |
|---|---|---|
| `measure.py` | `results/measure.json` | Tables on benchmarks, optimization, sizes, time; Figs. on reduction, sizes, density |
| `difftest.py` | `results/difftest.json` | Differential-testing table |
| `ablation.py` | `results/ablation.json` | Ablation figure and text |
| `scaling.py` | `results/scaling.json` | Scaling and throughput figures, Huffman break-even |
| `compare.py` | `results/compare.json` | Comparison with Brotli, Zstandard, xz and DEFLATE |
| `baselines.py` | `results/baselines.json` | Comparison with Java class files and LLVM bitcode |
| `make_tables.py` | `paper/tables/*.tex`, `paper/tables/numbers.tex` | All data tables; every number in the text |
| `make_figures.py` | `paper/figures/fig_*.pdf` (data figures) | All data figures |

Shared code: `pipeline.py` runs the compiler stage by stage, `interp.py` holds
the two reference interpreters, `generator.py` the random-program generator,
and `common.py` the benchmark list, encoders and compressor settings.

## Checks performed

* Every CLIR package is decoded without any table from the encoder and must
  equal the optimized program up to a consistent renaming; it is also rebuilt
  into control-flow graphs and executed.
* Every columnar container is decoded back to instructions and compared the
  same way.
* Every Huffman stream is decoded; its size is predicted from the code lengths.
* The raw TAC, the SSA form, the optimized form and the decoded CLIR package
  are executed by the reference interpreters (C semantics for `/` and `%`) and
  must print the same values. The kernels are also compiled natively with
  clang, and their Java translations are run; both must print the same numbers.
* Every compressor output is decompressed and compared with its input.

The unit tests (`python3 -m pytest tests`) include a small version of the
differential test.

## Seeds

Random programs use disjoint seed ranges: differential testing 1,000,000+
(and 4,000,000+ with input), ablation 2,000,000+ (2,500,000+ with input),
scaling 3,000,000+, dictionary training 5,000,000+.
