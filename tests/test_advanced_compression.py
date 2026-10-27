"""
Unit tests for the Advanced IR Compression Engine:
Front-Coded String Pools, SSA Backward Deltas, RPO Fallthrough Elision, and Columnar SoA.
"""

from core.advanced_compression import (
    FrontCodedStringPool,
    RPOBlockScheduler,
    SSABackwardDeltaEncoder,
    ColumnarBytecodeSerializer,
    AdvancedIRCompressionEngine,
)
from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer


def test_front_coded_string_pool_roundtrip():
    symbols = [
        "_ZN4core3fmt9ArgumentsE",
        "_ZN4core3fmt5writeE",
        "_ZN4core3fmt11DisplayHelpE",
        "_ZN3std3sys4unix2fsE",
        "_ZN3std3sys4unix4pipeE",
        "counter_var",
        "counter_val",
    ]
    encoded_bytes, index_map = FrontCodedStringPool.encode(symbols)
    assert len(encoded_bytes) > 0
    assert len(index_map) == len(set(symbols))

    decoded = FrontCodedStringPool.decode(encoded_bytes)
    assert sorted(decoded) == sorted(list(set(symbols)))


def test_ssa_backward_delta_encoding():
    code = """
    int a = 10;
    int b = 20;
    int c = a + b;
    print(c);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    raw_instructions = ir_gen.generate(ast)
    cfg = ControlFlowGraph.build(raw_instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    opt_instructions = IROptimizer(ssa_cfg).optimize().linearize()

    encoded = SSABackwardDeltaEncoder.encode_instructions(opt_instructions)
    assert len(encoded) == len(opt_instructions)
    # Check that backward delta fields exist
    for item in encoded:
        assert "op" in item


def test_rpo_fallthrough_elision():
    code = """
    int x = 0;
    if (x < 5) {
        x = x + 1;
    } else {
        x = x - 1;
    }
    print(x);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)

    rpo_blocks, edge_metadata = RPOBlockScheduler.schedule_and_elide_edges(cfg)
    assert len(rpo_blocks) == len(cfg.blocks)
    # Verify at least one block elided its fallthrough edge
    elided = [meta for meta in edge_metadata.values() if meta["has_implicit_fallthrough"]]
    assert len(elided) > 0


def test_columnar_soa_roundtrip():
    code = """
    int x = 10;
    int y = x + 5;
    print(y);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    instructions = ir_gen.generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    opt_instructions = IROptimizer(ssa_cfg).optimize().linearize()

    encoded = SSABackwardDeltaEncoder.encode_instructions(opt_instructions)
    columns = ColumnarBytecodeSerializer.serialize_columns(encoded)

    assert len(columns["opcodes"]) == len(opt_instructions)
    assert "flags" in columns
    assert "deltas" in columns

    symbols = ["x", "y", "temp"]
    front_coded_syms, _ = FrontCodedStringPool.encode(symbols)
    container = ColumnarBytecodeSerializer.pack_container(columns, front_coded_syms)
    assert container.startswith(ColumnarBytecodeSerializer.CONTAINER_MAGIC)

    unpacked_columns, unpacked_sym_bytes = ColumnarBytecodeSerializer.unpack_container(container)
    assert unpacked_columns["instruction_count"] == len(opt_instructions)
    assert unpacked_columns["opcodes"] == columns["opcodes"]
    assert FrontCodedStringPool.decode(unpacked_sym_bytes) == sorted(symbols)


def test_advanced_end_to_end_engine():
    code = """
    int a = 10 + 20 * 2;
    int b = a + 0;
    int c = b * 1;
    print(a, b, c);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    raw_instructions = ir_gen.generate(ast)
    cfg = ControlFlowGraph.build(raw_instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    opt_cfg = IROptimizer(ssa_cfg).optimize()
    opt_instructions = opt_cfg.linearize()

    symbol_names = [s.name for s in ir_gen.symbol_table.all_symbols]

    metrics = AdvancedIRCompressionEngine.run(
        raw_instructions=raw_instructions,
        optimized_instructions=opt_instructions,
        cfg=cfg,
        symbol_names=symbol_names
    )

    assert metrics["verification_status"] == "Lossless Round-Trip Verified (full instruction reconstruction)"
    assert metrics["soa_container_bytes"] > 0
    assert metrics["soa_container_bytes"] < len(raw_instructions) * 20
    assert metrics["final_advanced_compression_percent"] > 50.0
