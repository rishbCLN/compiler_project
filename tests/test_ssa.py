"""
Unit tests for Static Single Assignment (SSA) Transformation.
"""

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.ir import Opcode


def test_ssa_phi_insertion():
    code = """
    int x = 1;
    if (x < 5) {
        x = x + 10;
    } else {
        x = x + 20;
    }
    print(x);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()

    ssa_transformer = SSATransformer(cfg, dom)
    ssa_cfg = ssa_transformer.transform()

    # Verify that at least one PHI instruction was placed
    all_instructions = ssa_cfg.linearize()
    phi_instrs = [i for i in all_instructions if i.op == Opcode.PHI]
    assert len(phi_instrs) >= 1
    assert "x" in str(phi_instrs[0].result)


def test_ssa_variable_versioning():
    code = """
    int a = 10;
    a = a + 5;
    a = a * 2;
    print(a);
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()

    ssa_transformer = SSATransformer(cfg, dom)
    ssa_cfg = ssa_transformer.transform()

    definitions = [i.defines() for i in ssa_cfg.linearize() if i.defines()]
    # Definitions of 'a' should now have unique version suffixes
    a_versions = [d for d in definitions if d and d.startswith("a_")]
    assert len(set(a_versions)) == len(a_versions)
