# IR Compression Studio — Readiness Assessment

> Scope: whole-project readiness review after the Tiger Teeth remediation.
> Context: 24/24 tests pass; all 5 benchmarks run with verified round-trips.
> This project is an academic / demo compiler, not a production service — scored
> accordingly.

## Overall Readiness Score: 7.5 / 10 (Demo-ready; not yet polished)

The compiler **core logic is now sound** after the 7 bug fixes. The remaining
gap to a higher score is almost entirely **test depth and documentation
accuracy**, plus two minor UI/serialization polish items. Nothing blocking a
demo; several things blocking a "defensible, self-consistent" submission.

## Scorecard by Dimension

| Dimension | Score | Notes |
|-----------|:----:|-------|
| Core correctness (lexer→SSA→opt→bytecode) | 9/10 | All Tiger Teeth bugs fixed; loop phis preserved; GVN now dominance-scoped; full columnar round-trip verified. |
| Architecture / modularity | 9/10 | Clean separation (`core/`, `api/`, `web/`); dataclasses; clear pass pipeline. |
| Robustness / edge handling | 7/10 | Lexer handles unterminated comment/string; parser handles `for` ops/types. Residual: const-pool overhead & front-coding 256-char prefix cap (Gap 2.6, cosmetic). |
| Automated testing | 6/10 | 24 tests pass but SHALLOW — none of the 7 fixed bugs has a dedicated regression test. The plan's own verification suite is absent. |
| Documentation accuracy | 5/10 | README badges/results table are STALE and now contradict actual output (see below). docs/ likely stale too. |
| Web UI | 6/10 | Functional, but Gap 2.7 (Cytoscape init render) unaddressed; server CFG-blocks JSON reflects post-mutation IR. |

## Confirmed Residual Issues (verified in code)

1. **No regression tests for the fixed bugs.** The 7 fixes rely only on
   pre-existing tests not breaking. A future refactor could silently reintroduce
   any of them.
2. **README is stale and self-contradicting:**
   - Badge says "19 Passing" + "100% code coverage"; actual suite is **24 tests**.
   - Results table (`README.md:100-106`) no longer matches the optimizer:
     - `sample4` listed as `22 → 4` instrs; actual run is **28 → 3**.
     - `sample2` listed `32 → 21`; actual **32 → 17**.
     - `sample3` listed `31 → 18`; actual **32 → 7**.
     - `sample5` listed `31 → 22`; actual **27 → 22**.
   - Compression percentages in the table are therefore unreliable.
3. **Gap 2.7 (Cytoscape) still open.** `cfg_visualizer.js:181-185` `fit()` calls
   `cy.fit()` only; it never calls `cy.resize()`. A graph laid out while its tab
   pane was `display:none` renders at 0×0 and `fit()` alone won't recover it on
   first activation. Fix: `cy.resize()` before `fit()` in the tab handler
   (`app.js:64-75`) / in `fit()`.
4. **Server CFG-blocks JSON reflects mutated IR.** `server.py:160` serializes
   `cfg.blocks` AFTER SSA + optimizer mutated those same `Instruction` objects
   in place (CFG built at `:104`, mutated at `:116`/`:123`). The visual
   `elements` snapshot (`:106`) is correct, but the `cfg.blocks[*].instructions`
   text is post-optimization, not the true initial CFG. (Residual of Bug 1.6 for
   the raw-CFG view specifically.)
5. **Gap 2.6 (cosmetic).** Constant-pool overhead can exceed raw bytes on tiny
   inputs (savings clamped to 0, never negative), and `FrontCodedStringPool`
   caps shared-prefix length at 1 byte (`prefix_len & 0xFF`), wrapping for ≥256
   identical leading chars. Edge-case only.

## Remediation Task List (ordered; raises score to ~9/10)

Priority A — correctness confidence (do first):
1. Add regression tests mirroring the plan's verification strategy:
   `test_ssa_underscored_identifiers`, `test_dead_branch_pruning` (assert
   sample4 reduces and the `999`/`ghost_var` block is gone), `test_gvn_dominance_safety`
   (parallel-branch expressions not shared), `test_bytecode_emitter_unary_and_constants`
   (NEG/NOT/NOP + correctly-typed, non-polluted constant pool),
   `test_columnar_soa_full_instruction_roundtrip` (deserialize == encoded),
   `test_cross_scope_minification` (same name in two scopes → distinct aliases).
2. Add a trivial-phi-elimination test (single-pred phi becomes a copy).

Priority B — documentation integrity:
3. Update `README.md`: fix test count badge, drop/qualify the "100% coverage"
   claim, and regenerate the results table from actual CLI output for all 5
   samples. Re-check `docs/PROJECT_REPORT.md` figures for the same drift.

Priority C — UI / server polish:
4. Fix Gap 2.7: call `this.cy.resize()` before `this.cy.fit()` in
   `cfg_visualizer.js` `fit()` (and the dom-tree visualizer equivalent).
5. Make `server.py` serialize a pre-SSA snapshot for `cfg.blocks` (build the CFG
   JSON from a deepcopy, or capture `blocks` text at `:106` alongside elements)
   so the raw-CFG tab shows unmutated IR.

Priority D — optional hardening:
6. Gap 2.6: report const-pool overhead honestly (allow showing net cost on tiny
   inputs) and LEB128-encode `prefix_len` in the front-coder to remove the
   256-char wrap.

## Validation After Remediation
- `python -m pytest -q` → all tests (old + new regression) green.
- Re-run all 5 benchmarks; paste real numbers into README table; confirm
  `verification_status` round-trip asserts hold.
- Manual Web Studio check: switch to CFG and Dominance tabs on first load — graph
  renders fully (no collapsed dot).

## Out of Scope
- Production concerns (auth, concurrency, persistence, packaging) — this is an
  academic single-user studio.
- Language feature expansion (functions, arrays) beyond current C-Lite grammar.

> Implementation of the remediation tasks requires source edits — switch to an
> implementation-capable (Code) agent to execute Priorities A–D.
