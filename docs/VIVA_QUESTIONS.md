# Top 25 Viva Voce Questions & Answers: IR Compression & Optimization

This guide is curated for university project defense, external examinations, and technical presentations on **Intermediate Representation Compression (SSA, CFG, Symbol Tables, Constants)**.

---

### Q1. What is Intermediate Representation (IR), and why is it essential in modern compilers?
**Answer:**  
An Intermediate Representation (IR) is a machine- and language-independent representation of the source program used internally by a compiler. It decouples the compiler frontend (lexer/parser) from the backend (code generator/register allocator). If a compiler supports $M$ source languages and $N$ target architectures, using an IR reduces the required translator modules from $M \times N$ to $M + N$. It also allows optimization passes to be written once and reused for all target architectures.

---

### Q2. What is Three-Address Code (TAC)?
**Answer:**  
Three-Address Code (TAC) is a linearized form of IR where every instruction has at most one operator on the right-hand side and at most three address references (typically two operands and one result: $x = y \text{ op } z$). In our project, TAC instructions are represented as quadruples: `(opcode, arg1, arg2, result)`.

---

### Q3. How do you partition linear TAC into Basic Blocks?
**Answer:**  
A Basic Block is a sequence of consecutive instructions where execution enters only at the first instruction and leaves only at the last instruction without stopping or branching in the middle. We partition TAC using **leader analysis**:
1. The first instruction is a leader.
2. Any instruction that is the target of a conditional or unconditional jump (a `LABEL`) is a leader.
3. Any instruction immediately following a conditional or unconditional jump or `return` is a leader.
Each block starts at a leader and extends to the instruction immediately preceding the next leader.

---

### Q4. What is a Control Flow Graph (CFG)?
**Answer:**  
A CFG is a directed graph $G = (V, E)$ where the vertices $V$ are basic blocks and the directed edges $E$ represent permissible transfers of control. Edges are classified into fallthrough edges, unconditional jump edges, and conditional branch true/false edges.

---

### Q5. What is Dominance in a Control Flow Graph?
**Answer:**  
In a CFG with entry node $r$, a node $d$ **dominates** a node $n$ ($d \text{ dom } n$) if every execution path from $r$ to $n$ must pass through $d$. Every node dominates itself.

---

### Q6. What is an Immediate Dominator ($IDom$)?
**Answer:**  
$IDom(n)$ is the unique strict dominator of $n$ ($d \text{ dom } n, d \neq n$) that does not dominate any other strict dominator of $n$. In graphical terms, $IDom(n)$ is the parent of $n$ in the **Dominator Tree**.

---

### Q7. What is a Dominance Frontier ($DF$)?
**Answer:**  
The Dominance Frontier $DF(x)$ of a node $x$ is the set of all nodes $y$ such that $x$ dominates a predecessor of $y$, but $x$ does not strictly dominate $y$ itself:
$$DF(x) = \{ y \mid \exists p \in \text{Pred}(y) \text{ such that } x \text{ dom } p \text{ and } x \text{ not sdom } y \}$$
$DF(x)$ marks the exact join points in the control flow graph where dominance of $x$ ends.

---

### Q8. Why is the Dominance Frontier critical for SSA transformation?
**Answer:**  
If a variable $v$ is defined in basic block $x$, that definition reaches all blocks dominated by $x$. However, at the border of $x$'s dominance—the Dominance Frontier $DF(x)$—control can arrive from an alternate path where $v$ might have a different definition. Therefore, **$DF(x)$ is precisely the set of basic blocks where a $\phi$ (Phi) function must be inserted for variable $v$!**

---

### Q9. What is Static Single Assignment (SSA) form?
**Answer:**  
SSA is an intermediate representation property where:
1. Every variable is assigned a value **exactly once**.
2. Every use of a variable is dominated by its unique definition.
Where multiple control paths converge, a special $\phi$-function selects the value based on which predecessor block executed.

---

### Q10. What are the key benefits of SSA form?
**Answer:**  
1. **Explicit Def-Use Chains**: Every variable name directly identifies its point of definition.
2. **Simplified Optimizations**: Constant propagation, Global Value Numbering, and Dead Code Elimination become significantly faster (often linear time) and more powerful because definitions never kill previous values.
3. **No False Anti-Dependencies**: Eliminates write-after-read (WAR) and write-after-write (WAW) hazards, facilitating instruction scheduling.

---

### Q11. What is a $\phi$ (Phi) function, and how does it execute?
**Answer:**  
A $\phi$-function has the form:
$$x_3 = \phi(BB_1: x_1, BB_2: x_2)$$
It chooses $x_1$ if control arrived from $BB_1$, or $x_2$ if control arrived from $BB_2$. $\phi$-functions do not exist in physical hardware; during machine code generation (SSA deconstruction), they are replaced by simple `COPY` instructions placed in the corresponding predecessor blocks.

---

### Q12. What is the difference between Minimal, Pruned, and Semi-Pruned SSA?
**Answer:**  
- **Minimal SSA**: Places $\phi$-functions at every iterated dominance frontier node for every variable, even if the variable is never used again (leads to unnecessary $\phi$ bloat).
- **Pruned SSA**: Uses full liveness analysis to only insert $\phi$-functions if the variable is live at that block. While optimal, computing global liveness is computationally expensive.
- **Semi-Pruned SSA (Used in our project)**: Identifies block-local variables (variables defined and used entirely within a single basic block) and avoids creating $\phi$-nodes for them. It is fast and eliminates over 80% of unnecessary $\phi$-nodes.

---

### Q13. How does the variable renaming step in SSA work?
**Answer:**  
We perform a Depth-First Search (DFS) over the **Dominator Tree**. For each variable, we maintain a version stack. When encountering a definition, we generate a fresh version (e.g., $x_1$) and push it to the stack. Uses are replaced with the top of the stack. When visiting successors, we populate their $\phi$-node arguments. When backtracking out of a basic block, we pop the versions pushed in that block to restore state for sibling branches.

---

### Q14. What is Constant Folding vs. Constant Propagation?
**Answer:**  
- **Constant Folding**: The compile-time evaluation of expressions whose operands are known constants (e.g., replacing $2 + 3$ with $5$).
- **Constant Propagation**: The process of replacing variable uses with their known constant values if a variable is guaranteed to hold a constant at that point (e.g., given $x = 5$, replacing $y = x + 2$ with $y = 5 + 2$).

---

### Q15. How does SSA simplify Constant Propagation?
**Answer:**  
In non-SSA form, determining whether a variable is constant requires complex dataflow equations across loops and branches. In SSA form, because each variable has only one assignment statement, if that assignment is constant, the variable is globally constant throughout its entire lifetime!

---

### Q16. What is Global Value Numbering (GVN)?
**Answer:**  
GVN is an optimization pass that assigns an integer value number to each variable and expression. If two expressions have the exact same operator and operand value numbers, they are guaranteed to compute identical values. GVN replaces the redundant computation with the existing variable, eliminating common subexpressions across the entire CFG.

---

### Q17. How does GVN handle commutative operations?
**Answer:**  
In our project, commutative operations (`+`, `*`, `==`, `!=`) canonicalize their operands (ordering them lexicographically). Therefore, $(a + b)$ and $(b + a)$ produce identical hash keys in the expression table, allowing the compiler to detect that they are the same computation.

---

### Q18. How does Dead Code Elimination (DCE) work in your project?
**Answer:**  
DCE uses def-use tracking. We inspect every instruction in the CFG: if an instruction defines a variable that has zero uses across all basic blocks, and the instruction does not produce side effects (like `print`, `return`, or branch jumps), the instruction is removed. This is repeated until no more dead instructions exist.

---

### Q19. What is Constant Pool Deduplication (Interning)?
**Answer:**  
In naive code, if the string `"Optimization Active"` or number `3.14159` appears 5 times, it is stored 5 separate times in memory. In our Constant Pool, identical literals are hashed and mapped to a single entry (`CP#0`, `CP#1`). All instructions reference this single index, saving memory.

---

### Q20. What is Symbol Table Minification?
**Answer:**  
Long variable names (e.g., `temporary_counter_index`) take up substantial memory in symbol tables. Our symbol table counts the reference frequency of every identifier and maps the most frequent identifiers to the shortest aliases (`_a`, `_b`, ...), yielding a 60–65% reduction in symbol table memory.

---

### Q21. Why did you compress the IR down to binary bytecode?
**Answer:**  
Text-based IRs (like raw TAC or `.ll` files) are verbose and human-readable, but too large for network transfer, caching, or execution in memory-constrained environments. Modern systems (like Java bytecode, Android DEX, and WebAssembly) use compact binary formats.

---

### Q22. What is LEB128 encoding?
**Answer:**  
LEB128 (Little-Endian Base 128) is a variable-length code used to store arbitrary large integers in a compact number of bytes. Numbers between 0 and 127 take only 1 byte instead of standard 4 or 8 bytes. It is the standard integer compression format in WebAssembly and DWARF debug formats.

---

### Q23. How does Canonical Huffman Coding work?
**Answer:**  
Huffman coding builds an optimal binary prefix tree where frequent byte values get shorter bit sequences and rare bytes get longer bit sequences. In our system, the serialized bytecode is compressed into a bitstream, achieving lossless compression. Decompression integrity is verified through round-trip assertions.

---

### Q24. What overall compression results did your project achieve?
**Answer:**  
- **Instruction Reduction**: 30% to 82% fewer instructions through constant folding, GVN, and DCE.
- **Physical Byte Reduction**: 74% to 85% byte reduction when translating raw TAC text into binary bytecode.
- **Overall Bitstream Compression**: Over 50% to 54% final bitstream reduction after Huffman coding.
- **Symbol Table Reduction**: 60% to 65% memory savings.

---

### Q25. What is the execution flow of your project?
**Answer:**  
1. Source code is tokenized by the **Lexer** and parsed by the **Parser** into an **AST**.
2. **IRGenerator** emits raw linear **TAC**, populating the **Symbol Table** and **Constant Pool**.
3. **ControlFlowGraph** partitions TAC into **Basic Blocks**.
4. **DominanceAnalyzer** constructs the **Dominator Tree** and calculates **Dominance Frontiers**.
5. **SSATransformer** inserts $\phi$-nodes and renames variables into SSA form.
6. **IROptimizer** executes Constant Folding, GVN, DCE, and block pruning.
7. **BytecodeEmitter** and **HuffmanCompressor** emit the final compact binary IR package.
8. The results are served via a **FastAPI backend** to an interactive **Web Studio** with real-time Cytoscape graph rendering.
