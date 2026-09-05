"""
Lexer (Tokenizer) for the C-Lite programming language.
Supports keywords, identifiers, numeric/string literals, operators, and comments.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional


class TokenType(Enum):
    # End of File
    EOF = auto()

    # Literals
    INT_LIT = auto()
    FLOAT_LIT = auto()
    STRING_LIT = auto()
    BOOL_LIT = auto()
    IDENTIFIER = auto()

    # Keywords
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    BOOL = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    PRINT = auto()
    RETURN = auto()

    # Operators
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # *
    SLASH = auto()          # /
    PERCENT = auto()        # %
    ASSIGN = auto()         # =
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=
    STAR_ASSIGN = auto()    # *=
    SLASH_ASSIGN = auto()   # /=
    EQUAL = auto()          # ==
    NOT_EQUAL = auto()      # !=
    LESS = auto()           # <
    LESS_EQUAL = auto()     # <=
    GREATER = auto()        # >
    GREATER_EQUAL = auto()  # >=
    AND = auto()            # &&
    OR = auto()             # ||
    NOT = auto()            # !

    # Delimiters
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    SEMICOLON = auto()      # ;
    COMMA = auto()          # ,


KEYWORDS = {
    "int": TokenType.INT,
    "float": TokenType.FLOAT,
    "string": TokenType.STRING,
    "bool": TokenType.BOOL,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "print": TokenType.PRINT,
    "return": TokenType.RETURN,
    "true": TokenType.BOOL_LIT,
    "false": TokenType.BOOL_LIT,
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def to_dict(self) -> dict:
        return {
            "type": self.type.name,
            "value": self.value,
            "line": self.line,
            "col": self.col,
        }

    def __repr__(self) -> str:
        return f"Token({self.type.name}, '{self.value}', L{self.line}:C{self.col})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Lexer Error at Line {line}, Column {col}: {message}")
        self.line = line
        self.col = col
        self.message = message


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)

    def current_char(self) -> Optional[str]:
        if self.pos >= self.length:
            return None
        return self.source[self.pos]

    def peek_char(self, offset: int = 1) -> Optional[str]:
        target = self.pos + offset
        if target >= self.length:
            return None
        return self.source[target]

    def advance(self) -> Optional[str]:
        ch = self.current_char()
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace_and_comments(self):
        while self.pos < self.length:
            ch = self.current_char()
            if ch in (' ', '\t', '\r', '\n'):
                self.advance()
            elif ch == '/' and self.peek_char() == '/':
                # Single line comment
                while self.current_char() is not None and self.current_char() != '\n':
                    self.advance()
            elif ch == '/' and self.peek_char() == '*':
                # Multi line comment
                self.advance()
                self.advance()
                while self.pos < self.length:
                    if self.current_char() == '*' and self.peek_char() == '/':
                        self.advance()
                        self.advance()
                        break
                    self.advance()
            else:
                break

    def read_number(self) -> Token:
        start_col = self.col
        start_line = self.line
        num_str = ""
        is_float = False

        while self.current_char() is not None and (self.current_char().isdigit() or self.current_char() == '.'):
            if self.current_char() == '.':
                if is_float:
                    break  # Second dot not allowed in number
                # Check if next char is digit
                next_c = self.peek_char()
                if next_c is None or not next_c.isdigit():
                    break
                is_float = True
            num_str += self.advance()

        token_type = TokenType.FLOAT_LIT if is_float else TokenType.INT_LIT
        return Token(token_type, num_str, start_line, start_col)

    def read_identifier_or_keyword(self) -> Token:
        start_col = self.col
        start_line = self.line
        ident_str = ""

        while self.current_char() is not None and (self.current_char().isalnum() or self.current_char() == '_'):
            ident_str += self.advance()

        token_type = KEYWORDS.get(ident_str, TokenType.IDENTIFIER)
        return Token(token_type, ident_str, start_line, start_col)

    def read_string(self) -> Token:
        start_col = self.col
        start_line = self.line
        self.advance()  # Skip opening quote
        str_val = ""

        while self.current_char() is not None and self.current_char() != '"':
            ch = self.advance()
            if ch == '\\':
                next_c = self.advance()
                if next_c == 'n':
                    str_val += '\n'
                elif next_c == 't':
                    str_val += '\t'
                elif next_c == '"':
                    str_val += '"'
                elif next_c == '\\':
                    str_val += '\\'
                else:
                    str_val += next_c if next_c else '\\'
            else:
                str_val += ch

        if self.current_char() != '"':
            raise LexerError("Unterminated string literal", start_line, start_col)
        self.advance()  # Skip closing quote

        return Token(TokenType.STRING_LIT, str_val, start_line, start_col)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while self.pos < self.length:
            self.skip_whitespace_and_comments()
            if self.pos >= self.length:
                break

            ch = self.current_char()
            start_line = self.line
            start_col = self.col

            if ch.isdigit():
                tokens.append(self.read_number())
            elif ch.isalpha() or ch == '_':
                tokens.append(self.read_identifier_or_keyword())
            elif ch == '"':
                tokens.append(self.read_string())
            elif ch == '+':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.PLUS, "+", start_line, start_col))
            elif ch == '-':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.MINUS, "-", start_line, start_col))
            elif ch == '*':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.STAR_ASSIGN, "*=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.STAR, "*", start_line, start_col))
            elif ch == '/':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.SLASH_ASSIGN, "/=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.SLASH, "/", start_line, start_col))
            elif ch == '%':
                self.advance()
                tokens.append(Token(TokenType.PERCENT, "%", start_line, start_col))
            elif ch == '=':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.EQUAL, "==", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col))
            elif ch == '!':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.NOT_EQUAL, "!=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.NOT, "!", start_line, start_col))
            elif ch == '<':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.LESS_EQUAL, "<=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.LESS, "<", start_line, start_col))
            elif ch == '>':
                self.advance()
                if self.current_char() == '=':
                    self.advance()
                    tokens.append(Token(TokenType.GREATER_EQUAL, ">=", start_line, start_col))
                else:
                    tokens.append(Token(TokenType.GREATER, ">", start_line, start_col))
            elif ch == '&':
                self.advance()
                if self.current_char() == '&':
                    self.advance()
                    tokens.append(Token(TokenType.AND, "&&", start_line, start_col))
                else:
                    raise LexerError("Expected '&&' for logical AND", start_line, start_col)
            elif ch == '|':
                self.advance()
                if self.current_char() == '|':
                    self.advance()
                    tokens.append(Token(TokenType.OR, "||", start_line, start_col))
                else:
                    raise LexerError("Expected '||' for logical OR", start_line, start_col)
            elif ch == '(':
                self.advance()
                tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col))
            elif ch == ')':
                self.advance()
                tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col))
            elif ch == '{':
                self.advance()
                tokens.append(Token(TokenType.LBRACE, "{", start_line, start_col))
            elif ch == '}':
                self.advance()
                tokens.append(Token(TokenType.RBRACE, "}", start_line, start_col))
            elif ch == ';':
                self.advance()
                tokens.append(Token(TokenType.SEMICOLON, ";", start_line, start_col))
            elif ch == ',':
                self.advance()
                tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))
            else:
                raise LexerError(f"Unexpected character: '{ch}'", start_line, start_col)

        tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return tokens
