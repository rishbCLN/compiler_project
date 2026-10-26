"""
Liveness Analysis for Control Flow Graphs in Static Single Assignment (SSA) Form.
Computes iterative backward dataflow liveness with predecessor-aware phi-node scoping.
Tracks instruction-level live sets and variable lifetime intervals.
"""

from typing import Dict, Set, List, Tuple, Optional, Any
from copy import deepcopy
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph, BasicBlock


class LivenessAnalyzer:
    """
    Performs backward dataflow liveness analysis on a Control Flow Graph.
    
    Standard equations:
      LiveOut[B] = Union_{S in Succ(B)} LiveOut(B, S)
      where LiveOut(B, S) = (LiveIn[S] \\ DefPhi[S]) U PhiUse(S, B)
      
      LiveIn[B] = (LiveOut[B] \\ Def[B]) U Use[B]
      with instruction-level propagation backwards from block exit.
    """

    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        # Block-level liveness: block_id -> Set of variable names
        self.live_in: Dict[str, Set[str]] = {}
        self.live_out: Dict[str, Set[str]] = {}
        # Edge-level liveness: (src_block, dst_block) -> Set of variable names live across edge
        self.edge_live: Dict[Tuple[str, str], Set[str]] = {}
        # Instruction-level liveness: list of dicts with instruction metadata and live sets
        self.instruction_liveness: List[Dict[str, Any]] = []
        # Variable lifetime intervals: var_name -> {"birth": int, "death": int, "length": int, "def_block": str}
        self.intervals: Dict[str, Dict[str, Any]] = {}
        # All unique variables detected in the CFG
        self.all_variables: Set[str] = set()

    def _get_phi_defs(self, block: BasicBlock) -> Set[str]:
        """Returns the set of variables defined by phi-nodes at the top of a basic block."""
        defs = set()
        for instr in block.instructions:
            if instr.op == Opcode.PHI and instr.result:
                defs.add(instr.result)
        return defs

    def _get_phi_uses_for_pred(self, block: BasicBlock, pred_id: str) -> Set[str]:
        """Returns variables used by phi-nodes in this block specifically along the edge from pred_id."""
        uses = set()
        for instr in block.instructions:
            if instr.op == Opcode.PHI:
                val = instr.phi_args.get(pred_id)
                if val and isinstance(val, str):
                    # Filter out numeric literals and boolean constants
                    if not val.lstrip('-').replace('.', '', 1).isdigit() and val not in ("true", "false"):
                        uses.add(val)
        return uses

    def compute_block_liveness(self) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """
        Iteratively computes LiveIn and LiveOut for every basic block until fixed-point convergence.
        Correctly scopes phi-node arguments to their incoming predecessor edges.
        """
        self.live_in = {b_id: set() for b_id in self.cfg.blocks}
        self.live_out = {b_id: set() for b_id in self.cfg.blocks}
        self.all_variables.clear()

        # Collect all variables defined or used across the CFG
        for bb in self.cfg.blocks.values():
            for instr in bb.instructions:
                defn = instr.defines()
                if defn:
                    self.all_variables.add(defn)
                for u in instr.uses():
                    self.all_variables.add(u)

        changed = True
        iteration = 0
        max_iterations = len(self.cfg.blocks) * 10 + 20

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            # Backward traversal over all blocks
            for b_id, bb in self.cfg.blocks.items():
                # 1. Compute LiveOut[B] from successors
                new_live_out: Set[str] = set()
                for succ_id in bb.successors:
                    succ_bb = self.cfg.get_block(succ_id)
                    if not succ_bb:
                        continue
                    
                    phi_defs = self._get_phi_defs(succ_bb)
                    phi_uses = self._get_phi_uses_for_pred(succ_bb, b_id)
                    # LiveOut(B, S) = (LiveIn[S] \ DefPhi[S]) U PhiUse(S, B)
                    edge_vars = (self.live_in[succ_id] - phi_defs) | phi_uses
                    self.edge_live[(b_id, succ_id)] = edge_vars
                    new_live_out |= edge_vars

                if new_live_out != self.live_out[b_id]:
                    self.live_out[b_id] = new_live_out
                    changed = True

                # 2. Compute LiveIn[B] by propagating backwards through instructions in B
                current_live = set(self.live_out[b_id])
                for instr in reversed(bb.instructions):
                    if instr.op == Opcode.PHI:
                        # Phi definitions are killed at block entry; phi uses are scoped to predecessor edges
                        if instr.result:
                            current_live.discard(instr.result)
                    else:
                        defn = instr.defines()
                        if defn:
                            current_live.discard(defn)
                        for u in instr.uses():
                            current_live.add(u)

                if current_live != self.live_in[b_id]:
                    self.live_in[b_id] = current_live
                    changed = True

        return self.live_in, self.live_out

    def compute_instruction_liveness(self) -> List[Dict[str, Any]]:
        """
        Computes the precise set of live variables before and after every individual instruction.
        Returns a linear sequence of instruction records with live sets.
        """
        self.instruction_liveness.clear()
        global_instr_idx = 0

        # Linearize blocks (using RPO or natural order)
        for b_id in sorted(self.cfg.blocks.keys()):
            bb = self.cfg.blocks[b_id]
            # Backward pass through block instructions to calculate live sets
            n = len(bb.instructions)
            live_after_list = [set() for _ in range(n)]
            live_before_list = [set() for _ in range(n)]

            curr = set(self.live_out.get(b_id, set()))
            for i in range(n - 1, -1, -1):
                instr = bb.instructions[i]
                live_after_list[i] = set(curr)

                if instr.op == Opcode.PHI:
                    if instr.result:
                        curr.discard(instr.result)
                    # Phi arguments are not added here (they come from predecessor edges)
                else:
                    defn = instr.defines()
                    if defn:
                        curr.discard(defn)
                    for u in instr.uses():
                        curr.add(u)

                live_before_list[i] = set(curr)

            # Record forward results with global index
            for i in range(n):
                instr = bb.instructions[i]
                self.instruction_liveness.append({
                    "global_index": global_instr_idx,
                    "block_id": b_id,
                    "instruction": instr,
                    "text": str(instr),
                    "live_before": sorted(list(live_before_list[i])),
                    "live_after": sorted(list(live_after_list[i])),
                    "defines": instr.defines(),
                    "uses": instr.uses(),
                })
                global_instr_idx += 1

        return self.instruction_liveness

    def compute_live_intervals(self) -> Dict[str, Dict[str, Any]]:
        """
        Computes the lifetime interval [birth, death] for each variable.
        Birth is the instruction index where the variable is defined.
        Death is the maximum instruction index where the variable is live or used.
        """
        if not self.instruction_liveness:
            self.compute_instruction_liveness()

        self.intervals.clear()
        
        # Initialize intervals for all known variables
        for var in self.all_variables:
            self.intervals[var] = {
                "variable": var,
                "birth": None,
                "death": None,
                "length": 0,
                "def_block": None,
                "use_count": 0,
            }

        # Scan instruction-level timeline
        for rec in self.instruction_liveness:
            idx = rec["global_index"]
            defn = rec["defines"]
            uses = rec["uses"]
            live_after = set(rec["live_after"])

            if defn and defn in self.intervals:
                if self.intervals[defn]["birth"] is None:
                    self.intervals[defn]["birth"] = idx
                    self.intervals[defn]["def_block"] = rec["block_id"]

            for u in uses:
                if u in self.intervals:
                    self.intervals[u]["use_count"] += 1
                    current_death = self.intervals[u]["death"]
                    if current_death is None or idx > current_death:
                        self.intervals[u]["death"] = idx

            for var in live_after:
                if var in self.intervals:
                    current_death = self.intervals[var]["death"]
                    if current_death is None or idx > current_death:
                        self.intervals[var]["death"] = idx

        # Finalize birth and death for any variables with missing endpoints
        for var, data in self.intervals.items():
            if data["birth"] is None:
                data["birth"] = 0
            if data["death"] is None:
                data["death"] = data["birth"]
            if data["death"] < data["birth"]:
                data["death"] = data["birth"]
            data["length"] = data["death"] - data["birth"] + 1

        return self.intervals

    def analyze(self) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """Full analysis pipeline: computes block liveness, instruction liveness, and intervals."""
        self.compute_block_liveness()
        self.compute_instruction_liveness()
        self.compute_live_intervals()
        return self.live_in, self.live_out

    def to_dict(self) -> dict:
        """Serializes liveness results for API payloads and visualization."""
        return {
            "block_live_in": {b: sorted(list(s)) for b, s in self.live_in.items()},
            "block_live_out": {b: sorted(list(s)) for b, s in self.live_out.items()},
            "variable_count": len(self.all_variables),
            "variables": sorted(list(self.all_variables)),
            "intervals": self.intervals,
            "instruction_count": len(self.instruction_liveness),
        }
