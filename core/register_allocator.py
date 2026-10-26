"""
SSA Chordal Register Allocator via Maximum Cardinality Search (MCS).
Implements Hack's Theorem (Hack et al. 2006; Pereira & Palsberg 2005):
Interference graphs in SSA form are chordal graphs.
Computes optimal graph coloring in O(V + E) time without backtracking or heuristics.
"""

from typing import Dict, Set, List, Tuple, Optional, Any
from copy import deepcopy
from core.ir import Instruction, Opcode
from core.cfg import ControlFlowGraph
from core.liveness import LivenessAnalyzer


class RegisterInterferenceGraph:
    """
    Constructs and analyzes the Register Interference Graph (RIG).
    Nodes represent variables; edges connect variables that are simultaneously live.
    """

    def __init__(self):
        self.nodes: Set[str] = set()
        self.adj: Dict[str, Set[str]] = {}
        self.max_clique_size: int = 0

    def add_node(self, var: str):
        if var not in self.nodes:
            self.nodes.add(var)
            self.adj[var] = set()

    def add_edge(self, u: str, v: str):
        if u == v:
            return
        self.add_node(u)
        self.add_node(v)
        self.adj[u].add(v)
        self.adj[v].add(u)

    @classmethod
    def build_from_liveness(cls, liveness: LivenessAnalyzer) -> 'RegisterInterferenceGraph':
        rig = cls()
        
        # Add all variables as nodes
        for var in liveness.all_variables:
            rig.add_node(var)

        # 1. Build interference from instruction-level live sets
        for rec in liveness.instruction_liveness:
            instr: Instruction = rec["instruction"]
            defn = rec["defines"]
            live_after = set(rec["live_after"])

            if defn:
                rig.add_node(defn)
                for v in live_after:
                    if v != defn:
                        # Copy coalescing opportunity: if d = v (ASSIGN), they do not interfere
                        if instr.op == Opcode.ASSIGN and str(instr.arg1) == v:
                            continue
                        rig.add_edge(defn, v)

            # Pairwise interference among all variables simultaneously live
            live_list = sorted(list(live_after))
            for i in range(len(live_list)):
                for j in range(i + 1, len(live_list)):
                    rig.add_edge(live_list[i], live_list[j])

        # 2. Add edges across block boundaries for variables live across the same block entry/exit
        for live_set in liveness.live_in.values():
            l_list = sorted(list(live_set))
            for i in range(len(l_list)):
                for j in range(i + 1, len(l_list)):
                    rig.add_edge(l_list[i], l_list[j])

        for live_set in liveness.live_out.values():
            l_list = sorted(list(live_set))
            for i in range(len(l_list)):
                for j in range(i + 1, len(l_list)):
                    rig.add_edge(l_list[i], l_list[j])

        return rig

    def get_stats(self) -> Dict[str, Any]:
        """Calculates graph metrics: node count, edge count, density, and max degree."""
        v = len(self.nodes)
        e = sum(len(neighbors) for neighbors in self.adj.values()) // 2
        density = (2.0 * e / (v * (v - 1))) if v > 1 else 0.0
        max_degree = max((len(neighbors) for neighbors in self.adj.values()), default=0)
        
        return {
            "node_count": v,
            "edge_count": e,
            "density": round(density, 4),
            "max_degree": max_degree,
            "nodes": sorted(list(self.nodes)),
        }

    def to_cytoscape_elements(self, allocation: Optional[Dict[str, int]] = None) -> List[dict]:
        """
        Converts the RIG into Cytoscape.js elements with distinct color-coded register assignments.
        """
        elements = []
        # Curated palette for physical registers (R0..R15)
        color_palette = [
            "#4361EE",  # R0 - Royal Blue
            "#2EC4B6",  # R1 - Teal
            "#7209B7",  # R2 - Purple
            "#F72585",  # R3 - Vivid Pink
            "#FF9F1C",  # R4 - Amber Orange
            "#06D6A0",  # R5 - Mint Green
            "#E63946",  # R6 - Crimson Red
            "#3A86FF",  # R7 - Sky Blue
            "#8338EC",  # R8 - Violet
            "#FB5607",  # R9 - Flame Orange
            "#118AB2",  # R10 - Ocean Blue
            "#073B4C",  # R11 - Navy
            "#9B5DE5",  # R12 - Orchid
            "#F15BB5",  # R13 - Magenta
            "#00BBF9",  # R14 - Electric Cyan
            "#00F5D4",  # R15 - Aquamarine
        ]

        allocation = allocation or {}

        # 1. Add Nodes
        for node in sorted(list(self.nodes)):
            reg_idx = allocation.get(node, 0)
            reg_name = f"R{reg_idx}" if node in allocation else "Unassigned"
            color = color_palette[reg_idx % len(color_palette)]
            degree = len(self.adj.get(node, set()))

            elements.append({
                "data": {
                    "id": node,
                    "label": f"{node} -> {reg_name}",
                    "var_name": node,
                    "register": reg_name,
                    "reg_idx": reg_idx,
                    "color": color,
                    "degree": degree,
                }
            })

        # 2. Add Undirected Edges
        seen_edges = set()
        for u in sorted(list(self.nodes)):
            for v in sorted(list(self.adj.get(u, set()))):
                edge_pair = tuple(sorted([u, v]))
                if edge_pair not in seen_edges:
                    seen_edges.add(edge_pair)
                    elements.append({
                        "data": {
                            "id": f"rig_{edge_pair[0]}_{edge_pair[1]}",
                            "source": edge_pair[0],
                            "target": edge_pair[1],
                        }
                    })

        return elements


class ChordalRegisterAllocator:
    """
    Computes optimal register allocation using Hack's Theorem for chordal SSA graphs.
    1. Maximum Cardinality Search (MCS) finds a Perfect Elimination Ordering (PEO).
    2. Greedy coloring in reverse PEO order achieves exact chromatic number chi(G) = omega(G).
    """

    def __init__(self, rig: RegisterInterferenceGraph):
        self.rig = rig
        self.allocation: Dict[str, int] = {}
        self.peo: List[str] = []
        self.k_registers: int = 0
        self.max_clique_size: int = 0

    def maximum_cardinality_search(self) -> List[str]:
        """
        Maximum Cardinality Search (MCS) by Tarjan & Yannakakis (1984).
        Generates a Perfect Elimination Ordering (PEO) in O(V + E) time.
        """
        nodes = set(self.rig.nodes)
        n = len(nodes)
        if n == 0:
            self.peo = []
            return []

        # Weights: count of already numbered neighbors
        weights: Dict[str, int] = {node: 0 for node in nodes}
        peo: List[str] = []
        unvisited = set(nodes)

        for _ in range(n):
            # Select unvisited vertex with maximum weight (tie-break by degree and name)
            max_v = max(unvisited, key=lambda v: (weights[v], len(self.rig.adj[v]), v))
            peo.append(max_v)
            unvisited.remove(max_v)

            # Increment weight of all unvisited neighbors of max_v
            for neighbor in self.rig.adj.get(max_v, set()):
                if neighbor in unvisited:
                    weights[neighbor] += 1

        # The search builds the ordering; reversing gives the simplicial elimination order (PEO)
        peo.reverse()
        self.peo = peo
        return self.peo

    def verify_peo(self, peo: List[str]) -> bool:
        """
        Verifies if an ordering is a valid Perfect Elimination Ordering (PEO).
        For each vertex v, its higher-indexed neighbors in the ordering must form a clique.
        """
        pos = {node: idx for idx, node in enumerate(peo)}
        for v in peo:
            v_idx = pos[v]
            # Neighbors appearing after v in peo
            higher_neighbors = [u for u in self.rig.adj.get(v, set()) if pos[u] > v_idx]
            # Check if higher_neighbors form a clique
            for i in range(len(higher_neighbors)):
                for j in range(i + 1, len(higher_neighbors)):
                    u1 = higher_neighbors[i]
                    u2 = higher_neighbors[j]
                    if u2 not in self.rig.adj.get(u1, set()):
                        return False
        return True

    def color_graph(self) -> Dict[str, int]:
        """
        Colors the chordal graph using the Perfect Elimination Ordering.
        Produces mathematically optimal register allocation without backtracking.
        """
        if not self.peo:
            self.maximum_cardinality_search()

        self.allocation.clear()

        # Iterate in reverse PEO order (or PEO order) to greedily color
        for v in reversed(self.peo):
            # Find colors used by already colored neighbors
            used_colors = set()
            for neighbor in self.rig.adj.get(v, set()):
                if neighbor in self.allocation:
                    used_colors.add(self.allocation[neighbor])

            # Assign smallest non-negative integer color available
            color = 0
            while color in used_colors:
                color += 1
            self.allocation[v] = color

        # Compute total physical registers needed (k)
        self.k_registers = (max(self.allocation.values()) + 1) if self.allocation else 0
        
        # Calculate maximum clique size omega(G)
        self.max_clique_size = self._compute_max_clique_size()
        self.rig.max_clique_size = self.max_clique_size

        # Sanity assertion: no two interfering nodes can have the same register
        self._validate_coloring()

        return self.allocation

    def _compute_max_clique_size(self) -> int:
        """Computes the maximum clique size in a chordal graph from the PEO."""
        if not self.peo:
            return 0
        pos = {node: idx for idx, node in enumerate(self.peo)}
        max_clique = 1
        for v in self.peo:
            v_idx = pos[v]
            higher_neighbors_count = sum(1 for u in self.rig.adj.get(v, set()) if pos[u] > v_idx)
            max_clique = max(max_clique, higher_neighbors_count + 1)
        return max_clique

    def _validate_coloring(self):
        """Validates that no adjacent nodes share the same physical register."""
        for u, neighbors in self.rig.adj.items():
            u_col = self.allocation.get(u)
            if u_col is None:
                continue
            for v in neighbors:
                v_col = self.allocation.get(v)
                if v_col is not None and u_col == v_col:
                    raise ValueError(f"Register allocation conflict! Interfering variables {u} and {v} both assigned to R{u_col}")

    def allocate(self) -> Dict[str, int]:
        """Convenience method running MCS and coloring."""
        self.maximum_cardinality_search()
        return self.color_graph()


class RegisterCompactor:
    """
    Substitutes virtual SSA variable names in instruction quadruples with allocated physical registers.
    e.g. 'x_1 = t0 + t1' -> 'R0 = R1 + R2'
    """

    @staticmethod
    def compact_instructions(instructions: List[Instruction],
                             allocation: Dict[str, int]) -> List[Instruction]:
        compacted: List[Instruction] = []

        def rename(val: Optional[Any]) -> Optional[Any]:
            if val is None:
                return None
            s = str(val)
            if s in allocation:
                return f"R{allocation[s]}"
            return val

        for instr in instructions:
            new_instr = deepcopy(instr)
            
            # Rewrite result
            if new_instr.result and new_instr.result in allocation:
                new_instr.result = f"R{allocation[new_instr.result]}"

            # Rewrite arg1 (if it represents a variable, not label/constant)
            if new_instr.op not in (Opcode.LABEL, Opcode.JUMP):
                new_instr.arg1 = rename(new_instr.arg1)

            # Rewrite arg2
            new_instr.arg2 = rename(new_instr.arg2)

            # Rewrite phi arguments
            if new_instr.op == Opcode.PHI and new_instr.phi_args:
                new_phi = {}
                for pred, v in new_instr.phi_args.items():
                    new_phi[pred] = rename(v)
                new_instr.phi_args = new_phi

            compacted.append(new_instr)

        return compacted

    @staticmethod
    def get_summary(original_vars: Set[str], allocation: Dict[str, int]) -> Dict[str, Any]:
        v_count = len(original_vars)
        k_count = (max(allocation.values()) + 1) if allocation else 0
        reduction_pct = ((v_count - k_count) / v_count * 100.0) if v_count > 0 else 0.0

        return {
            "virtual_variable_count": v_count,
            "physical_register_count": k_count,
            "reduction_percentage": round(reduction_pct, 2),
            "allocation_map": {k: f"R{v}" for k, v in sorted(allocation.items())},
        }
