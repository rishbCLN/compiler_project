"""
Unit tests for LEB128 encoding, Bytecode emission, and Huffman lossless compression.
"""

from core.binary_compression import LEB128, HuffmanCompressor, BytecodeEmitter, IRCompressionPipeline
from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer


def test_leb128_roundtrip():
    test_values = [0, 1, 127, 128, 255, 300, 16384, 1000000]
    for val in test_values:
        encoded = LEB128.encode_unsigned(val)
        decoded, length = LEB128.decode_unsigned(bytes(encoded))
        assert decoded == val
        assert length == len(encoded)


def test_huffman_lossless_roundtrip():
    original_data = b"THE_QUICK_BROWN_FOX_JUMPS_OVER_THE_LAZY_DOG_1234567890_CLIR_COMPILER_STUDIO"
    compressed = HuffmanCompressor.compress(original_data)
    decompressed = HuffmanCompressor.decompress(compressed)

    assert decompressed == original_data


def test_full_pipeline_compression_metrics():
    code = """
    int a = 10 + 20;
    int b = a * 2;
    int c = b + 0;
    print(c);
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

    metrics = IRCompressionPipeline.run(
        raw_instructions=raw_instructions,
        optimized_instructions=opt_instructions,
        symbol_table=ir_gen.symbol_table,
        constant_pool=ir_gen.constant_pool
    )

    assert metrics["final_compression_ratio_percent"] > 0
    assert metrics["huffman_compressed_bytes"] < metrics["raw_ir_text_bytes"]
