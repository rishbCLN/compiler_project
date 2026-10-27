"""
Three-Address Code (TAC) Intermediate Representation (IR) definitions.
Supports Quadruples (Op, Arg1, Arg2, Result), Labels, Jumps, and SSA Phi nodes.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Union, Tuple

_INT_LITERAL = re.compile(r"-?[0-9]+")
_FLOAT_LITERAL = re.compile(r"-?([0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)([eE][-+]?[0-9]+)?")


def literal_type(operand: Any) -> Optional[str]:
    """Return 'int', 'float', 'bool' or 'string' if the operand text is a
    literal, or None if it names a variable."""
    s = str(operand)
    if s in ("true", "false"):
        return "bool"
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        return "string"
    if _INT_LITERAL.fullmatch(s):
        return "int"
    if _FLOAT_LITERAL.fullmatch(s):
        return "float"
    return None


class Opcode(Enum):
    # Arithmetic
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    MOD = "MOD"
    NEG = "NEG"

    # Logical / Bitwise
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # Relational
    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"

    # Data movement
    ASSIGN = "ASSIGN"       # result = arg1
    LOAD_CONST = "LOAD_CONST" # result = constant_pool[arg1] or literal

    # Control Flow
    LABEL = "LABEL"         # Label: arg1
    JUMP = "JUMP"           # goto arg1
    JUMP_IF_TRUE = "JUMP_IF_TRUE"   # if arg1 goto result
    JUMP_IF_FALSE = "JUMP_IF_FALSE" # if not arg1 goto result
    RETURN = "RETURN"       # return arg1

    # SSA
    PHI = "PHI"             # result = phi(BB_pred1: var1, BB_pred2: var2, ...)

    # System / Built-in
    PRINT = "PRINT"         # print arg1
    NOP = "NOP"
    READ = "READ"           # result = next value from the program input

    # Functions
    PARAM = "PARAM"         # result = parameter number arg1 of the function
    CALL = "CALL"           # result = call arg1(call_args...)


@dataclass
class Instruction:
    op: Opcode
    arg1: Optional[Any] = None
    arg2: Optional[Any] = None
    result: Optional[str] = None
    # Source metadata
    line: int = 0
    # For PHI nodes: dict mapping block_id -> var_name (e.g. {"BB0": "x_0", "BB1": "x_1"})
    phi_args: Dict[str, str] = field(default_factory=dict)
    # Extra annotations (e.g. constant value, live range)
    annotation: Optional[str] = None
    # For CALL: the argument operands, in order
    call_args: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.op == Opcode.LABEL:
            return f"{self.arg1}:"
        elif self.op == Opcode.JUMP:
            return f"goto {self.arg1}"
        elif self.op == Opcode.JUMP_IF_TRUE:
            return f"if {self.arg1} goto {self.result}"
        elif self.op == Opcode.JUMP_IF_FALSE:
            return f"if_false {self.arg1} goto {self.result}"
        elif self.op == Opcode.RETURN:
            return f"return {self.arg1}" if self.arg1 is not None else "return"
        elif self.op == Opcode.PRINT:
            return f"print {self.arg1}"
        elif self.op == Opcode.ASSIGN:
            return f"{self.result} = {self.arg1}"
        elif self.op == Opcode.LOAD_CONST:
            return f"{self.result} = {self.arg1}"
        elif self.op == Opcode.PHI:
            phi_str = ", ".join(f"{pred}: {var}" for pred, var in sorted(self.phi_args.items()))
            return f"{self.result} = phi({phi_str})"
        elif self.op in (Opcode.NEG, Opcode.NOT):
            symbol = "-" if self.op == Opcode.NEG else "!"
            return f"{self.result} = {symbol}{self.arg1}"
        elif self.op == Opcode.NOP:
            return "nop"
        elif self.op == Opcode.READ:
            return f"{self.result} = read"
        elif self.op == Opcode.PARAM:
            return f"{self.result} = param {self.arg1}"
        elif self.op == Opcode.CALL:
            return f"{self.result} = call {self.arg1}({', '.join(str(a) for a in self.call_args)})"
        else:
            # Binary operation
            op_symbols = {
                Opcode.ADD: "+", Opcode.SUB: "-", Opcode.MUL: "*", Opcode.DIV: "/", Opcode.MOD: "%",
                Opcode.EQ: "==", Opcode.NE: "!=", Opcode.LT: "<", Opcode.LE: "<=",
                Opcode.GT: ">", Opcode.GE: ">=", Opcode.AND: "&&", Opcode.OR: "||"
            }
            sym = op_symbols.get(self.op, self.op.name)
            return f"{self.result} = {self.arg1} {sym} {self.arg2}"

    def to_dict(self) -> dict:
        return {
            "op": self.op.name,
            "arg1": str(self.arg1) if self.arg1 is not None else None,
            "arg2": str(self.arg2) if self.arg2 is not None else None,
            "result": self.result,
            "line": self.line,
            "phi_args": self.phi_args if self.op == Opcode.PHI else None,
            "call_args": [str(a) for a in self.call_args] if self.op == Opcode.CALL else None,
            "text": str(self),
            "annotation": self.annotation,
        }

    def uses(self) -> List[str]:
        """Return list of variable names used by this instruction."""
        used = []
        if self.op in (Opcode.READ, Opcode.PARAM):
            return used
        if self.op == Opcode.CALL:
            return [str(a) for a in self.call_args if literal_type(a) is None]
        if self.op == Opcode.PHI:
            for var in self.phi_args.values():
                if isinstance(var, str) and not var.lstrip('-').replace('.', '', 1).isdigit() and var not in ("true", "false"):
                    used.append(var)
            return used

        for arg in (self.arg1, self.arg2):
            if isinstance(arg, str):
                # Exclude string literals, numbers, boolean keywords
                if not (arg.startswith('"') and arg.endswith('"')) and \
                   not arg.lstrip('-').replace('.', '', 1).isdigit() and \
                   arg not in ("true", "false"):
                    # For JUMP / LABEL, arg1 is label target, not variable use
                    if self.op not in (Opcode.JUMP, Opcode.LABEL):
                        used.append(arg)

        # For conditional jumps, arg1 is condition variable
        if self.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE) and isinstance(self.arg1, str):
            if self.arg1 not in used:
                used.append(self.arg1)

        return used

    def defines(self) -> Optional[str]:
        """Return the variable name defined by this instruction, if any."""
        if self.op in (Opcode.LABEL, Opcode.JUMP, Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE, Opcode.RETURN, Opcode.PRINT, Opcode.NOP):
            return None
        return self.result


def canonical_form(instructions: List[Instruction],
                   block_order: Optional[List[str]] = None) -> List[Tuple]:
    """Rewrite an instruction list with variables, labels, phi predecessor
    blocks and called functions renamed v0, ... / L0, ... / B0, ... / F0, ... in order of first
    appearance, keeping literals. Blocks are numbered in `block_order` when
    it is given. Two lists are equal up to a consistent renaming exactly
    when their canonical forms are equal."""
    names: Dict[str, Dict[str, str]] = {"v": {}, "L": {}, "B": {}, "F": {}}
    for block in block_order or []:
        names["B"].setdefault(str(block), f"B{len(names['B'])}")

    def rename(space: str, name: Any) -> Optional[str]:
        if name is None:
            return None
        table = names[space]
        key = str(name)
        if key not in table:
            table[key] = f"{space}{len(table)}"
        return table[key]

    def value(operand: Any) -> Optional[str]:
        if operand is None:
            return None
        return str(operand) if literal_type(operand) else rename("v", operand)

    out: List[Tuple] = []
    for instr in instructions:
        if instr.op in (Opcode.LABEL, Opcode.JUMP):
            out.append((instr.op, rename("L", instr.arg1)))
        elif instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
            out.append((instr.op, value(instr.arg1), rename("L", instr.result)))
        elif instr.op == Opcode.CALL:
            out.append((instr.op, rename("v", instr.result), rename("F", instr.arg1),
                        tuple(value(a) for a in instr.call_args)))
        elif instr.op == Opcode.PHI:
            res = rename("v", instr.result)
            args = tuple(sorted((rename("B", p), value(v)) for p, v in instr.phi_args.items()))
            out.append((instr.op, res, args))
        else:
            out.append((instr.op, rename("v", instr.result), value(instr.arg1), value(instr.arg2)))
    return out
