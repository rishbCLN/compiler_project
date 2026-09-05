"""
Unit tests for IR Optimization passes (Constant Folding, GVN, DCE).
"""

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.ir import Opcode


def test_constant_folding_and_propagation():
    code = """
    int a = 10 + 20 * 2;
    int b = a + 0;
    int c = b * 1;
    int d = c * 0;
    print(a, b, c, d);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()

    optimizer = IROptimizer(ssa_cfg)
    opt_cfg = optimizer.optimize()

    assert optimizer.stats["constant_folds"] > 0
    # Operations should be folded into constant loads
    binary_ops = [i for i in opt_cfg.linearize() if i.op in (Opcode.ADD, Opcode.MUL)]
    assert len(binary_ops) == 0


def test_dead_code_elimination():
    code = """
    int active = 100;
    int dead1 = 500 * 2;
    int dead2 = dead1 + 30;
    print(active);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()

    optimizer = IROptimizer(ssa_cfg)
    opt_cfg = optimizer.optimize()

    assert optimizer.stats["dead_instructions_removed"] > 0
    remaining_defs = [i.defines() for i in opt_cfg.linearize() if i.defines()]
    # dead1 and dead2 should be completely removed
    assert not any("dead1" in str(d) for d in remaining_defs)
    assert not any("dead2" in str(d) for d in remaining_defs)
