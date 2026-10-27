"""
FastAPI Backend Server for Intermediate Representation (IR) Compression Studio.
Serves compiler pipeline execution, graph serialization, sample benchmarks, and static UI.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
import os
import glob
from typing import Dict, Any, Optional

from core.lexer import Lexer, LexerError
from core.parser import Parser, ParserError
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.binary_compression import BytecodeEmitter, HuffmanCompressor, IRCompressionPipeline

app = FastAPI(
    title="IR Compression Studio API",
    description="End-to-End Compiler Optimization & IR Compression Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompileRequest(BaseModel):
    code: str


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "IR Compression Studio"}


@app.get("/api/samples")
def get_samples():
    """Returns pre-loaded benchmark programs for demonstration."""
    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    sample_files = glob.glob(os.path.join(benchmarks_dir, "*.lang")) + glob.glob(os.path.join(benchmarks_dir, "*.c"))
    samples = []

    descriptions = {
        "sample1_arithmetic_constants.lang": "Arithmetic Optimization & Constant Pool Deduplication",
        "sample2_loops_and_conditionals.lang": "CFG Branching & SSA Phi-Node Resolution",
        "sample3_redundant_gvn.lang": "Global Value Numbering (GVN) & Common Subexpression Elimination",
        "sample4_dead_code.lang": "Dead Code Elimination (DCE) & Unreachable Branch Pruning",
        "sample5_matrix_fibonacci.lang": "Iterative Fibonacci Algorithm & End-to-End Compression",
        "sample6_standard_cfg_demo.lang": "CFG Visualizer Showcase: Diamond Branch & Loop Cycle (C-Lite)",
        "sample7_standard_c_program.c": "Standard C Program: #include, main(), Branches & printf",
    }

    for fpath in sorted(sample_files):
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        samples.append({
            "filename": fname,
            "title": descriptions.get(fname, fname),
            "code": content,
        })

    return {"samples": samples}


@app.post("/api/compile")
def compile_code(req: CompileRequest):
    """
    Executes the full compiler pipeline:
    Source -> Tokens -> AST -> TAC IR -> CFG -> Dominators -> SSA -> Optimizers -> Compressed Binary IR
    """
    source_code = req.code.strip()
    if not source_code:
        raise HTTPException(status_code=400, detail="Source code cannot be empty.")

    try:
        # 1. Lexical Analysis
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()

        # 2. Syntax Analysis (AST)
        parser = Parser(tokens)
        ast = parser.parse()

        # 3. Intermediate Representation Generation (TAC)
        ir_gen = IRGenerator()
        raw_instructions = ir_gen.generate(ast)
        from copy import deepcopy
        initial_raw_instructions = [deepcopy(i) for i in raw_instructions]
        symbol_table = ir_gen.symbol_table
        constant_pool = ir_gen.constant_pool

        # 4. Control Flow Graph (CFG) Construction
        cfg = ControlFlowGraph.build(raw_instructions)
        cfg_stats_initial = cfg.get_stats()
        cfg_elements = cfg.to_cytoscape_elements()
        # Snapshot the raw-CFG block serialization NOW, before SSA renaming and
        # the optimizer mutate these Instruction objects in place. Without this,
        # the raw-CFG tab would display post-optimization instruction text.
        cfg_blocks_initial = {b_id: b.to_dict() for b_id, b in cfg.blocks.items()}

        # 5. Dominance Analysis (Dominators, IDom, DomTree, DF)
        dom = DominanceAnalyzer(cfg)
        dom.compute_all()
        dom_dict = dom.to_dict()
        dom_elements = dom.to_cytoscape_elements()

        # 6. Static Single Assignment (SSA) Transformation
        ssa_transformer = SSATransformer(cfg, dom)
        ssa_cfg = ssa_transformer.transform()
        ssa_stats = ssa_transformer.get_stats()
        ssa_instructions = ssa_cfg.linearize()
        ssa_elements = ssa_cfg.to_cytoscape_elements()

        # 7. Multi-Pass IR Optimization (Constant Folding, GVN, DCE, CFG pruning)
        optimizer = IROptimizer(ssa_cfg)
        optimized_cfg = optimizer.optimize()
        opt_instructions = optimized_cfg.linearize()
        # User-defined functions other than main are optimized on their own.
        from core.module import optimize_functions
        function_units = optimize_functions(ir_gen.functions)
        opt_stats = optimizer.stats
        opt_cfg_stats = optimized_cfg.get_stats()
        opt_elements = optimized_cfg.to_cytoscape_elements()

        # 8. Symbol Table Minification & Constant Pool Deduplication
        minified_mapping = symbol_table.minify_symbols()

        # 9. Binary Bytecode Serialization & Canonical Huffman Compression
        pipeline_metrics = IRCompressionPipeline.run(
            raw_instructions=initial_raw_instructions,
            optimized_instructions=opt_instructions,
            symbol_table=symbol_table,
            constant_pool=constant_pool,
            cfg=optimized_cfg,
            extra_units=function_units,
        )

        # 10. Advanced Architecture: Front-Coding, RPO Fallthrough, SSA Backward Deltas, Columnar SoA
        from core.advanced_compression import AdvancedIRCompressionEngine
        symbol_names = [s.name for s in symbol_table.all_symbols]
        advanced_metrics = AdvancedIRCompressionEngine.run(
            raw_instructions=initial_raw_instructions,
            optimized_instructions=opt_instructions,
            cfg=optimized_cfg,
            symbol_names=symbol_names
        )

        # 11. Multi-Algorithm Mainstream Compression Comparison Benchmark
        from core.compression_benchmarks import CompressionBenchmarkSuite
        emitter = BytecodeEmitter(symbol_table, constant_pool)
        bytecode_bytes = bytes(emitter.serialize_module([("main", opt_instructions, optimized_cfg)] + function_units))
        raw_text_bytes = len("\n".join(str(i) for i in initial_raw_instructions).encode('utf-8'))
        compression_comparison = CompressionBenchmarkSuite.run_benchmark(
            target_payload=bytecode_bytes,
            raw_ir_text_bytes=raw_text_bytes,
            custom_metrics=advanced_metrics
        )

        # 12. Decompression Phase & Lossless Semantic Fidelity Verification
        from core.decompression import DecompressionEngine
        huffman_bitstream = HuffmanCompressor.compress(bytecode_bytes)
        decompression_result = DecompressionEngine.run(
            huffman_bitstream=huffman_bitstream,
            raw_bytecode=bytecode_bytes,
            original_instructions=opt_instructions,
            emitter=emitter,
            allocator_label_map=emitter.id_to_label,
            decompression_matrix=compression_comparison.get("decompression_matrix", []),
            decompression_summary=compression_comparison.get("decompression_summary", {})
        )

        return {
            "success": True,
            "tokens": [t.to_dict() for t in tokens if t.type.name != "EOF"],
            "ast": ast.to_dict(),
            "raw_ir": {
                "instructions": [i.to_dict() for i in initial_raw_instructions],
                "text": "\n".join(str(i) for i in initial_raw_instructions),
                "count": len(initial_raw_instructions),
            },
            "cfg": {
                "blocks": cfg_blocks_initial,
                "stats": cfg_stats_initial,
                "elements": cfg_elements,
            },
            "dominance": {
                "data": dom_dict,
                "elements": dom_elements,
            },
            "ssa": {
                "instructions": [i.to_dict() for i in ssa_instructions],
                "text": "\n".join(str(i) for i in ssa_instructions),
                "stats": ssa_stats,
                "elements": ssa_elements,
            },
            "optimized_ir": {
                "instructions": [i.to_dict() for i in opt_instructions],
                "text": "\n".join(str(i) for i in opt_instructions),
                "elements": opt_elements,
                "stats": opt_stats,
                "cfg_stats": opt_cfg_stats,
            },
            "symbol_table": symbol_table.to_dict(),
            "constant_pool": constant_pool.to_dict(),
            "compression_metrics": pipeline_metrics,
            "advanced_compression": advanced_metrics,
            "register_allocation": advanced_metrics.get("register_allocation", {}),
            "compression_comparison": compression_comparison,
            "decompression": decompression_result,
        }

    except (LexerError, ParserError) as e:
        return {
            "success": False,
            "error_type": "SyntaxError",
            "message": str(e),
            "line": getattr(e, "line", 1),
            "col": getattr(e, "col", 1),
        }
    except Exception as e:
        return {
            "success": False,
            "error_type": "InternalError",
            "message": str(e),
        }


@app.post("/api/export")
def export_compressed_binary(req: CompileRequest):
    """Exports compressed binary byte package for download."""
    try:
        tokens = Lexer(req.code).tokenize()
        ast = Parser(tokens).parse()
        ir_gen = IRGenerator()
        raw_instructions = ir_gen.generate(ast)
        cfg = ControlFlowGraph.build(raw_instructions)
        dom = DominanceAnalyzer(cfg)
        dom.compute_all()
        ssa_cfg = SSATransformer(cfg, dom).transform()
        opt_cfg = IROptimizer(ssa_cfg).optimize()
        opt_instructions = opt_cfg.linearize()

        emitter = BytecodeEmitter(ir_gen.symbol_table, ir_gen.constant_pool)
        from core.module import optimize_functions
        bytecode = emitter.serialize_module([("main", opt_instructions, opt_cfg)]
                                            + optimize_functions(ir_gen.functions))
        huffman_compressed = HuffmanCompressor.compress(bytes(bytecode))

        return Response(
            content=huffman_compressed,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=compiled_compressed_ir.cir"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static frontend files
web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="static")
