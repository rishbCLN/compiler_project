"""
AST Node definitions for the C-Lite programming language.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Union


@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    line: int = 1
    col: int = 1

    def to_dict(self) -> dict:
        """Convert AST node to a nested dictionary for visualization/API."""
        res = {"type": self.__class__.__name__, "line": self.line, "col": self.col}
        for k, v in self.__dict__.items():
            if k in ("line", "col"):
                continue
            if isinstance(v, ASTNode):
                res[k] = v.to_dict()
            elif isinstance(v, list):
                res[k] = [item.to_dict() if isinstance(item, ASTNode) else item for item in v]
            else:
                res[k] = v
        return res


@dataclass
class ProgramNode(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class VarDeclNode(ASTNode):
    var_type: str = "int"
    name: str = ""
    initializer: Optional[ASTNode] = None


@dataclass
class AssignNode(ASTNode):
    name: str = ""
    value: Optional[ASTNode] = None
    op: str = "="  # =, +=, -=, *=, /=


@dataclass
class LiteralNode(ASTNode):
    value: Any = None
    literal_type: str = "int"  # int, float, string, bool


@dataclass
class VariableNode(ASTNode):
    name: str = ""


@dataclass
class BinaryOpNode(ASTNode):
    op: str = "+"
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None


@dataclass
class UnaryOpNode(ASTNode):
    op: str = "-"
    operand: Optional[ASTNode] = None


@dataclass
class BlockNode(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class IfNode(ASTNode):
    condition: Optional[ASTNode] = None
    then_branch: Optional[ASTNode] = None
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileNode(ASTNode):
    condition: Optional[ASTNode] = None
    body: Optional[ASTNode] = None


@dataclass
class ForNode(ASTNode):
    init: Optional[ASTNode] = None
    condition: Optional[ASTNode] = None
    update: Optional[ASTNode] = None
    body: Optional[ASTNode] = None


@dataclass
class PrintNode(ASTNode):
    expressions: List[ASTNode] = field(default_factory=list)


@dataclass
class ReturnNode(ASTNode):
    value: Optional[ASTNode] = None


@dataclass
class InputNode(ASTNode):
    """input(): reads the next integer of the program input."""


@dataclass
class ScanNode(ASTNode):
    """scanf("%d...", &a, &b, ...): reads one integer into each variable."""
    names: List[str] = field(default_factory=list)


@dataclass
class CallNode(ASTNode):
    name: str = ""
    args: List[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDefNode(ASTNode):
    name: str = ""
    return_type: str = "int"
    params: List[str] = field(default_factory=list)
    body: Optional[ASTNode] = None
