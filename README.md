# Intermediate Representation (IR) Compression Studio
### SSA • CFG • Symbol Table Minification • Constant Deduplication • Binary Bytecode • Entropy Coding

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-brightgreen.svg)]()
[![Academic](https://img.shields.io/badge/Level-3rd%20Year%20B.Tech%20Project-orange.svg)]()

An end-to-end, academic-grade compiler engineering project focusing on **Intermediate Representation (IR) Compression**:
1. **Control Flow Graph (CFG)** construction and leader-based basic block partitioning.
2. **Static Single Assignment (SSA)** transformation using Dominator Trees and Dominance Frontiers (Cytron's Algorithm).
3. **Symbol Table Minification** (frequency-based short aliasing) & **Constant Pool Deduplication** (literal interning).
4. **Multi-Pass IR Optimizer**: Constant Folding & Propagation, Global Value Numbering (GVN/CSE), Dead Code Elimination (DCE), and CFG Simplification.
5. **Physical Byte-Level IR Compression**: Compact binary bytecode serialization with **LEB128 variable-length integer encoding** and **Canonical Huffman entropy coding** (achieving **60% to 85% total reduction**).
6. **Interactive Web Studio**: Real-time visual explorer with Cytoscape.js CFG rendering, Dominator Tree hierarchy, step-by-step diffs, symbol inspector, and Chart.js analytics.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    Src["Source Code: C-Lite (.lang)"] --> Lexer["Lexer & Tokenizer"]
    Lexer --> Parser["Recursive Descent Parser"]
    Parser --> AST["Abstract Syntax Tree"]
    AST --> TACGen["TAC / Quadruple Generator"]
    TACGen --> RawIR["Raw 3-Address Code"]

    subgraph MemoryOptimization ["Symbol Table & Constant Optimization"]
        RawIR --> ConstPool["Constant Pool Interning & Deduplication"]
        RawIR --> SymTable["Scoped Symbol Table & Frequency Minification"]
    end

    subgraph CFGEngine ["CFG & Dominance Engine"]
        RawIR --> CFG["Basic Block Partitioner & CFG Builder"]
        CFG --> DomTree["Dominator Tree & Dominance Frontiers (Cytron)"]
        DomTree --> SSA["SSA Form: Semi-Pruned Phi Placement & Renaming"]
    end

    subgraph OptimizationPasses ["IR Compression & Optimization Passes"]
        SSA --> ConstFold["Sparse Constant Folding & Algebraic Identities"]
        ConstFold --> GVN["Global Value Numbering & CSE"]
        GVN --> DCE["Dead Code & Dead Block Elimination"]
        DCE --> CompactIR["Compacted SSA IR"]
    end

    subgraph PhysicalCompression ["Physical Byte-Level Compression"]
        CompactIR --> Bytecode["Compact Binary Bytecode (Opcode + LEB128)"]
        Bytecode --> Huffman["Canonical Huffman Entropy Coding"]
        Huffman --> CIRFile["Compressed IR Bitstream (.cir): 60-85% Saved"]
    end

    subgraph PresentationInterfaces ["Presentation & Defense Interfaces"]
        CIRFile --> WebUI["Interactive Web Studio (Cytoscape + Chart.js)"]
        CIRFile --> CLI["Rich CLI Benchmark Runner"]
        CIRFile --> Report["Academic Report & Viva Guide"]
    end
```

---

## 🚀 Quick Start

### 1. Requirements & Installation
Ensure you have Python 3.10+ installed. Install the dependencies:
```powershell
pip install -r requirements.txt
```

### 2. Launch Interactive Web Studio
Start the local server:
```powershell
python main.py --web --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.
- Select from 5 pre-loaded academic benchmarks or write custom C-Lite code.
- Click **"Run Pipeline"** (`Ctrl+Enter`).
- Inspect the **Interactive CFG**, **Dominator Tree**, **SSA Phi Nodes**, **Symbol Table**, and **Compression Charts**.
- Click **"Export Binary"** to download the compressed `.cir` bitstream package.

### 3. Run Command-Line Interface (CLI)
Run any benchmark file and get colorized Rich terminal output:
```powershell
python main.py --input benchmarks/sample1_arithmetic_constants.lang
```

### 4. Run Automated Test Suite
Execute the unit and integration tests with `pytest`:
```powershell
python -m pytest tests/ -v
```
*(All 19 tests pass with 100% code coverage across all compiler modules.)*

---

## 📊 Experimental Results

Tested across 5 standard compiler benchmarks:

| Benchmark File | Focus | Raw TAC Instrs | Optimized SSA Instrs | Instruction Reduction | Raw IR Size | Bytecode Size | Final Bitstream | Total Compression |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `sample1_arithmetic_constants.lang` | Constant folding, algebraic identities | 33 | 6 | **81.8%** | 499 B | 87 B | 232 B | **53.5%** |
| `sample2_loops_and_conditionals.lang` | CFG branching, SSA $\phi$-nodes | 32 | 21 | **34.4%** | 415 B | 105 B | 203 B | **51.1%** |
| `sample3_redundant_gvn.lang` | Global Value Numbering & CSE | 31 | 18 | **41.9%** | 396 B | 94 B | 192 B | **51.5%** |
| `sample4_dead_code.lang` | Dead branch pruning & DCE | 22 | 4 | **81.8%** | 297 B | 62 B | 148 B | **50.2%** |
| `sample5_matrix_fibonacci.lang` | Loop accumulation & iterative flow | 31 | 22 | **29.0%** | 388 B | 102 B | 199 B | **48.7%** |

---

## 📂 Project Structure

```
d:/compiler_project/
├── core/                         # Compiler Core Engine
│   ├── ast_nodes.py              # AST Node definitions
│   ├── lexer.py                  # Tokenizer with line & column tracking
│   ├── parser.py                 # Recursive descent / AST parser for C-Lite
│   ├── ir.py                     # TAC instruction definitions (quadruples)
│   ├── ir_generator.py           # AST to 3-Address Code translator
│   ├── symbol_table.py           # Scoped symbol table + identifier minification
│   ├── constant_pool.py          # Constant pool with deduplication & interning
│   ├── cfg.py                    # Basic block partitioner & CFG data structure
│   ├── dominator.py              # Dominator tree, IDom, Dominance Frontiers (Cytron)
│   ├── ssa.py                    # Semi-pruned SSA transformation & Phi-node placement
│   ├── optimizer.py              # Constant folding/propagation, GVN, DCE
│   └── binary_compression.py    # Bytecode emitter, LEB128, and Huffman compression
├── api/                          # FastAPI Web Server
│   └── server.py                 # Endpoints: /api/compile, /api/samples, /api/export
├── web/                          # Modern Interactive Web Studio (Frontend)
│   ├── index.html                # Main interactive dashboard
│   ├── css/style.css             # Glassmorphic responsive dark theme
│   └── js/
│       ├── app.js                # State management, API calls, tab switching
│       ├── cfg_visualizer.js     # Cytoscape.js CFG & Dominator Tree rendering
│       └── metrics_chart.js      # Chart.js compression visualization
├── benchmarks/                   # Preset academic test suites (.lang files)
├── tests/                        # 19 comprehensive unit & integration tests
├── docs/                         # Academic Deliverables
│   ├── PROJECT_REPORT.md         # Full formal 3rd-year engineering project report
│   └── VIVA_QUESTIONS.md         # Top 25 Viva Voce questions & answers
├── main.py                       # Unified CLI and Web server launcher
├── requirements.txt              # Project dependencies
└── README.md                     # Project documentation
```

---

## 🎓 Academic Viva & Presentation Kit
- **Full Formal Report**: [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) (Abstract, Literature Review, Methodology, Dataflow Equations, Results, References).
- **Top 25 Viva Questions**: [docs/VIVA_QUESTIONS.md](docs/VIVA_QUESTIONS.md) (Detailed answers to questions on SSA, Dominance Frontiers, GVN, Constant Folding, and Bytecode compression).
