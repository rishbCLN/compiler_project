"""
Regression tests for the fixes made in response to the IEEE Access review
(major revision). Each test names the review comment it pins.
"""

from copy import deepcopy

import pytest

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.ir import Opcode


def _compile(code):
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


def _printed_literals(instrs):
    """Values printed by a fully folded program (every PRINT operand is a
    literal or a variable loaded from one)."""
    consts = {i.result: str(i.arg1) for i in instrs if i.op == Opcode.LOAD_CONST}
    return [consts.get(str(i.arg1), str(i.arg1)) for i in instrs if i.op == Opcode.PRINT]


# ------------------------------------------------------------- Comment 4

@pytest.mark.parametrize("a,b,quot,rem", [
    (-31, 1000, 0, -31),
    (-7, 2, -3, -1),
    (7, -2, -3, 1),
    (-7, -2, 3, -1),
    (7, 2, 3, 1),
])
def test_folding_uses_c_truncating_division(a, b, quot, rem):
    """Constant folding must follow C: / truncates toward zero and % takes
    the sign of the dividend. The released folder used Python's floor rule
    and folded -31 % 1000 to 969."""
    # Negative operands are written as 0 - n so that they reach the folder
    # through binary subtraction.
    def lit(v):
        return f"0 - {-v}" if v < 0 else str(v)
    code = f"int a = {lit(a)};\nint b = {lit(b)};\nprint(a / b);\nprint(a % b);\n"
    _, _, _, opt, _ = _compile(code)
    assert _printed_literals(opt) == [str(quot), str(rem)]


def test_division_by_zero_is_not_folded():
    _, _, _, opt, _ = _compile("int z = 0;\nint x = 5 / z;\nprint(x);\n")
    assert any(i.op == Opcode.DIV for i in opt)


# ------------------------------------------------- Front end (found in revision)

def test_temporaries_do_not_overwrite_user_variables_named_like_temps():
    """A user variable called t1 used to share its name with the generator's
    temporary t1, so `int t1 = 9; int a = 1 + 2 + 3; print(t1);` printed 1."""
    code = "int t1 = 9;\nint a = 1 + 2 + 3;\nprint(t1);\nprint(a);\n"
    _, _, _, opt, raw = _compile(code)
    assert _printed_literals(opt) == ["9", "6"]
    user_defs = {"t1", "a"}
    temps = {i.result for i in raw if i.result and i.result not in user_defs}
    assert temps and all(t.startswith("_t") for t in temps)


# ------------------------------------------------------- Comments 2 and 8

import glob

from core.ir import Instruction, canonical_form
from core.binary_compression import BytecodeEmitter, BytecodeDecoder

BENCHMARKS = sorted(glob.glob("benchmarks/*.lang") + glob.glob("benchmarks/*.c"))


def _block_order(cfg):
    return [b.id for b in sorted(cfg.blocks.values(), key=lambda b: int(b.id[2:]))]


@pytest.mark.parametrize("path", BENCHMARKS)
def test_clir_is_self_describing(path):
    """Decoding with no side tables at all (no name maps, no literal table)
    must give back the optimized program up to a consistent renaming."""
    _, _, opt_cfg, opt, _ = _compile(open(path, encoding="utf-8").read())
    package = bytes(BytecodeEmitter().serialize_program(opt, cfg=opt_cfg))
    blocks, _ = BytecodeDecoder.decode_blocks(package)
    decoded = [i for _, instrs in blocks for i in instrs]
    assert canonical_form(decoded, [b for b, _ in blocks]) == \
        canonical_form(opt, _block_order(opt_cfg))


def test_literal_operands_are_stored_in_the_package():
    """Literal operands inside instructions (not only LOAD_CONST) round-trip."""
    instrs = [
        Instruction(op=Opcode.ADD, arg1="x", arg2="5", result="y"),
        Instruction(op=Opcode.LT, arg1="-3", arg2="y", result="c"),
        Instruction(op=Opcode.ASSIGN, arg1="2.5", result="f"),
        Instruction(op=Opcode.PRINT, arg1='"done"'),
        Instruction(op=Opcode.PRINT, arg1="true"),
        Instruction(op=Opcode.RETURN, arg1="0"),
    ]
    package = bytes(BytecodeEmitter().serialize_program(instrs))
    decoded, pool = BytecodeDecoder.decode_program(package)
    assert [str(i) for i in decoded] == [
        "v0 = v1 + 5", "v2 = -3 < v0", "v3 = 2.5", 'print "done"', "print true", "return 0"]
    assert [e.value for e in pool.entries] == [5, -3, 2.5, "done", True, 0]


@pytest.mark.parametrize("path", BENCHMARKS)
def test_constant_pool_holds_only_referenced_literals(path):
    _, _, opt_cfg, opt, _ = _compile(open(path, encoding="utf-8").read())
    emitter = BytecodeEmitter()
    emitter.serialize_program(opt, cfg=opt_cfg)
    used = set()
    for i in opt:
        operands = list(i.phi_args.values()) + [i.arg1, i.arg2]
        used |= {str(o) for o in operands
                 if o is not None and BytecodeEmitter.classify_operand(o)
                 and i.op not in (Opcode.LABEL, Opcode.JUMP)}
    pooled = {(e.const_type, e.value) for e in emitter.pool.entries}
    assert len(emitter.pool.entries) == len(used)
    assert len(pooled) == len(emitter.pool.entries)


# ------------------------------------------------------------- Comment 3

from core.advanced_compression import (
    SSABackwardDeltaEncoder, ColumnarBytecodeSerializer, FrontCodedStringPool)


def _columnar_roundtrip(instrs):
    columns = ColumnarBytecodeSerializer.serialize_columns(
        SSABackwardDeltaEncoder.encode_instructions(instrs))
    container = ColumnarBytecodeSerializer.pack_container(columns, FrontCodedStringPool.encode([])[0])
    unpacked, _ = ColumnarBytecodeSerializer.unpack_container(container)
    return ColumnarBytecodeSerializer.decode_instructions(
        ColumnarBytecodeSerializer.deserialize_columns(unpacked))


def test_columnar_keeps_forward_phi_references():
    """A loop-carried phi argument is defined after the phi in linear order.
    The released encoder stored 0 for it, so the argument was lost."""
    instrs = [
        Instruction(op=Opcode.LOAD_CONST, arg1="0", result="i_0"),
        Instruction(op=Opcode.LABEL, arg1="L_head"),
        Instruction(op=Opcode.PHI, result="i_1", phi_args={"BB0": "i_0", "BB2": "i_2"}),
        Instruction(op=Opcode.LT, arg1="i_1", arg2="10", result="c_0"),
        Instruction(op=Opcode.JUMP_IF_FALSE, arg1="c_0", result="L_end"),
        Instruction(op=Opcode.ADD, arg1="i_1", arg2="1", result="i_2"),
        Instruction(op=Opcode.JUMP, arg1="L_head"),
        Instruction(op=Opcode.LABEL, arg1="L_end"),
        Instruction(op=Opcode.PRINT, arg1="i_1"),
    ]
    decoded = _columnar_roundtrip(instrs)
    assert decoded[2].phi_args == {"BB0": "%0", "BB2": "%5"}
    assert canonical_form(decoded) == canonical_form(instrs)


@pytest.mark.parametrize("path", BENCHMARKS)
def test_columnar_container_is_lossless_on_benchmarks(path):
    _, _, _, opt, _ = _compile(open(path, encoding="utf-8").read())
    assert canonical_form(_columnar_roundtrip(opt)) == canonical_form(opt)


# ------------------------------------------------------------- Comment 7

import random

from core.binary_compression import HuffmanCompressor, FrequencyTableHuffman


def _random_bytes(seed, n, alphabet=range(256)):
    rng = random.Random(seed)
    alphabet = list(alphabet)
    return bytes(rng.choice(alphabet) for _ in range(n))


def _fibonacci_skewed(n_symbols=22):
    """Frequencies 1, 1, 2, 3, 5, ... force an unbounded Huffman tree deeper
    than 15 levels, which exercises length limiting."""
    a, b = 1, 1
    out = bytearray()
    for s in range(n_symbols):
        out.extend(bytes([s]) * a)
        a, b = b, a + b
    return bytes(out)


@pytest.mark.parametrize("data", [
    b"a",
    b"aaaaaaa",
    b"ab",
    bytes(range(256)),
    _random_bytes(1, 5000),
    _random_bytes(2, 3000, b"\x00\x01\x02\x11\x12\x80"),
    _fibonacci_skewed(),
])
def test_canonical_huffman_round_trip(data):
    packed = HuffmanCompressor.compress(data)
    assert HuffmanCompressor.decompress(packed) == data
    assert HuffmanCompressor.analyze(data)["total_bytes"] == len(packed)
    assert max(HuffmanCompressor.code_lengths(data).values()) <= 15


def test_canonical_header_is_small():
    """The frequency-table header costs 7 + 5k bytes (1,287 for k = 256);
    canonical coding stores only 4-bit code lengths."""
    data = _random_bytes(3, 4000)
    info = HuffmanCompressor.analyze(data)
    assert info["distinct_symbols"] == 256
    assert info["header_bytes"] <= 2 + 1 + 128
    old = FrequencyTableHuffman.compress(data)
    assert len(old) - info["payload_bytes"] >= 1287 - 1
    assert FrequencyTableHuffman.decompress(old) == data
