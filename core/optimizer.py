"""
Multi-Pass IR Optimizer for Intermediate Representation Compression.
Performs:
1. Constant Folding & Sparse Constant Propagation
2. Global Value Numbering (GVN) / Common Subexpression Elimination (CSE)
3. Dead Code Elimination (DCE)
4. Control Flow Graph Block Merging and Jump Threading
"""

from typing import Dict, Set, List, Optional, Any, Tuple
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph, BasicBlock


class IROptimizer:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        self.stats = {
            "constant_folds": 0,
            "constant_propagations": 0,
            "gvn_eliminations": 0,
            "dead_instructions_removed": 0,
            "dead_blocks_removed": 0,
            "initial_instructions": 0,
            "final_instructions": 0,
            "compression_ratio": 0.0,
        }

    def optimize(self) -> ControlFlowGraph:
        """Runs iterative optimization passes until fixed point."""
        self.stats["initial_instructions"] = sum(len(b.instructions) for b in self.cfg.blocks.values())

        max_iterations = 10
        for _ in range(max_iterations):
            prev_instr_count = sum(len(b.instructions) for b in self.cfg.blocks.values())

            # Pass 1: Constant Folding & Propagation
            self.pass_constant_folding_and_propagation()

            # Pass 2: Global Value Numbering (GVN)
            self.pass_gvn()

            # Pass 3: Dead Code Elimination (DCE)
            self.pass_dead_code_elimination()

            # Pass 4: CFG Simplification (prune dead blocks & merge)
            self.pass_cfg_simplification()

            curr_instr_count = sum(len(b.instructions) for b in self.cfg.blocks.values())
            if curr_instr_count == prev_instr_count:
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

    def _eval_binary(self, op: Opcode, v1: Any, v2: Any) -> Optional[Any]:
        try:
            if op == Opcode.ADD:
                return v1 + v2
            elif op == Opcode.SUB:
                return v1 - v2
            elif op == Opcode.MUL:
                return v1 * v2
            elif op == Opcode.DIV:
                return v1 // v2 if isinstance(v1, int) and isinstance(v2, int) else v1 / v2
            elif op == Opcode.MOD:
                return v1 % v2
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
                        if should_jump:
                            # Turn into unconditional jump
                            new_instructions.append(Instruction(op=Opcode.JUMP, arg1=instr.result, line=instr.line))
                        else:
                            # Branch never taken, remove jump (fall through)
                            pass
                        self.stats["constant_folds"] += 1
                        continue

                new_instructions.append(instr)

            bb.instructions = new_instructions

    # ---------------- Pass 2: Global Value Numbering (GVN) ----------------

    def pass_gvn(self):
        """
        Global Value Numbering across basic blocks:
        Maps (Opcode, Arg1, Arg2) -> primary_var_name.
        If identical operation was previously computed, replace with COPY/ASSIGN.
        """
        expr_table: Dict[Tuple[str, str, str], str] = {}

        for bb in self.cfg.blocks.values():
            new_instructions: List[Instruction] = []

            for instr in bb.instructions:
                if instr.op in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD,
                                Opcode.EQ, Opcode.NE, Opcode.LT, Opcode.LE, Opcode.GT, Opcode.GE,
                                Opcode.AND, Opcode.OR):
                    # Commutative canonicalization (ADD, MUL, EQ, NE)
                    a1 = str(instr.arg1)
                    a2 = str(instr.arg2)
                    if instr.op in (Opcode.ADD, Opcode.MUL, Opcode.EQ, Opcode.NE):
                        if a1 > a2:
                            a1, a2 = a2, a1

                    key = (instr.op.name, a1, a2)

                    if key in expr_table and instr.result:
                        existing_var = expr_table[key]
                        # Replace computation with direct assignment from existing value
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

                new_instructions.append(instr)

            bb.instructions = new_instructions

    # ---------------- Pass 3: Dead Code Elimination (DCE) ----------------

    def pass_dead_code_elimination(self):
        """
        Removes definitions that are never used anywhere in the CFG,
        as long as the instruction produces no side effects (like PRINT, RETURN, JUMP).
        """
        changed = True
        while changed:
            changed = False

            # Collect all variable uses across all blocks
            all_uses: Set[str] = set()
            for bb in self.cfg.blocks.values():
                for instr in bb.instructions:
                    for u in instr.uses():
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
