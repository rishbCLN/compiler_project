"""
Multi-Pass IR Optimizer for Intermediate Representation Compression.
Performs:
1. Constant Folding & Sparse Constant Propagation
2. Sparse Conditional Constant Propagation (SCCP, Wegman-Zadeck)
3. Copy Propagation
4. Global Value Numbering (GVN) / Common Subexpression Elimination (CSE)
5. Dead Code Elimination (DCE)
6. Control Flow Graph Block Merging and Jump Threading
7. Trivial Phi Elimination
"""

import math
from typing import Dict, Set, List, Optional, Any, Tuple
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph, BasicBlock


class IROptimizer:
    # Pass names, in the order a round runs them. Any subset can be enabled;
    # the evaluation disables one pass at a time to measure its effect.
    ALL_PASSES = ("fold", "sccp", "copy_prop", "gvn", "dce", "cfg", "trivial_phi")
    # The five passes of the first release, before SCCP and copy propagation.
    BASE_PASSES = ("fold", "gvn", "dce", "cfg", "trivial_phi")

    def __init__(self, cfg: ControlFlowGraph, passes: Optional[Tuple[str, ...]] = None,
                 max_iterations: int = 10):
        self.cfg = cfg
        self.passes = tuple(self.ALL_PASSES if passes is None else passes)
        unknown = set(self.passes) - set(self.ALL_PASSES)
        if unknown:
            raise ValueError(f"Unknown optimizer passes: {sorted(unknown)}")
        self.max_iterations = max_iterations
        self.stats = {
            "constant_folds": 0,
            "constant_propagations": 0,
            "sccp_constants": 0,
            "sccp_branches_resolved": 0,
            "copies_propagated": 0,
            "gvn_eliminations": 0,
            "dead_instructions_removed": 0,
            "dead_blocks_removed": 0,
            "initial_instructions": 0,
            "final_instructions": 0,
            "rounds": 0,
            "compression_ratio": 0.0,
        }

    def _fingerprint(self) -> Tuple:
        return tuple((b_id, tuple(str(i) for i in bb.instructions))
                     for b_id, bb in sorted(self.cfg.blocks.items()))

    def is_ssa(self) -> bool:
        """True if every variable is defined at most once. Copy propagation and
        SCCP rely on this and are skipped for code that is not in SSA form."""
        seen: Set[str] = set()
        for bb in self.cfg.blocks.values():
            for instr in bb.instructions:
                d = instr.defines()
                if d is not None:
                    if d in seen:
                        return False
                    seen.add(d)
        return True

    def optimize(self) -> ControlFlowGraph:
        """Runs the enabled passes in rounds until a round leaves the program
        unchanged (a fixed point) or max_iterations rounds have run."""
        self.stats["initial_instructions"] = sum(len(b.instructions) for b in self.cfg.blocks.values())
        ssa = self.is_ssa()

        steps = [
            ("fold", self.pass_constant_folding_and_propagation),
            ("sccp", self.pass_sccp),
            ("copy_prop", self.pass_copy_propagation),
            ("gvn", self.pass_gvn),
            ("dce", self.pass_dead_code_elimination),
            ("cfg", self.pass_cfg_simplification),
            # Phis with a single distinct incoming value become plain copies.
            ("trivial_phi", self.pass_trivial_phi_elimination),
        ]
        for _ in range(self.max_iterations):
            before = self._fingerprint()
            self.stats["rounds"] += 1
            for name, run in steps:
                if name not in self.passes:
                    continue
                if name in ("sccp", "copy_prop") and not ssa:
                    continue
                run()
            if self._fingerprint() == before:
                break

        self.stats["final_instructions"] = sum(len(b.instructions) for b in self.cfg.blocks.values())
        init_cnt = self.stats["initial_instructions"]
        final_cnt = self.stats["final_instructions"]
        if init_cnt > 0:
            self.stats["compression_ratio"] = round((init_cnt - final_cnt) / init_cnt * 100, 2)

        return self.cfg

    # ---------------- Pass 1: Constant Folding & Propagation ----------------

    def _parse_constant(self, val: Any) -> Optional[Tuple[Any, str]]:
        """Return (value, type) if val is a constant literal, else None."""
        if val is None:
            return None
        val_str = str(val)
        if val_str == "true":
            return True, "bool"
        elif val_str == "false":
            return False, "bool"
        elif val_str.startswith('"') and val_str.endswith('"'):
            return val_str[1:-1], "string"
        try:
            if '.' in val_str:
                return float(val_str), "float"
            return int(val_str), "int"
        except ValueError:
            return None

    @staticmethod
    def _c_int_div(a: int, b: int) -> int:
        """Integer division with C semantics (truncation toward zero).
        Python's // floors, which differs for operands of opposite sign:
        -7 // 2 == -4 in Python but -7 / 2 == -3 in C. The C remainder
        a % b is then a - b * (a / b), so it takes the sign of the dividend."""
        if b == 0:
            raise ZeroDivisionError
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b >= 0) else -q

    def _eval_binary(self, op: Opcode, v1: Any, v2: Any) -> Optional[Any]:
        try:
            if op == Opcode.ADD:
                return v1 + v2
            elif op == Opcode.SUB:
                return v1 - v2
            elif op == Opcode.MUL:
                return v1 * v2
            elif op == Opcode.DIV:
                if isinstance(v1, int) and isinstance(v2, int):
                    return self._c_int_div(v1, v2)
                return v1 / v2
            elif op == Opcode.MOD:
                if isinstance(v1, int) and isinstance(v2, int):
                    return v1 - v2 * self._c_int_div(v1, v2)
                return math.fmod(v1, v2)
            elif op == Opcode.EQ:
                return v1 == v2
            elif op == Opcode.NE:
                return v1 != v2
            elif op == Opcode.LT:
                return v1 < v2
            elif op == Opcode.LE:
                return v1 <= v2
            elif op == Opcode.GT:
                return v1 > v2
            elif op == Opcode.GE:
                return v1 >= v2
            elif op == Opcode.AND:
                return bool(v1 and v2)
            elif op == Opcode.OR:
                return bool(v1 or v2)
        except ZeroDivisionError:
            return None
        return None

    def pass_constant_folding_and_propagation(self):
        # Known constant values: var_name -> literal_value_str
        known_constants: Dict[str, str] = {}

        for bb in self.cfg.blocks.values():
            new_instructions: List[Instruction] = []

            for instr in bb.instructions:
                # 1. Propagate known constants into instruction arguments
                if instr.arg1 is not None and str(instr.arg1) in known_constants:
                    instr.arg1 = known_constants[str(instr.arg1)]
                    self.stats["constant_propagations"] += 1

                if instr.arg2 is not None and str(instr.arg2) in known_constants:
                    instr.arg2 = known_constants[str(instr.arg2)]
                    self.stats["constant_propagations"] += 1

                # 2. Check if this is a constant assignment or load
                if instr.op in (Opcode.LOAD_CONST, Opcode.ASSIGN):
                    parsed = self._parse_constant(instr.arg1)
                    if parsed is not None and instr.result:
                        known_constants[instr.result] = str(instr.arg1)
                    new_instructions.append(instr)
                    continue

                # 3. Check for Constant Folding in binary operations
                c1 = self._parse_constant(instr.arg1)
                c2 = self._parse_constant(instr.arg2)

                if c1 is not None and c2 is not None and instr.result:
                    evaluated = self._eval_binary(instr.op, c1[0], c2[0])
                    if evaluated is not None:
                        # Convert bool to lowercase string
                        if isinstance(evaluated, bool):
                            eval_str = "true" if evaluated else "false"
                        else:
                            eval_str = str(evaluated)

                        # Replace binary instruction with LOAD_CONST
                        folded = Instruction(
                            op=Opcode.LOAD_CONST,
                            arg1=eval_str,
                            result=instr.result,
                            line=instr.line,
                            annotation="folded",
                        )
                        known_constants[instr.result] = eval_str
                        new_instructions.append(folded)
                        self.stats["constant_folds"] += 1
                        continue

                # 4. Check for Algebraic Identities:
                # x + 0 = x, x * 1 = x, x * 0 = 0, x - 0 = x
                if instr.op == Opcode.ADD:
                    if str(instr.arg2) == "0":
                        new_instructions.append(Instruction(op=Opcode.ASSIGN, arg1=instr.arg1, result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue
                    elif str(instr.arg1) == "0":
                        new_instructions.append(Instruction(op=Opcode.ASSIGN, arg1=instr.arg2, result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue
                elif instr.op == Opcode.MUL:
                    if str(instr.arg2) == "1":
                        new_instructions.append(Instruction(op=Opcode.ASSIGN, arg1=instr.arg1, result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue
                    elif str(instr.arg1) == "1":
                        new_instructions.append(Instruction(op=Opcode.ASSIGN, arg1=instr.arg2, result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue
                    elif str(instr.arg2) == "0" or str(instr.arg1) == "0":
                        new_instructions.append(Instruction(op=Opcode.LOAD_CONST, arg1="0", result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue
                elif instr.op == Opcode.SUB:
                    if str(instr.arg2) == "0":
                        new_instructions.append(Instruction(op=Opcode.ASSIGN, arg1=instr.arg1, result=instr.result, line=instr.line))
                        self.stats["constant_folds"] += 1
                        continue

                # 5. Constant condition folding for branches
                if instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                    cond_val = self._parse_constant(instr.arg1)
                    if cond_val is not None:
                        truthy = bool(cond_val[0])
                        should_jump = truthy if instr.op == Opcode.JUMP_IF_TRUE else (not truthy)
                        # Resolve the branch-target block and the fallthrough block
                        target_lbl = str(instr.result)
                        target_bb_id = self.cfg.label_to_block.get(target_lbl)
                        if should_jump:
                            # Branch always taken: turn into unconditional jump,
                            # sever every successor edge except the taken target.
                            new_instructions.append(Instruction(op=Opcode.JUMP, arg1=instr.result, line=instr.line))
                            for succ_id in list(bb.successors):
                                if succ_id != target_bb_id:
                                    self._sever_edge(bb.id, succ_id)
                        else:
                            # Branch never taken: fall through, sever the target edge only.
                            if target_bb_id is not None:
                                self._sever_edge(bb.id, target_bb_id)
                        self.stats["constant_folds"] += 1
                        continue

                new_instructions.append(instr)

            bb.instructions = new_instructions

    def _sever_edge(self, src_id: str, dst_id: str):
        """Remove a CFG edge (src -> dst) and clean up any phi incoming args
        in the destination block that referenced the now-dead predecessor."""
        src_bb = self.cfg.blocks.get(src_id)
        dst_bb = self.cfg.blocks.get(dst_id)
        if src_bb is not None:
            src_bb.successors.discard(dst_id)
        if dst_bb is not None:
            dst_bb.predecessors.discard(src_id)
            # Drop phi arguments flowing from the severed predecessor
            for instr in dst_bb.instructions:
                if instr.op == Opcode.PHI and instr.phi_args and src_id in instr.phi_args:
                    del instr.phi_args[src_id]
        self.cfg.edge_types.pop((src_id, dst_id), None)

    # ---------------- Sparse Conditional Constant Propagation ----------------

    @staticmethod
    def _format_constant(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _eval_unary(self, op: Opcode, v: Any) -> Optional[Any]:
        if op == Opcode.NEG and isinstance(v, (int, float)) and not isinstance(v, bool):
            return -v
        if op == Opcode.NOT:
            return not v
        return None

    def _block_out_edges(self, bb: BasicBlock, cond_value) -> List[str]:
        """Successors reached from bb given the lattice value of its branch
        condition (None if bb does not end in a conditional jump)."""
        last = bb.instructions[-1] if bb.instructions else None
        if last is None or last.op not in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
            return list(bb.successors)
        if cond_value is self._TOP:
            return []
        if cond_value is self._BOTTOM:
            return list(bb.successors)
        target = self.cfg.label_to_block.get(str(last.result))
        others = [s for s in bb.successors if s != target]
        truthy = bool(cond_value[1])
        taken = truthy if last.op == Opcode.JUMP_IF_TRUE else not truthy
        if taken:
            return [target] if target in bb.successors else []
        # A branch to the very next block has that block as its only successor.
        return others if others else ([target] if target in bb.successors else [])

    _TOP = object()
    _BOTTOM = object()

    def pass_sccp(self):
        """Wegman-Zadeck sparse conditional constant propagation. Values are
        propagated through phi-functions, and only along CFG edges that can
        execute, so a constant branch also makes the code behind it
        unreachable. Constant definitions become literal loads, constant
        uses become literals, constant branches become jumps or fall-throughs,
        and edges that can never execute are removed."""
        TOP, BOTTOM = self._TOP, self._BOTTOM
        cfg = self.cfg
        if cfg.entry_block_id not in cfg.blocks:
            return

        defs: Dict[str, Tuple[str, Instruction]] = {}
        users: Dict[str, List[Tuple[str, Instruction]]] = {}
        for bb in cfg.blocks.values():
            for instr in bb.instructions:
                d = instr.defines()
                if d is not None:
                    defs[d] = (bb.id, instr)
                for u in instr.uses():
                    users.setdefault(u, []).append((bb.id, instr))

        lattice: Dict[str, Any] = {}

        def value_of(operand: Any):
            if operand is None:
                return BOTTOM
            c = self._parse_constant(operand)
            if c is not None:
                return ("c", c[0])
            name = str(operand)
            if name not in defs:
                return BOTTOM  # e.g. x_undef: unknown at compile time
            return lattice.get(name, TOP)

        def same(a, b) -> bool:
            return type(a[1]) is type(b[1]) and a[1] == b[1]

        def meet(a, b):
            if a is TOP:
                return b
            if b is TOP:
                return a
            if a is BOTTOM or b is BOTTOM:
                return BOTTOM
            return a if same(a, b) else BOTTOM

        def evaluate(b_id: str, instr: Instruction):
            if instr.op == Opcode.PHI:
                result = TOP
                for pred, arg in instr.phi_args.items():
                    if (pred, b_id) in executable:
                        result = meet(result, value_of(arg))
                return result
            if instr.op in (Opcode.LOAD_CONST, Opcode.ASSIGN):
                return value_of(instr.arg1)
            if instr.op in (Opcode.NEG, Opcode.NOT):
                v = value_of(instr.arg1)
                if v is TOP or v is BOTTOM:
                    return v
                r = self._eval_unary(instr.op, v[1])
                return BOTTOM if r is None else ("c", r)
            if instr.op in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD,
                            Opcode.EQ, Opcode.NE, Opcode.LT, Opcode.LE, Opcode.GT, Opcode.GE,
                            Opcode.AND, Opcode.OR):
                v1, v2 = value_of(instr.arg1), value_of(instr.arg2)
                if v1 is BOTTOM or v2 is BOTTOM:
                    return BOTTOM
                if v1 is TOP or v2 is TOP:
                    return TOP
                try:
                    r = self._eval_binary(instr.op, v1[1], v2[1])
                except TypeError:
                    r = None
                return BOTTOM if r is None else ("c", r)
            return BOTTOM  # any other definition is unknown at compile time

        executable: Set[Tuple[Optional[str], str]] = set()
        visited: Set[str] = set()
        flow: List[Tuple[Optional[str], str]] = [(None, cfg.entry_block_id)]
        ssa_work: List[str] = []

        def cond_value(bb: BasicBlock):
            last = bb.instructions[-1] if bb.instructions else None
            if last is not None and last.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                return value_of(last.arg1)
            return None

        def equal(a, b) -> bool:
            return a is b or (isinstance(a, tuple) and isinstance(b, tuple) and same(a, b))

        def visit(b_id: str, instr: Instruction):
            d = instr.defines()
            if d is not None:
                old = lattice.get(d, TOP)
                new = meet(old, evaluate(b_id, instr))  # values only move down
                if not equal(new, old):
                    lattice[d] = new
                    ssa_work.append(d)
            bb = cfg.blocks[b_id]
            if bb.instructions and instr is bb.instructions[-1]:
                for succ in self._block_out_edges(bb, cond_value(bb)):
                    flow.append((b_id, succ))

        while flow or ssa_work:
            if flow:
                edge = flow.pop()
                if edge in executable:
                    continue
                executable.add(edge)
                b_id = edge[1]
                bb = cfg.blocks.get(b_id)
                if bb is None:
                    continue
                for instr in bb.instructions:
                    if instr.op == Opcode.PHI:
                        visit(b_id, instr)
                if b_id not in visited:
                    visited.add(b_id)
                    for instr in bb.instructions:
                        if instr.op != Opcode.PHI:
                            visit(b_id, instr)
                    if not bb.instructions:
                        for succ in bb.successors:
                            flow.append((b_id, succ))
            else:
                name = ssa_work.pop()
                for b_id, instr in users.get(name, []):
                    if b_id in visited:
                        visit(b_id, instr)

        def constant_of(name: str):
            v = lattice.get(name)
            return v if isinstance(v, tuple) else None

        # In strict SSA form every branch condition of a reachable block has a
        # value by now. If one is still undetermined, keep the program as is.
        if any(cond_value(cfg.blocks[b]) is TOP for b in visited):
            return

        # Rewrite the program with the solution.
        for b_id in visited:
            bb = cfg.blocks[b_id]
            new_instructions: List[Instruction] = []
            for idx, instr in enumerate(bb.instructions):
                is_last = idx == len(bb.instructions) - 1
                if is_last and instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                    c = value_of(instr.arg1)
                    if isinstance(c, tuple):
                        truthy = bool(c[1])
                        taken = truthy if instr.op == Opcode.JUMP_IF_TRUE else not truthy
                        self.stats["sccp_branches_resolved"] += 1
                        if taken:
                            new_instructions.append(Instruction(op=Opcode.JUMP, arg1=instr.result,
                                                                line=instr.line, annotation="sccp"))
                        continue
                d = instr.defines()
                c = constant_of(d) if d is not None else None
                if c is not None and instr.op != Opcode.LOAD_CONST:
                    new_instructions.append(Instruction(op=Opcode.LOAD_CONST, arg1=self._format_constant(c[1]),
                                                        result=d, line=instr.line, annotation="sccp"))
                    self.stats["sccp_constants"] += 1
                    continue
                if instr.op == Opcode.PHI:
                    for pred, arg in list(instr.phi_args.items()):
                        ca = constant_of(str(arg))
                        if ca is not None:
                            instr.phi_args[pred] = self._format_constant(ca[1])
                            self.stats["sccp_constants"] += 1
                elif instr.op not in (Opcode.LABEL, Opcode.JUMP):
                    for field in ("arg1", "arg2"):
                        operand = getattr(instr, field)
                        if operand is None:
                            continue
                        ca = constant_of(str(operand)) if self._parse_constant(operand) is None else None
                        if ca is not None:
                            setattr(instr, field, self._format_constant(ca[1]))
                            self.stats["sccp_constants"] += 1
                new_instructions.append(instr)
            bb.instructions = new_instructions

        # Remove every CFG edge that can never execute.
        for src_id, src in list(cfg.blocks.items()):
            for dst_id in list(src.successors):
                if (src_id, dst_id) not in executable:
                    self._sever_edge(src_id, dst_id)

    # ---------------- Copy Propagation ----------------

    def pass_copy_propagation(self):
        """Replace every use of x, where x = y is a copy, by y (following
        chains of copies). In SSA form the definition of y dominates the copy
        and therefore every use of x, so the replacement is safe; the copy
        itself is then dead and removed by DCE. Value numbering produces such
        copies when it finds a redundant expression."""
        copies: Dict[str, str] = {}
        for bb in self.cfg.blocks.values():
            for instr in bb.instructions:
                if instr.op == Opcode.ASSIGN and instr.result and instr.arg1 is not None \
                        and str(instr.arg1) != instr.result:
                    copies[instr.result] = str(instr.arg1)

        def resolve(name: str) -> str:
            seen: Set[str] = set()
            while name in copies and name not in seen:
                seen.add(name)
                name = copies[name]
            return name

        for bb in self.cfg.blocks.values():
            for instr in bb.instructions:
                if instr.op == Opcode.PHI:
                    for pred, arg in list(instr.phi_args.items()):
                        if str(arg) in copies:
                            instr.phi_args[pred] = resolve(str(arg))
                            self.stats["copies_propagated"] += 1
                elif instr.op not in (Opcode.LABEL, Opcode.JUMP):
                    for field in ("arg1", "arg2"):
                        operand = getattr(instr, field)
                        if operand is not None and str(operand) in copies:
                            setattr(instr, field, resolve(str(operand)))
                            self.stats["copies_propagated"] += 1

    # ---------------- Pass 2: Global Value Numbering (GVN) ----------------

    def pass_gvn(self):
        """
        Dominator-based Value Numbering (DVNT).
        Maps (Opcode, Arg1, Arg2) -> primary_var_name, but an expression may
        only be reused in a block that is DOMINATED by the block defining it.
        This prevents illegally sharing values computed on disjoint branches.
        """
        from core.dominator import DominanceAnalyzer

        # Recompute dominance over the (possibly edge-mutated) CFG.
        dom = DominanceAnalyzer(self.cfg)
        dom.compute_all()

        expr_table: Dict[Tuple[str, str, str], str] = {}

        def visit(b_id: str):
            bb = self.cfg.blocks.get(b_id)
            if bb is None:
                return
            # Record keys inserted at this dom-tree level for backtracking.
            inserted_keys: List[Tuple[str, str, str]] = []
            new_instructions: List[Instruction] = []

            for instr in bb.instructions:
                if instr.op in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD,
                                Opcode.EQ, Opcode.NE, Opcode.LT, Opcode.LE, Opcode.GT, Opcode.GE,
                                Opcode.AND, Opcode.OR):
                    a1 = str(instr.arg1)
                    a2 = str(instr.arg2)
                    if instr.op in (Opcode.ADD, Opcode.MUL, Opcode.EQ, Opcode.NE):
                        if a1 > a2:
                            a1, a2 = a2, a1

                    key = (instr.op.name, a1, a2)

                    if key in expr_table and instr.result:
                        existing_var = expr_table[key]
                        assigned = Instruction(
                            op=Opcode.ASSIGN,
                            arg1=existing_var,
                            result=instr.result,
                            line=instr.line,
                            annotation="gvn_eliminated"
                        )
                        new_instructions.append(assigned)
                        self.stats["gvn_eliminations"] += 1
                        continue
                    elif instr.result:
                        expr_table[key] = instr.result
                        inserted_keys.append(key)

                new_instructions.append(instr)

            bb.instructions = new_instructions

            # Recurse into blocks this block immediately dominates.
            for child_id in dom.dom_tree.get(b_id, []):
                visit(child_id)

            # Backtrack: expressions defined here are not valid for siblings.
            for key in inserted_keys:
                expr_table.pop(key, None)

        visit(self.cfg.entry_block_id)

    # ---------------- Pass 3: Dead Code Elimination (DCE) ----------------

    def pass_dead_code_elimination(self):
        """
        Removes definitions that are never used anywhere in the CFG,
        as long as the instruction produces no side effects (like PRINT, RETURN, JUMP).
        """
        changed = True
        while changed:
            changed = False

            # Collect all variable uses across all blocks.
            # Cycle-aware: a PHI's reference to its own result does not keep it
            # alive, so loop-carried phi cycles with no external use are dead.
            all_uses: Set[str] = set()
            for bb in self.cfg.blocks.values():
                for instr in bb.instructions:
                    for u in instr.uses():
                        if instr.op == Opcode.PHI and u == instr.result:
                            continue
                        all_uses.add(u)

            # Eliminate unused definitions
            for bb in self.cfg.blocks.values():
                filtered_instructions: List[Instruction] = []

                for instr in bb.instructions:
                    defn = instr.defines()

                    # Instructions with side effects must be preserved
                    if instr.op in (Opcode.PRINT, Opcode.RETURN, Opcode.JUMP,
                                    Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE, Opcode.LABEL):
                        filtered_instructions.append(instr)
                        continue

                    if defn is not None and defn not in all_uses:
                        # Dead definition!
                        self.stats["dead_instructions_removed"] += 1
                        changed = True
                    else:
                        filtered_instructions.append(instr)

                bb.instructions = filtered_instructions

    # ---------------- Pass 4: CFG Simplification ----------------

    def pass_cfg_simplification(self):
        """Prunes unreachable blocks and reconstructs edges."""
        pruned = self.cfg.prune_unreachable_blocks()
        if pruned > 0:
            self.stats["dead_blocks_removed"] += pruned
        # After pruning, drop phi incoming args whose predecessor block no
        # longer exists / is no longer a predecessor of the owning block.
        for bb in self.cfg.blocks.values():
            for instr in bb.instructions:
                if instr.op == Opcode.PHI and instr.phi_args:
                    stale = [p for p in instr.phi_args
                             if p not in self.cfg.blocks or p not in bb.predecessors]
                    for p in stale:
                        del instr.phi_args[p]

    # ---------------- Pass 5: Trivial Phi Elimination ----------------

    def pass_trivial_phi_elimination(self):
        """Replace phi nodes that have a single distinct incoming value (after
        ignoring self-references) with a direct ASSIGN. Trivial phis commonly
        appear once dead predecessor edges have been pruned."""
        for bb in self.cfg.blocks.values():
            new_instructions: List[Instruction] = []
            for instr in bb.instructions:
                if instr.op == Opcode.PHI:
                    distinct = {v for v in instr.phi_args.values() if v != instr.result}
                    if len(distinct) == 1:
                        src = next(iter(distinct))
                        new_instructions.append(Instruction(
                            op=Opcode.ASSIGN,
                            arg1=src,
                            result=instr.result,
                            line=instr.line,
                            annotation="trivial_phi",
                        ))
                        continue
                    elif len(distinct) == 0:
                        # Phi carries no real value; drop it.
                        continue
                new_instructions.append(instr)
            bb.instructions = new_instructions
