"""
Reference interpreters used to check that optimization preserves behavior.

Two interpreters are written independently of the optimizer:

* run_tac(module) executes linear three-address code (labels, jumps).
* run_cfg(module) executes control-flow graphs in SSA form: the phi-functions
  of a block are evaluated together, using the edge the block was entered
  by. Blocks are visited in the order of their ids, so a fall-through goes to
  the next block of that order.

A module maps function names to code; "main" (or "F0" for a decoded CLIR
package) is the entry point. A call runs the callee in a fresh frame whose
PARAM instructions pick up the arguments; READ takes the next input value.
Both functions also accept a single instruction list or CFG.

Both follow C for integer arithmetic: / truncates toward zero and % takes the
sign of the dividend. Integers are unbounded (the generator keeps values
small). The observable behavior Obs(T) is the list of printed values followed
by the returned value.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.ir import Instruction, Opcode


class Trap(Exception):
    """Run-time error in the interpreted program (e.g. division by zero)."""


class StepLimit(Exception):
    pass


# Value of a phi argument that names a variable with no definition on that
# path (semi-pruned SSA writes x_undef). Carrying it is fine; using it traps.
UNDEF = object()


# Set by floor_semantics(): integer / and % then follow Python's floor rule
# instead of C's. Used only to classify divergences of the released folder.
_FLOOR_DIVISION = False


class floor_semantics:
    def __enter__(self):
        global _FLOOR_DIVISION
        _FLOOR_DIVISION = True

    def __exit__(self, *exc):
        global _FLOOR_DIVISION
        _FLOOR_DIVISION = False


def c_div(a: int, b: int) -> int:
    if b == 0:
        raise Trap("division by zero")
    if _FLOOR_DIVISION:
        return a // b
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def literal(text: str) -> Tuple[bool, Any]:
    """(True, value) if text is a literal, else (False, None)."""
    if text == "true":
        return True, True
    if text == "false":
        return True, False
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return True, text[1:-1]
    try:
        return True, int(text)
    except ValueError:
        pass
    try:
        if any(ch.isdigit() for ch in text) and not text[0].isalpha() and text[0] != "_":
            return True, float(text)
    except ValueError:
        pass
    return False, None


def binary(op: Opcode, a: Any, b: Any) -> Any:
    ints = isinstance(a, int) and isinstance(b, int)
    if op == Opcode.ADD:
        return a + b
    if op == Opcode.SUB:
        return a - b
    if op == Opcode.MUL:
        return a * b
    if op == Opcode.DIV:
        if ints:
            return c_div(a, b)
        if b == 0:
            raise Trap("division by zero")
        return a / b
    if op == Opcode.MOD:
        if ints:
            return a - b * c_div(a, b)
        raise Trap("% on non-integers")
    if op == Opcode.EQ:
        return a == b
    if op == Opcode.NE:
        return a != b
    if op == Opcode.LT:
        return a < b
    if op == Opcode.LE:
        return a <= b
    if op == Opcode.GT:
        return a > b
    if op == Opcode.GE:
        return a >= b
    if op == Opcode.AND:
        return bool(a) and bool(b)
    if op == Opcode.OR:
        return bool(a) or bool(b)
    raise Trap(f"unknown binary op {op}")


def normalize(value: Any) -> Any:
    """Booleans print as 0/1 so that a folded `true` equals a computed 1 == 1."""
    if isinstance(value, bool):
        return int(value)
    return value


class _State:
    """Shared by all frames of one run: output, remaining input, step budget."""

    def __init__(self, inputs: Sequence[int], max_steps: int, max_depth: int = 200):
        self.out: List[Any] = []
        self.inputs = list(inputs)
        self.steps = 0
        self.max_steps = max_steps
        self.depth = 0
        self.max_depth = max_depth

    def tick(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimit()


class _Frame:
    def __init__(self, state: _State, args: Sequence[Any], call):
        self.state = state
        self.env: Dict[str, Any] = {}
        self.args = list(args)
        self.call = call   # call(name, args) -> return value

    def get(self, operand: Any) -> Any:
        text = str(operand)
        is_lit, value = literal(text)
        if is_lit:
            return value
        value = self.env.get(text, UNDEF)
        if value is UNDEF:
            raise Trap(f"read of undefined variable {text}")
        return value

    def get_lazy(self, operand: Any) -> Any:
        """Like get, but an undefined variable yields UNDEF (for phis)."""
        text = str(operand)
        is_lit, value = literal(text)
        return value if is_lit else self.env.get(text, UNDEF)

    def execute(self, instr: Instruction) -> None:
        """Execute a straight-line instruction (not a jump, label, phi or return)."""
        op = instr.op
        if op == Opcode.ASSIGN:
            # A copy may move an undefined value (e.g. after trivial-phi
            # removal); only a real use of it is an error.
            self.env[instr.result] = self.get_lazy(instr.arg1)
        elif op == Opcode.LOAD_CONST:
            self.env[instr.result] = self.get(instr.arg1)
        elif op == Opcode.NEG:
            self.env[instr.result] = -self.get(instr.arg1)
        elif op == Opcode.NOT:
            self.env[instr.result] = not self.get(instr.arg1)
        elif op == Opcode.PRINT:
            self.state.out.append(normalize(self.get(instr.arg1)))
        elif op == Opcode.NOP:
            pass
        elif op == Opcode.READ:
            if not self.state.inputs:
                raise Trap("input exhausted")
            self.env[instr.result] = self.state.inputs.pop(0)
        elif op == Opcode.PARAM:
            index = int(instr.arg1)
            if index >= len(self.args):
                raise Trap(f"missing argument {index}")
            self.env[instr.result] = self.args[index]
        elif op == Opcode.CALL:
            args = [self.get(a) for a in instr.call_args]
            self.env[instr.result] = self.call(str(instr.arg1), args)
        else:
            self.env[instr.result] = binary(op, self.get(instr.arg1), self.get(instr.arg2))


def _entry(module: Dict[str, Any]) -> str:
    return "main" if "main" in module else "F0"


def _ret_value(frame: _Frame, instr: Instruction) -> Any:
    return normalize(frame.get(instr.arg1)) if instr.arg1 is not None else None


def run_tac(module, inputs: Sequence[int] = (), max_steps: int = 2_000_000) -> List[Any]:
    """Execute linear TAC; returns printed values plus ('ret', value).
    module: {name: (params, instructions)} or one instruction list."""
    if isinstance(module, list):
        module = {"main": ([], module)}
    state = _State(inputs, max_steps)
    labels = {name: {str(i.arg1): idx for idx, i in enumerate(code) if i.op == Opcode.LABEL}
              for name, (_, code) in module.items()}

    def call(name: str, args: Sequence[Any]) -> Any:
        if name not in module:
            raise Trap(f"call of undefined function {name}")
        state.depth += 1
        if state.depth > state.max_depth:
            raise Trap("call depth exceeded")
        code = module[name][1]
        frame = _Frame(state, args, call)
        pc = 0
        try:
            while pc < len(code):
                state.tick()
                instr = code[pc]
                op = instr.op
                if op == Opcode.LABEL:
                    pc += 1
                elif op == Opcode.JUMP:
                    pc = labels[name][str(instr.arg1)]
                elif op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                    cond = bool(frame.get(instr.arg1))
                    jump = cond if op == Opcode.JUMP_IF_TRUE else not cond
                    pc = labels[name][str(instr.result)] if jump else pc + 1
                elif op == Opcode.RETURN:
                    return _ret_value(frame, instr)
                elif op == Opcode.PHI:
                    raise Trap("phi in linear TAC")
                else:
                    frame.execute(instr)
                    pc += 1
            return None
        finally:
            state.depth -= 1

    ret = call(_entry(module), [])
    return state.out + [("ret", ret)]


def _block_key(b_id: str):
    digits = "".join(ch for ch in b_id if ch.isdigit())
    return (int(digits) if digits else 0, b_id)


def run_cfg(module, inputs: Sequence[int] = (), max_steps: int = 2_000_000) -> List[Any]:
    """Execute CFGs (SSA or not); returns printed values plus ('ret', value).
    module: {name: cfg} or one cfg."""
    if not isinstance(module, dict):
        module = {"main": module}
    state = _State(inputs, max_steps)
    layout = {}
    for name, cfg in module.items():
        order = sorted(cfg.blocks, key=_block_key)
        next_block = {b: (order[i + 1] if i + 1 < len(order) else None) for i, b in enumerate(order)}
        label_block: Dict[str, str] = {}
        for b_id in order:
            for instr in cfg.blocks[b_id].instructions:
                if instr.op == Opcode.LABEL:
                    label_block[str(instr.arg1)] = b_id
        layout[name] = (next_block, label_block)

    def call(name: str, args: Sequence[Any]) -> Any:
        if name not in module:
            raise Trap(f"call of undefined function {name}")
        state.depth += 1
        if state.depth > state.max_depth:
            raise Trap("call depth exceeded")
        cfg = module[name]
        next_block, label_block = layout[name]
        frame = _Frame(state, args, call)
        prev: Optional[str] = None
        cur: Optional[str] = cfg.entry_block_id if cfg.blocks else None
        try:
            while cur is not None:
                instrs = cfg.blocks[cur].instructions
                # Phi-functions read their arguments before any of them is written.
                phis = [i for i in instrs if i.op == Opcode.PHI]
                if phis:
                    if prev is None:
                        raise Trap(f"phi in entry block {cur}")
                    values = {}
                    for phi in phis:
                        if prev not in phi.phi_args:
                            raise Trap(f"phi {phi.result} has no argument for edge {prev}->{cur}")
                        values[phi.result] = frame.get_lazy(phi.phi_args[prev])
                    frame.env.update(values)
                target: Optional[str] = next_block[cur]
                for instr in instrs:
                    state.tick()
                    op = instr.op
                    if op in (Opcode.PHI, Opcode.LABEL):
                        continue
                    if op == Opcode.JUMP:
                        target = label_block[str(instr.arg1)]
                        break
                    if op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                        cond = bool(frame.get(instr.arg1))
                        jump = cond if op == Opcode.JUMP_IF_TRUE else not cond
                        target = label_block[str(instr.result)] if jump else next_block[cur]
                        break
                    if op == Opcode.RETURN:
                        return _ret_value(frame, instr)
                    frame.execute(instr)
                prev, cur = cur, target
            return None
        finally:
            state.depth -= 1

    ret = call(_entry(module), [])
    return state.out + [("ret", ret)]


def observe(runner, *args, **kwargs) -> Tuple[str, Any]:
    """Run and classify: ('ok', output) or ('trap', message) or ('limit', None)."""
    try:
        return "ok", runner(*args, **kwargs)
    except Trap as exc:
        return "trap", str(exc)
    except StepLimit:
        return "limit", None
