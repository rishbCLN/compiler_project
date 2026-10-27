"""
Runs the compiler pipeline of core/ stage by stage and keeps every
intermediate result, so the evaluation scripts can measure and check each
stage. Nothing in core/ is modified.

A program is a module: the main unit (top-level statements and the body of
main) plus one unit per user-defined function. Every unit goes through CFG
construction, SSA conversion and optimization on its own.
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
from core.ir import Instruction, Opcode


@dataclass
class Unit:
    name: str
    params: List[str]
    raw: List[Instruction]                 # TAC before SSA (untouched copy)
    raw_cfg: ControlFlowGraph              # CFG of the raw TAC (untouched copy)
    ssa_cfg: ControlFlowGraph              # SSA form before optimization (copy)
    opt_cfg: ControlFlowGraph              # optimized SSA form
    opt: List[Instruction]                 # opt_cfg linearized
    optimizer: IROptimizer
    dom_frontier_blocks: int = 0


@dataclass
class Compiled:
    source: str
    units: List[Unit]                      # main first, then functions in definition order
    generator: IRGenerator
    times_ms: Dict[str, float] = field(default_factory=dict)

    @property
    def main(self) -> Unit:
        return self.units[0]

    # Module-wide views -------------------------------------------------
    @property
    def raw(self) -> List[Instruction]:
        return [i for u in self.units for i in u.raw]

    @property
    def opt(self) -> List[Instruction]:
        return [i for u in self.units for i in u.opt]

    def ssa_instructions(self) -> List[Instruction]:
        return [i for u in self.units for i in u.ssa_cfg.linearize()]

    @property
    def phi_count(self) -> int:
        return sum(count_phis(u.ssa_cfg) for u in self.units)

    def stat(self, key: str) -> int:
        return sum(u.optimizer.stats[key] for u in self.units)

    def raw_module(self) -> Dict[str, Tuple[List[str], List[Instruction]]]:
        return {u.name: (u.params, u.raw) for u in self.units}

    def cfg_module(self, which: str) -> Dict[str, ControlFlowGraph]:
        return {u.name: getattr(u, which) for u in self.units}

    def clir_units(self):
        return [(u.name, u.opt, u.opt_cfg) for u in self.units]


def count_phis(cfg: ControlFlowGraph) -> int:
    return sum(1 for b in cfg.blocks.values() for i in b.instructions if i.op == Opcode.PHI)


def _compile_unit(name, params, raw, passes, times, optimizer_cls=IROptimizer) -> Unit:
    raw_copy = [deepcopy(i) for i in raw]

    t = time.perf_counter()
    cfg = ControlFlowGraph.build(raw)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    times["cfg_dom"] += time.perf_counter() - t
    raw_cfg = ControlFlowGraph.build([deepcopy(i) for i in raw_copy])

    t = time.perf_counter()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    times["ssa"] += time.perf_counter() - t
    ssa_copy = ssa_cfg.clone()

    t = time.perf_counter()
    optimizer = optimizer_cls(ssa_cfg, passes=passes)
    opt_cfg = optimizer.optimize()
    opt = opt_cfg.linearize()
    times["opt"] += time.perf_counter() - t

    return Unit(name=name, params=list(params), raw=raw_copy, raw_cfg=raw_cfg,
                ssa_cfg=ssa_copy, opt_cfg=opt_cfg, opt=opt, optimizer=optimizer)


def compile_source(source: str, passes: Optional[Tuple[str, ...]] = None,
                   optimizer_cls=IROptimizer) -> Compiled:
    times: Dict[str, float] = {"front": 0.0, "tac": 0.0, "cfg_dom": 0.0, "ssa": 0.0, "opt": 0.0}

    t = time.perf_counter()
    ast = Parser(Lexer(source).tokenize()).parse()
    times["front"] = time.perf_counter() - t

    t = time.perf_counter()
    gen = IRGenerator()
    main = gen.generate(ast)
    times["tac"] = time.perf_counter() - t

    units = [_compile_unit("main", [], main, passes, times, optimizer_cls)]
    for name, (params, instrs) in gen.functions.items():
        units.append(_compile_unit(name, params, instrs, passes, times, optimizer_cls))

    return Compiled(source=source, units=units, generator=gen,
                    times_ms={k: v * 1000 for k, v in times.items()})


def module_text(units: List[Tuple[str, List[str], List[Instruction]]]) -> bytes:
    """Textual form of a module: the main unit's instructions, one per line,
    then for every function a header line `func name(params):` followed by
    its instructions. UTF-8."""
    lines: List[str] = []
    for idx, (name, params, instrs) in enumerate(units):
        if idx > 0:
            lines.append(f"func {name}({', '.join(params)}):")
        lines.extend(str(i) for i in instrs)
    return "\n".join(lines).encode("utf-8")


def raw_text(c: Compiled) -> bytes:
    return module_text([(u.name, u.params, u.raw) for u in c.units])


def ssa_text(c: Compiled) -> bytes:
    return module_text([(u.name, u.params, u.ssa_cfg.linearize()) for u in c.units])


def opt_text(c: Compiled) -> bytes:
    return module_text([(u.name, u.params, u.opt) for u in c.units])


class ReleasedFolderOptimizer(IROptimizer):
    """The folder as first released: integer / and % folded with Python's
    floor rule (-31 % 1000 == 969). Used only by the differential test."""

    @staticmethod
    def _c_int_div(a: int, b: int) -> int:
        if b == 0:
            raise ZeroDivisionError
        return a // b
