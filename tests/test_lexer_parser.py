"""
Unit tests for the C-Lite Lexer and Parser.
"""

import pytest
from core.lexer import Lexer, TokenType, LexerError
from core.parser import Parser, ParserError
from core.ast_nodes import ProgramNode, VarDeclNode, IfNode, WhileNode, ForNode, BinaryOpNode


def test_lexer_tokens():
    code = 'int count = 42; float pi = 3.14; string msg = "hello"; bool flag = true;'
    lexer = Lexer(code)
    tokens = lexer.tokenize()

    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types[0] == TokenType.INT
    assert types[1] == TokenType.IDENTIFIER
    assert types[2] == TokenType.ASSIGN
    assert types[3] == TokenType.INT_LIT
    assert types[4] == TokenType.SEMICOLON
    assert tokens[3].value == "42"


def test_lexer_operators():
    code = "a += 5; b == c && d != e || !f;"
    tokens = Lexer(code).tokenize()
    op_types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.PLUS_ASSIGN in op_types
    assert TokenType.EQUAL in op_types
    assert TokenType.AND in op_types
    assert TokenType.NOT_EQUAL in op_types
    assert TokenType.OR in op_types
    assert TokenType.NOT in op_types


def test_parser_variable_declaration():
    code = "int x = 10 + 20 * 3;"
    tokens = Lexer(code).tokenize()
    ast = Parser(tokens).parse()

    assert isinstance(ast, ProgramNode)
    assert len(ast.statements) == 1
    stmt = ast.statements[0]
    assert isinstance(stmt, VarDeclNode)
    assert stmt.name == "x"
    assert stmt.var_type == "int"
    # Precedence: 20 * 3 should be grouped before 10 + (...)
    assert isinstance(stmt.initializer, BinaryOpNode)
    assert stmt.initializer.op == "+"


def test_parser_control_structures():
    code = """
    if (x > 0) {
        y = 1;
    } else {
        y = 2;
    }
    while (y < 10) {
        y += 1;
    }
    """
    tokens = Lexer(code).tokenize()
    ast = Parser(tokens).parse()

    assert len(ast.statements) == 2
    assert isinstance(ast.statements[0], IfNode)
    assert isinstance(ast.statements[1], WhileNode)


def test_syntax_error():
    code = "int x = ;"
    tokens = Lexer(code).tokenize()
    with pytest.raises(ParserError):
        Parser(tokens).parse()
