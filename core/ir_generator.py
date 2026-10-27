"""
AST to Three-Address Code (TAC) Intermediate Representation Generator.
Translates structured high-level AST into linear quadruples with temporary registers,
populates the Symbol Table, and registers literals into the Constant Pool.
"""

from typing import Dict, List, Optional, Any, Tuple
from core.ast_nodes import (
    ASTNode, ProgramNode, VarDeclNode, AssignNode, LiteralNode,
    VariableNode, BinaryOpNode, UnaryOpNode, BlockNode, IfNode,
    WhileNode, ForNode, PrintNode, ReturnNode, InputNode, ScanNode, CallNode,
    FunctionDefNode
)
from core.ir import Instruction, Opcode
from core.symbol_table import SymbolTable
from core.constant_pool import ConstantPool


class IRGenerator:
    """Lowers a program to TAC. The top-level statements (and the body of
    main) form the main unit returned by generate(); every other function
    definition becomes its own unit in self.functions, whose instructions
    start with one PARAM per parameter."""

    def __init__(self):
        self.instructions: List[Instruction] = []
        # name -> (parameter names, instructions), in definition order
        self.functions: Dict[str, Tuple[List[str], List[Instruction]]] = {}
        self.temp_counter = 0
        self.label_counter = 0
        self.temp_prefix = "t"
        self.symbol_table = SymbolTable()
        self.constant_pool = ConstantPool()

    def new_temp(self) -> str:
        temp_name = f"{self.temp_prefix}{self.temp_counter}"
        self.temp_counter += 1
        return temp_name

    @staticmethod
    def _collect_identifiers(node: Any, names: set):
        """Collect every variable name that appears in the AST."""
        if isinstance(node, list):
            for item in node:
                IRGenerator._collect_identifiers(item, names)
            return
        if not isinstance(node, ASTNode):
            return
        if isinstance(node, (VarDeclNode, AssignNode, VariableNode)):
            names.add(node.name)
        if isinstance(node, (ScanNode, FunctionDefNode)):
            names.update(node.names if isinstance(node, ScanNode) else node.params)
        for value in node.__dict__.values():
            if isinstance(value, (ASTNode, list)):
                IRGenerator._collect_identifiers(value, names)

    def _choose_temp_prefix(self, ast: ProgramNode) -> str:
        """Temporaries are named t0, t1, ... unless the program itself declares
        a variable of that shape (e.g. `int t1`); then the prefix is lengthened
        with underscores until no temporary can overwrite a user variable."""
        names: set = set()
        self._collect_identifiers(ast, names)
        prefix = "t"
        while any(n.startswith(prefix) and n[len(prefix):].isdigit() for n in names):
            prefix = "_" + prefix
        return prefix

    def new_label(self, prefix: str = "L") -> str:
        lbl = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return lbl

    def emit(self, op: Opcode, arg1: Any = None, arg2: Any = None, result: Optional[str] = None, line: int = 1) -> Instruction:
        instr = Instruction(op=op, arg1=arg1, arg2=arg2, result=result, line=line)
        self.instructions.append(instr)
        return instr

    def generate(self, ast: ProgramNode) -> List[Instruction]:
        self.instructions = []
        self.functions = {}
        self.temp_counter = 0
        self.label_counter = 0
        self.temp_prefix = self._choose_temp_prefix(ast)

        for stmt in ast.statements:
            self.visit(stmt)

        return self.instructions

    def visit(self, node: ASTNode) -> Optional[str]:
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode):
        raise NotImplementedError(f"No IR visitor implemented for {node.__class__.__name__}")

    def visit_ProgramNode(self, node: ProgramNode):
        for stmt in node.statements:
            self.visit(stmt)

    def visit_BlockNode(self, node: BlockNode):
        self.symbol_table.enter_scope()
        for stmt in node.statements:
            self.visit(stmt)
        self.symbol_table.exit_scope()

    def visit_VarDeclNode(self, node: VarDeclNode):
        self.symbol_table.declare_symbol(node.name, node.var_type, line=node.line)
        if node.initializer is not None:
            rhs_place = self.visit(node.initializer)
            self.emit(Opcode.ASSIGN, arg1=rhs_place, result=node.name, line=node.line)

    def visit_AssignNode(self, node: AssignNode):
        self.symbol_table.record_reference(node.name, line=node.line)
        rhs_place = self.visit(node.value)
        self.emit(Opcode.ASSIGN, arg1=rhs_place, result=node.name, line=node.line)
        return node.name

    def visit_LiteralNode(self, node: LiteralNode) -> str:
        # Register in constant pool
        pool_idx = self.constant_pool.register(node.value, node.literal_type)
        t = self.new_temp()
        # Instruction stores the literal representation
        val_str = str(node.value)
        if node.literal_type == "string":
            val_str = f'"{node.value}"'
        elif node.literal_type == "bool":
            val_str = "true" if node.value else "false"

        instr = self.emit(Opcode.LOAD_CONST, arg1=val_str, result=t, line=node.line)
        instr.annotation = f"CP#{pool_idx}"
        return t

    def visit_VariableNode(self, node: VariableNode) -> str:
        self.symbol_table.record_reference(node.name, line=node.line)
        return node.name

    def visit_BinaryOpNode(self, node: BinaryOpNode) -> str:
        left_place = self.visit(node.left)
        right_place = self.visit(node.right)
        t = self.new_temp()

        op_map = {
            "+": Opcode.ADD, "-": Opcode.SUB, "*": Opcode.MUL, "/": Opcode.DIV, "%": Opcode.MOD,
            "==": Opcode.EQ, "!=": Opcode.NE, "<": Opcode.LT, "<=": Opcode.LE,
            ">": Opcode.GT, ">=": Opcode.GE, "&&": Opcode.AND, "||": Opcode.OR
        }
        opcode = op_map.get(node.op, Opcode.ADD)
        self.emit(opcode, arg1=left_place, arg2=right_place, result=t, line=node.line)
        return t

    def visit_UnaryOpNode(self, node: UnaryOpNode) -> str:
        operand_place = self.visit(node.operand)
        t = self.new_temp()
        opcode = Opcode.NEG if node.op == "-" else Opcode.NOT
        self.emit(opcode, arg1=operand_place, result=t, line=node.line)
        return t

    def visit_IfNode(self, node: IfNode):
        cond_place = self.visit(node.condition)
        lbl_else = self.new_label("L_else_")
        lbl_end = self.new_label("L_endif_")

        if node.else_branch is not None:
            self.emit(Opcode.JUMP_IF_FALSE, arg1=cond_place, result=lbl_else, line=node.line)
            self.visit(node.then_branch)
            self.emit(Opcode.JUMP, arg1=lbl_end, line=node.line)
            self.emit(Opcode.LABEL, arg1=lbl_else, line=node.line)
            self.visit(node.else_branch)
            self.emit(Opcode.LABEL, arg1=lbl_end, line=node.line)
        else:
            self.emit(Opcode.JUMP_IF_FALSE, arg1=cond_place, result=lbl_end, line=node.line)
            self.visit(node.then_branch)
            self.emit(Opcode.LABEL, arg1=lbl_end, line=node.line)

    def visit_WhileNode(self, node: WhileNode):
        lbl_start = self.new_label("L_while_start_")
        lbl_end = self.new_label("L_while_end_")

        self.emit(Opcode.LABEL, arg1=lbl_start, line=node.line)
        cond_place = self.visit(node.condition)
        self.emit(Opcode.JUMP_IF_FALSE, arg1=cond_place, result=lbl_end, line=node.line)

        self.visit(node.body)
        self.emit(Opcode.JUMP, arg1=lbl_start, line=node.line)
        self.emit(Opcode.LABEL, arg1=lbl_end, line=node.line)

    def visit_ForNode(self, node: ForNode):
        self.symbol_table.enter_scope()

        if node.init is not None:
            self.visit(node.init)

        lbl_start = self.new_label("L_for_start_")
        lbl_end = self.new_label("L_for_end_")

        self.emit(Opcode.LABEL, arg1=lbl_start, line=node.line)

        if node.condition is not None:
            cond_place = self.visit(node.condition)
            self.emit(Opcode.JUMP_IF_FALSE, arg1=cond_place, result=lbl_end, line=node.line)

        self.visit(node.body)

        if node.update is not None:
            self.visit(node.update)

        self.emit(Opcode.JUMP, arg1=lbl_start, line=node.line)
        self.emit(Opcode.LABEL, arg1=lbl_end, line=node.line)

        self.symbol_table.exit_scope()

    def visit_PrintNode(self, node: PrintNode):
        for expr in node.expressions:
            place = self.visit(expr)
            self.emit(Opcode.PRINT, arg1=place, line=node.line)

    def visit_FunctionDefNode(self, node: FunctionDefNode):
        if node.name in self.functions or node.name == "main":
            raise ValueError(f"Function '{node.name}' is defined twice")
        outer = self.instructions
        self.instructions = []
        self.symbol_table.enter_scope()
        for index, param in enumerate(node.params):
            self.symbol_table.declare_symbol(param, "int", line=node.line)
            self.emit(Opcode.PARAM, arg1=str(index), result=param, line=node.line)
        self.visit(node.body)
        if not self.instructions or self.instructions[-1].op != Opcode.RETURN:
            self.emit(Opcode.RETURN, line=node.line)
        self.symbol_table.exit_scope()
        self.functions[node.name] = (list(node.params), self.instructions)
        self.instructions = outer

    def visit_CallNode(self, node: CallNode) -> str:
        places = [self.visit(arg) for arg in node.args]
        t = self.new_temp()
        instr = self.emit(Opcode.CALL, arg1=node.name, result=t, line=node.line)
        instr.call_args = places
        return t

    def visit_InputNode(self, node: InputNode) -> str:
        t = self.new_temp()
        self.emit(Opcode.READ, result=t, line=node.line)
        return t

    def visit_ScanNode(self, node: ScanNode):
        for name in node.names:
            self.symbol_table.record_reference(name, line=node.line)
            self.emit(Opcode.READ, result=name, line=node.line)

    def visit_ReturnNode(self, node: ReturnNode):
        place = self.visit(node.value) if node.value else None
        self.emit(Opcode.RETURN, arg1=place, line=node.line)
