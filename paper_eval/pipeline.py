"""
Runs the compiler pipeline of core/ stage by stage and keeps every
intermediate result, so the evaluation scripts can measure and check each
stage. Nothing in core/ is modified.
"""

import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.ir import Instruction


@dataclass
class Compiled:
    source: str
    raw: List[Instruction]                 # TAC before SSA (untouched copy)
    raw_cfg: ControlFlowGraph              # CFG of the raw TAC (untouched copy)
    ssa_cfg: ControlFlowGraph              # SSA form before optimization (copy)
    opt_cfg: ControlFlowGraph              # optimized SSA form
    opt: List[Instruction]                 # opt_cfg linearized
    generator: IRGenerator
    optimizer: IROptimizer
    phi_count: int
    times_ms: Dict[str, float] = field(default_factory=dict)


def count_phis(cfg: ControlFlowGraph) -> int:
    return sum(1 for b in cfg.blocks.values() for i in b.instructions if i.op.name == "PHI")


def compile_source(source: str, passes: Optional[Tuple[str, ...]] = None) -> Compiled:
    times: Dict[str, float] = {}

    t = time.perf_counter()
    ast = Parser(Lexer(source).tokenize()).parse()
    times["front"] = time.perf_counter() - t

    t = time.perf_counter()
    gen = IRGenerator()
    raw = gen.generate(ast)
    times["tac"] = time.perf_counter() - t
    raw_copy = [deepcopy(i) for i in raw]

    t = time.perf_counter()
    cfg = ControlFlowGraph.build(raw)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    times["cfg_dom"] = time.perf_counter() - t
    raw_cfg = ControlFlowGraph.build([deepcopy(i) for i in raw_copy])

    t = time.perf_counter()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    times["ssa"] = time.perf_counter() - t
    ssa_copy = ssa_cfg.clone()

    t = time.perf_counter()
    optimizer = IROptimizer(ssa_cfg, passes=passes)
    opt_cfg = optimizer.optimize()
    opt = opt_cfg.linearize()
    times["opt"] = time.perf_counter() - t

    return Compiled(source=source, raw=raw_copy, raw_cfg=raw_cfg, ssa_cfg=ssa_copy,
                    opt_cfg=opt_cfg, opt=opt, generator=gen, optimizer=optimizer,
                    phi_count=count_phis(ssa_copy),
                    times_ms={k: v * 1000 for k, v in times.items()})


def text_bytes(instructions: List[Instruction]) -> int:
    """Size of the textual form: one instruction per line, UTF-8."""
    return len("\n".join(str(i) for i in instructions).encode("utf-8"))


def text_of(instructions: List[Instruction]) -> bytes:
    return "\n".join(str(i) for i in instructions).encode("utf-8")
