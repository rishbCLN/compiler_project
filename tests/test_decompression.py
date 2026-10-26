"""
Unit tests for the Decompression Phase & Lossless Semantic Fidelity Verification Engine.
"""

from core.decompression import DecompressionEngine
from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.binary_compression import BytecodeEmitter, HuffmanCompressor


def test_decompression_phase_straight_line_lossless():
    code = """
    int x = 10;
    int y = 20;
    int z = x + y;
    print(z);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    raw = ir_gen.generate(ast)

    emitter = BytecodeEmitter(ir_gen.symbol_table, ir_gen.constant_pool)
    bc = emitter.serialize_program(raw)
    huff = HuffmanCompressor.compress(bytes(bc))

    result = DecompressionEngine.run(
        huffman_bitstream=huff,
        raw_bytecode=bytes(bc),
        original_instructions=raw,
        emitter=emitter,
    )

    assert result["is_lossless"] is True
    assert result["match_rate_percent"] == 100.0
    assert result["mismatched_instructions"] == 0
    assert result["matched_instructions"] == len(raw)
    assert result["bits_lost"] == 0
    assert len(result["diff_lines"]) == len(raw)
    assert all(d["is_match"] for d in result["diff_lines"])


def test_decompression_phase_optimized_ssa_lossless():
    code = """
    int a = 5 * 2;
    int b = a + 0;
    int c = 100;
    if (b > 5) {
        c = 200;
    }
    print(c);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    raw = ir_gen.generate(ast)
    cfg = ControlFlowGraph.build(raw)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    opt_cfg = IROptimizer(ssa_cfg).optimize()
    opt_instructions = opt_cfg.linearize()

    emitter = BytecodeEmitter(ir_gen.symbol_table, ir_gen.constant_pool)
    bc = emitter.serialize_program(opt_instructions)
    huff = HuffmanCompressor.compress(bytes(bc))

    result = DecompressionEngine.run(
        huffman_bitstream=huff,
        raw_bytecode=bytes(bc),
        original_instructions=opt_instructions,
        emitter=emitter,
    )

    assert result["is_lossless"] is True
    assert result["match_rate_percent"] == 100.0
    assert result["verdict_badge"] == "100% BIT-PERFECT LOSSLESS"


def test_all_academic_benchmarks_lossless_decompression():
    import glob
    import os
    benchmark_files = glob.glob("benchmarks/*.lang") + glob.glob("benchmarks/*.c")
    assert len(benchmark_files) >= 5

    for fpath in benchmark_files:
        with open(fpath, "r", encoding="utf-8") as f:
            code = f.read()

        ast = Parser(Lexer(code).tokenize()).parse()
        ir_gen = IRGenerator()
        raw = ir_gen.generate(ast)
        cfg = ControlFlowGraph.build(raw)
        dom = DominanceAnalyzer(cfg)
        dom.compute_all()
        ssa_cfg = SSATransformer(cfg, dom).transform()
        opt_cfg = IROptimizer(ssa_cfg).optimize()
        opt_instructions = opt_cfg.linearize()

        emitter = BytecodeEmitter(ir_gen.symbol_table, ir_gen.constant_pool)
        bc = emitter.serialize_program(opt_instructions)
        huff = HuffmanCompressor.compress(bytes(bc))

        res = DecompressionEngine.run(
            huffman_bitstream=huff,
            raw_bytecode=bytes(bc),
            original_instructions=opt_instructions,
            emitter=emitter,
        )

        assert res["is_lossless"] is True, f"Benchmark {fpath} failed lossless decompression check!"
        assert res["match_rate_percent"] == 100.0
        assert res["mismatched_instructions"] == 0


def test_cross_paradigm_decompression_matrix_sha256_lossless():
    from core.compression_benchmarks import CompressionBenchmarkSuite
    sample_payload = b"CLIR\x01\x10\x02\x05alpha\x03\x04beta\x11\x00\x01\x11\x01\x02\x01\x02\x00\x01\x18\x03" * 8

    suite = CompressionBenchmarkSuite.run_benchmark(
        target_payload=sample_payload,
        raw_ir_text_bytes=len(sample_payload) * 4,
        custom_metrics={
            "register_allocation": {"packed_bytecode_bytes": 64},
            "soa_container_bytes": 72,
        }
    )

    assert "decompression_matrix" in suite
    assert "decompression_summary" in suite

    matrix = suite["decompression_matrix"]
    assert len(matrix) >= 10

    # Ensure EVERY algorithm in the decompression matrix is cryptographically verified
    for item in matrix:
        assert item["verified_lossless"] is True, f"Algorithm {item['name']} failed lossless verification"
        assert item["sha256_matched"] is True, f"Algorithm {item['name']} SHA-256 mismatch: {item['sha256_in']} vs {item['sha256_out']}"
        assert item["bits_drift"] == 0, f"Algorithm {item['name']} had non-zero bit drift: {item['bits_drift']}"
        assert item["decode_time_us"] > 0
        assert item["decode_throughput_mb_s"] > 0
        assert "asymmetry_ratio" in item
        assert "lossless_verdict" in item
        assert "100% BIT-PERFECT LOSSLESS" in item["lossless_verdict"]

    summary = suite["decompression_summary"]
    assert summary["all_lossless_verified"] is True
    assert summary["total_drift_bits"] == 0
    assert summary["sha256_verified_count"] == len(matrix)
    assert summary["asymmetry_champion_ratio"] > 1.0


def test_all_academic_benchmarks_cross_paradigm_decompression_matrix():
    """
    Rigorously tests all 7 academic benchmarks across the entire multi-algorithm
    decompression matrix to verify bit-level bijective reconstruction and speed asymmetry.
    """
    import glob
    from core.compression_benchmarks import CompressionBenchmarkSuite
    benchmark_files = sorted(glob.glob("benchmarks/*.lang") + glob.glob("benchmarks/*.c"))
    assert len(benchmark_files) >= 5

    for fpath in benchmark_files:
        with open(fpath, "r", encoding="utf-8") as f:
            code = f.read()

        ast = Parser(Lexer(code).tokenize()).parse()
        ir_gen = IRGenerator()
        raw = ir_gen.generate(ast)
        cfg = ControlFlowGraph.build(raw)
        dom = DominanceAnalyzer(cfg)
        dom.compute_all()
        ssa_cfg = SSATransformer(cfg, dom).transform()
        opt_cfg = IROptimizer(ssa_cfg).optimize()
        opt_instructions = opt_cfg.linearize()

        emitter = BytecodeEmitter(ir_gen.symbol_table, ir_gen.constant_pool)
        bc = bytes(emitter.serialize_program(opt_instructions))

        suite = CompressionBenchmarkSuite.run_benchmark(
            target_payload=bc,
            raw_ir_text_bytes=len(code.encode("utf-8")),
            custom_metrics={
                "register_allocation": {"packed_bytecode_bytes": max(12, int(len(bc) * 0.75))},
                "soa_container_bytes": max(16, int(len(bc) * 0.85)),
            }
        )

        matrix = suite["decompression_matrix"]
        assert len(matrix) >= 12, f"Expected 12 algorithms in matrix for {fpath}, got {len(matrix)}"

        for algo in matrix:
            # 1. Cryptographic SHA-256 bijectivity
            assert algo["sha256_matched"] is True, f"{fpath} - {algo['name']} SHA-256 mismatch!"
            assert algo["sha256_in"] == algo["sha256_out"], f"{fpath} - {algo['name']} SHA mismatch"

            # 2. Strict zero-bit drift
            assert algo["bits_drift"] == 0, f"{fpath} - {algo['name']} non-zero bit drift: {algo['bits_drift']}"

            # 3. Size identity
            assert algo["decompressed_bytes"] == len(bc), f"{fpath} - {algo['name']} byte mismatch"

            # 4. Latency & Throughput validity
            assert algo["decode_time_us"] > 0, f"{fpath} - {algo['name']} decode_time_us <= 0"
            assert algo["decode_throughput_mb_s"] > 0, f"{fpath} - {algo['name']} throughput <= 0"

            # 5. Verified Lossless
            assert algo["verified_lossless"] is True, f"{fpath} - {algo['name']} verified_lossless is False"
            assert "100% BIT-PERFECT LOSSLESS" in algo["lossless_verdict"]

        summary = suite["decompression_summary"]
        assert summary["all_lossless_verified"] is True
        assert summary["total_drift_bits"] == 0
        assert summary["sha256_verified_count"] == len(matrix)



