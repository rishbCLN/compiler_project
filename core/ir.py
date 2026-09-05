"""
Three-Address Code (TAC) Intermediate Representation (IR) definitions.
Supports Quadruples (Op, Arg1, Arg2, Result), Labels, Jumps, and SSA Phi nodes.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Union


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
            "text": str(self),
            "annotation": self.annotation,
        }

    def uses(self) -> List[str]:
        """Return list of variable names used by this instruction."""
        used = []
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
