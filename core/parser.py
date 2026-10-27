"""
Recursive Descent Parser for C-Lite.
Builds an Abstract Syntax Tree (AST) from a sequence of tokens with proper operator precedence.
"""

from typing import List, Optional
from core.lexer import Token, TokenType
from core.ast_nodes import (
    ASTNode, ProgramNode, VarDeclNode, AssignNode, LiteralNode,
    VariableNode, BinaryOpNode, UnaryOpNode, BlockNode, IfNode,
    WhileNode, ForNode, PrintNode, ReturnNode, InputNode, ScanNode, CallNode,
    FunctionDefNode
)


class ParserError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"Parser Error at Line {token.line}, Column {token.col}: {message} (got '{token.value}')")
        self.token = token
        self.message = message


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF token

    def peek_token(self, offset: int = 1) -> Token:
        target = self.pos + offset
        if target < len(self.tokens):
            return self.tokens[target]
        return self.tokens[-1]

    def match(self, *expected_types: TokenType) -> bool:
        if self.current_token().type in expected_types:
            self.pos += 1
            return True
        return False

    def expect(self, expected_type: TokenType, err_msg: Optional[str] = None) -> Token:
        tok = self.current_token()
        if tok.type == expected_type:
            self.pos += 1
            return tok
        msg = err_msg or f"Expected {expected_type.name}"
        raise ParserError(msg, tok)

    def parse(self) -> ProgramNode:
        statements: List[ASTNode] = []
        start_tok = self.current_token()
        while self.current_token().type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return ProgramNode(line=start_tok.line, col=start_tok.col, statements=statements)

    def parse_statement(self) -> ASTNode:
        tok = self.current_token()

        if tok.type in (TokenType.INT, TokenType.FLOAT, TokenType.STRING, TokenType.BOOL):
            return self.parse_var_decl()
        elif tok.type == TokenType.IF:
            return self.parse_if()
        elif tok.type == TokenType.WHILE:
            return self.parse_while()
        elif tok.type == TokenType.FOR:
            return self.parse_for()
        elif tok.type == TokenType.PRINT:
            return self.parse_print()
        elif tok.type == TokenType.SCANF:
            return self.parse_scanf()
        elif tok.type == TokenType.RETURN:
            return self.parse_return()
        elif tok.type == TokenType.LBRACE:
            return self.parse_block()
        elif tok.type == TokenType.IDENTIFIER:
            # Assignment or expression statement
            return self.parse_assign_or_expr_stmt()
        elif tok.type == TokenType.SEMICOLON:
            # Empty statement
            self.pos += 1
            return BlockNode(line=tok.line, col=tok.col, statements=[])
        else:
            raise ParserError(f"Unexpected statement beginning with token '{tok.value}'", tok)

    def parse_var_decl(self) -> ASTNode:
        type_tok = self.current_token()
        self.pos += 1
        name_tok = self.expect(TokenType.IDENTIFIER, "Expected identifier after type name")

        # Function definition or prototype: e.g. int main() { ... } or int f(int a);
        if self.match(TokenType.LPAREN):
            params: List[str] = []
            while self.current_token().type not in (TokenType.RPAREN, TokenType.EOF):
                if self.current_token().type in (TokenType.INT, TokenType.FLOAT,
                                                 TokenType.STRING, TokenType.BOOL):
                    self.pos += 1  # parameter type (or `void`)
                    if self.current_token().type == TokenType.IDENTIFIER:
                        params.append(self.current_token().value)
                        self.pos += 1
                elif self.current_token().type == TokenType.COMMA:
                    self.pos += 1
                else:
                    raise ParserError("Expected a parameter declaration", self.current_token())
            self.expect(TokenType.RPAREN, "Expected ')' after parameters")
            if self.match(TokenType.SEMICOLON):
                # Function prototype
                return BlockNode(line=type_tok.line, col=type_tok.col, statements=[])
            body = self.parse_block()
            if name_tok.value == "main":
                # The body of main() is the program itself.
                return body
            return FunctionDefNode(line=type_tok.line, col=type_tok.col, name=name_tok.value,
                                   return_type=type_tok.value, params=params, body=body)

        initializer: Optional[ASTNode] = None
        if self.match(TokenType.ASSIGN):
            initializer = self.parse_expression()

        self.expect(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        return VarDeclNode(
            line=type_tok.line,
            col=type_tok.col,
            var_type=type_tok.value,
            name=name_tok.value,
            initializer=initializer,
        )

    def parse_assign_or_expr_stmt(self) -> ASTNode:
        ident_tok = self.current_token()
        next_tok = self.peek_token(1)

        # Compound or direct assignment: x = ..., x += ...
        if next_tok.type in (TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
                             TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN):
            self.pos += 1  # consume identifier
            op_tok = self.current_token()
            self.pos += 1  # consume assignment operator

            val_expr = self.parse_expression()
            self.expect(TokenType.SEMICOLON, "Expected ';' after assignment")

            if op_tok.type != TokenType.ASSIGN:
                # Convert `x += e` to `x = x + e`
                base_op = op_tok.value[0]  # '+', '-', '*', '/'
                expanded = BinaryOpNode(
                    line=op_tok.line,
                    col=op_tok.col,
                    op=base_op,
                    left=VariableNode(line=ident_tok.line, col=ident_tok.col, name=ident_tok.value),
                    right=val_expr,
                )
                return AssignNode(
                    line=ident_tok.line,
                    col=ident_tok.col,
                    name=ident_tok.value,
                    value=expanded,
                    op="=",
                )

            return AssignNode(
                line=ident_tok.line,
                col=ident_tok.col,
                name=ident_tok.value,
                value=val_expr,
                op="=",
            )

        # Expression statement
        expr = self.parse_expression()
        self.expect(TokenType.SEMICOLON, "Expected ';' after expression")
        return expr

    def parse_block(self) -> BlockNode:
        lbrace = self.expect(TokenType.LBRACE)
        statements: List[ASTNode] = []
        while self.current_token().type not in (TokenType.RBRACE, TokenType.EOF):
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        self.expect(TokenType.RBRACE, "Expected '}' to close block")
        return BlockNode(line=lbrace.line, col=lbrace.col, statements=statements)

    def parse_if(self) -> IfNode:
        if_tok = self.expect(TokenType.IF)
        self.expect(TokenType.LPAREN, "Expected '(' after 'if'")
        condition = self.parse_expression()
        self.expect(TokenType.RPAREN, "Expected ')' after condition")

        then_branch = self.parse_statement_or_block()
        else_branch: Optional[ASTNode] = None

        if self.match(TokenType.ELSE):
            else_branch = self.parse_statement_or_block()

        return IfNode(
            line=if_tok.line,
            col=if_tok.col,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def parse_statement_or_block(self) -> ASTNode:
        if self.current_token().type == TokenType.LBRACE:
            return self.parse_block()
        return self.parse_statement()

    def parse_while(self) -> WhileNode:
        while_tok = self.expect(TokenType.WHILE)
        self.expect(TokenType.LPAREN, "Expected '(' after 'while'")
        condition = self.parse_expression()
        self.expect(TokenType.RPAREN, "Expected ')' after condition")
        body = self.parse_statement_or_block()
        return WhileNode(line=while_tok.line, col=while_tok.col, condition=condition, body=body)

    def parse_for(self) -> ForNode:
        for_tok = self.expect(TokenType.FOR)
        self.expect(TokenType.LPAREN, "Expected '(' after 'for'")

        init: Optional[ASTNode] = None
        if self.current_token().type != TokenType.SEMICOLON:
            if self.current_token().type in (TokenType.INT, TokenType.FLOAT, TokenType.STRING, TokenType.BOOL):
                init = self.parse_var_decl()
            else:
                ident_tok = self.expect(TokenType.IDENTIFIER)
                self.expect(TokenType.ASSIGN)
                val = self.parse_expression()
                self.expect(TokenType.SEMICOLON)
                init = AssignNode(line=ident_tok.line, col=ident_tok.col, name=ident_tok.value, value=val)
        else:
            self.expect(TokenType.SEMICOLON)

        condition: Optional[ASTNode] = None
        if self.current_token().type != TokenType.SEMICOLON:
            condition = self.parse_expression()
        self.expect(TokenType.SEMICOLON, "Expected ';' after for-loop condition")

        update: Optional[ASTNode] = None
        if self.current_token().type != TokenType.RPAREN:
            # Could be assignment without semicolon
            ident_tok = self.expect(TokenType.IDENTIFIER)
            assign_op = self.current_token()
            if assign_op.type in (TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
                                 TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN):
                self.pos += 1
                val = self.parse_expression()
                if assign_op.type != TokenType.ASSIGN:
                    base_op = assign_op.value[0]
                    expanded = BinaryOpNode(
                        line=assign_op.line, col=assign_op.col, op=base_op,
                        left=VariableNode(line=ident_tok.line, col=ident_tok.col, name=ident_tok.value),
                        right=val
                    )
                    update = AssignNode(line=ident_tok.line, col=ident_tok.col, name=ident_tok.value, value=expanded)
                else:
                    update = AssignNode(line=ident_tok.line, col=ident_tok.col, name=ident_tok.value, value=val)
            else:
                raise ParserError("Expected assignment in for update clause", assign_op)

        self.expect(TokenType.RPAREN, "Expected ')' after for clauses")
        body = self.parse_statement_or_block()

        return ForNode(
            line=for_tok.line,
            col=for_tok.col,
            init=init,
            condition=condition,
            update=update,
            body=body,
        )

    def parse_print(self) -> PrintNode:
        print_tok = self.expect(TokenType.PRINT)
        self.expect(TokenType.LPAREN, "Expected '(' after 'print'")
        expressions: List[ASTNode] = []

        if self.current_token().type != TokenType.RPAREN:
            expressions.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                expressions.append(self.parse_expression())

        self.expect(TokenType.RPAREN, "Expected ')' after print arguments")
        self.expect(TokenType.SEMICOLON, "Expected ';' after print statement")
        return PrintNode(line=print_tok.line, col=print_tok.col, expressions=expressions)

    def parse_scanf(self) -> ScanNode:
        """scanf("<format>", &a, &b, ...); -- the format string is ignored and
        one integer is read into each listed variable."""
        scan_tok = self.expect(TokenType.SCANF)
        self.expect(TokenType.LPAREN, "Expected '(' after 'scanf'")
        self.expect(TokenType.STRING_LIT, "Expected a format string in scanf")
        names: List[str] = []
        while self.match(TokenType.COMMA):
            self.expect(TokenType.AMPERSAND, "Expected '&' before a scanf target")
            names.append(self.expect(TokenType.IDENTIFIER, "Expected a variable after '&'").value)
        self.expect(TokenType.RPAREN, "Expected ')' after scanf arguments")
        self.expect(TokenType.SEMICOLON, "Expected ';' after scanf")
        return ScanNode(line=scan_tok.line, col=scan_tok.col, names=names)

    def parse_return(self) -> ReturnNode:
        ret_tok = self.expect(TokenType.RETURN)
        val: Optional[ASTNode] = None
        if self.current_token().type != TokenType.SEMICOLON:
            val = self.parse_expression()
        self.expect(TokenType.SEMICOLON, "Expected ';' after return")
        return ReturnNode(line=ret_tok.line, col=ret_tok.col, value=val)

    # ---------------- Expression Parsing with Precedence ----------------

    def parse_expression(self) -> ASTNode:
        return self.parse_logical_or()

    def parse_logical_or(self) -> ASTNode:
        node = self.parse_logical_and()
        while self.match(TokenType.OR):
            op = "||"
            right = self.parse_logical_and()
            node = BinaryOpNode(line=node.line, col=node.col, op=op, left=node, right=right)
        return node

    def parse_logical_and(self) -> ASTNode:
        node = self.parse_equality()
        while self.match(TokenType.AND):
            op = "&&"
            right = self.parse_equality()
            node = BinaryOpNode(line=node.line, col=node.col, op=op, left=node, right=right)
        return node

    def parse_equality(self) -> ASTNode:
        node = self.parse_comparison()
        while self.current_token().type in (TokenType.EQUAL, TokenType.NOT_EQUAL):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_comparison()
            node = BinaryOpNode(line=op_tok.line, col=op_tok.col, op=op_tok.value, left=node, right=right)
        return node

    def parse_comparison(self) -> ASTNode:
        node = self.parse_additive()
        while self.current_token().type in (TokenType.LESS, TokenType.LESS_EQUAL,
                                            TokenType.GREATER, TokenType.GREATER_EQUAL):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_additive()
            node = BinaryOpNode(line=op_tok.line, col=op_tok.col, op=op_tok.value, left=node, right=right)
        return node

    def parse_additive(self) -> ASTNode:
        node = self.parse_multiplicative()
        while self.current_token().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_multiplicative()
            node = BinaryOpNode(line=op_tok.line, col=op_tok.col, op=op_tok.value, left=node, right=right)
        return node

    def parse_multiplicative(self) -> ASTNode:
        node = self.parse_unary()
        while self.current_token().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_unary()
            node = BinaryOpNode(line=op_tok.line, col=op_tok.col, op=op_tok.value, left=node, right=right)
        return node

    def parse_unary(self) -> ASTNode:
        tok = self.current_token()
        if tok.type in (TokenType.MINUS, TokenType.NOT):
            self.pos += 1
            operand = self.parse_unary()
            return UnaryOpNode(line=tok.line, col=tok.col, op=tok.value, operand=operand)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        tok = self.current_token()

        if tok.type == TokenType.INT_LIT:
            self.pos += 1
            return LiteralNode(line=tok.line, col=tok.col, value=int(tok.value), literal_type="int")
        elif tok.type == TokenType.FLOAT_LIT:
            self.pos += 1
            return LiteralNode(line=tok.line, col=tok.col, value=float(tok.value), literal_type="float")
        elif tok.type == TokenType.STRING_LIT:
            self.pos += 1
            return LiteralNode(line=tok.line, col=tok.col, value=tok.value, literal_type="string")
        elif tok.type == TokenType.BOOL_LIT:
            self.pos += 1
            return LiteralNode(line=tok.line, col=tok.col, value=(tok.value == "true"), literal_type="bool")
        elif tok.type == TokenType.IDENTIFIER:
            self.pos += 1
            if self.current_token().type == TokenType.LPAREN:
                self.pos += 1
                args: List[ASTNode] = []
                if self.current_token().type != TokenType.RPAREN:
                    args.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        args.append(self.parse_expression())
                self.expect(TokenType.RPAREN, "Expected ')' after call arguments")
                if tok.value == "input" and not args:
                    return InputNode(line=tok.line, col=tok.col)
                return CallNode(line=tok.line, col=tok.col, name=tok.value, args=args)
            return VariableNode(line=tok.line, col=tok.col, name=tok.value)
        elif tok.type == TokenType.LPAREN:
            self.pos += 1
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN, "Expected ')' after expression")
            return expr
        else:
            raise ParserError(f"Unexpected primary expression token '{tok.value}'", tok)
