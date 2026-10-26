"""
Unit Tests for Mainstream Compression Comparison Benchmark Suite.
Tests that all mainstream algorithms (Huffman, Arithmetic, Deflate, Zstd, Brotli, LZ4, Bzip2, LZMA, LZW, RLE)
execute cleanly, report accurate comparisons vs Huffman, and produce bit-perfect round-trip fidelity.
"""

import pytest
from core.compression_benchmarks import (
    CompressionBenchmarkSuite,
    ArithmeticCoder,
    LZWCompressor,
    RLECompressor,
)


def test_arithmetic_coder_roundtrip():
    data = b"HELLO_COMPILER_ARITHMETIC_ENTROPY_CODING_1234567890_!@#$%^" * 4
    compressed = ArithmeticCoder.compress(data)
    assert len(compressed) > 0
    decompressed = ArithmeticCoder.decompress(compressed)
    assert decompressed == data


def test_lzw_compressor_roundtrip():
    data = b"THE_QUICK_BROWN_FOX_JUMPS_OVER_THE_LAZY_DOG_REPEAT_REPEAT" * 3
    compressed = LZWCompressor.compress(data)
    assert len(compressed) > 0
    decompressed = LZWCompressor.decompress(compressed)
    assert decompressed == data


def test_rle_compressor_roundtrip():
    data = b"AAAAABBBBBCCCCCDDDDDEEEEE" + b"XYZ" * 5
    compressed = RLECompressor.compress(data)
    assert len(compressed) > 0
    decompressed = RLECompressor.decompress(compressed)
    assert decompressed == data


def test_benchmark_suite_compares_all_against_huffman():
    sample_bytecode = b"\x01\x00\x02\x03\x01\x00\x04\x05\x0A\x01\x00\x06" * 10
    raw_text_len = 500

    suite = CompressionBenchmarkSuite.run_benchmark(
        target_payload=sample_bytecode,
        raw_ir_text_bytes=raw_text_len,
        custom_metrics={
            "register_allocation": {"packed_bytecode_bytes": 45},
            "soa_container_bytes": 55,
        }
    )

    assert "techniques" in suite
    assert "ranked_techniques" in suite
    assert "baseline_huffman_bytes" in suite
    assert suite["baseline_huffman_bytes"] > 0
    assert suite["total_algorithms_evaluated"] >= 10

    # Ensure baseline is Huffman
    huffman_entry = next((t for t in suite["techniques"] if t["id"] == "huffman"), None)
    assert huffman_entry is not None
    assert huffman_entry["is_baseline"] is True
    assert huffman_entry["bytes_vs_huffman"] == 0
    assert huffman_entry["percent_vs_huffman"] == 0.0

    # Ensure every algorithm has direct comparison fields
    for t in suite["techniques"]:
        assert "name" in t
        assert "family" in t
        assert "compressed_bytes" in t
        assert "percent_vs_huffman" in t
        assert "vs_huffman_label" in t
        assert "verified_lossless" in t
        assert t["verified_lossless"] is True
