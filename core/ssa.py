"""
Static Single Assignment (SSA) Transformation Engine.
Implements Cytron's algorithm:
1. Pruned/Semi-pruned Phi-node placement via Iterated Dominance Frontiers (IDF).
2. Dominator Tree DFS variable renaming with version stacks and push/pop backtracking.
"""

from typing import Dict, Set, List, Optional
from copy import deepcopy
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph, BasicBlock
from core.dominator import DominanceAnalyzer


class SSATransformer:
    def __init__(self, cfg: ControlFlowGraph, dom_analyzer: DominanceAnalyzer):
        self.cfg = cfg
        self.dom = dom_analyzer
        # Stacks for variable renaming: var_name -> list of versioned names
        self.stacks: Dict[str, List[str]] = {}
        # Version counters: var_name -> int
        self.counters: Dict[str, int] = {}
        # Track inserted phi nodes: block_id -> list of Instructions
        self.phi_nodes_inserted: Dict[str, List[Instruction]] = {}
        # Track all variable definitions across blocks
        self.def_blocks: Dict[str, Set[str]] = {}
        # Track variables used across blocks (non-local)
        self.global_vars: Set[str] = set()

    def transform(self) -> ControlFlowGraph:
        """Transforms the CFG into SSA form in-place and returns it."""
        self.identify_definitions_and_globals()
        self.insert_phi_functions()
        self.rename_variables()
        return self.cfg

    def identify_definitions_and_globals(self):
        """Find where each variable is defined, and identify which variables cross block boundaries."""
        self.def_blocks.clear()
        self.global_vars.clear()

        for b_id, bb in self.cfg.blocks.items():
            var_killed: Set[str] = set()
            for instr in bb.instructions:
                # Check uses before def in this block
                for use in instr.uses():
                    if use not in var_killed:
                        self.global_vars.add(use)

                defn = instr.defines()
                if defn is not None:
                    var_killed.add(defn)
                    if defn not in self.def_blocks:
                        self.def_blocks[defn] = set()
                    self.def_blocks[defn].add(b_id)

    def insert_phi_functions(self):
        """
        Computes Iterated Dominance Frontier (IDF) for each global variable
        and inserts uninitialized phi-functions at those join points.
        """
        self.phi_nodes_inserted = {b: [] for b in self.cfg.blocks}

        for var, def_sites in self.def_blocks.items():
            # Semi-pruned SSA: only insert phi for variables live across block boundaries
            if var not in self.global_vars:
                continue

            worklist = list(def_sites)
            has_phi: Set[str] = set()

            while worklist:
                node = worklist.pop(0)
                for frontier_node in self.dom.dom_frontiers.get(node, set()):
                    if frontier_node not in has_phi and frontier_node in self.cfg.blocks:
                        has_phi.add(frontier_node)

                        # Create empty phi instruction
                        phi_instr = Instruction(
                            op=Opcode.PHI,
                            result=var,
                            phi_args={},  # Pred_id -> var_version
                            line=self.cfg.blocks[frontier_node].instructions[0].line if self.cfg.blocks[frontier_node].instructions else 1,
                            annotation=var,  # Preserves exact base variable name for renaming
                        )
                        # Insert phi instruction after any leading labels in the basic block
                        target_bb = self.cfg.blocks[frontier_node]
                        insert_idx = 0
                        while insert_idx < len(target_bb.instructions) and target_bb.instructions[insert_idx].op == Opcode.LABEL:
                            insert_idx += 1
                        target_bb.instructions.insert(insert_idx, phi_instr)
                        self.phi_nodes_inserted[frontier_node].append(phi_instr)

                        if frontier_node not in def_sites:
                            worklist.append(frontier_node)

    def new_version(self, var: str) -> str:
        count = self.counters.get(var, 0)
        self.counters[var] = count + 1
        return f"{var}_{count}"

    def rename_variables(self):
        """Performs DFS over Dominator Tree to rename all variable defs and uses to SSA versions."""
        self.stacks = {}
        self.counters = {}

        for var in list(self.def_blocks.keys()) + list(self.global_vars):
            self.stacks[var] = []
            self.counters[var] = 0

        self._rename_block(self.cfg.entry_block_id)

    def _rename_block(self, b_id: str):
        bb = self.cfg.blocks.get(b_id)
        if not bb:
            return

        pushed_vars: List[str] = []

        # 1. Process Phi-functions in this block: give new SSA names to their results
        for instr in bb.instructions:
            if instr.op == Opcode.PHI:
                orig_var = instr.annotation or instr.result
                if orig_var in self.stacks:
                    new_name = self.new_version(orig_var)
                    instr.result = new_name
                    self.stacks[orig_var].append(new_name)
                    pushed_vars.append(orig_var)

        # 2. Process regular instructions in this block
        for instr in bb.instructions:
            if instr.op == Opcode.PHI:
                continue

            # Rename uses
            if instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
            elif instr.op == Opcode.PRINT:
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
            elif instr.op == Opcode.RETURN:
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
            elif instr.op == Opcode.ASSIGN:
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
            elif instr.op in (Opcode.NEG, Opcode.NOT):
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
            elif instr.op == Opcode.CALL:
                instr.call_args = [self.stacks[str(a)][-1] if str(a) in self.stacks and self.stacks[str(a)] else a
                                   for a in instr.call_args]
            elif instr.op not in (Opcode.LABEL, Opcode.JUMP, Opcode.LOAD_CONST, Opcode.NOP,
                                  Opcode.READ, Opcode.PARAM):
                # Binary operations
                if instr.arg1 and str(instr.arg1) in self.stacks and self.stacks[str(instr.arg1)]:
                    instr.arg1 = self.stacks[str(instr.arg1)][-1]
                if instr.arg2 and str(instr.arg2) in self.stacks and self.stacks[str(instr.arg2)]:
                    instr.arg2 = self.stacks[str(instr.arg2)][-1]

            # Rename def
            defn = instr.defines()
            if defn and defn in self.stacks:
                new_name = self.new_version(defn)
                instr.result = new_name
                self.stacks[defn].append(new_name)
                pushed_vars.append(defn)

        # 3. Update Phi-function arguments in successor blocks
        for succ_id in bb.successors:
            succ_bb = self.cfg.blocks.get(succ_id)
            if not succ_bb:
                continue
            for succ_instr in succ_bb.instructions:
                if succ_instr.op == Opcode.PHI:
                    base_var = succ_instr.annotation or (succ_instr.result.rsplit('_', 1)[0] if '_' in str(succ_instr.result) else str(succ_instr.result))
                    if base_var in self.stacks and self.stacks[base_var]:
                        curr_version = self.stacks[base_var][-1]
                        succ_instr.phi_args[b_id] = curr_version
                    else:
                        # Undefined or initial value
                        succ_instr.phi_args[b_id] = f"{base_var}_undef"

        # 4. Recursively visit children in the Dominator Tree
        dom_children = self.dom.dom_tree.get(b_id, [])
        for child_id in dom_children:
            self._rename_block(child_id)

        # 5. Pop all versions pushed during this block's processing (backtracking)
        for var in pushed_vars:
            if self.stacks[var]:
                self.stacks[var].pop()

    def get_stats(self) -> dict:
        total_phi = sum(len(phis) for phis in self.phi_nodes_inserted.values())
        return {
            "phi_functions_inserted": total_phi,
            "variables_converted": len(self.def_blocks),
            "ssa_blocks": len(self.cfg.blocks),
        }
