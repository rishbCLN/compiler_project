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
