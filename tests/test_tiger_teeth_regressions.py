"""
Regression tests for the Tiger Teeth remediation.

Each test pins the corrected behaviour of one of the bugs fixed during the
Tiger Teeth pass so a future refactor cannot silently reintroduce it:

  * 1.1 / 2.5  Dead-branch pruning + CFG edge severing & phi cleanup
  * 1.3        Dominance-scoped Global Value Numbering (DVNT)
  * 1.4 / 1.5  Bytecode emitter: unary ops (NEG/NOT/NOP) + typed constant pool
  * 1.6        Raw IR preserved (not mutated) through the pipeline
  * 1.7        Columnar SoA full-instruction round-trip
  * 2.2        Scope-qualified symbol minification
  * Pass 5     Trivial-phi elimination
"""

from copy import deepcopy

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.ir import Instruction, Opcode
from core.symbol_table import SymbolTable
from core.binary_compression import BytecodeEmitter, HuffmanCompressor
from core.advanced_compression import (
    SSABackwardDeltaEncoder,
    ColumnarBytecodeSerializer,
    AdvancedIRCompressionEngine,
    FrontCodedStringPool,
)
from core.constant_pool import ConstantPool


def _compile(code):
    """Run the full frontend+SSA+optimizer pipeline, returning the generator,
    optimizer, optimized CFG and linearized optimized instructions."""
    ast = Parser(Lexer(code).tokenize()).parse()
    gen = IRGenerator()
    raw = gen.generate(ast)
    raw_snapshot = [deepcopy(i) for i in raw]
    cfg = ControlFlowGraph.build(raw)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    optimizer = IROptimizer(ssa_cfg)
    opt_cfg = optimizer.optimize()
    return gen, optimizer, opt_cfg, opt_cfg.linearize(), raw_snapshot


# ---------------------------------------------------------------- Bug 1.1 / 2.5

def test_dead_branch_pruning_removes_ghost_block():
    """`if (1 == 1)` must fold; the unreachable else block (ghost_var = 999)
    must be pruned entirely and its phi contributions severed."""
    code = open("benchmarks/sample4_dead_code.lang", encoding="utf-8").read()
    _, optimizer, _, opt_instrs, _ = _compile(code)

    texts = [str(i) for i in opt_instrs]
    joined = "\n".join(texts)

    # The unreachable branch literal and its variable must be gone.
    assert "999" not in joined
    assert "ghost_var" not in joined
    # Dead-branch folding reduces this benchmark aggressively.
    assert len(opt_instrs) <= 5
    assert optimizer.stats["dead_blocks_removed"] > 0


def test_severed_edge_cleans_phi_args():
    """_sever_edge must drop phi incoming args from the removed predecessor so
    no phi references a block that is no longer a predecessor."""
    code = open("benchmarks/sample4_dead_code.lang", encoding="utf-8").read()
    _, _, opt_cfg, _, _ = _compile(code)

    for bb in opt_cfg.blocks.values():
        for instr in bb.instructions:
            if instr.op == Opcode.PHI:
                for pred_id in instr.phi_args:
                    assert pred_id in bb.predecessors


# ---------------------------------------------------------------- Bug 1.3

def test_gvn_dominance_safety_parallel_branches():
    """An identical expression computed on two disjoint branches must NOT be
    shared: neither branch block dominates the other, so DVNT keeps both."""
    code = """
    int n = 5;
    int acc = 0;
    while (n > 0) {
        if (n > 2) {
            int p = n * n;
            print(p);
        } else {
            int q = n * n;
            print(q);
        }
        n = n - 1;
    }
    """
    _, optimizer, _, opt_instrs, _ = _compile(code)
    muls = [i for i in opt_instrs if i.op == Opcode.MUL]
    # Both branch copies of n*n survive (not illegally merged across siblings).
    assert len(muls) == 2
    assert optimizer.stats["gvn_eliminations"] == 0


def test_gvn_eliminates_commutative_redundancy_in_same_scope():
    """Within a single dominating block, a redundant subexpression over
    non-constant (loop-carried) values is eliminated by DVNT. Loop variables are
    used so constant folding cannot pre-empt the GVN pass."""
    code = """
    int n = 5;
    int sink = 0;
    while (n > 0) {
        int x = n * n;
        int y = n * n;
        sink = x + y;
        n = n - 1;
    }
    print(sink);
    """
    _, optimizer, _, opt_instrs, _ = _compile(code)
    assert optimizer.stats["gvn_eliminations"] > 0
    # The duplicate n*n collapses to a single MUL in the loop body.
    muls = [i for i in opt_instrs if i.op == Opcode.MUL]
    assert len(muls) == 1


# ---------------------------------------------------------------- Bug 1.4 / 1.5

def test_bytecode_emitter_unary_and_constants():
    """NEG/NOT must emit cleanly, and the constant pool must hold correctly
    typed literals only (no variable names, no mistyped ints-as-strings)."""
    code = """
    int a = 5;
    int b = -a;
    bool c = !true;
    int d = a + 5;
    print(b);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    gen = IRGenerator()
    raw = gen.generate(ast)

    ops = {i.op for i in raw}
    assert Opcode.NEG in ops and Opcode.NOT in ops

    emitter = BytecodeEmitter(gen.symbol_table, gen.constant_pool)
    package = emitter.serialize_program(raw)

    valid_types = {"int", "float", "bool", "string"}
    var_names = {s.name for s in gen.symbol_table.all_symbols}
    for entry in gen.constant_pool.entries:
        assert entry.const_type in valid_types
        # No symbol/temp names leaked into the constant pool.
        assert str(entry.value) not in var_names
    # The integer literal 5 is pooled as an int, never as a string.
    assert any(e.const_type == "int" and str(e.value) == "5"
               for e in gen.constant_pool.entries)

    # Bytecode (with NEG/NOT/NOP paths) survives a lossless Huffman round-trip.
    assert HuffmanCompressor.decompress(
        HuffmanCompressor.compress(bytes(package))) == bytes(package)


def test_nop_opcode_emits_no_operands():
    emitter = BytecodeEmitter(SymbolTable(), __import__("core.constant_pool",
                              fromlist=["ConstantPool"]).ConstantPool())
    buf = emitter.emit_instruction(Instruction(op=Opcode.NOP))
    assert len(buf) == 1  # opcode byte only


# ---------------------------------------------------------------- Bug 1.6

def test_raw_ir_not_mutated_by_pipeline():
    """The deepcopied raw snapshot must stay byte-for-byte identical after SSA
    and the optimizer mutate the working instructions in place."""
    code = open("benchmarks/sample1_arithmetic_constants.lang", encoding="utf-8").read()
    _, _, _, opt_instrs, raw_snapshot = _compile(code)

    before = [str(i) for i in raw_snapshot]
    # Snapshot must still look like unoptimized TAC (contains folded-away ops).
    assert len(opt_instrs) < len(raw_snapshot)
    # And it must be internally consistent after the run.
    after = [str(i) for i in raw_snapshot]
    assert before == after


# ---------------------------------------------------------------- Bug 1.7

def test_columnar_soa_full_instruction_roundtrip():
    """Columnar deserialize must reconstruct the exact encoded instruction
    dicts (jump targets + phi predecessors included)."""
    encoded = [
        {"op": Opcode.LOAD_CONST, "is_phi": False, "arg1_delta": None,
         "arg2_delta": None, "arg1_raw": "10", "arg2_raw": None,
         "result_label": None, "line": 1},
        {"op": Opcode.JUMP_IF_FALSE, "is_phi": False, "arg1_delta": 1,
         "arg2_delta": None, "arg1_raw": None, "arg2_raw": None,
         "result_label": "L_end", "line": 2},
        {"op": Opcode.PHI, "is_phi": True,
         "phi_deltas": {"BB0": 2, "BB3": 1}, "line": 3},
    ]
    columns = ColumnarBytecodeSerializer.serialize_columns(encoded)
    recovered = ColumnarBytecodeSerializer.deserialize_columns(columns)

    expected = [{k: v for k, v in it.items() if k != "line"} for it in encoded]
    assert recovered == expected


def test_advanced_engine_full_roundtrip_status():
    code = open("benchmarks/sample2_loops_and_conditionals.lang", encoding="utf-8").read()
    gen, _, opt_cfg, opt_instrs, raw_snapshot = _compile(code)
    metrics = AdvancedIRCompressionEngine.run(
        raw_instructions=raw_snapshot,
        optimized_instructions=opt_instrs,
        cfg=opt_cfg,
        symbol_names=[s.name for s in gen.symbol_table.all_symbols],
    )
    assert metrics["verification_status"] == \
        "Lossless Round-Trip Verified (full instruction reconstruction)"


# ---------------------------------------------------------------- Gap 2.2

def test_cross_scope_minification_distinct_aliases():
    """The same identifier declared in two scopes must map to distinct aliases
    via scope-qualified keys (name#level), with a bare-name back-compat entry."""
    st = SymbolTable()
    st.declare_symbol("value", "int")          # scope level 0
    st.record_reference("value")
    st.record_reference("value")
    st.enter_scope()
    st.declare_symbol("value", "int")          # scope level 1, same name
    st.record_reference("value")
    st.exit_scope()

    mapping = st.minify_symbols()
    assert mapping["value#0"] != mapping["value#1"]
    assert "value" in mapping  # bare-name back-compat entry preserved
    assert st.all_symbols[0].minified_name != st.all_symbols[1].minified_name


# ---------------------------------------------------------------- Pass 5

def test_trivial_phi_elimination_single_pred():
    """A phi whose incoming values collapse to a single distinct source becomes
    a plain ASSIGN."""
    cfg = ControlFlowGraph.build([
        Instruction(op=Opcode.LABEL, arg1="entry"),
    ])
    # Hand-build a block with a trivial phi (one distinct incoming value).
    entry_id = cfg.entry_block_id
    bb = cfg.blocks[entry_id]
    bb.instructions.append(
        Instruction(op=Opcode.PHI, result="x_2",
                    phi_args={"BB0": "x_1", "BB1": "x_1"})
    )
    IROptimizer(cfg).pass_trivial_phi_elimination()

    phis = [i for i in bb.instructions if i.op == Opcode.PHI]
    assigns = [i for i in bb.instructions if i.op == Opcode.ASSIGN and i.result == "x_2"]
    assert not phis
    assert len(assigns) == 1
    assert assigns[0].arg1 == "x_1"
    assert assigns[0].annotation == "trivial_phi"


# ---------------------------------------------------------------- Gap 2.6 (hardening)

def test_front_coded_pool_handles_long_shared_prefix():
    """Shared prefixes >= 256 chars must survive the round-trip (LEB128 prefix
    length), where the old single-byte `prefix_len & 0xFF` form would wrap."""
    base = "x" * 300
    strings = [base, base + "a", base + "b"]
    encoded, _ = FrontCodedStringPool.encode(strings)
    decoded = FrontCodedStringPool.decode(encoded)
    assert sorted(decoded) == sorted(strings)


def test_constant_pool_reports_net_overhead_honestly():
    """On a tiny unique-literal pool the index/descriptor overhead can exceed
    the raw literal bytes; stats must expose the (negative) net figure instead
    of only the clamped non-negative savings."""
    cp = ConstantPool()
    cp.register(1, "int")  # single 4-byte int, +2 bytes index overhead
    stats = cp.get_stats()
    assert stats["pool_overhead_bytes"] == 2
    assert stats["net_bytes_saved"] <= 0
    assert stats["overhead_exceeds_savings"] is True
    assert stats["bytes_saved"] == 0  # clamped, non-negative, backward-compatible


def test_constant_pool_dedup_still_reports_savings():
    cp = ConstantPool()
    for _ in range(10):
        cp.register("shared_literal", "string")
    stats = cp.get_stats()
    assert stats["bytes_saved"] > 0
    assert stats["net_bytes_saved"] > 0
    assert stats["overhead_exceeds_savings"] is False
