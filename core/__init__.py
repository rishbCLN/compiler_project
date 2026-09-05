"""
Intermediate Representation (IR) Compression Compiler Core Engine.
"""

from core.lexer import Lexer, Token, TokenType
from core.parser import Parser
from core.ast_nodes import ProgramNode, ASTNode
from core.ir import Instruction, Opcode
from core.symbol_table import SymbolTable, Symbol
from core.constant_pool import ConstantPool, ConstantEntry
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph, BasicBlock
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.binary_compression import BytecodeEmitter, HuffmanCompressor, IRCompressionPipeline, LEB128
from core.advanced_compression import (
    FrontCodedStringPool,
    RPOBlockScheduler,
    SSABackwardDeltaEncoder,
    ColumnarBytecodeSerializer,
    AdvancedIRCompressionEngine,
)

__all__ = [
    "Lexer", "Token", "TokenType",
    "Parser", "ProgramNode", "ASTNode",
    "Instruction", "Opcode",
    "SymbolTable", "Symbol",
    "ConstantPool", "ConstantEntry",
    "IRGenerator",
    "ControlFlowGraph", "BasicBlock",
    "DominanceAnalyzer",
    "SSATransformer",
    "IROptimizer",
    "BytecodeEmitter", "HuffmanCompressor", "IRCompressionPipeline", "LEB128",
    "FrontCodedStringPool", "RPOBlockScheduler", "SSABackwardDeltaEncoder",
    "ColumnarBytecodeSerializer", "AdvancedIRCompressionEngine",
]
