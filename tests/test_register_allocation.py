"""
Comprehensive Unit Tests for SSA-Driven Chordal Register Allocation
and 4-Bit Nibble Register-Packed Bytecode Compaction (Hack's Theorem).
"""

import pytest
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph, BasicBlock
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.liveness import LivenessAnalyzer
from core.register_allocator import (
    RegisterInterferenceGraph,
    ChordalRegisterAllocator,
    RegisterCompactor,
)
from core.binary_compression import (
    RegisterPackedBytecodeEmitter,
    RegisterPackedBytecodeDecoder,
)
from core.advanced_compression import AdvancedIRCompressionEngine
from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.optimizer import IROptimizer


def test_liveness_basic_straight_line():
    """Verify LiveIn, LiveOut, and instruction-level live sets for straight-line instructions."""
    instrs = [
        Instruction(op=Opcode.LOAD_CONST, arg1=10, result="x_0"),
        Instruction(op=Opcode.LOAD_CONST, arg1=20, result="y_0"),
        Instruction(op=Opcode.ADD, arg1="x_0", arg2="y_0", result="z_0"),
        Instruction(op=Opcode.PRINT, arg1="z_0"),
    ]
    cfg = ControlFlowGraph.build(instrs)
    liveness = LivenessAnalyzer(cfg)
    live_in, live_out = liveness.analyze()

    # Block level: BB0 has entry live empty (all defined locally), exit empty (consumed)
    assert live_in["BB0"] == set()
    assert live_out["BB0"] == set()

    # Instruction level: after y_0 is loaded, x_0 and y_0 are both live
    rec = liveness.instruction_liveness
    assert len(rec) == 4
    # After LOAD_CONST y_0:
    assert "x_0" in rec[1]["live_after"]
    assert "y_0" in rec[1]["live_after"]

    # Intervals:
    intervals = liveness.intervals
    assert intervals["x_0"]["birth"] == 0
    assert intervals["x_0"]["death"] == 2  # Used in ADD
    assert intervals["y_0"]["birth"] == 1
    assert intervals["y_0"]["death"] == 2  # Used in ADD


def test_liveness_phi_predecessor_scoping():
    """
    Verify that phi arguments are scoped strictly to their incoming predecessor edge
    and do not cause false interference across disjoint branches.
    """
    bb0 = BasicBlock(id="BB0", instructions=[
        Instruction(op=Opcode.LOAD_CONST, arg1=1, result="cond"),
        Instruction(op=Opcode.JUMP_IF_TRUE, arg1="cond", result="L_true"),
        Instruction(op=Opcode.JUMP, arg1="L_false"),
    ], successors={"BB1", "BB2"})

    bb1 = BasicBlock(id="BB1", instructions=[
        Instruction(op=Opcode.LABEL, arg1="L_true"),
        Instruction(op=Opcode.LOAD_CONST, arg1=100, result="x_true"),
        Instruction(op=Opcode.JUMP, arg1="L_merge"),
    ], predecessors={"BB0"}, successors={"BB3"})

    bb2 = BasicBlock(id="BB2", instructions=[
        Instruction(op=Opcode.LABEL, arg1="L_false"),
        Instruction(op=Opcode.LOAD_CONST, arg1=200, result="x_false"),
        Instruction(op=Opcode.JUMP, arg1="L_merge"),
    ], predecessors={"BB0"}, successors={"BB3"})

    bb3 = BasicBlock(id="BB3", instructions=[
        Instruction(op=Opcode.LABEL, arg1="L_merge"),
        Instruction(op=Opcode.PHI, result="x_final", phi_args={"BB1": "x_true", "BB2": "x_false"}),
        Instruction(op=Opcode.PRINT, arg1="x_final"),
    ], predecessors={"BB1", "BB2"}, successors=set())

    cfg = ControlFlowGraph()
    cfg.blocks = {"BB0": bb0, "BB1": bb1, "BB2": bb2, "BB3": bb3}

    liveness = LivenessAnalyzer(cfg)
    liveness.analyze()

    # x_true should be live on exit from BB1, but NOT from BB2
    assert "x_true" in liveness.live_out["BB1"]
    assert "x_true" not in liveness.live_out["BB2"]

    # x_false should be live on exit from BB2, but NOT from BB1
    assert "x_false" in liveness.live_out["BB2"]
    assert "x_false" not in liveness.live_out["BB1"]

    # In RIG, x_true and x_false should NOT interfere!
    rig = RegisterInterferenceGraph.build_from_liveness(liveness)
    assert "x_false" not in rig.adj.get("x_true", set())


def test_rig_construction_and_metrics():
    """Verify RIG nodes, edges, density, and Cytoscape representation."""
    rig = RegisterInterferenceGraph()
    rig.add_edge("a", "b")
    rig.add_edge("b", "c")
    rig.add_edge("a", "c")  # Triangle K3

    stats = rig.get_stats()
    assert stats["node_count"] == 3
    assert stats["edge_count"] == 3
    assert stats["density"] == 1.0
    assert stats["max_degree"] == 2

    elements = rig.to_cytoscape_elements({"a": 0, "b": 1, "c": 2})
    nodes = [e for e in elements if "source" not in e["data"]]
    edges = [e for e in elements if "source" in e["data"]]
    assert len(nodes) == 3
    assert len(edges) == 3
    assert nodes[0]["data"]["register"] in ("R0", "R1", "R2")


def test_maximum_cardinality_search_and_peo():
    """Verify that MCS computes a valid Simplicial / Perfect Elimination Ordering on chordal graphs."""
    rig = RegisterInterferenceGraph()
    # Create chordal graph: 4-cycle with chord (a-b-c-d with chord a-c)
    rig.add_edge("a", "b")
    rig.add_edge("b", "c")
    rig.add_edge("c", "d")
    rig.add_edge("d", "a")
    rig.add_edge("a", "c")  # Chord!

    allocator = ChordalRegisterAllocator(rig)
    peo = allocator.maximum_cardinality_search()
    assert len(peo) == 4
    # Verify that it is a valid PEO
    assert allocator.verify_peo(peo) is True


def test_chordal_register_coloring_optimality():
    """Verify that optimal register coloring achieves chromatic number = max clique size."""
    rig = RegisterInterferenceGraph()
    # Triangle (a, b, c) sharing edge (b, c) with triangle (b, c, d)
    rig.add_edge("a", "b")
    rig.add_edge("a", "c")
    rig.add_edge("b", "c")
    rig.add_edge("b", "d")
    rig.add_edge("c", "d")

    allocator = ChordalRegisterAllocator(rig)
    allocation = allocator.allocate()

    # Total physical registers should be exactly 3 (max clique size of 3)
    assert allocator.k_registers == 3
    assert allocator.max_clique_size == 3

    # Interfering nodes must have distinct colors
    for u, neighbors in rig.adj.items():
        for v in neighbors:
            assert allocation[u] != allocation[v]

    # Nodes 'a' and 'd' do not interfere, so they can share the same register!
    assert allocation["a"] == allocation["d"]


def test_register_compactor_instruction_rewriting():
    """Verify that virtual temporaries are rewritten into physical registers."""
    instructions = [
        Instruction(op=Opcode.LOAD_CONST, arg1=5, result="t0"),
        Instruction(op=Opcode.LOAD_CONST, arg1=10, result="t1"),
        Instruction(op=Opcode.ADD, arg1="t0", arg2="t1", result="t2"),
    ]
    allocation = {"t0": 0, "t1": 1, "t2": 0}  # t2 reuses R0
    compacted = RegisterCompactor.compact_instructions(instructions, allocation)

    assert compacted[0].result == "R0"
    assert compacted[1].result == "R1"
    assert compacted[2].arg1 == "R0"
    assert compacted[2].arg2 == "R1"
    assert compacted[2].result == "R0"


def test_register_packed_bytecode_lossless_roundtrip():
    """Verify 4-bit nibble register packing and lossless round-trip decoding."""
    instructions = [
        Instruction(op=Opcode.LOAD_CONST, arg1=42, result="R0"),
        Instruction(op=Opcode.LOAD_CONST, arg1=100, result="R1"),
        Instruction(op=Opcode.ADD, arg1="R0", arg2="R1", result="R2"),
        Instruction(op=Opcode.SUB, arg1="R2", arg2="R0", result="R3"),
        Instruction(op=Opcode.ASSIGN, arg1="R3", result="R0"),
        Instruction(op=Opcode.PRINT, arg1="R0"),
    ]

    emitter = RegisterPackedBytecodeEmitter()
    bytecode = emitter.serialize_program(instructions, k_registers=4)
    assert len(bytecode) > 0
    assert bytes(bytecode[:4]) == b"RPIR"

    # Decode and verify
    decoded, k_regs = RegisterPackedBytecodeDecoder.decode_program(bytes(bytecode))
    assert k_regs == 4
    assert len(decoded) == len(instructions)
    for orig, dec in zip(instructions, decoded):
        assert orig.op == dec.op
        assert orig.result == dec.result
        assert str(orig.arg1) == str(dec.arg1)
        if orig.arg2 is not None:
            assert str(orig.arg2) == str(dec.arg2)


def test_end_to_end_advanced_compression_with_register_allocation():
    """Verify that full pipeline populates register_allocation stats and Cytoscape elements."""
    code = """
    int main() {
        int sum = 0;
        int i = 1;
        while (i <= 10) {
            sum = sum + i;
            i = i + 1;
        }
        return sum;
    }
    """
    tokens = Lexer(code).tokenize()
    ast = Parser(tokens).parse()
    ir_gen = IRGenerator()
    raw_instrs = ir_gen.generate(ast)
    cfg = ControlFlowGraph.build(raw_instrs)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_transformer = SSATransformer(cfg, dom)
    ssa_cfg = ssa_transformer.transform()
    optimizer = IROptimizer(ssa_cfg)
    opt_cfg = optimizer.optimize()
    opt_instrs = opt_cfg.linearize()
    sym_names = [s.name for s in ir_gen.symbol_table.all_symbols]

    metrics = AdvancedIRCompressionEngine.run(
        raw_instructions=raw_instrs,
        optimized_instructions=opt_instrs,
        cfg=opt_cfg,
        symbol_names=sym_names
    )

    assert "register_allocation" in metrics
    reg_alloc = metrics["register_allocation"]
    assert reg_alloc["physical_registers"] > 0
    assert reg_alloc["virtual_variables"] >= reg_alloc["physical_registers"]
    assert reg_alloc["packed_bytecode_bytes"] > 0
    assert len(reg_alloc["rig_elements"]) > 0
    assert len(reg_alloc["live_intervals"]) > 0
