"""
Helpers for programs with user-defined functions. The front end returns the
main unit from IRGenerator.generate() and keeps every other function in
IRGenerator.functions; each of them is optimized on its own.
"""

from typing import Any, Dict, List, Optional, Tuple

from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ir import Instruction
from core.optimizer import IROptimizer
from core.ssa import SSATransformer


def optimize_unit(instructions: List[Instruction],
                  passes: Optional[Tuple[str, ...]] = None) -> Tuple[List[Instruction], ControlFlowGraph]:
    """CFG, SSA and optimization for one unit; returns (instructions, cfg)."""
    cfg = ControlFlowGraph.build(instructions)
    dom = DominanceAnalyzer(cfg)
    dom.compute_all()
    ssa_cfg = SSATransformer(cfg, dom).transform()
    opt_cfg = IROptimizer(ssa_cfg, passes=passes).optimize()
    return opt_cfg.linearize(), opt_cfg


def optimize_functions(functions: Dict[str, Tuple[List[str], List[Instruction]]],
                       passes: Optional[Tuple[str, ...]] = None
                       ) -> List[Tuple[str, List[Instruction], ControlFlowGraph]]:
    """Optimize every function of IRGenerator.functions, in definition order,
    as (name, instructions, cfg) units for BytecodeEmitter.serialize_module."""
    units = []
    for name, (_, instructions) in functions.items():
        opt, cfg = optimize_unit(instructions, passes)
        units.append((name, opt, cfg))
    return units
