"""
Unit tests for 3-Address Code (TAC) Generation.
"""

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.ir import Opcode


def test_tac_arithmetic_generation():
    code = "int res = a + b * c;"
    ast = Parser(Lexer(code).tokenize()).parse()
    ir_gen = IRGenerator()
    instructions = ir_gen.generate(ast)

    # Should contain MUL, ADD, and ASSIGN
    opcodes = [i.op for i in instructions]
    assert Opcode.MUL in opcodes
    assert Opcode.ADD in opcodes
    assert Opcode.ASSIGN in opcodes


def test_tac_if_branch_generation():
    code = """
    if (a < 5) {
        x = 1;
    } else {
        x = 2;
    }
    """
    ast = Parser(Lexer(code).tokenize()).parse()
    instructions = IRGenerator().generate(ast)

    opcodes = [i.op for i in instructions]
    assert Opcode.JUMP_IF_FALSE in opcodes
    assert Opcode.JUMP in opcodes
    assert Opcode.LABEL in opcodes
