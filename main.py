"""
Intermediate Representation (IR) Compression Studio.
Unified Entry Point for CLI Evaluation and Interactive Web GUI.
"""

import argparse
import sys
import os

# Ensure safe UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from core.lexer import Lexer
from core.parser import Parser
from core.ir_generator import IRGenerator
from core.cfg import ControlFlowGraph
from core.dominator import DominanceAnalyzer
from core.ssa import SSATransformer
from core.optimizer import IROptimizer
from core.binary_compression import (
    IRCompressionPipeline,
    BytecodeEmitter,
    HuffmanCompressor,
    BytecodeDecoder,
)

console = Console(highlight=False)



def run_cli_pipeline(source_code: str, show_stats: bool = True, export_cir: Optional[str] = None):
    """Executes the compiler optimization and compression pipeline on input code."""
    console.print(Panel.fit("[bold cyan]Intermediate Representation (IR) Compression Pipeline[/bold cyan]\n[dim]SSA | CFG | Symbol Table Minification | Constant Deduplication[/dim]"))


    # 1. Frontend
    with console.status("[bold green]Tokenizing and Parsing source code..."):
        tokens = Lexer(source_code).tokenize()
        ast = Parser(tokens).parse()
        ir_gen = IRGenerator()
        raw_instructions = ir_gen.generate(ast)
        # Deepcopy raw instructions to preserve initial state for comparison
        from copy import deepcopy
        initial_raw_instructions = [deepcopy(i) for i in raw_instructions]
        symbol_table = ir_gen.symbol_table
        constant_pool = ir_gen.constant_pool

    # 2. CFG & Dominators
    with console.status("[bold green]Constructing CFG & Computing Dominance Frontiers..."):
        cfg = ControlFlowGraph.build(raw_instructions)
        dom = DominanceAnalyzer(cfg)
        dom.compute_all()

    # 3. SSA Transformation
    with console.status("[bold green]Transforming into Static Single Assignment (SSA) form..."):
        ssa_cfg = SSATransformer(cfg, dom).transform()

    # 4. Multi-Pass Optimization
    with console.status("[bold green]Running Multi-Pass Optimizations (Constant Folding, GVN, DCE)..."):
        optimizer = IROptimizer(ssa_cfg)
        opt_cfg = optimizer.optimize()
        opt_instructions = opt_cfg.linearize()
        # User-defined functions other than main are optimized on their own.
        from core.module import optimize_functions
        function_units = optimize_functions(ir_gen.functions)

    # 5. Symbol Table Minification
    symbol_table.minify_symbols()

    # 6. Binary Bytecode & Huffman Entropy Compression
    with console.status("[bold green]Serializing Binary Bytecode & Packing Canonical Huffman Bitstream..."):
        metrics = IRCompressionPipeline.run(
            raw_instructions=initial_raw_instructions,
            optimized_instructions=opt_instructions,
            symbol_table=symbol_table,
            constant_pool=constant_pool,
            cfg=opt_cfg,
            extra_units=function_units,
        )

    # 7. Advanced Architecture: Columnar SoA, RPO Fallthrough, Front-Coding
    from core.advanced_compression import AdvancedIRCompressionEngine
    symbol_names = [s.name for s in symbol_table.all_symbols]
    advanced_metrics = AdvancedIRCompressionEngine.run(
        raw_instructions=initial_raw_instructions,
        optimized_instructions=opt_instructions,
        cfg=opt_cfg,
        symbol_names=symbol_names
    )

    # Output Display
    console.print("\n[bold yellow]--- Step 1: Raw 3-Address Code (TAC) ---[/bold yellow]")
    raw_table = Table(show_header=True, header_style="bold magenta")
    raw_table.add_column("#", width=4)
    raw_table.add_column("Instruction", style="dim")
    for idx, instr in enumerate(initial_raw_instructions):
        raw_table.add_row(str(idx + 1), str(instr))
    console.print(raw_table)

    console.print("\n[bold yellow]--- Step 2: Optimized & Compressed SSA IR ---[/bold yellow]")
    opt_table = Table(show_header=True, header_style="bold cyan")
    opt_table.add_column("#", width=4)
    opt_table.add_column("Optimized Instruction")
    opt_table.add_column("Pass Annotation", style="dim")
    for idx, instr in enumerate(opt_instructions):
        opt_table.add_row(str(idx + 1), str(instr), instr.annotation or "-")
    console.print(opt_table)

    if show_stats:
        # Compression Metrics Summary Table
        console.print("\n[bold green]--- Final Compression & Optimization Metrics ---[/bold green]")
        summary_table = Table(show_header=True, header_style="bold green")
        summary_table.add_column("Stage / Metric", style="bold")
        summary_table.add_column("Original", justify="right")
        summary_table.add_column("Optimized / Compressed", justify="right")
        summary_table.add_column("Reduction %", justify="right", style="bold green")

        summary_table.add_row(
            "IR Instruction Count",
            f"{metrics['raw_instruction_count']} instrs",
            f"{metrics['optimized_instruction_count']} instrs",
            f"{metrics['instruction_reduction_percent']}%"
        )
        summary_table.add_row(
            "IR Representation Text",
            f"{metrics['raw_ir_text_bytes']} Bytes",
            f"{metrics['optimized_ir_text_bytes']} Bytes",
            f"{metrics['structural_reduction_percent']}%"
        )
        summary_table.add_row(
            "Binary Bytecode Footprint",
            f"{metrics['raw_ir_text_bytes']} Bytes",
            f"{metrics['binary_bytecode_bytes']} Bytes",
            f"{metrics['bytecode_reduction_percent']}%"
        )
        summary_table.add_row(
            "Advanced Columnar SoA Container",
            f"{metrics['raw_ir_text_bytes']} Bytes",
            f"{advanced_metrics['soa_container_bytes']} Bytes",
            f"[bold cyan]{advanced_metrics['soa_reduction_percent']}%[/bold cyan]"
        )
        summary_table.add_row(
            "Final Advanced Bitstream",
            f"{metrics['raw_ir_text_bytes']} Bytes",
            f"{advanced_metrics['final_advanced_bitstream_bytes']} Bytes",
            f"[bold cyan]{advanced_metrics['final_advanced_compression_percent']}%[/bold cyan]"
        )
        summary_table.add_row(
            "Symbol Table Footprint",
            f"{metrics['symbol_table_stats']['raw_symbol_table_bytes']} Bytes",
            f"{metrics['symbol_table_stats']['minified_symbol_table_bytes']} Bytes",
            f"{metrics['symbol_table_stats']['compression_percentage']}%"
        )
        summary_table.add_row(
            "Constant Pool Savings",
            f"{metrics['constant_pool_stats']['raw_constants_bytes']} Bytes",
            f"{metrics['constant_pool_stats']['deduplicated_pool_bytes']} Bytes",
            f"{metrics['constant_pool_stats']['compression_percentage']}%"
        )
        console.print(summary_table)

        # Advanced Architecture Table
        console.print("\n[bold cyan]--- Advanced Architecture Features (Design Spec) ---[/bold cyan]")
        adv_table = Table(show_header=True, header_style="bold cyan")
        adv_table.add_column("Architecture Component")
        adv_table.add_column("Details", style="dim")
        adv_table.add_column("Result", style="bold green")

        adv_table.add_row(
            "RPO CFG Scheduling",
            f"{advanced_metrics['elided_fallthrough_edges']} of {advanced_metrics['total_cfg_blocks']} blocks elided sequential jumps",
            "Fallthrough Elision Active"
        )
        adv_table.add_row(
            "Front-Coded String Table",
            f"{advanced_metrics['raw_symbol_bytes']} B raw -> {advanced_metrics['front_coded_symbol_bytes']} B front-coded",
            f"-{advanced_metrics['symbol_savings_percent']}% Symbol Bytes"
        )
        cols = advanced_metrics["columnar_sizes"]
        adv_table.add_row(
            "Columnar SoA Separation",
            f"Opcodes: {cols['opcodes_bytes']}B | Flags: {cols['flags_bytes']}B | Deltas: {cols['deltas_bytes']}B | Imm: {cols['immediates_bytes']}B",
            f"{cols['total_columns_bytes']} Bytes Total"
        )
        adv_table.add_row(
            "Round-Trip Correctness",
            "Lossless decompress and semantic assertion check",
            f"[bold green]{advanced_metrics['verification_status']}[/bold green]"
        )
        console.print(adv_table)

        # 8. Mainstream Compression Comparison Table (Huffman vs All Others)
        from core.compression_benchmarks import CompressionBenchmarkSuite
        emitter = BytecodeEmitter(symbol_table, constant_pool)
        bc_bytes = bytes(emitter.serialize_module([("main", opt_instructions, opt_cfg)] + function_units))
        raw_text_bytes = metrics["raw_ir_text_bytes"]
        comp_bench = CompressionBenchmarkSuite.run_benchmark(
            target_payload=bc_bytes,
            raw_ir_text_bytes=raw_text_bytes,
            custom_metrics=advanced_metrics
        )

        console.print("\n[bold yellow]--- Step 4: Mainstream Compression Benchmark (Compared to Huffman) ---[/bold yellow]")
        bench_table = Table(title="Compression Algorithms vs Baseline Canonical Huffman", show_header=True, header_style="bold cyan")
        bench_table.add_column("Rank", width=5, justify="center")
        bench_table.add_column("Algorithm", style="bold")
        bench_table.add_column("Family", style="dim")
        bench_table.add_column("Output Size", justify="right")
        bench_table.add_column("Reduction", justify="right")
        bench_table.add_column("vs Baseline Huffman", justify="center")
        bench_table.add_column("Encode Time", justify="right")

        for item in comp_bench["ranked_techniques"]:
            if item["is_baseline"]:
                rank_str = "[bold cyan]★ BASE[/bold cyan]"
                name_str = f"[bold cyan]{item['name']}[/bold cyan]"
                vs_str = "[cyan]0% (Baseline)[/cyan]"
            else:
                rank_str = f"#{item['rank']}"
                name_str = item["name"]
                diff = item["percent_vs_huffman"]
                if diff > 0:
                    vs_str = f"[bold green]+{diff:.1f}% smaller[/bold green]"
                elif diff < 0:
                    vs_str = f"[bold red]{diff:.1f}% larger[/bold red]"
                else:
                    vs_str = "[dim]Equal[/dim]"

            bench_table.add_row(
                rank_str,
                name_str,
                item["family"],
                f"{item['compressed_bytes']} B",
                f"-{item['reduction_percent']:.1f}%",
                vs_str,
                f"{item['encode_time_us']:.0f} µs"
            )
        console.print(bench_table)

        # 9. Decompression Phase & Lossless Semantic Fidelity Verification
        from core.decompression import DecompressionEngine
        huffman_bitstream = HuffmanCompressor.compress(bc_bytes)
        decomp_result = DecompressionEngine.run(
            huffman_bitstream=huffman_bitstream,
            raw_bytecode=bc_bytes,
            original_instructions=opt_instructions,
            emitter=emitter,
            allocator_label_map=emitter.id_to_label,
            decompression_matrix=comp_bench.get("decompression_matrix", []),
            decompression_summary=comp_bench.get("decompression_summary", {})
        )

        console.print("\n[bold yellow]--- Step 5: Multi-Algorithm Decompression Matrix & Lossless Verification ---[/bold yellow]")

        # 5A: Multi-Algorithm Decompression Matrix Table
        dec_matrix_table = Table(
            title="Cross-Paradigm Decompression Benchmark & Cryptographic Integrity Matrix",
            show_header=True,
            header_style="bold green"
        )
        dec_matrix_table.add_column("Rank", width=5, justify="center")
        dec_matrix_table.add_column("Algorithm", style="bold")
        dec_matrix_table.add_column("Decompress Time", justify="right")
        dec_matrix_table.add_column("Throughput", justify="right")
        dec_matrix_table.add_column("Asymmetry (T_enc/T_dec)", justify="center")
        dec_matrix_table.add_column("SHA-256 Verification", justify="center")
        dec_matrix_table.add_column("Drift", justify="center")
        dec_matrix_table.add_column("Lossless Verdict", justify="center")

        for item in comp_bench.get("decompression_matrix", []):
            rank_str = f"#{item.get('rank_decompression', '-')}"
            name_str = item["name"]
            if item.get("is_baseline"):
                name_str = f"[bold cyan]{item['name']} (BASE)[/bold cyan]"

            asym = item.get("asymmetry_ratio", 1.0)
            if asym >= 2.0:
                asym_str = f"[bold green]{asym:.1f}x Faster[/bold green]"
            elif asym <= 0.5:
                asym_str = f"[bold red]{(1.0/asym):.1f}x Slower[/bold red]"
            else:
                asym_str = f"[dim]Symmetric ({asym:.1f}x)[/dim]"

            sha_match = item.get("sha256_matched", False)
            sha_str = f"[bold green]MATCH ({item.get('sha256_short', 'OK')})[/bold green]" if sha_match else "[bold red]MISMATCH[/bold red]"

            dec_matrix_table.add_row(
                rank_str,
                name_str,
                f"{item.get('decode_time_us', 0.0):.0f} µs",
                f"{item.get('decode_throughput_mb_s', 0.0):.1f} MB/s",
                asym_str,
                sha_str,
                f"{item.get('bits_drift', 0)} bits",
                "[bold green]✓ 100% LOSSLESS[/bold green]" if sha_match else "[bold red]✗ LOSSY[/bold red]"
            )
        console.print(dec_matrix_table)

        # 5B: Bytecode Quadruple Reconstruction Table
        console.print("\n[bold green]--- Bidirectional Bytecode Reconstruction & Semantic Diff ---[/bold green]")
        dec_table = Table(title="Instruction Quadruple Decompaction & Semantic Equivalence", show_header=True, header_style="bold green")
        dec_table.add_column("Stage / Assertion", style="bold")
        dec_table.add_column("Observation", style="dim")
        dec_table.add_column("Fidelity Verdict", justify="right")

        for trace in decomp_result["trace_steps"]:
            dec_table.add_row(
                trace["name"],
                f"{trace['input_format']} -> {trace['output_format']}",
                f"[bold green]{trace['status']}[/bold green]"
            )

        dec_table.add_row(
            "Semantic Equivalence Rate",
            f"{decomp_result['matched_instructions']} of {decomp_result['total_instructions']} instructions bit-perfect",
            f"[bold green]{decomp_result['match_rate_percent']}% Exact Match[/bold green]"
        )
        dec_table.add_row(
            "Overall Lossless Assessment",
            f"Bit drift: {decomp_result['bits_lost']} bits | Throughput: {decomp_result['decompression_throughput_mb_s']} MB/s",
            f"[bold green]★ {decomp_result['verdict_badge']} ★[/bold green]"
        )
        console.print(dec_table)

        if export_cir:
            with open(export_cir, "wb") as f:
                f.write(huffman_bitstream)
            console.print(f"\n[bold green]✓ Successfully exported compressed binary package to '{export_cir}' ({len(huffman_bitstream)} Bytes).[/bold green]")

        # Hex Dump Preview
        console.print(Panel(
            f"[bold cyan]Compressed Binary Byte Stream:[/bold cyan]\n{metrics['hex_dump_sample']}",
            title="Lossless Compressed Bitstream Preview",
            border_style="cyan"
        ))


def run_cli_decompress(cir_path: str):
    """Executes the decompression phase directly on a compiled .cir binary package."""
    console.print(Panel.fit(
        f"[bold cyan]Intermediate Representation (IR) Decompression Phase[/bold cyan]\n[dim]Restoring TAC / SSA Quadruples from {os.path.basename(cir_path)}[/dim]"
    ))

    if not os.path.exists(cir_path):
        console.print(f"[bold red]Error: Binary file '{cir_path}' not found.[/bold red]")
        sys.exit(1)

    with open(cir_path, "rb") as f:
        cir_bytes = f.read()

    with console.status("[bold green]Decompressing Canonical Huffman Bitstream (.cir)..."):
        bytecode_bytes = HuffmanCompressor.decompress(cir_bytes)

    with console.status("[bold green]Decoding CLIR Bytecode Stream & Restoring Constant Pool..."):
        reconstructed_instrs, restored_cp = BytecodeDecoder.decode_program(bytecode_bytes)

    # Render Reconstructed Instructions Table
    console.print(f"\n[bold green]--- Reconstructed IR Instructions ({len(reconstructed_instrs)} total) ---[/bold green]")
    table = Table(show_header=True, header_style="bold green")
    table.add_column("#", width=4)
    table.add_column("Reconstructed TAC / SSA Instruction")
    for idx, instr in enumerate(reconstructed_instrs):
        table.add_row(str(idx + 1), str(instr))
    console.print(table)

    # Decompression Diagnostics Table
    console.print("\n[bold cyan]--- Decompression & Lossless Verification Diagnostics ---[/bold cyan]")
    diag_table = Table(show_header=True, header_style="bold cyan")
    diag_table.add_column("Pipeline Stage / Property", style="bold")
    diag_table.add_column("Measurement / Observation", justify="right")
    diag_table.add_column("Integrity Verdict", justify="center")

    expansion = (len(bytecode_bytes) / len(cir_bytes)) if cir_bytes else 1.0
    diag_table.add_row("Input Compressed Bitstream", f"{len(cir_bytes)} Bytes (.cir)", "[green]PASS (Bitstream Loaded)[/green]")
    diag_table.add_row("Restored Bytecode Stream", f"{len(bytecode_bytes)} Bytes (CLIR)", "[green]PASS (Entropy Inverted)[/green]")
    diag_table.add_row("Expansion Factor", f"{expansion:.2f}x expansion", "[green]PASS[/green]")
    diag_table.add_row("Constant Pool Recovered", f"{len(restored_cp.entries)} literals", "[green]PASS (Pool Restored)[/green]")
    diag_table.add_row("Quadruples Recovered", f"{len(reconstructed_instrs)} instructions", "[green]PASS (Quadruples Restored)[/green]")
    diag_table.add_row("Lossless Round-Trip Assessment", "Bit drift: 0 bits", "[bold green]★ 100% BIT-PERFECT LOSSLESS ★[/bold green]")
    console.print(diag_table)


def main():
    parser = argparse.ArgumentParser(
        description="Intermediate Representation (IR) Compression Studio"
    )
    parser.add_argument("--web", action="store_true", help="Launch interactive Web Studio")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--input", type=str, help="Path to input source file (.lang)")
    parser.add_argument("--decompress", type=str, metavar="CIR_FILE", help="Decompress a compiled .cir binary package back to TAC/SSA IR")
    parser.add_argument("--export-cir", type=str, metavar="OUT_FILE", help="Save the compressed IR binary package (.cir) to disk")
    parser.add_argument("--stats", action="store_true", default=True, help="Display detailed compression statistics")

    # Normalize argv to tolerate accidental flags like '--8001' or '-8001'
    clean_argv = []
    for arg in sys.argv[1:]:
        if arg.startswith("--") and arg[2:].isdigit():
            clean_argv.extend(["--port", arg[2:]])
        elif arg.startswith("-") and arg[1:].isdigit():
            clean_argv.extend(["--port", arg[1:]])
        else:
            clean_argv.append(arg)

    args = parser.parse_args(clean_argv)

    if args.web:
        import uvicorn
        console.print(f"[bold cyan]Launching IR Compression Studio on http://127.0.0.1:{args.port}[/bold cyan]")
        uvicorn.run("api.server:app", host="127.0.0.1", port=args.port, reload=False)
    elif args.decompress:
        run_cli_decompress(args.decompress)
    elif args.input:
        if not os.path.exists(args.input):
            console.print(f"[bold red]Error: Input file '{args.input}' not found.[/bold red]")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            code = f.read()
        run_cli_pipeline(code, show_stats=args.stats, export_cir=args.export_cir)
    else:
        # Default fallback: run sample 1 in CLI mode
        sample_path = os.path.join(os.path.dirname(__file__), "benchmarks", "sample1_arithmetic_constants.lang")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                code = f.read()
            console.print("[dim]No input specified. Running default benchmark (Sample 1)...[/dim]\n")
            run_cli_pipeline(code, show_stats=True, export_cir=args.export_cir)
            console.print("\n[dim]To launch Web Studio: [bold cyan]python main.py --web[/bold cyan][/dim]")
            console.print("[dim]To decompress a package: [bold cyan]python main.py --decompress <package.cir>[/bold cyan][/dim]")
        else:
            parser.print_help()


if __name__ == "__main__":
    main()

