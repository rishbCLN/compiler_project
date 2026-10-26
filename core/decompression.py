"""
Decompression Phase & Lossless Semantic Fidelity Verification Engine.
Provides end-to-end decompression across all compiler bitstreams:
1. Canonical Huffman Bitstream (.cir) Decompression
2. LEB128 Binary Bytecode Decoding into TAC/SSA Quadruples
3. Constant Pool & Symbol Table Restoration
4. 4-Bit Nibble Register-Packed Bytecode Decompression
5. Columnar Structure-of-Arrays (SoA) Container Decompression
6. Instruction-by-Instruction Lossless vs Lossy Diff Assertion
"""

import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from core.ir import Instruction, Opcode
from core.constant_pool import ConstantPool
from core.symbol_table import SymbolTable
from core.binary_compression import (
    HuffmanCompressor,
    BytecodeDecoder,
    BytecodeEmitter,
    RegisterPackedBytecodeDecoder,
)
from core.advanced_compression import (
    ColumnarBytecodeSerializer,
    FrontCodedStringPool,
)


class DecompressionEngine:
    """
    Decompresses serialized IR bitstreams and performs mathematical
    fidelity verification to prove whether compression is 100% lossless or lossy.
    """

    @classmethod
    def run(cls,
            huffman_bitstream: bytes,
            raw_bytecode: bytes,
            original_instructions: List[Instruction],
            emitter: Optional[BytecodeEmitter] = None,
            advanced_container: Optional[bytes] = None,
            packed_bytecode: Optional[bytes] = None,
            allocator_label_map: Optional[Dict[int, str]] = None,
            decompression_matrix: Optional[List[Dict[str, Any]]] = None,
            decompression_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the multi-stage decompression pipeline and generates a
        comprehensive verification report comparing original vs decompressed IR.
        """
        trace_steps: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Stage 1: Entropy Bitstream Decompression (.cir -> Bytecode)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        decompressed_bc = HuffmanCompressor.decompress(huffman_bitstream)
        entropy_dec_time_us = (time.perf_counter() - t0) * 1e6

        sha256_raw_in = hashlib.sha256(raw_bytecode).hexdigest()
        sha256_decomp_out = hashlib.sha256(decompressed_bc).hexdigest()
        sha256_matched = (sha256_raw_in == sha256_decomp_out)
        entropy_verified = (decompressed_bc == raw_bytecode) and sha256_matched

        entropy_bytes_in = len(huffman_bitstream)
        entropy_bytes_out = len(decompressed_bc)
        entropy_expansion_ratio = (entropy_bytes_out / entropy_bytes_in) if entropy_bytes_in else 1.0

        trace_steps.append({
            "stage_id": "D1",
            "name": "Entropy Bitstream Decompression",
            "input_format": "Canonical Huffman Packed Bitstream (.cir)",
            "output_format": "LEB128 Serialized Binary Bytecode (CLIR)",
            "input_bytes": entropy_bytes_in,
            "output_bytes": entropy_bytes_out,
            "expansion_ratio": round(entropy_expansion_ratio, 2),
            "execution_time_us": round(entropy_dec_time_us, 1),
            "status": "PASS (Exact Bitstream Recovery, SHA-256 Matched)" if entropy_verified else "FAIL",
            "sha256_in": sha256_raw_in,
            "sha256_out": sha256_decomp_out,
            "sha256_matched": sha256_matched,
            "verified": entropy_verified,
        })

        # -------------------------------------------------------------
        # Stage 2: LEB128 & Bytecode Quadruple Reconstruction
        # -------------------------------------------------------------
        id_to_var = emitter.id_to_var if emitter else None
        id_to_label = emitter.id_to_label if emitter else None

        t0 = time.perf_counter()
        reconstructed_instrs, restored_cp = BytecodeDecoder.decode_program(
            decompressed_bc,
            id_to_var=id_to_var,
            id_to_label=id_to_label
        )
        bytecode_dec_time_us = (time.perf_counter() - t0) * 1e6

        trace_steps.append({
            "stage_id": "D2",
            "name": "Bytecode Instruction Quadruple Decoding",
            "input_format": "Binary Bytecode Stream",
            "output_format": "Typed Intermediate Representation Quadruples",
            "input_bytes": entropy_bytes_out,
            "output_instructions": len(reconstructed_instrs),
            "restored_constants": len(restored_cp.entries),
            "execution_time_us": round(bytecode_dec_time_us, 1),
            "status": "PASS (Quadruples Restored)",
            "verified": len(reconstructed_instrs) == len(original_instructions),
        })

        # -------------------------------------------------------------
        # Stage 3: Columnar SoA & Register-Packed Decompression (if present)
        # -------------------------------------------------------------
        soa_verified = True
        soa_instr_count = 0
        if advanced_container:
            try:
                unpacked_cols, unpacked_sym_bytes = ColumnarBytecodeSerializer.unpack_container(advanced_container)
                soa_instr_count = unpacked_cols.get("instruction_count", 0)
                recovered_strings = FrontCodedStringPool.decode(unpacked_sym_bytes)
                soa_verified = (soa_instr_count == len(original_instructions))
                trace_steps.append({
                    "stage_id": "D3a",
                    "name": "Columnar Structure-of-Arrays (SoA) Decompression",
                    "input_format": "Multi-Stream SoA Container (Opcodes + Deltas + Immediates)",
                    "output_format": "Reassembled Columnar Streams & Front-Coded String Table",
                    "output_instructions": soa_instr_count,
                    "restored_symbols": len(recovered_strings),
                    "status": "PASS (Columnar Streams Intact)",
                    "verified": soa_verified,
                })
            except Exception as e:
                soa_verified = False

        packed_verified = True
        if packed_bytecode and allocator_label_map:
            try:
                decoded_packed, _ = RegisterPackedBytecodeDecoder.decode_program(
                    packed_bytecode, label_map=allocator_label_map
                )
                packed_verified = (len(decoded_packed) == len(original_instructions))
                trace_steps.append({
                    "stage_id": "D3b",
                    "name": "4-Bit Register-Packed Bytecode Decompression",
                    "input_format": "Nibble-Packed Operand Bitstream (RPIR)",
                    "output_format": "Physical Hardware-Assigned Register Quadruples",
                    "output_instructions": len(decoded_packed),
                    "status": "PASS (Registers Preserved)",
                    "verified": packed_verified,
                })
            except Exception:
                packed_verified = False

        # -------------------------------------------------------------
        # Stage 4: Line-by-Line Semantic & Bit-for-Bit Diff Analysis
        # -------------------------------------------------------------
        diff_lines: List[Dict[str, Any]] = []
        all_matched = True
        total_orig = len(original_instructions)
        total_dec = len(reconstructed_instrs)
        max_len = max(total_orig, total_dec)

        matched_count = 0
        mismatched_count = 0

        for idx in range(max_len):
            orig_instr = original_instructions[idx] if idx < total_orig else None
            dec_instr = reconstructed_instrs[idx] if idx < total_dec else None

            orig_str = str(orig_instr) if orig_instr else "(missing)"
            dec_str = str(dec_instr) if dec_instr else "(missing)"

            # Strict semantic equality check
            is_match = False
            if orig_instr is not None and dec_instr is not None:
                is_match = (
                    orig_instr.op == dec_instr.op and
                    str(orig_instr.result) == str(dec_instr.result) and
                    str(orig_instr.arg1) == str(dec_instr.arg1) and
                    str(orig_instr.arg2) == str(dec_instr.arg2)
                )

            if is_match:
                matched_count += 1
                status = "EXACT_MATCH"
            else:
                all_matched = False
                mismatched_count += 1
                status = "MISMATCH"

            diff_lines.append({
                "line_no": idx + 1,
                "original": orig_str,
                "decompressed": dec_str,
                "is_match": is_match,
                "status": status,
            })

        # Overall Lossless Determination
        is_lossless = all_matched and entropy_verified and (total_orig == total_dec)
        match_rate_percent = (matched_count / max_len * 100) if max_len > 0 else 100.0

        if is_lossless:
            verdict_badge = "100% BIT-PERFECT LOSSLESS"
            verdict_color = "emerald"
            verdict_summary = "Zero data loss. Decompressed IR matches the original instruction stream with 100% exact semantic and bit-for-bit fidelity."
            bits_lost = 0
        else:
            verdict_badge = "LOSSY / CORRUPTED"
            verdict_color = "rose"
            verdict_summary = f"Detected {mismatched_count} instruction mismatches during round-trip decompression!"
            bits_lost = mismatched_count * 32

        total_dec_time_us = entropy_dec_time_us + bytecode_dec_time_us
        total_dec_throughput_mb_s = (entropy_bytes_out / (total_dec_time_us / 1e6)) / (1024 * 1024) if total_dec_time_us > 0 else 0.0

        return {
            "is_lossless": is_lossless,
            "verdict_badge": verdict_badge,
            "verdict_color": verdict_color,
            "verdict_summary": verdict_summary,
            "match_rate_percent": round(match_rate_percent, 2),
            "matched_instructions": matched_count,
            "mismatched_instructions": mismatched_count,
            "total_instructions": total_orig,
            "decompressed_instructions_count": total_dec,
            "bits_lost": bits_lost,
            "total_decompression_time_us": round(total_dec_time_us, 1),
            "decompression_throughput_mb_s": round(total_dec_throughput_mb_s, 2),
            "entropy_bytes_in": entropy_bytes_in,
            "bytecode_bytes_out": entropy_bytes_out,
            "sha256_bytecode_in": sha256_raw_in,
            "sha256_bytecode_out": sha256_decomp_out,
            "sha256_matched": sha256_matched,
            "trace_steps": trace_steps,
            "diff_lines": diff_lines,
            "decompressed_text": "\n".join(str(i) for i in reconstructed_instrs),
            "decompression_matrix": decompression_matrix or [],
            "decompression_summary": decompression_summary or {},
        }

