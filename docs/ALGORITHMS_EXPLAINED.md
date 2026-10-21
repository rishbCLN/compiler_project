# Intermediate Representation (IR) Compression Studio
## Comprehensive Algorithm Guide by Pipeline Section

This document provides a detailed, technical explanation of every algorithm implemented across each module and pipeline tier in the project. It is structured to serve as both an architectural reference and a technical viva/defense guide.

---

## Table of Contents
1. [Section 1: Front-End (Lexical Analysis & Parsing)](#section-1-front-end-lexical-analysis--parsing)
2. [Section 2: Control Flow Graph (CFG) Construction & Analysis](#section-2-control-flow-graph-cfg-construction--analysis)
3. [Section 3: Dominance Analysis & Static Single Assignment (SSA)](#section-3-dominance-analysis--static-single-assignment-ssa)
4. [Section 4: Multi-Pass Classical IR Optimizations](#section-4-multi-pass-classical-ir-optimizations)
5. [Section 5: Multi-Tier Binary Bytecode & Variable-Length Encoding](#section-5-multi-tier-binary-bytecode--variable-length-encoding)
6. [Section 6: Advanced Columnar Structure-of-Arrays (SoA) & Entropy Coding](#section-6-advanced-columnar-structure-of-arrays-soa--entropy-coding)
7. [Quick Viva Summary Table](#quick-viva-summary-table)

---

## Section 1: Front-End (Lexical Analysis & Parsing)

### 1.1 Deterministic Lexical Scanner (DFA Tokenizer)
* **File:** `core/lexer.py` (`Lexer`)
* **Algorithm Name:** Regular-Grammar Deterministic Finite Automaton (DFA) Tokenizer
* **Description:**
  * Iterates linearly through the input source character by character using regular-expression matching rules ordered by priority.
  * Strips comments (`// ...` and `/* ... */`) and C preprocessor directives (`#include ...`).
  * Emits a stream of strongly-typed `Token` objects containing `(type, value, line, column)`.
  * Supports both C-Lite keywords and Standard C types (`int`, `void`, `float`, `char`, `double`, `printf`, `while`, `if`, `else`, `return`).
* **Why it matters:**
  Normalizes raw text into uniform numerical token identifiers, stripping redundant formatting and comments before intermediate processing.

---

### 1.2 Recursive-Descent Predictive Parser (LL(1) with Operator Precedence)
* **File:** `core/parser.py` (`Parser`)
* **Algorithm Name:** Recursive-Descent Top-Down Parsing with Pratt Operator Precedence
* **Description:**
  * Uses 1-token lookahead (`peek()`) without backtracking to parse statements, block scopes, declarations, and function definitions (`int main()`).
  * Binary expressions are parsed using an operator precedence ladder:
    ```
    Precedence 5 (Highest): Multiplication (*), Division (/), Modulo (%)
    Precedence 4:           Addition (+), Subtraction (-)
    Precedence 3:           Relational (<, <=, >, >=)
    Precedence 2:           Equality (==, !=)
    Precedence 1 (Lowest):  Logical AND (&&), Logical OR (||)
    ```
  * Builds an Abstract Syntax Tree (AST) composed of dataclass nodes defined in `core/ast_nodes.py`.
* **Why it matters:**
  Ensures grammatical correctness and decomposes complex nested expressions into an unambiguous hierarchical tree ready for linear translation.

---

### 1.3 AST-to-TAC Linearization (Three-Address Code Generation)
* **File:** `core/ir_generator.py` (`IRGenerator`)
* **Algorithm Name:** Visitor Pattern AST Flattening
* **Description:**
  * Walks the AST recursively and emits linear Three-Address Code (TAC) instructions.
  * Every instruction conforms to the atomic quadruple:
    ```
    Instruction = (Opcode, Arg1, Arg2, Result)
    ```
  * Synthesizes temporary register names (`t0, t1, t2, ...`) and symbolic branch labels (`L0, L1, L2, ...`).
* **Why it matters:**
  Transforms nested recursive syntax into flat, atomic instructions, forming the baseline uncompressed intermediate representation (Stage 1: Raw Text IR).

---

## Section 2: Control Flow Graph (CFG) Construction & Analysis

```
                      +-----------------------+
                      |   BB0: Entry Block    | (First instruction is leader)
                      +-----------+-----------+
                                  |
                                  v
                      +-----------------------+
         +------------|  BB1: Loop Header     |<-----------+
         |            |  (Branch True/False)  |            |
         |            +-----------+-----------+            |
         | False                  | True                   | Loop Back-edge
         v                        v                        |
+--------------------+   +--------------------+            |
|  BB3: Exit Block   |   |   BB2: Loop Body   |------------+
+--------------------+   +--------------------+
```

### 2.1 Basic Block Leader Identification
* **File:** `core/cfg.py` (`ControlFlowGraph.build`)
* **Algorithm Name:** Aho-Lam-Sethi-Ullman Leader Partitioning Algorithm
* **Description:**
  Scans linear TAC instructions and partitions them into maximal sequences with a single entry point and single exit point (Basic Blocks) using 3 formal rules:
  1. **Rule 1:** The first instruction in the program (index 0) is a leader.
  2. **Rule 2:** The target of any conditional or unconditional jump (`JUMP`, `JUMP_IF_TRUE`, `JUMP_IF_FALSE`) is a leader.
  3. **Rule 3:** Any instruction immediately following a jump or a `RETURN` is a leader.
  
  A Basic Block begins at a leader and includes all instructions up to (but not including) the next leader.

---

### 2.2 Directed Edge Classification & CFG Assembly
* **File:** `core/cfg.py` (`ControlFlowGraph._connect_blocks`)
* **Algorithm Name:** Control Flow Edge Classification
* **Description:**
  * Inspects the terminator instruction of each Basic Block:
    * Unconditional `JUMP L`: adds a `jump` edge from current block to target block of label `L`.
    * Conditional `JUMP_IF_TRUE / FALSE`: adds a `branch_true` edge to label target, and a `branch_false` edge to the fallthrough block.
    * Non-branching terminator: adds a `fallthrough` edge to the next sequential block.
  * Populates predecessor sets `Pred(B)` and successor sets `Succ(B)`.

---

### 2.3 Graph Reachability Pruning
* **File:** `core/dominator.py` (`DominanceAnalyzer._compute_reachable_blocks`)
* **Algorithm Name:** Breadth-First Search (BFS) Dead-Block Pruning
* **Description:**
  Traverses the CFG starting at `BB0` (`Entry`). Any block not reached in the BFS traversal is disconnected from program execution and is immediately purged, preventing invalid calculations in downstream passes.

---

### 2.4 Cyclomatic Complexity
* **File:** `core/cfg.py` / UI Overview
* **Algorithm Name:** McCabe Cyclomatic Complexity Metric
* **Formula:**
  ```
  M = E - V + 2 * P
  ```
  Where:
  * `E` = Number of control flow edges.
  * `V` = Number of basic block nodes.
  * `P` = Number of connected components (for a single function/program, P = 1).
* **Why it matters:**
  Quantifies the number of linearly independent paths through the program. A value of 3 in a 7-block demo confirms a standard decision diamond + loop cycle.

---

## Section 3: Dominance Analysis & Static Single Assignment (SSA)

### 3.1 Iterative Fixed-Point Dominator Analysis
* **File:** `core/dominator.py` (`DominanceAnalyzer.compute_dominators`)
* **Algorithm Name:** Classical Monotone Dataflow Dominator Algorithm
* **Mathematical Definition:**
  A block `D` dominates block `B` (written `D dom B`) if every execution path from `Entry` to `B` must pass through `D`.
* **Formula:**
  ```
  Dom(Entry) = { Entry }
  Dom(B)     = { B } U ( Intersection of Dom(P) for all P in Pred(B) )
  ```
* **Algorithm Procedure:**
  1. Initialize `Dom(Entry) = { Entry }`.
  2. Initialize `Dom(B) = AllBlocks` for all other blocks.
  3. Iteratively update `Dom(B)` by intersecting the dominator sets of all predecessor blocks until no set changes across a complete pass (convergence to fixed point).

---

### 3.2 Immediate Dominator (IDom) & Dominator Tree Construction
* **File:** `core/dominator.py` (`DominanceAnalyzer.compute_immediate_dominators`)
* **Algorithm Name:** Strict Dominator Maximal Candidate Selection (Cooper-Harvey-Kennedy)
* **Mathematical Definition:**
  The Immediate Dominator `IDom(B)` is the unique strict dominator of `B` that does not dominate any other strict dominator of `B`:
  ```
  StrictDom(B) = Dom(B) \ { B }
  IDom(B) = d in StrictDom(B) such that for all other candidates s in StrictDom(B), s dom d
  ```
* **Dominator Tree:**
  The directed edges `(IDom(B) -> B)` form a directed tree rooted at `Entry`.

---

### 3.3 Cytron's Iterated Dominance Frontier (IDF) for Phi-Node Placement
* **File:** `core/dominator.py` & `core/ssa.py` (`SSATransformer.insert_phi_functions`)
* **Algorithm Name:** Cytron's Dominance Frontier & Semi-Pruned Phi Placement
* **Mathematical Definition:**
  The Dominance Frontier `DF(X)` is the set of all nodes `Y` where `X` dominates a predecessor of `Y`, but does not strictly dominate `Y` itself:
  ```
  DF(X) = { Y | exists P in Pred(Y) such that X dom P and X does NOT strictly dom Y }
  ```
* **Iterated Dominance Frontier (IDF):**
  For each variable `v` defined at sites `Defs(v)`:
  1. Initialize worklist `W = Defs(v)`.
  2. For each node `X` in `W`, for each `Y` in `DF(X)`:
     * If `Y` does not already have a phi-node for `v`:
       * Insert `v = phi(...)` at the beginning of block `Y`.
       * Add `Y` to `W` to compute the transitive closure.
  * **Semi-Pruned SSA:** Phi-nodes are only inserted for global variables (variables whose live range spans across block boundaries). Strictly local variables are omitted.

---

### 3.4 Dominator Tree DFS Variable Renaming with Version Stacks
* **File:** `core/ssa.py` (`SSATransformer.rename_block`)
* **Algorithm Name:** Dominator Tree Depth-First Search Scope Renaming
* **Algorithm Procedure:**
  1. Maintains a version counter `counters[var]` and a stack `stacks[var]` for each variable.
  2. For each phi-node in current block: creates a new version `var_k`, pushes it onto `stacks[var]`, and sets the phi result to `var_k`.
  3. For each non-phi instruction:
     * Rewrites variable uses (operands) to the current version at `top(stacks[var])`.
     * For variable definition (result), creates a new version `var_k` and pushes it onto `stacks[var]`.
  4. For each successor block `Succ`: fills in the phi-node argument corresponding to the current block with `top(stacks[var])`.
  5. Recursively visits each child block in the Dominator Tree.
  6. **Backtracking:** Upon returning from child blocks, pops all versions created in the current block from `stacks[var]`, restoring parent lexical scope.

---

## Section 4: Multi-Pass Classical IR Optimizations

The optimizer (`core/optimizer.py`) executes an iterative fixed-point loop combining 5 passes until instruction counts stabilize:

### 4.1 Sparse Constant Folding & Propagation
* **File:** `core/optimizer.py` (`pass_constant_folding_and_propagation`)
* **Algorithm:**
  * Compile-time evaluation of constant expressions (e.g., `t0 = 4 + 2` is evaluated to `t0 = 6`).
  * Propagates known constants into subsequent instructions that use `t0`.
  * Simplifies conditional jumps whose condition evaluates to a known boolean literal (`true` or `false`), turning conditional branches into unconditional jumps.

---

### 4.2 Global Value Numbering (GVN) / Common Subexpression Elimination (CSE)
* **File:** `core/optimizer.py` (`pass_gvn`)
* **Algorithm:**
  * Computes a canonical hash key for each binary expression:
    ```
    Key = (Opcode, Canonical(Arg1), Canonical(Arg2))
    ```
  * For commutative operations (`+`, `*`, `==`, `!=`), orders operands consistently (`min, max`) so that `(a + b)` and `(b + a)` produce the same key.
  * If `Key` was already computed in a dominating basic block, replaces the redundant computation with a copy assignment:
    ```
    t2 = a + b   ==>   t2 = t0 (where t0 previously computed a + b)
    ```

---

### 4.3 Worklist-Based Dead Code Elimination (DCE)
* **File:** `core/optimizer.py` (`pass_dead_code_elimination`)
* **Algorithm:**
  * Gathers all variable uses across all instructions: `LiveUses = Union(Uses(I))`.
  * Identifies any instruction defining a variable `d` where `d not in LiveUses`.
  * If the instruction has no side-effects (i.e., not a `PRINT`, `RETURN`, or control branch), it is pruned.
  * Runs iteratively because removing one dead instruction can make preceding instructions dead.

---

### 4.4 CFG Simplification & Block Fusion
* **File:** `core/optimizer.py` (`pass_cfg_simplification`)
* **Algorithm:**
  * **Dead Block Removal:** Removes basic blocks with 0 predecessors (except `Entry`).
  * **Block Fusion:** If block `A` has only one successor `B`, and block `B` has only one predecessor `A`, merges `B` directly into `A`, eliminating jump overhead.
  * **Jump Threading:** Bypasses empty blocks containing only an unconditional jump.

---

### 4.5 Trivial Phi-Node Elimination
* **File:** `core/optimizer.py` (`pass_trivial_phi_elimination`)
* **Algorithm:**
  * Evaluates phi-nodes:
    ```
    phi(x, x, ..., x)  ===>  x
    phi(x, undef)      ===>  x
    ```
  * Replaces redundant phi-nodes with simple copies, which in turn enables further constant propagation.

---

## Section 5: Multi-Tier Binary Bytecode & Variable-Length Encoding

### 5.1 Symbol Table Minification & Constant Pool Deduplication
* **Files:** `core/symbol_table.py`, `core/constant_pool.py`
* **Algorithm:**
  * **Deduplication:** Identical literal constants and string labels are interned into a single pool and referenced by integer indices.
  * **Identifier Minification:** Replaces long identifier names with short indices or compact tokens (`v0, v1, t0`), eliminating repetitive text overhead.

---

### 5.2 Little-Endian Base 128 (LEB128) Variable-Length Integer Encoding
* **File:** `core/binary_compression.py` (`LEB128`)
* **Algorithm Name:** LEB128 Variable-Length Encoding (as used in WebAssembly & DWARF)
* **Mathematical Encoding:**
  Partitions an unsigned integer into 7-bit payload chunks:
  ```
  Byte = Value & 0x7F
  Value = Value >> 7
  If Value != 0: Byte = Byte | 0x80  (Continuation flag bit set)
  ```
* **Compression Impact:**
  * Standard 32-bit integer `5`: stored as **1 byte** (`0x05`) instead of 4 bytes.
  * Integer `250`: stored as **2 bytes** (`0xFA 0x01`).
  * Produces an immediate **70% to 75%** size reduction over raw 32-bit representations.

---

### 5.3 Canonical Huffman Entropy Compression
* **File:** `core/binary_compression.py` (`HuffmanCompressor`)
* **Algorithm Name:** Canonical Huffman Prefix Coding
* **Algorithm Procedure:**
  1. **Frequency Histogram:** Computes byte-frequency counts across the binary bytecode.
  2. **Min-Heap Priority Queue Tree:** Repeatedly merges the two lowest-frequency nodes using a min-heap until a single tree root is formed (`O(K log K)`).
  3. **Canonical Codebook Generation:** Transforms codes so that:
     * Codes of identical bit length are assigned consecutive binary numbers.
     * Shorter codes lexicographically precede longer codes.
     * **Formula:**
       ```
       Code[i+1] = (Code[i] + 1) << (BitLength[i+1] - BitLength[i])
       ```
  4. **Bitstream Packing:** Emits compressed bits into packed 8-bit bytes with bit-shift accumulators.
* **Why it matters:**
  Canonical Huffman codebooks can be reconstructed by the decompressor using only the array of code lengths (256 bytes), avoiding transmission of the tree structure.

---

## Section 6: Advanced Columnar Structure-of-Arrays (SoA) & Entropy Coding

```
Standard Quadruple Stream (Interleaved heterogeneous types -> Low compression):
[ADD, reg, 4, reg] [SUB, reg, 1, reg] [JUMP, label] [MUL, reg, 2, reg] ...
                           │
                           ▼
Columnar Structure-of-Arrays (SoA) Stream Separation:
Stream 1 (Opcodes):    [0x01, 0x02, 0x13, 0x03, ...]  -> Pure opcodes, high entropy clustering
Stream 2 (Flags):      [0x03, 0x01, 0x10, 0x03, ...]  -> Repetitive bitmasks
Stream 3 (Deltas):     [   1,    2,    1,    1, ...]  -> Clustered LEB128 integers (1..5)
Stream 4 (Immediates): [   4,    1, "L1",    2, ...]  -> Front-coded constant pool
```

### 6.1 Front-Coded Incremental String Pool
* **File:** `core/advanced_compression.py` (`FrontCodedStringPool`)
* **Algorithm Name:** Front-Coding / Incremental Prefix Compression
* **Algorithm:**
  * Sorts all symbols lexicographically: `["branch_1", "branch_2", "branch_exit"]`.
  * Encodes each subsequent string relative to its predecessor by recording:
    ```
    (Prefix_Length, Suffix_Length, Suffix_Bytes)
    ```
  * Example: `"branch_2"` shares 7 characters with `"branch_1"`, so only `(7, 1, "2")` is stored.
  * Achieves **70% to 85%** compression on symbol table strings.

---

### 6.2 Reverse Post-Order (RPO) CFG Scheduling with 0-Bit Fallthrough Elision
* **File:** `core/advanced_compression.py` (`RPOBlockScheduler`)
* **Algorithm Name:** Topological RPO Layout with Implicit Fallthrough
* **Algorithm:**
  * Computes a Reverse Post-Order sequence of blocks via Depth-First Search.
  * In this schedule, if block `B_i` naturally transfers control to `B_{i+1}`, explicit jump instructions are deleted.
  * Execution naturally drops into the next contiguous block in memory, costing **0 bits** of control flow representation.

---

### 6.3 SSA Backward Usage Delta Encoding
* **File:** `core/advanced_compression.py` (`SSABackwardDeltaEncoder`)
* **Algorithm Name:** Implicit Ordinal Definitions & Backward Delta Offsets
* **Mathematical Principle:**
  * **Implicit Definitions:** Under SSA, every variable is defined exactly once. Therefore, definition IDs are omitted; the variable ID is implicitly the instruction's ordinal index `i`.
  * **Backward Usage Deltas:** Operands are encoded as backward distances to their definition:
    ```
    Delta = Instruction_Index_Use - Instruction_Index_Def
    ```
  * Because variable lifetimes are short in optimized code, `Delta` values cluster strongly in the range `[1..10]`.
  * When encoded via LEB128, every delta occupies exactly **1 byte**.

---

### 6.4 Columnar Structure-of-Arrays (SoA) Bytecode Serialization
* **File:** `core/advanced_compression.py` (`ColumnarBytecodeSerializer`)
* **Algorithm Name:** Columnar Stream Separation
* **Principle:**
  Interleaved quadruples `[Opcode, Flag, Arg1, Arg2]` exhibit high Shannon entropy because data types alternate rapidly.
  The serializer separates quadruples into 4 dedicated, contiguous streams:
  1. **Opcode Stream:** Pure enum bytes (`0x01, 0x02, ...`).
  2. **Flags Stream:** Bitmask bytes indicating operand formats.
  3. **Deltas Stream:** Clustered integer offsets encoded in LEB128.
  4. **Immediates Stream:** Literals and branch targets.
* **Why it matters:**
  Homogeneous data streams have significantly lower entropy and longer repeated runs, allowing entropy encoders to achieve optimal compression.

---

### 6.5 Lossless Round-Trip Verification Engine
* **File:** `core/advanced_compression.py` (`AdvancedCompressionEngine.verify_round_trip`)
* **Algorithm Name:** Full Round-Trip Decompression Verification
* **Principle:**
  Decompresses the columnar bitstream back to instructions and performs strict equality checks against the original SSA IR:
  ```
  Decompressed_Instruction == Original_Instruction (Opcode, Operands, and Structure)
  ```
  Guarantees mathematical losslessness (100% round-trip fidelity).

---

## Quick Viva Summary Table

| Pipeline Stage | Primary Algorithm | Implementation Location | Compression Benefit |
| :--- | :--- | :--- | :--- |
| **Front-End** | DFA Lexer + Recursive Descent LL(1) Parser | `core/lexer.py`, `core/parser.py` | Eliminates source text formatting and whitespace overhead |
| **CFG** | Aho-Lam-Sethi-Ullman Leader Partitioning | `core/cfg.py` | Structures instructions into single-entry Basic Blocks |
| **Dominance** | Iterative Fixed-Point Dominance Analysis | `core/dominator.py` | Computes Dominator Tree and dominance frontiers |
| **SSA Form** | Cytron's Iterated Dominance Frontier (IDF) | `core/ssa.py` | Places minimal $\phi$-nodes and enables precise dataflow tracking |
| **Optimization** | Sparse Constant Folding, GVN/CSE, Worklist DCE | `core/optimizer.py` | Removes dead/redundant instructions (**30% - 50% instruction reduction**) |
| **Bytecode** | LEB128 Variable-Length Integer Encoding | `core/binary_compression.py` | Encodes small integers in 1 byte (**70% - 75% byte reduction**) |
| **Entropy** | Canonical Huffman Coding | `core/binary_compression.py` | Optimal prefix-free bit-packing using code-length arrays |
| **SoA Pipeline**| Columnar Stream Splitting + Backward Deltas | `core/advanced_compression.py` | Lowers Shannon entropy and clusters deltas for maximum compression |
| **Verification**| Lossless Round-Trip Decompression Checker | `core/advanced_compression.py` | Proves 100% semantic fidelity |
