# IR Compression Studio

**Optimize Before You Compress: SSA-Based Compaction of Three-Address Code, Verified by Differential Testing**

Compiler Design project, Team 16, School of Computer Science and Engineering, Vellore Institute of Technology, Vellore.

| Register number | Name |
|---|---|
| 24BCE0740 | Rishabh Kumar |
| 24BCE0815 | Hrituraj Deb |
| 24BCE2148 | Gautham G |
| 24BDS0073 | Aarnav Bhasin |

---

## 1. Project overview

IR Compression Studio is a compiler for a small C-like language and a subset of C. It measures how much smaller intermediate code becomes when it is optimized in static single assignment (SSA) form *before* it is encoded, and it checks with reference interpreters that the optimized and encoded program still behaves like the original.

```
source (.lang or .c)
  → lexer → recursive-descent parser → AST
  → three-address code (TAC) + symbol table + constant pool        (one unit per function)
  → basic blocks and control-flow graph (leader algorithm)
  → dominators, dominator tree, dominance frontiers (Cooper–Harvey–Kennedy)
  → semi-pruned SSA (φ on the iterated dominance frontier, renaming on the dominator tree)
  → optimizer, 7 passes to a fixed point:
       constant folding · sparse conditional constant propagation (SCCP) · copy propagation
       · value numbering · dead-code elimination · CFG simplification · trivial-φ removal
  → CLIR v2: self-describing bytecode (1 opcode byte + LEB128 operands + pruned literal pool)
  → optional canonical Huffman coding, columnar container, .cir export and lossless decompression
```

The language has `int`, `float`, `string` and `bool` variables, `if`/`else`, `while`, `for`, user-defined functions with `return`, `print`/`printf`, and input through `input()` and `scanf`. C files may use `#include` and `main()`.

The compiler can be used from the command line or from a web studio that shows the CFG, the dominator tree, the SSA form, the optimization steps and the size metrics.

### Main results

From the manuscript (`manuscript/`); details in [`results/`](results/README.md).

| Metric | Result |
|---|---|
| Instructions removed by optimization | 48.1% – 89.3% on 7 demonstration programs; 19.0% – 34.3% on 10 C kernels |
| CLIR vs. best of Brotli / Zstandard / xz on the optimized text | 3.4% – 59.7% smaller (demonstration programs), 39.5% – 50.9% smaller (kernels) |
| With a shared compressor dictionary | compressors win on 5 of the 7 small programs; CLIR still 25.5% – 37.9% smaller on the kernels |
| Canonical Huffman coding | pays off for CLIR packages of about 115 bytes or more |
| Differential testing, 1,000 random programs | the first release miscompiled 213 (21.3%) by folding `/` and `%` with floor semantics; the current release agrees on all of them and on 500 programs with input |
| Compile time per benchmark | 1.01 – 3.96 ms |

---

## 2. Repository structure

```
compiler_project/
├── main.py                  # command-line interface; also starts the web studio
├── core/                    # the compiler
│   ├── lexer.py  parser.py  ast_nodes.py  ir.py  ir_generator.py  module.py
│   ├── symbol_table.py  constant_pool.py
│   ├── cfg.py  dominator.py  ssa.py  optimizer.py  liveness.py  register_allocator.py
│   ├── binary_compression.py       # LEB128, CLIR bytecode, Huffman coding
│   ├── advanced_compression.py     # columnar container, delta and front coding
│   ├── decompression.py            # decoding and lossless round-trip checks
│   └── compression_benchmarks.py   # comparison with general-purpose compressors (web studio)
├── api/server.py            # FastAPI backend of the web studio
├── web/                     # web studio front end (HTML, CSS, JavaScript, Cytoscape.js, Chart.js)
├── benchmarks/              # dataset: S1–S7 demonstration programs
│   └── kernels/             # dataset: K1–K10 C kernels with input
├── tests/                   # unit and regression tests; tests/ui: browser tests (Playwright)
├── paper_eval/              # evaluation scripts that produce every number in the manuscript
│   └── results/             # raw experimental results (JSON)
├── results/                 # results summary, figures and sample outputs
├── paper/                   # LaTeX source of the manuscript (IEEE Access template)
├── manuscript/              # manuscript PDF + LaTeX zip for Overleaf
├── scripts/                 # setup, test, run and reproduction scripts
├── docs/                    # design notes and project report
├── .github/workflows/       # GitHub Actions: runs the full test suite on every push
├── requirements.txt         # runtime dependencies
├── requirements-dev.txt     # test dependencies (Playwright, optional compressors)
└── paper_eval/requirements.txt  # evaluation dependencies (pinned)
```

---

## 3. System requirements

- Python **3.10 or newer** (developed with Python 3.14 on macOS; GitHub Actions uses 3.12 on Ubuntu)
- macOS, Linux or Windows
- A modern browser (Chrome, Firefox, Safari or Edge) for the web studio
- Internet access for `pip install`
- Optional, only for `paper_eval/baselines.py`: `clang`, `javac` and `java` on the `PATH` (without them the stored results are used)
- Optional, only to rebuild the manuscript: a LaTeX installation with `pdflatex`, or Overleaf

### Dependencies

| File | Packages | Needed for |
|---|---|---|
| `requirements.txt` | fastapi ≥ 0.110, uvicorn ≥ 0.28, pydantic ≥ 2.6, rich ≥ 13.7, networkx ≥ 3.2, pytest ≥ 8.0 | CLI, web studio, tests |
| `requirements-dev.txt` | pytest-playwright ≥ 0.4.4, httpx ≥ 0.27, brotli ≥ 1.1, zstandard ≥ 0.22, lz4 ≥ 4.3 | full test suite (browser tests and the compressor comparison) |
| `paper_eval/requirements.txt` | brotli 1.2.0, zstandard 0.25.0, matplotlib 3.10.8 | reproducing the manuscript results |

The compiler in `core/` itself uses only the Python standard library.

---

## 4. Installation

```bash
git clone https://github.com/rishbCLN/compiler_project.git
cd compiler_project

python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium  # only for the browser tests
```

On macOS or Linux, `bash scripts/setup.sh` does all of this.

---

## 5. Configuration

No configuration file, API key or password is needed. Settings are command-line options:

| Command | Default | Meaning |
|---|---|---|
| `python3 main.py` | — | compiles `benchmarks/sample1_arithmetic_constants.lang` |
| `python3 main.py --input <file>` | — | compiles a `.lang` or `.c` program |
| `python3 main.py --input <file> --export-cir <out.cir>` | — | also saves the compressed IR package |
| `python3 main.py --decompress <file.cir>` | — | decompresses a package and checks the round trip |
| `python3 main.py --web [--port N]` | port 8000 | starts the web studio on `http://127.0.0.1:N` |

Other configuration files: `conftest.py` (pytest fixture that starts the web server for the browser tests), `.github/workflows/ui.yml` (CI environment: Ubuntu, Python 3.12, Chromium) and `.gitignore`. The evaluation settings (seeds, program counts, compressor levels) are constants in `paper_eval/common.py` and the individual scripts, and are listed in Table 2 of the manuscript.

---

## 6. Execution

### Command line

```bash
python3 main.py --input benchmarks/sample2_loops_and_conditionals.lang
python3 main.py --input benchmarks/kernels/k01_gcd_lcm.c --export-cir gcd.cir
python3 main.py --decompress gcd.cir
```

The CLI prints the raw three-address code, the optimized SSA code and the compression metrics. `bash scripts/run_demo.sh` compiles all 17 benchmarks.

### Web studio

```bash
python3 main.py --web          # or: bash scripts/run_web.sh
```

Open `http://127.0.0.1:8000`, choose an example from the drop-down (or type a program) and press **Compile** (Ctrl+Enter). The tabs show the overview metrics, the CFG, the SSA form, the symbol table, the optimization steps and the AST; **Export** downloads the compressed IR.

### Tests

```bash
python3 -m pytest tests --ignore=tests/ui     # unit and regression tests (or: bash scripts/run_tests.sh)
python3 -m pytest                            # everything, including the browser tests
```

### Reproduce the manuscript results

```bash
pip install -r paper_eval/requirements.txt
python3 paper_eval/run_all.py        # several minutes; or: bash scripts/reproduce_results.sh
python3 paper_eval/check_paper.py    # checks every number, table, figure and reference of the manuscript
```

`run_all.py` rewrites `paper_eval/results/*.json`, `paper/tables/` and the data figures in `paper/figures/`. All sizes and counts are deterministic; only timings change from machine to machine. `python3 paper_eval/sample_outputs.py` writes the per-benchmark sample outputs in `results/sample_outputs/`. See [`paper_eval/README.md`](paper_eval/README.md) for every script.

---

## 7. Dataset

- `benchmarks/`: seven demonstration programs S1–S7.
- `benchmarks/kernels/`: ten C kernels K1–K10 that call functions and read input; each file's input is on its `// input:` line.
- Random programs are generated on the fly from fixed seeds by `paper_eval/generator.py` (1,000 + 500 for differential testing, 200 + 200 for the ablation, 64 for scaling, 300 for training the compressor dictionary). No download or preprocessing is needed.

## 8. Trained models

Not applicable: the project uses no machine-learning models.

## 9. Results

[`results/README.md`](results/README.md) summarizes the experimental results and evaluation metrics, with tables, figures and per-benchmark sample outputs. The raw results are in `paper_eval/results/`.

## 10. Documentation

- `manuscript/Manuscript_Draft2_IEEE_Access_Team16.pdf`: the manuscript (Draft 2, revised), IEEE Access format.
- `manuscript/manuscript_latex_overleaf.zip`: LaTeX source with all figures, tables, class and font files. On Overleaf choose *New Project → Upload Project*, upload the zip and compile `ir_compaction_access.tex` with pdfLaTeX. `paper/BUILD.md` describes a local build.
- `paper/response_to_reviewers.md`: how each review comment was addressed.
- `docs/`: design notes and project report.

## 11. Demo video

[Demo video link: add after uploading]
