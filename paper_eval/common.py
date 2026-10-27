"""
Shared definitions for the evaluation scripts: the benchmark sets, every
encoding of a compiled program, and the general-purpose compressors with
their settings.
"""

import json
import math
import os
import platform
import re
import sys
import zlib
import lzma
from collections import Counter
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.binary_compression import (  # noqa: E402
    BytecodeEmitter, BytecodeDecoder, HuffmanCompressor, FrequencyTableHuffman, LEB128)
from core.advanced_compression import (  # noqa: E402
    SSABackwardDeltaEncoder, ColumnarBytecodeSerializer, FrontCodedStringPool)
from paper_eval.pipeline import Compiled, raw_text, opt_text  # noqa: E402

RESULTS = os.path.join(ROOT, "paper_eval", "results")
PAPER = os.path.join(ROOT, "paper")

# ---------------------------------------------------------------- benchmarks

BENCHMARKS = [
    ("S1", "sample1_arithmetic_constants.lang", "Constant folding, identities"),
    ("S2", "sample2_loops_and_conditionals.lang", "Diamond + loop, $\\phi$ nodes"),
    ("S3", "sample3_redundant_gvn.lang", "Redundant subexpressions"),
    ("S4", "sample4_dead_code.lang", "Dead code, constant branch"),
    ("S5", "sample5_matrix_fibonacci.lang", "Fibonacci loop"),
    ("S6", "sample6_standard_cfg_demo.lang", "Diamond + loop (CFG demo)"),
    ("S7", "sample7_standard_c_program.c", "C program (\\texttt{main}, \\texttt{printf})"),
]

KERNELS = [
    ("K1", "k01_gcd_lcm.c", "GCD and LCM (Euclid)"),
    ("K2", "k02_isqrt.c", "Integer sqrt (Newton)"),
    ("K3", "k03_modpow.c", "Modular exponentiation"),
    ("K4", "k04_bitcount.c", "Bit counting"),
    ("K5", "k05_collatz.c", "Collatz lengths"),
    ("K6", "k06_primes.c", "Primes by trial division"),
    ("K7", "k07_fibonacci.c", "Fibonacci (iter., rec.)"),
    ("K8", "k08_adler32.c", "Adler-32 running sums"),
    ("K9", "k09_day_of_week.c", "Day of week (Zeller)"),
    ("K10", "k10_iir_filter.c", "Low-pass filter"),
]


def benchmark_path(name: str) -> str:
    sub = "kernels" if name.startswith("k") and name[1:3].isdigit() else ""
    return os.path.join(ROOT, "benchmarks", sub, name)


def load(name: str) -> Tuple[str, List[int]]:
    """Source text and program input (from a '// input:' line, if any)."""
    with open(benchmark_path(name), encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"// input:(.*)", src)
    return src, [int(x) for x in m.group(1).split()] if m else []


def all_benchmarks():
    """(id, file, focus, set) for the seven samples and the ten kernels."""
    return [(i, f, d, "S") for i, f, d in BENCHMARKS] + [(i, f, d, "K") for i, f, d in KERNELS]


# ---------------------------------------------------------------- encodings

def clir(c: Compiled) -> Tuple[bytes, BytecodeEmitter]:
    emitter = BytecodeEmitter()
    package = bytes(emitter.serialize_module(c.clir_units()))
    return package, emitter


def columnar(c: Compiled) -> Tuple[bytes, bytes, bool]:
    """(stored bitstream with its flag byte, raw container, Huffman applied)."""
    function_columns = [
        ColumnarBytecodeSerializer.serialize_columns(SSABackwardDeltaEncoder.encode_instructions(u.opt))
        for u in c.units]
    symbols = [s.name for s in c.generator.symbol_table.all_symbols]
    container = ColumnarBytecodeSerializer.pack_module(function_columns, FrontCodedStringPool.encode(symbols)[0])
    coded = HuffmanCompressor.compress(container)
    if len(coded) < len(container):
        return b"\x01" + coded, container, True
    return b"\x00" + container, container, False


def entropy_bits_per_byte(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return -sum(f / n * math.log2(f / n) for f in Counter(data).values())


def entropy_bound(data: bytes) -> float:
    """n * H / 8 bytes: no symbol-by-symbol code of data can be smaller."""
    return len(data) * entropy_bits_per_byte(data) / 8


def freq_huffman_header(data: bytes) -> int:
    return 7 + 5 * len(set(data)) if data else 0


# ---------------------------------------------------------------- compressors

def deflate_raw(data: bytes, zdict: Optional[bytes] = None) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY,
                          **({"zdict": zdict} if zdict else {}))
    return co.compress(data) + co.flush()


def brotli_c(data: bytes) -> bytes:
    import brotli
    return brotli.compress(data, quality=11, lgwin=22)


def zstd_frame(data: bytes) -> bytes:
    import zstandard
    return zstandard.ZstdCompressor(level=19).compress(data)


def zstd_headerless(data: bytes, dictionary=None) -> bytes:
    """Magic-less frame without checksum, content size or dictionary id."""
    import zstandard
    params = zstandard.ZstdCompressionParameters.from_level(
        19, format=zstandard.FORMAT_ZSTD1_MAGICLESS,
        write_checksum=0, write_content_size=0, write_dict_id=0)
    return zstandard.ZstdCompressor(compression_params=params, dict_data=dictionary).compress(data)


def xz_container(data: bytes) -> bytes:
    return lzma.compress(data, preset=9)


def lzma2_raw(data: bytes) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}])


def check_roundtrips(data: bytes, zstd_dict=None, zdict: Optional[bytes] = None) -> None:
    """Every compressor used must restore its input exactly."""
    import brotli
    import zstandard
    assert brotli.decompress(brotli_c(data)) == data
    assert zstandard.ZstdDecompressor().decompress(zstd_frame(data)) == data
    assert lzma.decompress(xz_container(data)) == data
    assert lzma.decompress(lzma2_raw(data), format=lzma.FORMAT_RAW,
                           filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}]) == data
    d = zlib.decompressobj(-15, **({"zdict": zdict} if zdict else {}))
    assert d.decompress(deflate_raw(data, zdict)) + d.flush() == data
    dd = zstandard.ZstdDecompressor(format=zstandard.FORMAT_ZSTD1_MAGICLESS, dict_data=zstd_dict)
    assert dd.decompressobj().decompress(zstd_headerless(data, zstd_dict)) == data


def library_versions() -> Dict[str, str]:
    import brotli
    import zstandard
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "brotli": brotli.__version__,
        "zstandard": ".".join(map(str, zstandard.ZSTD_VERSION)),
        "zstandard_binding": zstandard.__version__,
        "zlib": zlib.ZLIB_VERSION,
        "liblzma": getattr(lzma, "__version__", "stdlib"),
    }


# ---------------------------------------------------------------- results

def save(name: str, data) -> str:
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=False)
        f.write("\n")
    return path


def read(name: str):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


def reduction(a: float, b: float) -> float:
    """R(a, b) = 100 (a - b) / a."""
    return 100.0 * (a - b) / a if a else 0.0
