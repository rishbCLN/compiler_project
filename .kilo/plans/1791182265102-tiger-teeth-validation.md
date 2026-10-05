# Tiger Teeth Plan — Validation Verdict & Implementation-Ready Task List

> Source reviewed: `tiger_teeth.md` (root). This file records a line-by-line
> re-verification of every claim against the current code, separating
> **still-valid bugs** from **already-fixed / stale claims**, and gives a
> corrected, ordered task list for the implementation agent.

## Overall Verdict

The plan is **partially valid and implementable, but materially stale**. It was
written against an older revision of the codebase. Of the 7 "Critical/High" bugs
and 7 "Moderate" gaps, several have already been fixed in the current source.
The implementation agent must NOT blindly execute the original plan — it would
"fix" code that is already correct and waste effort. Use the corrected scope
below.

Line references in `tiger_teeth.md` do not match current files (e.g. the plan
cites `ssa.py#L168-176` and `insert(0, phi_instr)` which no longer exist).

## Claim-by-Claim Findings

### Still VALID (must fix)

| ID | Claim | Verification |
|----|-------|-------------|
| 1.1 | Dead-branch folding never severs CFG edges | VALID. `optimizer.py:195-207` drops/rewrites the jump but never updates `successors`/`predecessors`/`edge_types`; `cfg.py:189` `prune_unreachable_blocks` walks `successors`, so dead blocks survive. |
| 1.3 | GVN uses one flat table across all blocks (no dominance) | VALID. `optimizer.py:221-255` uses a single `expr_table` iterating `self.cfg.blocks.values()`; unsound across disjoint branches. |
| 1.4 | Constant pool mutated after serialization | VALID. `binary_compression.py:304` serializes pool, then `:261` calls `constant_pool.register(..., "string")` during `emit_instruction`; new entries never land in `cp_bytes`, and every const is typed `"string"`. |
| 1.5 | NEG/NOT/NOP fall into 3-operand `else` | VALID. `binary_compression.py:285-292` is the catch-all; no handlers for `NEG`/`NOT`/`NOP`, so phantom operands are emitted. |
| 1.6 | Mutated instructions passed as "raw" IR | VALID (partially mitigated). `main.py:49` creates `initial_raw_instructions` but `main.py:75` still passes the mutated `raw_instructions`. `server.py:134` likewise passes mutated `raw_instructions` to the pipeline (though `server.py:144` already uses `initial_raw_instructions` for the advanced engine). Fix = pass the deepcopy to `IRCompressionPipeline.run`. |
| 1.7 | Columnar SoA drops jump targets / phi preds, no deserializer | VALID. `advanced_compression.py:231` captures `result_label` but `serialize_columns` (`:273-302`) never emits it; phi only emits `delta`, not `pred_id`; verification (`:405-410`) only checks container equality, instruction_count, and symbol set — no real instruction round-trip; no `deserialize_columns`. |
| 2.2 | Cross-scope symbol minification collision | VALID. `symbol_table.py:131-132` keys `mapping`/`name_to_minified` by `sym.name`, so same-named symbols in different scopes collide. |
| 2.5 | Loop-carried phi cycles not removed by DCE | VALID (by inspection). `optimizer.py:261-297` uses a global `all_uses` set; a self-referential phi `x_2 = phi(..., x_2)` keeps itself live. |
| 2.6 | Const-pool overhead / front-coding negative savings | PARTIALLY VALID. `constant_pool.py:93` clamps savings with `max(0, ...)` so it never reports negative, but overhead can still exceed raw. `advanced_compression.py:51` `prefix_len & 0xFF` truncates prefixes ≥256 chars (edge case only). Low severity / cosmetic. |
| 2.7 | Cytoscape hidden-container layout glitch | NOT verified in code this pass (web/js). Treat as UNVERIFIED; low risk. Confirm by manual UI test before investing. |

### Already FIXED / STALE (do NOT act)

| ID | Original claim | Current reality |
|----|----------------|-----------------|
| 1.2 | Underscore identifiers corrupted to `_undef` via `rsplit('_',1)` | FIXED. `ssa.py:173` now uses `succ_instr.annotation or (...)`, and phi nodes store `annotation=var` (`ssa.py:84`). The base name is preserved; `rsplit` is only a fallback. No corruption for `sum_total` etc. |
| 2.1 | Only first label mapped per block | FIXED. `cfg.py:119-122` sets `current_bb.label` only once but writes `cfg.label_to_block[label] = bb.id` for EVERY label instruction. All labels resolve. |
| 2.3 | `for` init rejects bool/string; update rejects `*=`,`/=` | FIXED. `parser.py:200` accepts INT/FLOAT/STRING/BOOL; `parser.py:221-222` accepts ASSIGN/PLUS/MINUS/STAR/SLASH `_ASSIGN`. |
| 2.4 | Phi inserted at index 0 before label | FIXED. `ssa.py:86-91` inserts phi AFTER leading labels via `insert_idx`. |

## Corrected, Ordered Implementation Task List

Dependencies first; each task is independently testable.

1. **Optimizer branch folding (Bug 1.1)** — In `optimizer.py:195-207`, when a
   constant branch is resolved, update the owning block's `successors`, the
   dropped target's `predecessors`, and `cfg.edge_types` so pruning sees the
   severed edge. Re-run `pass_cfg_simplification` after.
2. **Dead phi-incoming cleanup (ties to 1.1 / 2.5)** — After pruning, remove
   `phi_args` entries whose predecessor block no longer exists; drop phis that
   become trivial/self-referential (`optimizer.py:261-297`).
3. **GVN dominance scoping (Bug 1.3)** — Replace the flat `expr_table` with
   dominator-tree-scoped value numbering (DVNT): push/pop table scopes along
   `dom.dom_tree`, only reusing expressions from dominating blocks.
4. **Bytecode emitter (Bugs 1.4 & 1.5)** — Register ALL constants into the pool
   BEFORE `constant_pool.serialize()` (pre-pass over instructions), preserve the
   real literal type instead of hard-coded `"string"`, and add explicit
   `NEG`/`NOT` (unary) and `NOP` (no-operand) branches in `emit_instruction`
   before the binary `else`.
5. **Raw-IR integrity (Bug 1.6)** — In `main.py:75` and `server.py:134` pass the
   deepcopied `initial_raw_instructions` (not the mutated list) into
   `IRCompressionPipeline.run`. Verify `metrics['raw_ir_text_bytes']` reflects
   pre-optimization IR.
6. **Columnar SoA correctness (Bug 1.7)** — Emit `result_label` for
   `JUMP_IF_TRUE/FALSE` and `pred_id` for phis into dedicated columns; implement
   `deserialize_columns`/`unpack` → `List[Instruction]`; change verification to
   assert the reconstructed instruction list equals the input, then keep the
   "Lossless" status string only if that assertion holds.
7. **Symbol minification scoping (Gap 2.2)** — Key minified mapping by a
   scope-qualified identity (e.g. `(scope_id, name)` or symbol object id) instead
   of bare `sym.name`.
8. **(Optional, low priority)** Gap 2.6 overhead reporting and Gap 2.7 Cytoscape
   relayout-on-tab-activation — only after confirming they reproduce.

## Validation Strategy

- Keep the 4 already-fixed items covered by regression tests to prevent reversion
  (`test_ssa_underscored_identifiers`, multi-label CFG, parser `for` ops, phi
  placement) — these should PASS immediately and guard the stale fixes.
- New tests for the valid bugs: dead-branch pruning count, GVN cross-branch
  safety, bytecode unary/const round-trip, columnar full-instruction round-trip,
  raw-IR byte count integrity, cross-scope minification uniqueness.
- Benchmark: `sample4_dead_code.lang` must reduce to the documented 4
  instructions ONLY after Bug 1.1 is fixed.

## Open Question

Gap 2.7 (Cytoscape) was not verifiable from the Python audit this pass. Recommend
confirming it reproduces in the Web Studio before scheduling work; if it does,
the fix is calling `cy.resize(); cy.layout(...).run(); cy.fit()` on tab-shown.

> Switch to an implementation-capable (Code) agent to execute tasks 1–7; this
> planning agent does not edit source files.
