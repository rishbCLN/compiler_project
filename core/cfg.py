"""
Control Flow Graph (CFG) Builder and Analyzer.
Partitions linear TAC instructions into Basic Blocks using leader analysis,
establishes control flow edges, performs reachability pruning, and serializes graph data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from core.ir import Instruction, Opcode


@dataclass
class BasicBlock:
    id: str
    instructions: List[Instruction] = field(default_factory=list)
    predecessors: Set[str] = field(default_factory=set)
    successors: Set[str] = field(default_factory=set)
    label: Optional[str] = None

    def is_empty(self) -> bool:
        # Check if contains only non-executable labels/nops
        for instr in self.instructions:
            if instr.op not in (Opcode.LABEL, Opcode.NOP):
                return False
        return True

    def get_terminator(self) -> Optional[Instruction]:
        if self.instructions:
            return self.instructions[-1]
        return None

    def clone(self) -> 'BasicBlock':
        from copy import deepcopy
        return BasicBlock(
            id=self.id,
            instructions=[deepcopy(i) for i in self.instructions],
            predecessors=set(self.predecessors),
            successors=set(self.successors),
            label=self.label
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "instructions": [instr.to_dict() for instr in self.instructions],
            "text": "\n".join(str(instr) for instr in self.instructions),
            "predecessors": sorted(list(self.predecessors)),
            "successors": sorted(list(self.successors)),
        }


class ControlFlowGraph:
    def __init__(self):
        self.blocks: Dict[str, BasicBlock] = {}
        self.entry_block_id: str = "BB0"
        self.label_to_block: Dict[str, str] = {}
        # Edge metadata: (src, dst) -> "fallthrough" | "jump" | "branch_true" | "branch_false"
        self.edge_types: Dict[Tuple[str, str], str] = {}

    def clone(self) -> 'ControlFlowGraph':
        new_cfg = ControlFlowGraph()
        new_cfg.entry_block_id = self.entry_block_id
        new_cfg.label_to_block = dict(self.label_to_block)
        new_cfg.edge_types = dict(self.edge_types)
        for b_id, b in self.blocks.items():
            new_cfg.blocks[b_id] = b.clone()
        return new_cfg

    def get_block(self, block_id: str) -> Optional[BasicBlock]:
        return self.blocks.get(block_id)

    @classmethod
    def build(cls, instructions: List[Instruction]) -> 'ControlFlowGraph':
        cfg = cls()
        if not instructions:
            return cfg

        # Step 1: Identify leaders
        n = len(instructions)
        is_leader = [False] * n
        is_leader[0] = True  # Rule 1: First instruction is a leader

        label_to_index: Dict[str, int] = {}
        for idx, instr in enumerate(instructions):
            if instr.op == Opcode.LABEL:
                label_to_index[str(instr.arg1)] = idx

        for idx, instr in enumerate(instructions):
            # Rule 2: Target of any jump is a leader
            if instr.op in (Opcode.JUMP, Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                target_lbl = str(instr.result if instr.op != Opcode.JUMP else instr.arg1)
                if target_lbl in label_to_index:
                    is_leader[label_to_index[target_lbl]] = True

                # Rule 3: Instruction immediately following a jump is a leader
                if idx + 1 < n:
                    is_leader[idx + 1] = True

            elif instr.op == Opcode.RETURN:
                if idx + 1 < n:
                    is_leader[idx + 1] = True

        # Step 2: Form basic blocks from leaders
        block_list: List[BasicBlock] = []
        current_bb: Optional[BasicBlock] = None
        bb_counter = 0

        for idx, instr in enumerate(instructions):
            if is_leader[idx]:
                bb_id = f"BB{bb_counter}"
                bb_counter += 1
                current_bb = BasicBlock(id=bb_id)
                block_list.append(current_bb)
                cfg.blocks[bb_id] = current_bb

            if current_bb is not None:
                current_bb.instructions.append(instr)
                if instr.op == Opcode.LABEL:
                    if current_bb.label is None:
                        current_bb.label = str(instr.arg1)
                    cfg.label_to_block[str(instr.arg1)] = current_bb.id

        if not block_list:
            return cfg

        cfg.entry_block_id = block_list[0].id

        # Step 3: Connect edges between basic blocks
        for i, bb in enumerate(block_list):
            if not bb.instructions:
                continue

            last_instr = bb.instructions[-1]

            if last_instr.op == Opcode.JUMP:
                target_lbl = str(last_instr.arg1)
                if target_lbl in cfg.label_to_block:
                    target_bb = cfg.label_to_block[target_lbl]
                    bb.successors.add(target_bb)
                    cfg.blocks[target_bb].predecessors.add(bb.id)
                    cfg.edge_types[(bb.id, target_bb)] = "jump"

            elif last_instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                target_lbl = str(last_instr.result)
                # Conditional jump target
                if target_lbl in cfg.label_to_block:
                    target_bb = cfg.label_to_block[target_lbl]
                    bb.successors.add(target_bb)
                    cfg.blocks[target_bb].predecessors.add(bb.id)
                    edge_kind = "branch_true" if last_instr.op == Opcode.JUMP_IF_TRUE else "branch_false"
                    cfg.edge_types[(bb.id, target_bb)] = edge_kind

                # Fallthrough to next block
                if i + 1 < len(block_list):
                    next_bb = block_list[i + 1].id
                    bb.successors.add(next_bb)
                    cfg.blocks[next_bb].predecessors.add(bb.id)
                    fall_kind = "branch_false" if last_instr.op == Opcode.JUMP_IF_TRUE else "branch_true"
                    cfg.edge_types[(bb.id, next_bb)] = fall_kind

            elif last_instr.op == Opcode.RETURN:
                # Terminator with no successors
                pass

            else:
                # Normal fallthrough to next sequential block
                if i + 1 < len(block_list):
                    next_bb = block_list[i + 1].id
                    bb.successors.add(next_bb)
                    cfg.blocks[next_bb].predecessors.add(bb.id)
                    cfg.edge_types[(bb.id, next_bb)] = "fallthrough"

        return cfg

    @classmethod
    def from_blocks(cls, blocks: List[Tuple[str, List[Instruction]]]) -> 'ControlFlowGraph':
        """Rebuild a CFG from an ordered list of (block id, instructions), as
        stored in a CLIR package. Edges follow the terminator of each block:
        a jump goes to the block holding its label, a conditional jump also
        falls through to the next block, a return ends the path, and any
        other block falls through. Empty blocks fall through as well."""
        cfg = cls()
        if not blocks:
            return cfg
        order = [b_id for b_id, _ in blocks]
        for b_id, instrs in blocks:
            bb = BasicBlock(id=b_id, instructions=list(instrs))
            cfg.blocks[b_id] = bb
            for instr in instrs:
                if instr.op == Opcode.LABEL:
                    if bb.label is None:
                        bb.label = str(instr.arg1)
                    cfg.label_to_block[str(instr.arg1)] = b_id
        cfg.entry_block_id = order[0]

        def connect(src: str, dst: str, kind: str):
            cfg.blocks[src].successors.add(dst)
            cfg.blocks[dst].predecessors.add(src)
            cfg.edge_types[(src, dst)] = kind

        for idx, b_id in enumerate(order):
            bb = cfg.blocks[b_id]
            nxt = order[idx + 1] if idx + 1 < len(order) else None
            last = bb.instructions[-1] if bb.instructions else None
            if last is not None and last.op == Opcode.JUMP:
                target = cfg.label_to_block.get(str(last.arg1))
                if target is not None:
                    connect(b_id, target, "jump")
            elif last is not None and last.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                target = cfg.label_to_block.get(str(last.result))
                if target is not None:
                    connect(b_id, target, "branch_true" if last.op == Opcode.JUMP_IF_TRUE else "branch_false")
                if nxt is not None:
                    connect(b_id, nxt, "branch_false" if last.op == Opcode.JUMP_IF_TRUE else "branch_true")
            elif last is not None and last.op == Opcode.RETURN:
                pass
            elif nxt is not None:
                connect(b_id, nxt, "fallthrough")
        return cfg

    def prune_unreachable_blocks(self) -> int:
        """
        CFG Compression: Removes blocks that cannot be reached from the entry block.
        Returns the number of pruned dead blocks.
        """
        reachable: Set[str] = set()
        queue = [self.entry_block_id] if self.entry_block_id in self.blocks else []

        while queue:
            curr = queue.pop(0)
            if curr in reachable:
                continue
            reachable.add(curr)
            for succ in self.blocks[curr].successors:
                if succ not in reachable and succ in self.blocks:
                    queue.append(succ)

        dead_blocks = [b_id for b_id in self.blocks if b_id not in reachable]

        for b_id in dead_blocks:
            # Disconnect edges
            bb = self.blocks[b_id]
            for succ in bb.successors:
                if succ in self.blocks:
                    self.blocks[succ].predecessors.discard(b_id)
            del self.blocks[b_id]

        # Clean edge_types
        self.edge_types = {
            (src, dst): kind for (src, dst), kind in self.edge_types.items()
            if src in self.blocks and dst in self.blocks
        }

        return len(dead_blocks)

    def linearize(self) -> List[Instruction]:
        """Convert basic blocks back into a linear sequence of TAC instructions."""
        res: List[Instruction] = []
        for bb in sorted(self.blocks.values(), key=lambda b: int(b.id[2:]) if b.id.startswith("BB") and b.id[2:].isdigit() else 0):
            res.extend(bb.instructions)
        return res

    def get_stats(self) -> dict:
        total_instructions = sum(len(bb.instructions) for bb in self.blocks.values())
        total_edges = sum(len(bb.successors) for bb in self.blocks.values())
        return {
            "basic_block_count": len(self.blocks),
            "edge_count": total_edges,
            "instruction_count": total_instructions,
            "cyclomatic_complexity": max(1, total_edges - len(self.blocks) + 2),
        }

    def to_cytoscape_elements(self) -> List[dict]:
        """Convert CFG to Cytoscape.js graph elements for web visualizer."""
        elements = []

        # Nodes
        for bb_id, bb in self.blocks.items():
            lines = [str(instr) for instr in bb.instructions]
            code_preview = "\n".join(lines) if lines else "(empty)"
            is_entry = (bb_id == self.entry_block_id)
            is_exit = (len(bb.successors) == 0)

            node_type = "normal"
            if is_entry:
                node_type = "entry"
            elif is_exit:
                node_type = "exit"

            elements.append({
                "data": {
                    "id": bb_id,
                    "label": f"{bb_id} ({bb.label})" if bb.label else bb_id,
                    "code": code_preview,
                    "type": node_type,
                    "instr_count": len(bb.instructions),
                }
            })

        # Edges
        edge_id = 0
        for (src, dst), edge_type in self.edge_types.items():
            elements.append({
                "data": {
                    "id": f"e{edge_id}",
                    "source": src,
                    "target": dst,
                    "label": edge_type,
                    "edge_type": edge_type,
                }
            })
            edge_id += 1

        return elements
