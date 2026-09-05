"""
Unit tests for Basic Block partitioning, CFG construction, and Dominance analysis.
"""

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer


def test_cfg_basic_blocks():
    code = """
    int x = 0;
    if (x < 10) {
        x = x + 1;
    } else {
        x = x - 1;
    }
    print(x);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)

    assert len(cfg.blocks) >= 4
    entry = cfg.get_block(cfg.entry_block_id)
    assert entry is not None
    assert len(entry.successors) >= 1


def test_dominance_frontiers():
    code = """
    int x = 0;
    if (x < 5) {
        x = 10;
    } else {
        x = 20;
    }
    print(x);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()

    # The join block (where print(x) resides) must have multiple predecessors
    join_blocks = [b for b, bb in cfg.blocks.items() if len(bb.predecessors) >= 2]
    assert len(join_blocks) >= 1
    join_bb = join_blocks[0]

    # Predecessors of join_bb must have join_bb in their dominance frontier
    for p in cfg.blocks[join_bb].predecessors:
        if p != dom.idom.get(join_bb):
            assert join_bb in dom.dom_frontiers.get(p, set())
