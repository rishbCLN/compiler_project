# Response to the reviewers

**Manuscript:** Optimize Before You Compress: SSA-Based Compaction of Three-Address Code, Verified by Differential Testing
**Decision:** Major revision

We thank the reviewer for a careful and constructive report. All fifteen comments are addressed below. Each answer
states what was changed in the compiler, in the evaluation, and in the manuscript. All numbers in the revised
manuscript come from the evaluation scripts that are now part of the repository (`paper_eval/`). The numbers in the
text are generated as LaTeX macros, so the prose, tables and figures cannot drift apart. Section and table numbers
refer to the revised manuscript.

---

### 1. (Major) Unfair comparison with compressors

*We agree.* The main comparison now applies Brotli, Zstandard and xz to the **optimized text**, i.e., the same
optimized program that the CLIR package encodes (Section IV-D, "Comparison with general-purpose compressors", Table 6, Fig. 10). CLIR is smaller than the best of
the three on every benchmark:

* by 3.4% to 59.7% on the seven demonstration programs, and
* by 39.5% to 50.9% on ten new kernels (comment 5).

The smallest margin is S1, whose package consists mainly of string literals. The DEFLATE values the reviewer cited
(45, 38 and 29 bytes for S1, S3 and S4) were smaller than the CLIR packages of the first version, because those
packages carried an unpruned constant pool (comment 8). With the revised encoder, CLIR takes 56, 29 and 20 bytes.
The raw-text comparison is kept only as context and is explicitly said to mix optimization with encoding. The
Abstract and the Conclusion now report the optimized-text comparison.

### 2. (Major) CLIR did not store all information needed to decode it

*We agree, and we fixed the format.* CLIR is now self-describing:

* **Operands.** A value operand is tagged in its lowest bit: `2r` for register `r`, `2q+1` for constant-pool index `q`.
  Literal operands that propagation places into instructions are therefore stored in the package.
* **Pool.** The pool is rebuilt from the optimized code (see comment 8).
* **Structure.** The package lists the basic blocks and the functions, and each φ-argument names its predecessor block.

The decoder now needs no table from the encoder. The reported sizes include everything (Eq. (12), Fig. 3).
Correctness is checked in two ways: every package is decoded without side tables and compared with the optimized
program up to a consistent renaming, and the decoded CFGs are executed by the reference interpreter
(Section IV-D, "Correctness"). Code: `core/binary_compression.py` (`BytecodeEmitter`, `BytecodeDecoder.decode_module`).

### 3. (Major) The columnar container lost φ-arguments

*We agree.* Use-to-definition distances are now signed and zigzag-coded, so the 7 forward-referencing φ-arguments of
S2, S5, S6 and S7 are stored. Every φ-argument and call argument carries its own kind flag, so literal arguments
survive too. The round-trip check now decodes the container back to instructions and compares them with the
optimized program, instead of comparing the encoder's own intermediate records (which a lossy encoding reproduces).
Regression tests cover a forward reference and every benchmark (`tests/test_review_fixes.py`).

### 4. (Major) Which version of the folder produced the results

* **Results.** All tables and figures of the revision were produced with the **corrected** folder. Integer `/`
  truncates toward zero and `%` takes the sign of the dividend (Eq. (7)).
* **Repository.** The fix is in the released repository (commit "fix(optimizer): fold / and % with C truncating
  semantics", tag `paper-revision-1`).
* **Severity.** The Abstract now states it: the first release miscompiled 213 of 1,000 random programs (21.3%). All
  213 divergences disappear when both programs are run with floor division (Table 10). With the corrected folder, all
  1,000 programs agree, as do 500 further programs that read input.
* **Second defect.** While preparing the revision we found and fixed a front-end defect: a temporary could share its
  name with a program variable such as `t1` (S5 declares one) and overwrite it. S5 was not affected. It is reported in
  Section IV-D, "Correctness".

### 5. (Major) The benchmarks favour constant folding

*We agree.* The language now supports user-defined functions (including recursion), `input()` and `scanf`. Ten C
kernels that read input and call functions were added (`benchmarks/kernels/`, Table 3): GCD/LCM, Newton's integer
square root, modular exponentiation, bit counting, Collatz, primes, Fibonacci (iterative and recursive), Adler-32 sums,
Zeller's congruence and a fixed-point filter.

* **Validity.** They are valid C. Their native clang build is the reference output, and they also run as mechanically
  translated Java.
* **Results.** They are reported separately: optimization removes only 19.0% to 34.3% of their instructions, against
  48.1% to 89.3% for the demonstration programs. The manuscript calls the latter an upper bound.
* **Random programs with input.** These are used for differential testing (500), ablation (200) and scaling (64).

### 6. (Major) Compare against existing compact bytecode formats

* **Literature.** A new subsection (Section II-E, "Code and Bytecode Compression") reviews code and bytecode compression: Ernst et al. (PLDI 1997),
  Franz and Kistler's slim binaries, Pugh's Java class-file compression, Lucco's split-stream compression (the idea
  behind our columnar container), Evans and Fraser's grammar rewriting, and Debray et al.'s code compaction.
* **Design comparison.** Table 7 compares CLIR with the WebAssembly binary format, LLVM bitcode and Java class files
  (integer encoding, operand model, literals, control flow, metadata, entropy coding).
* **Measured sizes.** Table 8 gives the kernels' Java class files (`javac -g:none`) and LLVM bitcode (`clang -Oz`),
  each with an empty-program baseline. Class files are 3.2–6.0× larger than CLIR (2.0–3.5× net of the empty program)
  and bitcode 22–46× (11–24× net). We state that both formats carry types, symbols and metadata that CLIR omits.
* **WebAssembly** is compared by design only: the installed clang has no wasm32 target.

### 7. (Major) The Huffman break-even point is caused by the header

*We agree, and implemented canonical Huffman coding.* The header now holds the input length and only the 4-bit code
lengths, as the smallest of three table layouts. It is at most 132 bytes, against 1,287 bytes for the old frequency
table; code lengths are limited to 15 bits (Eq. (13), Fig. 3(b)).

* **Break-even.** In the scaling study, canonical coding breaks even between 81 and 115 bytes. With the old header the
  threshold lay between 5,031 and 7,837 bytes. The break-even model classifies all 64 programs correctly for both
  headers.
* **Benchmarks.** Canonical coding now shrinks 11 of the 17 packages, including 9 of the 10 kernels.
* **Text.** The manuscript says explicitly that the earlier 5.7 kB figure was a property of the header design. The old
  coder is kept as `FrequencyTableHuffman` for this comparison.

### 8. (Major) Prune the constant pool

*Done.* The pool holds exactly the literals the optimized instructions refer to, in order of first use. Integers are
zigzag LEB128 and Booleans take only a tag byte. S4 shrinks from 61 bytes (47 of them an unused pool) to 20 bytes
(4 of them pool). The effect is reported in Section IV-D, "Size reduction", and in Table 5 (pool/instruction split).

### 9. (Major) Strengthen the optimizer

*Implemented both passes.*

* **SCCP.** Wegman–Zadeck sparse conditional constant propagation propagates constants through φ-functions along
  executable edges and removes branches that can never be taken (Eq. (8)).
* **Copy propagation** replaces every use of a copy by its source; in SSA form this is always safe.
* **Measured effect.**
  * S5 now keeps 14 instead of 22 of its 27 instructions.
  * On 200 random programs, the five original passes leave 32,165 of 64,048 instructions and all seven leave 25,173.
  * Disabling copy propagation costs +17.4%.
* **Value numbering** now replaces 108 expressions in 67 programs, and disabling it costs 66 instructions, because the
  copies it creates are propagated away. Folding and SCCP overlap, which the ablation shows (Fig. 8).
* **Switchable passes.** Every pass can be switched off (`IROptimizer(passes=...)`), and the fixed-point loop now
  stops when the program text, not only the instruction count, stops changing.

### 10. (Minor) Why some representations grow

*Explained in Section IV-D, "Size reduction" and "Instruction reduction".*

* **Text size.** SSA conversion appends a version number to every variable occurrence and adds φ-lines. The SSA text is
  therefore 29.8% to 68.9% longer than the raw text, although it has only 0% to 16.1% more instructions. In the
  kernels, version suffixes (1,360 bytes) and φ-lines (1,626 bytes) outweigh the removed instructions, so the optimized
  text (8,401 bytes) is longer than the raw text (7,818 bytes). With copy propagation, S5's optimized text (280 bytes)
  is now shorter than its raw text (350 bytes). CLIR numbers names, so it is not affected.
* **The 144.6% figure.** The ablation bars are relative to the fully optimized result, not to the raw TAC. Relative to
  the raw TAC, the SSA form adds only 8.9% (its φ-functions). The figure caption and the text now say so.

### 11. (Minor) Container overhead on very small inputs

*Done* (Section IV-D, "Comparison with general-purpose compressors", Table 6).

* **Headerless streams.** We report magic-less Zstandard frames without checksum, content size and dictionary id, and
  raw LZMA2 instead of `.xz`. Brotli streams and raw DEFLATE have no container to remove. CLIR remains smaller on all
  kernels (by 39.5–50.9%) and on six of the seven demonstration programs; it loses by 3.7% on S1.
* **Shared dictionary.** We also report a 4 KiB dictionary trained by Zstandard on 300 random programs, used by Zstandard
  and as DEFLATE preset dictionary, and not counted per file. With it, the compressors beat CLIR on S1, S2, S3, S4 and
  S6, the smallest programs, which consist mostly of dictionary tokens; CLIR stays 25.5–37.9% smaller on all kernels.
  The Python Brotli binding offers no custom dictionaries, so Brotli is not tested with one.

### 12. (Major) Release the evaluation scripts

*Done.* The evaluation scripts are in `paper_eval/`, together with their results (`paper_eval/results/*.json`), a README
and pinned requirements. `python3 paper_eval/run_all.py` regenerates every table, figure and number in about three
minutes. The scripts used for the first draft were not in the repository; they were rewritten for the revision. The
Data and Code Availability statement points to the repository and the tag `paper-revision-1`.
`paper_eval/check_paper.py` checks that every number macro, table file, figure, reference and citation of the manuscript
resolves. The repository's test suite (113 tests) includes a small differential test.

### 13. (Major) IEEE-style references

*Done.* All 41 references are in IEEE style, with initials, abbreviated venues, "et al." beyond six authors, and
numbering in order of first citation. DOIs were checked against Crossref.

* **Published versions** are cited where they exist: CompilerGym (CGO 2022) and the WebAssembly superoptimization
  paper (Companion Proc. ⟨Programming⟩ 2020).
* **arXiv only:** MLGO and the 2023 LLM paper have no published version.
* **Web sources** are given as URLs: specifications, documentation and software.

### 14. (Major) Individual contribution statements

Section III-D and the Author Contributions section now attribute each part of the work to named authors (front end;
CFG, dominance and SSA; optimizer; encoders; server and web front end; tests, kernels and evaluation; writing).

The Acknowledgements disclose the use of the AI assistant Claude (Anthropic). It was used to draft the manuscript, to
write the evaluation scripts and figures, and, in the revision, to implement the requested changes under the authors'
direction. We have confirmed that this use is permitted under the course and institutional policy.
**[Authors: fill in the names in Section III-D and Author Contributions, and confirm the policy check before sending
this letter.]**

### 15. (Minor) IEEE Access front matter

The manuscript now uses the current official IEEE Access LaTeX template (13 May 2026), and the footer shows volume 14,
2026. The `\history` dates and the DOI are left in the form of the official template, which IEEE fills in on
publication; the obsolete `ACCESS.2017.DOI` and "VOLUME 4, 2016" placeholders are gone. Author biographies with
photographs have been added. **[Authors: complete the biographies and replace the placeholder photographs in
`paper/photos/`.]**
