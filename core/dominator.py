"""
Dominator Tree and Dominance Frontier Analysis for Control Flow Graphs.
Computes Dominator sets, Immediate Dominators (IDom), Dominator Trees,
and Dominance Frontiers (DF) using iterative dataflow algorithms (Cytron / Cooper-Harvey-Kennedy).
"""

from typing import Dict, Set, List, Optional
from core.cfg import ControlFlowGraph


class DominanceAnalyzer:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        self.blocks = list(cfg.blocks.keys())
        self.entry = cfg.entry_block_id
        # idom: block_id -> immediate dominator block_id
        self.idom: Dict[str, Optional[str]] = {}
        # dominator tree children: parent_id -> list of child_ids
        self.dom_tree: Dict[str, List[str]] = {b: [] for b in self.blocks}
        # dominance frontiers: block_id -> set of block_ids
        self.dom_frontiers: Dict[str, Set[str]] = {b: set() for b in self.blocks}
        # all dominators: block_id -> set of all dominators
        self.dominators: Dict[str, Set[str]] = {}

    def compute_all(self):
        self.compute_dominators()
        self.compute_immediate_dominators()
        self.build_dom_tree()
        self.compute_dominance_frontiers()

    def compute_dominators(self):
        """
        Computes the set of all dominators Dom(B) for each basic block using fixed-point iteration:
        Dom(Entry) = { Entry }
        Dom(B) = { B } U (Intersection of Dom(P) for all P in Pred(B))
        """
        all_blocks = set(self.blocks)
        self.dominators = {b: set(all_blocks) for b in self.blocks}

        if self.entry in self.dominators:
            self.dominators[self.entry] = {self.entry}

        changed = True
        while changed:
            changed = False
            for b in self.blocks:
                if b == self.entry:
                    continue

                preds = self.cfg.blocks[b].predecessors
                if not preds:
                    new_dom = {b}
                else:
                    # Intersection of dominators of predecessors
                    pred_dom_lists = [self.dominators[p] for p in preds if p in self.dominators]
                    if pred_dom_lists:
                        intersection = set.intersection(*pred_dom_lists)
                        new_dom = {b} | intersection
                    else:
                        new_dom = {b}

                if new_dom != self.dominators[b]:
                    self.dominators[b] = new_dom
                    changed = True

    def compute_immediate_dominators(self):
        """
        IDom(B) is the unique strict dominator of B that does not dominate any other strict dominator of B.
        """
        for b in self.blocks:
            if b == self.entry:
                self.idom[b] = None
                continue

            strict_doms = self.dominators[b] - {b}
            # Among strict_doms, find the one whose dominator set is maximal (closest to B)
            # In other words, IDom dominates B, and any other strict dominator also dominates IDom.
            idom_candidate = None
            for cand in strict_doms:
                # Check if cand is dominated by all other candidates in strict_doms
                # cand is IDom if other strict dominators dominate cand
                other_doms = strict_doms - {cand}
                if other_doms.issubset(self.dominators[cand]):
                    idom_candidate = cand
                    break

            self.idom[b] = idom_candidate

    def build_dom_tree(self):
        """Build children list for the Dominator Tree."""
        for b in self.blocks:
            parent = self.idom.get(b)
            if parent is not None:
                if parent not in self.dom_tree:
                    self.dom_tree[parent] = []
                self.dom_tree[parent].append(b)

    def compute_dominance_frontiers(self):
        """
        Computes Dominance Frontier DF(X) for all nodes:
        For each node X with multiple predecessors:
          For each predecessor P of X:
            Runner = P
            While Runner != IDom(X):
              DF(Runner) = DF(Runner) U { X }
              Runner = IDom(Runner)
        """
        for b in self.blocks:
            self.dom_frontiers[b] = set()

        for b in self.blocks:
            preds = self.cfg.blocks[b].predecessors
            if len(preds) >= 2:
                for p in preds:
                    runner = p
                    while runner is not None and runner != self.idom.get(b):
                        self.dom_frontiers[runner].add(b)
                        runner = self.idom.get(runner)

    def to_dict(self) -> dict:
        return {
            "idom": self.idom,
            "dom_tree": self.dom_tree,
            "dominance_frontiers": {k: sorted(list(v)) for k, v in self.dom_frontiers.items()},
            "dominators": {k: sorted(list(v)) for k, v in self.dominators.items()},
        }

    def to_cytoscape_elements(self) -> List[dict]:
        """Elements for rendering the Dominator Tree in Cytoscape."""
        elements = []
        for b in self.blocks:
            elements.append({
                "data": {
                    "id": f"dom_{b}",
                    "label": b,
                    "df": ", ".join(sorted(list(self.dom_frontiers.get(b, [])))),
                }
            })

        edge_id = 0
        for parent, children in self.dom_tree.items():
            for child in children:
                elements.append({
                    "data": {
                        "id": f"dom_e{edge_id}",
                        "source": f"dom_{parent}",
                        "target": f"dom_{child}",
                        "label": "idom",
                    }
                })
                edge_id += 1

        return elements
