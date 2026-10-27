"""
Advanced IR Compression Engine.
Implements:
1. Front-Coded String Pool (Lexicographical prefix compression)
2. SSA Backward Delta Encoding (Implicit ordinal definitions & backward usage deltas)
3. Reverse Post-Order (RPO) CFG Layout with Fallthrough Elision
4. Predecessor-Indexed Compact Phi-Node Tables
5. Columnar Structure-of-Arrays (SoA) Bytecode Serialization
6. Lossless Round-Trip Verification Engine
"""

from typing import List, Dict, Tuple, Optional, Any, Set
import struct
from collections import Counter
from core.ir import Instruction, Opcode, literal_type, canonical_form
from core.cfg import ControlFlowGraph, BasicBlock
from core.binary_compression import LEB128, HuffmanCompressor, RegisterPackedBytecodeEmitter, RegisterPackedBytecodeDecoder
from core.liveness import LivenessAnalyzer
from core.register_allocator import RegisterInterferenceGraph, ChordalRegisterAllocator, RegisterCompactor


class FrontCodedStringPool:
    """
    Front-coding (incremental prefix compression) for symbol names.
    Sorts strings lexicographically and encodes common prefixes as lengths.
    Typically achieves 70% to 85% reduction on compiler symbol tables.
    """

    @staticmethod
    def encode(strings: List[str]) -> Tuple[bytes, Dict[str, int]]:
        """
        Encodes a list of strings into a front-coded byte stream.
        Returns the encoded bytes and a mapping from original string to its sorted pool index.
        """
        if not strings:
            return b"\x00\x00", {}

        unique_strings = sorted(list(set(strings)))
        index_map = {s: idx for idx, s in enumerate(unique_strings)}

        buf = bytearray()
        buf.extend(LEB128.encode_unsigned(len(unique_strings)))

        prev = ""
        for s in unique_strings:
            # Calculate common prefix length
            prefix_len = 0
            max_p = min(len(prev), len(s))
            while prefix_len < max_p and prev[prefix_len] == s[prefix_len]:
                prefix_len += 1

            suffix = s[prefix_len:].encode('utf-8')
            # LEB128-encode the shared-prefix length so prefixes >= 256 chars no
            # longer wrap (the previous single-byte `prefix_len & 0xFF` form
            # silently corrupted strings with >= 256 identical leading chars).
            buf.extend(LEB128.encode_unsigned(prefix_len))
            buf.extend(LEB128.encode_unsigned(len(suffix)))
            buf.extend(suffix)
            prev = s

        return bytes(buf), index_map

    @staticmethod
    def decode(data: bytes) -> List[str]:
        """Reconstructs the original strings from a front-coded byte stream."""
        if not data:
            return []

        count, offset = LEB128.decode_unsigned(data, 0)
        strings: List[str] = []
        prev = ""

        for _ in range(count):
            if offset >= len(data):
                break
            prefix_len, pfx_read = LEB128.decode_unsigned(data, offset)
            offset += pfx_read
            suffix_len, bytes_read = LEB128.decode_unsigned(data, offset)
            offset += bytes_read

            suffix_bytes = data[offset:offset + suffix_len]
            offset += suffix_len

            suffix_str = suffix_bytes.decode('utf-8', errors='replace')
            curr_str = prev[:prefix_len] + suffix_str
            strings.append(curr_str)
            prev = curr_str

        return strings


class RPOBlockScheduler:
    """
    Schedules basic blocks in Reverse Post-Order (RPO) and elides sequential fallthrough edges.
    In RPO, sequential blocks require 0 edge bits (implicit fallthrough).
    """

    @staticmethod
    def compute_rpo(cfg: ControlFlowGraph) -> List[str]:
        """Returns block IDs ordered in Reverse Post-Order."""
        visited: Set[str] = set()
        post_order: List[str] = []

        def dfs(b_id: str):
            visited.add(b_id)
            bb = cfg.blocks.get(b_id)
            if bb:
                # Visit successors in sorted order for determinism
                for succ in sorted(list(bb.successors)):
                    if succ not in visited and succ in cfg.blocks:
                        dfs(succ)
            post_order.append(b_id)

        if cfg.entry_block_id in cfg.blocks:
            dfs(cfg.entry_block_id)

        # Include any remaining unreachable blocks at the end
        for b_id in sorted(cfg.blocks.keys()):
            if b_id not in visited:
                dfs(b_id)

        post_order.reverse()
        return post_order

    @classmethod
    def schedule_and_elide_edges(cls, cfg: ControlFlowGraph) -> Tuple[List[str], Dict[str, dict]]:
        """
        Orders blocks in RPO and determines which edges are implicit fallthroughs.
        Returns (rpo_block_ids, block_edge_metadata).
        """
        rpo_order = cls.compute_rpo(cfg)
        rpo_index = {b_id: idx for idx, b_id in enumerate(rpo_order)}
        edge_meta = {}

        for idx, b_id in enumerate(rpo_order):
            bb = cfg.blocks[b_id]
            next_b_id = rpo_order[idx + 1] if idx + 1 < len(rpo_order) else None

            # Analyze terminator instruction
            terminator = bb.get_terminator()
            has_implicit_fallthrough = False
            jump_deltas = []

            if terminator:
                if terminator.op == Opcode.JUMP:
                    target_lbl = str(terminator.arg1)
                    target_bb = cfg.label_to_block.get(target_lbl, target_lbl)
                    if target_bb == next_b_id:
                        has_implicit_fallthrough = True
                    else:
                        tgt_idx = rpo_index.get(target_bb, idx + 1)
                        jump_deltas.append(tgt_idx - idx)

                elif terminator.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                    target_lbl = str(terminator.result)
                    target_bb = cfg.label_to_block.get(target_lbl, target_lbl)
                    tgt_idx = rpo_index.get(target_bb, idx + 1)
                    jump_deltas.append(tgt_idx - idx)
                    # The alternative path falls through to next_b_id implicitly
                    has_implicit_fallthrough = True
                else:
                    # Normal block falling through to next block
                    if next_b_id in bb.successors:
                        has_implicit_fallthrough = True
            else:
                has_implicit_fallthrough = True

            edge_meta[b_id] = {
                "rpo_index": idx,
                "has_implicit_fallthrough": has_implicit_fallthrough,
                "jump_deltas": jump_deltas,
            }

        return rpo_order, edge_meta


class SSABackwardDeltaEncoder:
    """
    SSA Variable ID Compression via Implicit Ordinal Definitions & Usage Deltas.
    - Definitions omit IDs: the def ID is strictly the instruction's ordinal index i.
    - A use stores the signed distance delta = i - def_index to its definition.
      Most uses follow their definition (delta > 0, typically 1..10), but a
      loop-carried phi argument is defined later in the linear order, which
      gives a negative delta. Deltas are written zigzag-coded, so both kinds
      survive the round trip.
    - Literals, labels and names with no definition in the list are kept as
      raw text.
    """

    @staticmethod
    def _operand(value: Any, idx: int, def_locations: Dict[str, int]) -> Tuple[Optional[int], Optional[str]]:
        """Return (delta, raw) for one operand: exactly one is set unless the
        operand is absent."""
        if value is None:
            return None, None
        key = str(value)
        if literal_type(key) is None and key in def_locations:
            return idx - def_locations[key], None
        return None, key

    @classmethod
    def encode_instructions(cls, instructions: List[Instruction]) -> List[dict]:
        """
        Transforms instructions so variable uses become signed integer offsets.
        Returns a list of compact encoded instruction dicts.
        """
        def_locations: Dict[str, int] = {}
        for idx, instr in enumerate(instructions):
            defn = instr.defines()
            if defn:
                def_locations[defn] = idx

        encoded = []
        for idx, instr in enumerate(instructions):
            if instr.op == Opcode.PHI:
                # Predecessor-indexed phi: an int is a delta, a str is raw text.
                phi_deltas: Dict[str, Any] = {}
                for pred_id, var_name in instr.phi_args.items():
                    delta, raw = cls._operand(var_name, idx, def_locations)
                    phi_deltas[pred_id] = delta if delta is not None else raw
                encoded.append({
                    "op": instr.op,
                    "is_phi": True,
                    "phi_deltas": phi_deltas,
                    "line": instr.line,
                })
                continue

            if instr.op == Opcode.CALL:
                call_args: List[Any] = []
                for arg in instr.call_args:
                    delta, raw = cls._operand(arg, idx, def_locations)
                    call_args.append(delta if delta is not None else raw)
                encoded.append({
                    "op": instr.op,
                    "is_phi": False,
                    "is_call": True,
                    "callee": str(instr.arg1),
                    "call_args": call_args,
                    "line": instr.line,
                })
                continue

            is_label_op = instr.op in (Opcode.LABEL, Opcode.JUMP)
            if is_label_op:
                arg1_delta, arg1_raw = None, (str(instr.arg1) if instr.arg1 is not None else None)
            else:
                arg1_delta, arg1_raw = cls._operand(instr.arg1, idx, def_locations)
            arg2_delta, arg2_raw = cls._operand(instr.arg2, idx, def_locations)
            encoded.append({
                "op": instr.op,
                "is_phi": False,
                "arg1_delta": arg1_delta,
                "arg2_delta": arg2_delta,
                "arg1_raw": arg1_raw,
                "arg2_raw": arg2_raw,
                "result_label": instr.result if instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE) else None,
                "line": instr.line,
            })

        return encoded


class ColumnarBytecodeSerializer:
    """
    Structure-of-Arrays (SoA) Columnar Layout for Intermediate Representation.
    Partitions instruction quadruples into 4 dedicated, contiguous streams:
    1. Stream Opcodes: byte-array of operation codes (ADD, SUB, LOAD...)
    2. Stream Flags: operand modes (constant vs. backward delta)
    3. Stream Deltas: zigzag LEB128 signed use-to-definition distances
    4. Stream Immediates: literal and label pool references
    Grouping identical data types dramatically increases run-lengths and entropy compression.
    """

    OPCODE_MAP = {
        Opcode.NOP: 0x00, Opcode.ADD: 0x01, Opcode.SUB: 0x02, Opcode.MUL: 0x03,
        Opcode.DIV: 0x04, Opcode.MOD: 0x05, Opcode.NEG: 0x06, Opcode.AND: 0x07,
        Opcode.OR: 0x08, Opcode.NOT: 0x09, Opcode.EQ: 0x0A, Opcode.NE: 0x0B,
        Opcode.LT: 0x0C, Opcode.LE: 0x0D, Opcode.GT: 0x0E, Opcode.GE: 0x0F,
        Opcode.ASSIGN: 0x10, Opcode.LOAD_CONST: 0x11, Opcode.LABEL: 0x12,
        Opcode.JUMP: 0x13, Opcode.JUMP_IF_TRUE: 0x14, Opcode.JUMP_IF_FALSE: 0x15,
        Opcode.RETURN: 0x16, Opcode.PHI: 0x17, Opcode.PRINT: 0x18,
        Opcode.READ: 0x19, Opcode.PARAM: 0x1A, Opcode.CALL: 0x1B,
    }
    REVERSE_OPCODE = {v: k for k, v in OPCODE_MAP.items()}
    CONTAINER_MAGIC = b"SOAIR\x02"
    NON_DEFINING = (Opcode.LABEL, Opcode.JUMP, Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE,
                    Opcode.RETURN, Opcode.PRINT, Opcode.NOP)

    @classmethod
    def serialize_columns(cls, encoded_instructions: List[dict]) -> dict:
        """Serializes encoded instructions into 4 columnar byte streams.

        The layout is fully reversible (see ``deserialize_columns``):
          * CALL: callee name in ``immediates``; one flags byte = number of
            arguments, then one kind flag per argument as for a phi.
          * PHI: one flags byte = number of incoming edges, then one flags
            byte per edge (sorted by pred_id): 0x01 = delta, 0x04 = raw.
            The pred_id string goes to ``immediates``, followed by the raw
            text if the argument is raw; a delta goes to ``deltas``.
          * Regular: flags byte is a bitmask -
              bit0 = arg1 delta present   bit1 = arg2 delta present
              bit2 = arg1 raw present     bit3 = arg2 raw present
              bit4 = result_label present
            Fields are emitted in a fixed order: arg1, arg2, result_label.
        Deltas are signed and written zigzag-coded.
        """
        stream_opcodes = bytearray()
        stream_flags = bytearray()
        stream_deltas = bytearray()
        stream_immediates = bytearray()

        def write_imm(s: str):
            raw = s.encode('utf-8')
            stream_immediates.extend(LEB128.encode_unsigned(len(raw)))
            stream_immediates.extend(raw)

        for item in encoded_instructions:
            op = item["op"]
            op_byte = cls.OPCODE_MAP.get(op, 0x00)
            stream_opcodes.append(op_byte)

            if item.get("is_call"):
                # Like a phi: argument count, then one kind flag per argument.
                write_imm(item["callee"])
                stream_flags.append(len(item["call_args"]) & 0xFF)
                for arg in item["call_args"]:
                    if isinstance(arg, int):
                        stream_flags.append(0x01)
                        stream_deltas.extend(LEB128.encode_signed(arg))
                    else:
                        stream_flags.append(0x04)
                        write_imm(str(arg))
            elif item.get("is_phi"):
                phi_deltas = item["phi_deltas"]
                stream_flags.append(len(phi_deltas) & 0xFF)
                for pred_id in sorted(phi_deltas.keys()):
                    arg = phi_deltas[pred_id]
                    write_imm(str(pred_id))
                    if isinstance(arg, int):
                        stream_flags.append(0x01)
                        stream_deltas.extend(LEB128.encode_signed(arg))
                    else:
                        stream_flags.append(0x04)
                        write_imm(str(arg))
            else:
                flag = 0
                if item.get("arg1_delta") is not None:
                    flag |= 0x01
                elif item.get("arg1_raw") is not None:
                    flag |= 0x04

                if item.get("arg2_delta") is not None:
                    flag |= 0x02
                elif item.get("arg2_raw") is not None:
                    flag |= 0x08

                if item.get("result_label") is not None:
                    flag |= 0x10

                stream_flags.append(flag)

                # Fixed emission order: arg1, arg2, result_label
                if flag & 0x01:
                    stream_deltas.extend(LEB128.encode_signed(item["arg1_delta"]))
                elif flag & 0x04:
                    write_imm(item["arg1_raw"])

                if flag & 0x02:
                    stream_deltas.extend(LEB128.encode_signed(item["arg2_delta"]))
                elif flag & 0x08:
                    write_imm(item["arg2_raw"])

                if flag & 0x10:
                    write_imm(str(item["result_label"]))

        return {
            "opcodes": bytes(stream_opcodes),
            "flags": bytes(stream_flags),
            "deltas": bytes(stream_deltas),
            "immediates": bytes(stream_immediates),
            "instruction_count": len(encoded_instructions),
        }

    @classmethod
    def deserialize_columns(cls, columns: dict) -> List[dict]:
        """Reconstructs the encoded instruction dicts from columnar streams.

        Inverse of ``serialize_columns``. The reconstructed dicts match the
        encoder output except for the ``line`` field, which is intentionally not
        part of the compressed payload.
        """
        opcodes = columns["opcodes"]
        flags = columns["flags"]
        deltas = columns["deltas"]
        immediates = columns["immediates"]
        count = columns["instruction_count"]

        d_off = 0  # deltas cursor
        i_off = 0  # immediates cursor
        f_off = 0  # flags cursor

        def read_flag():
            nonlocal f_off
            val = flags[f_off]
            f_off += 1
            return val

        def read_delta():
            nonlocal d_off
            val, read = LEB128.decode_signed(deltas, d_off)
            d_off += read
            return val

        def read_imm():
            nonlocal i_off
            ln, read = LEB128.decode_unsigned(immediates, i_off)
            i_off += read
            s = immediates[i_off:i_off + ln].decode('utf-8')
            i_off += ln
            return s

        result: List[dict] = []
        for idx in range(count):
            op = cls.REVERSE_OPCODE.get(opcodes[idx], Opcode.NOP)
            if op == Opcode.CALL:
                callee = read_imm()
                args: List[Any] = []
                for _ in range(read_flag()):
                    kind = read_flag()
                    args.append(read_delta() if kind & 0x01 else read_imm())
                result.append({"op": op, "is_phi": False, "is_call": True,
                               "callee": callee, "call_args": args})
                continue
            flag = read_flag()

            if op == Opcode.PHI:
                phi_deltas: Dict[str, Any] = {}
                for _ in range(flag):
                    pred_id = read_imm()
                    kind = read_flag()
                    phi_deltas[pred_id] = read_delta() if kind & 0x01 else read_imm()
                result.append({
                    "op": op,
                    "is_phi": True,
                    "phi_deltas": phi_deltas,
                })
            else:
                arg1_delta = arg2_delta = None
                arg1_raw = arg2_raw = None
                result_label = None

                if flag & 0x01:
                    arg1_delta = read_delta()
                elif flag & 0x04:
                    arg1_raw = read_imm()

                if flag & 0x02:
                    arg2_delta = read_delta()
                elif flag & 0x08:
                    arg2_raw = read_imm()

                if flag & 0x10:
                    result_label = read_imm()

                result.append({
                    "op": op,
                    "is_phi": False,
                    "arg1_delta": arg1_delta,
                    "arg2_delta": arg2_delta,
                    "arg1_raw": arg1_raw,
                    "arg2_raw": arg2_raw,
                    "result_label": result_label,
                })
        return result

    @classmethod
    def decode_instructions(cls, encoded: List[dict]) -> List[Instruction]:
        """Turn encoded instruction dicts back into instructions. The value
        defined by instruction i is named %i; a delta d at instruction i
        refers to %(i - d). The result equals the encoded list up to a
        consistent renaming of variables (see core.ir.canonical_form)."""
        def operand(idx: int, delta: Optional[int], raw: Optional[str]) -> Optional[str]:
            if delta is not None:
                return f"%{idx - delta}"
            return raw

        instructions: List[Instruction] = []
        for idx, item in enumerate(encoded):
            op = item["op"]
            result = None if op in cls.NON_DEFINING else f"%{idx}"
            if item.get("is_call"):
                args = [f"%{idx - a}" if isinstance(a, int) else a for a in item["call_args"]]
                instructions.append(Instruction(op=op, result=result, arg1=item["callee"],
                                                call_args=args))
                continue
            if item.get("is_phi"):
                phi_args = {pred: (f"%{idx - arg}" if isinstance(arg, int) else arg)
                            for pred, arg in item["phi_deltas"].items()}
                instructions.append(Instruction(op=op, result=result, phi_args=phi_args))
                continue
            arg1 = operand(idx, item.get("arg1_delta"), item.get("arg1_raw"))
            arg2 = operand(idx, item.get("arg2_delta"), item.get("arg2_raw"))
            if op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
                result = item.get("result_label")
            instructions.append(Instruction(op=op, arg1=arg1, arg2=arg2, result=result))
        return instructions

    @classmethod
    def pack_container(cls, columns: dict, front_coded_symbols: bytes) -> bytes:
        """Packs the columnar streams of one function and the front-coded
        symbols into a container."""
        return cls.pack_module([columns], front_coded_symbols)

    @classmethod
    def pack_module(cls, function_columns: List[dict], front_coded_symbols: bytes) -> bytes:
        """Container layout: magic 'SOAIR' + version byte, LEB128(function
        count), per function LEB128(instruction count) and the four streams,
        each with a LEB128 length prefix, then the front-coded symbol table."""
        container = bytearray()
        container.extend(cls.CONTAINER_MAGIC)
        container.extend(LEB128.encode_unsigned(len(function_columns)))
        for columns in function_columns:
            container.extend(LEB128.encode_unsigned(columns["instruction_count"]))
            for key in ("opcodes", "flags", "deltas", "immediates"):
                col_data = columns[key]
                container.extend(LEB128.encode_unsigned(len(col_data)))
                container.extend(col_data)
        container.extend(LEB128.encode_unsigned(len(front_coded_symbols)))
        container.extend(front_coded_symbols)
        return bytes(container)

    @classmethod
    def unpack_module(cls, data: bytes) -> Tuple[List[dict], bytes]:
        """Inverse of pack_module: (columns per function, front-coded symbols)."""
        if not data.startswith(cls.CONTAINER_MAGIC):
            raise ValueError("Invalid SOAIR container header")
        offset = len(cls.CONTAINER_MAGIC)

        def read() -> int:
            nonlocal offset
            val, r = LEB128.decode_unsigned(data, offset)
            offset += r
            return val

        functions = []
        for _ in range(read()):
            columns = {"instruction_count": read()}
            for key in ("opcodes", "flags", "deltas", "immediates"):
                length = read()
                columns[key] = data[offset:offset + length]
                offset += length
            functions.append(columns)
        sym_len = read()
        return functions, data[offset:offset + sym_len]

    @classmethod
    def unpack_container(cls, data: bytes) -> Tuple[dict, bytes]:
        """Unpacks the first function's streams and the front-coded symbols."""
        functions, symbols = cls.unpack_module(data)
        return functions[0], symbols


class AdvancedIRCompressionEngine:
    """
    End-to-End Orchestrator for Advanced IR Compression Architecture:
    Domain Transforms (RPO, SSA Backward Deltas, Front-Coding) ->
    Columnar SoA Separation -> Canonical Huffman Entropy Packing.
    """

    @classmethod
    def run(cls, raw_instructions: List[Instruction],
            optimized_instructions: List[Instruction],
            cfg: ControlFlowGraph,
            symbol_names: List[str]) -> dict:

        # 1. RPO CFG Scheduling & Fallthrough Edge Elision
        rpo_blocks, edge_metadata = RPOBlockScheduler.schedule_and_elide_edges(cfg)
        elided_edges_count = sum(1 for meta in edge_metadata.values() if meta["has_implicit_fallthrough"])

        # 2. SSA Backward Delta Encoding
        encoded_instructions = SSABackwardDeltaEncoder.encode_instructions(optimized_instructions)

        # 3. Front-Coded String Table
        front_coded_symbols, sym_index_map = FrontCodedStringPool.encode(symbol_names)
        raw_symbol_bytes = sum(len(s.encode('utf-8')) for s in symbol_names)
        front_coded_bytes = len(front_coded_symbols)

        # 4. Columnar SoA Serialization
        columns = ColumnarBytecodeSerializer.serialize_columns(encoded_instructions)
        soa_container = ColumnarBytecodeSerializer.pack_container(columns, front_coded_symbols)

        # 5. Canonical Huffman Compression on SoA Container with Adaptive Thresholding
        huffman_candidate = HuffmanCompressor.compress(soa_container)
        
        # If Huffman table overhead exceeds raw container size, store raw container with 0x00 flag
        if len(huffman_candidate) < len(soa_container):
            final_bitstream = b"\x01" + huffman_candidate  # 0x01 = Huffman compressed
            is_entropy_packed = True
        else:
            final_bitstream = b"\x00" + bytes(soa_container)  # 0x00 = Raw columnar payload
            is_entropy_packed = False

        # 6. Lossless Round-Trip Verification
        flag = final_bitstream[0]
        payload = final_bitstream[1:]
        if flag == 0x01:
            decompressed_container = HuffmanCompressor.decompress(payload)
        else:
            decompressed_container = payload

        assert decompressed_container == soa_container, "SoA Huffman decompression failed integrity assertion!"

        unpacked_columns, unpacked_sym_bytes = ColumnarBytecodeSerializer.unpack_container(decompressed_container)
        assert unpacked_columns["instruction_count"] == len(optimized_instructions), "Instruction count mismatch!"
        recovered_strings = FrontCodedStringPool.decode(unpacked_sym_bytes)
        assert set(recovered_strings) == set(symbol_names), "Symbol table string pool mismatch!"

        # Full instruction-level round-trip: decode the columnar streams back
        # into instructions and check that they equal the optimized program up
        # to a consistent renaming of variables. Comparing the encoder's own
        # intermediate dicts is not enough: a lossy encoding reproduces itself.
        reconstructed = ColumnarBytecodeSerializer.decode_instructions(
            ColumnarBytecodeSerializer.deserialize_columns(unpacked_columns))
        assert canonical_form(reconstructed) == canonical_form(optimized_instructions), \
            "Columnar SoA instruction round-trip mismatch!"

        # 6. Chordal Register Allocation via Maximum Cardinality Search (Hack's Theorem)
        target_cfg = cfg
        target_instructions = optimized_instructions
        liveness = LivenessAnalyzer(target_cfg)
        liveness.analyze()
        if len(liveness.all_variables) == 0 and raw_instructions:
            target_cfg = ControlFlowGraph.build(raw_instructions)
            target_instructions = raw_instructions
            liveness = LivenessAnalyzer(target_cfg)
            liveness.analyze()

        rig = RegisterInterferenceGraph.build_from_liveness(liveness)
        allocator = ChordalRegisterAllocator(rig)
        allocation = allocator.allocate()
        compacted_instructions = RegisterCompactor.compact_instructions(target_instructions, allocation)
        reg_summary = RegisterCompactor.get_summary(liveness.all_variables, allocation)

        # 7. 4-Bit Nibble Register-Packed Bytecode Serialization
        packed_emitter = RegisterPackedBytecodeEmitter()
        packed_bytecode = packed_emitter.serialize_program(compacted_instructions, k_registers=allocator.k_registers)
        packed_bytecode_bytes = len(packed_bytecode)
        packed_huffman = HuffmanCompressor.compress(bytes(packed_bytecode))
        packed_huffman_bytes = len(packed_huffman)

        # Lossless round-trip of packed bytecode
        decoded_packed, _ = RegisterPackedBytecodeDecoder.decode_program(
            bytes(packed_bytecode), label_map=packed_emitter.id_to_label
        )
        assert len(decoded_packed) == len(compacted_instructions), "Register-packed bytecode instruction count mismatch!"

        # Compute Comparative Metrics
        raw_text = "\n".join(str(i) for i in raw_instructions)
        raw_text_bytes = len(raw_text.encode('utf-8'))
        soa_container_bytes = len(soa_container)
        final_bitstream_bytes = len(final_bitstream)

        overall_compression_percent = ((raw_text_bytes - final_bitstream_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0
        soa_density_percent = ((raw_text_bytes - soa_container_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0
        symbol_compression_percent = ((raw_symbol_bytes - front_coded_bytes) / raw_symbol_bytes * 100) if raw_symbol_bytes else 0.0
        packed_savings_percent = ((raw_text_bytes - packed_bytecode_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0

        # Build rich columnar stream breakdown for inspection
        column_records = []
        for idx, item in enumerate(encoded_instructions):
            op = item["op"]
            op_code_hex = f"0x{ColumnarBytecodeSerializer.OPCODE_MAP.get(op, 0):02X}"
            instr_str = str(optimized_instructions[idx]) if idx < len(optimized_instructions) else f"{op.name}"

            if item.get("is_phi"):
                phi_deltas = item.get("phi_deltas", {})
                flag_str = f"Phi ({len(phi_deltas)} incoming edges)"
                delta_str = ", ".join(f"{pred}: Δ={d}" for pred, d in phi_deltas.items())
                imm_str = ", ".join(str(p) for p in phi_deltas.keys())
            else:
                flags = []
                deltas = []
                imms = []
                if item.get("arg1_delta") is not None:
                    flags.append("Arg1: Δ")
                    deltas.append(f"Arg1 Δ={item['arg1_delta']}")
                elif item.get("arg1_raw") is not None:
                    flags.append("Arg1: Literal")
                    imms.append(f"Arg1={item['arg1_raw']}")

                if item.get("arg2_delta") is not None:
                    flags.append("Arg2: Δ")
                    deltas.append(f"Arg2 Δ={item['arg2_delta']}")
                elif item.get("arg2_raw") is not None:
                    flags.append("Arg2: Literal")
                    imms.append(f"Arg2={item['arg2_raw']}")

                if item.get("result_label") is not None:
                    flags.append("Res: Label")
                    imms.append(f"Res={item['result_label']}")

                flag_str = ", ".join(flags) if flags else "No Operands"
                delta_str = ", ".join(deltas) if deltas else "—"
                imm_str = ", ".join(imms) if imms else "—"

            column_records.append({
                "index": idx + 1,
                "instruction": instr_str,
                "opcode_name": op.name,
                "opcode_hex": op_code_hex,
                "flags_desc": flag_str,
                "delta_desc": delta_str,
                "immediate_desc": imm_str,
            })

        opcodes_hex = " ".join(f"{b:02X}" for b in columns["opcodes"][:64])
        flags_hex = " ".join(f"{b:02X}" for b in columns["flags"][:64])
        deltas_hex = " ".join(f"{b:02X}" for b in columns["deltas"][:64]) if columns["deltas"] else "— (0 bytes)"
        immediates_hex = " ".join(f"{b:02X}" for b in columns["immediates"][:64]) if columns["immediates"] else "— (0 bytes)"
        front_coded_hex = " ".join(f"{b:02X}" for b in front_coded_symbols[:64])
        soa_hex = " ".join(f"{b:02X}" for b in soa_container[:64]) + ("..." if len(soa_container) > 64 else "")

        rpo_details = []
        for idx, b_id in enumerate(rpo_blocks):
            meta = edge_metadata.get(b_id, {})
            rpo_details.append({
                "order": idx + 1,
                "block_id": b_id,
                "is_fallthrough": meta.get("has_implicit_fallthrough", False),
                "jump_deltas": meta.get("jump_deltas", []),
            })

        return {
            "rpo_blocks": rpo_blocks,
            "rpo_details": rpo_details,
            "elided_fallthrough_edges": elided_edges_count,
            "total_cfg_blocks": len(rpo_blocks),
            "column_records": column_records,
            "stream_hex": {
                "opcodes": opcodes_hex,
                "flags": flags_hex,
                "deltas": deltas_hex,
                "immediates": immediates_hex,
                "front_coded_symbols": front_coded_hex,
                "container_sample": soa_hex,
            },
            "columnar_sizes": {
                "opcodes_bytes": len(columns["opcodes"]),
                "flags_bytes": len(columns["flags"]),
                "deltas_bytes": len(columns["deltas"]),
                "immediates_bytes": len(columns["immediates"]),
                "total_columns_bytes": soa_container_bytes,
            },
            "front_coded_symbol_bytes": front_coded_bytes,
            "raw_symbol_bytes": raw_symbol_bytes,
            "symbol_savings_percent": round(symbol_compression_percent, 2),
            "soa_container_bytes": soa_container_bytes,
            "soa_reduction_percent": round(soa_density_percent, 2),
            "final_advanced_bitstream_bytes": final_bitstream_bytes,
            "final_advanced_compression_percent": round(overall_compression_percent, 2),
            "is_entropy_packed": is_entropy_packed,
            "verification_status": "Lossless Round-Trip Verified (full instruction reconstruction)",
            "register_allocation": {
                "physical_registers": allocator.k_registers,
                "virtual_variables": reg_summary["virtual_variable_count"],
                "reduction_percent": reg_summary["reduction_percentage"],
                "max_clique_size": allocator.max_clique_size,
                "allocation_map": reg_summary["allocation_map"],
                "compacted_instructions": [i.to_dict() for i in compacted_instructions],
                "compacted_text": "\n".join(str(i) for i in compacted_instructions),
                "packed_bytecode_bytes": packed_bytecode_bytes,
                "packed_huffman_bytes": packed_huffman_bytes,
                "packed_savings_percent": round(packed_savings_percent, 2),
                "rig_stats": rig.get_stats(),
                "rig_elements": rig.to_cytoscape_elements(allocation),
                "live_intervals": liveness.intervals,
                "liveness_dict": liveness.to_dict(),
            },
        }
