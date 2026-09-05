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
from core.binary_compression import IRCompressionPipeline, BytecodeEmitter, HuffmanCompressor

console = Console(highlight=False)



def run_cli_pipeline(source_code: str, show_stats: bool = True):
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

    # 5. Symbol Table Minification
    symbol_table.minify_symbols()

    # 6. Binary Bytecode & Huffman Entropy Compression
    with console.status("[bold green]Serializing Binary Bytecode & Packing Canonical Huffman Bitstream..."):
        metrics = IRCompressionPipeline.run(
            raw_instructions=raw_instructions,
            optimized_instructions=opt_instructions,
            symbol_table=symbol_table,
            constant_pool=constant_pool
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

        # Hex Dump Preview
        console.print(Panel(
            f"[bold cyan]Compressed Binary Byte Stream:[/bold cyan]\n{metrics['hex_dump_sample']}",
            title="Lossless Compressed Bitstream Preview",
            border_style="cyan"
        ))


def main():
    parser = argparse.ArgumentParser(
        description="Intermediate Representation (IR) Compression Studio"
    )
    parser.add_argument("--web", action="store_true", help="Launch interactive Web Studio")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--input", type=str, help="Path to input source file (.lang)")
    parser.add_argument("--stats", action="store_true", default=True, help="Display detailed compression statistics")

    args = parser.parse_args()

    if args.web:
        import uvicorn
        console.print(f"[bold cyan]Launching IR Compression Studio on http://127.0.0.1:{args.port}[/bold cyan]")
        uvicorn.run("api.server:app", host="127.0.0.1", port=args.port, reload=False)
    elif args.input:
        if not os.path.exists(args.input):
            console.print(f"[bold red]Error: Input file '{args.input}' not found.[/bold red]")
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            code = f.read()
        run_cli_pipeline(code, show_stats=args.stats)
    else:
        # Default fallback: run sample 1 in CLI mode
        sample_path = os.path.join(os.path.dirname(__file__), "benchmarks", "sample1_arithmetic_constants.lang")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                code = f.read()
            console.print("[dim]No input specified. Running default benchmark (Sample 1)...[/dim]\n")
            run_cli_pipeline(code, show_stats=True)
            console.print("\n[dim]To launch Web Studio: [bold cyan]python main.py --web[/bold cyan][/dim]")
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
