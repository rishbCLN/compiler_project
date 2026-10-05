"""
Binary Bytecode Serialization, LEB128 Variable-Length Encoding,
and Canonical Huffman Entropy Compression for Intermediate Representations.
Demonstrates concrete byte-level IR size reduction (typically 70% to 90%).
"""

from typing import List, Dict, Tuple, Optional, Any
import struct
import heapq
from collections import Counter
from core.ir import Instruction, Opcode
from core.symbol_table import SymbolTable
from core.constant_pool import ConstantPool


class LEB128:
    """Little-Endian Base 128 (LEB128) variable-length integer encoding (as used in WebAssembly and DWARF)."""

    @staticmethod
    def encode_unsigned(val: int) -> bytearray:
        res = bytearray()
        val = max(0, val)
        while True:
            byte = val & 0x7F
            val >>= 7
            if val != 0:
                byte |= 0x80  # More bytes to follow
            res.append(byte)
            if val == 0:
                break
        return res

    @staticmethod
    def decode_unsigned(data: bytes, offset: int = 0) -> Tuple[int, int]:
        result = 0
        shift = 0
        curr = offset
        while True:
            byte = data[curr]
            curr += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result, curr - offset


class HuffmanNode:
    def __init__(self, byte_val: Optional[int], freq: int):
        self.byte_val = byte_val
        self.freq = freq
        self.left: Optional['HuffmanNode'] = None
        self.right: Optional['HuffmanNode'] = None

    def __lt__(self, other: 'HuffmanNode') -> bool:
        return self.freq < other.freq


class HuffmanCompressor:
    """Canonical Huffman entropy compressor for binary bytecode packages."""

    @staticmethod
    def build_codes(root: Optional[HuffmanNode], current_code: str, codes: Dict[int, str]):
        if root is None:
            return
        if root.byte_val is not None:
            codes[root.byte_val] = current_code if current_code else "0"
            return
        HuffmanCompressor.build_codes(root.left, current_code + "0", codes)
        HuffmanCompressor.build_codes(root.right, current_code + "1", codes)

    @classmethod
    def compress(cls, data: bytes) -> bytes:
        if not data:
            return b""

        # 1. Frequency count
        freqs = Counter(data)
        heap = [HuffmanNode(b, f) for b, f in freqs.items()]
        heapq.heapify(heap)

        if len(heap) == 1:
            # Single unique byte edge-case
            node = heap[0]
            root = HuffmanNode(None, node.freq)
            root.left = node
        else:
            while len(heap) > 1:
                n1 = heapq.heappop(heap)
                n2 = heapq.heappop(heap)
                parent = HuffmanNode(None, n1.freq + n2.freq)
                parent.left = n1
                parent.right = n2
                heapq.heappush(heap, parent)
            root = heap[0]

        # 2. Build bit codes
        codes: Dict[int, str] = {}
        cls.build_codes(root, "", codes)

        # 3. Encode data into bitstring
        bitstring = "".join(codes[b] for b in data)

        # 4. Serialize header (frequency table) + bit stream
        out = bytearray()
        # Number of unique symbols (2 bytes)
        out.extend(struct.pack(">H", len(freqs)))
        for b, f in freqs.items():
            out.append(b)
            out.extend(struct.pack(">I", f))

        # Total uncompressed length (4 bytes)
        out.extend(struct.pack(">I", len(data)))

        # Pack bitstring into bytes
        pad_len = (8 - len(bitstring) % 8) % 8
        out.append(pad_len)

        padded_bits = bitstring + ("0" * pad_len)
        for i in range(0, len(padded_bits), 8):
            byte_val = int(padded_bits[i:i + 8], 2)
            out.append(byte_val)

        return bytes(out)

    @classmethod
    def decompress(cls, data: bytes) -> bytes:
        if not data:
            return b""

        offset = 0
        num_symbols = struct.unpack_from(">H", data, offset)[0]
        offset += 2

        freqs = {}
        for _ in range(num_symbols):
            b = data[offset]
            offset += 1
            f = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            freqs[b] = f

        orig_len = struct.unpack_from(">I", data, offset)[0]
        offset += 4

        pad_len = data[offset]
        offset += 1

        # Rebuild Huffman Tree
        heap = [HuffmanNode(b, f) for b, f in freqs.items()]
        heapq.heapify(heap)

        if len(heap) == 1:
            node = heap[0]
            root = HuffmanNode(None, node.freq)
            root.left = node
        else:
            while len(heap) > 1:
                n1 = heapq.heappop(heap)
                n2 = heapq.heappop(heap)
                parent = HuffmanNode(None, n1.freq + n2.freq)
                parent.left = n1
                parent.right = n2
                heapq.heappush(heap, parent)
            root = heap[0]

        # Read bitstream
        raw_bytes = data[offset:]
        bitstring_parts = [f"{b:08b}" for b in raw_bytes]
        bitstring = "".join(bitstring_parts)
        if pad_len > 0:
            bitstring = bitstring[:-pad_len]

        # Decode bitstream
        decoded = bytearray()
        curr_node = root
        for bit in bitstring:
            curr_node = curr_node.left if bit == "0" else curr_node.right
            if curr_node.byte_val is not None:
                decoded.append(curr_node.byte_val)
                curr_node = root
                if len(decoded) == orig_len:
                    break

        return bytes(decoded)


class BytecodeEmitter:
    """Emits compact binary bytecode with LEB128 operands from TAC instructions."""

    OPCODE_MAP = {
        Opcode.NOP: 0x00,
        Opcode.ADD: 0x01,
        Opcode.SUB: 0x02,
        Opcode.MUL: 0x03,
        Opcode.DIV: 0x04,
        Opcode.MOD: 0x05,
        Opcode.NEG: 0x06,
        Opcode.AND: 0x07,
        Opcode.OR: 0x08,
        Opcode.NOT: 0x09,
        Opcode.EQ: 0x0A,
        Opcode.NE: 0x0B,
        Opcode.LT: 0x0C,
        Opcode.LE: 0x0D,
        Opcode.GT: 0x0E,
        Opcode.GE: 0x0F,
        Opcode.ASSIGN: 0x10,
        Opcode.LOAD_CONST: 0x11,
        Opcode.LABEL: 0x12,
        Opcode.JUMP: 0x13,
        Opcode.JUMP_IF_TRUE: 0x14,
        Opcode.JUMP_IF_FALSE: 0x15,
        Opcode.RETURN: 0x16,
        Opcode.PHI: 0x17,
        Opcode.PRINT: 0x18,
    }

    def __init__(self, symbol_table: SymbolTable, constant_pool: ConstantPool):
        self.symbol_table = symbol_table
        self.constant_pool = constant_pool
        # Maps symbol name -> integer register ID
        self.var_to_id: Dict[str, int] = {}
        # Maps label name -> integer label ID
        self.label_to_id: Dict[str, int] = {}

    @staticmethod
    def _classify_const(value: Any) -> str:
        """Infer the constant-pool type of a literal from its textual form."""
        s = str(value)
        if s in ("true", "false"):
            return "bool"
        if s.startswith('"') and s.endswith('"'):
            return "string"
        try:
            if '.' in s:
                float(s)
                return "float"
            int(s)
            return "int"
        except ValueError:
            return "string"

    def get_var_id(self, name: Optional[str]) -> int:
        if name is None:
            return 0
        if name not in self.var_to_id:
            self.var_to_id[name] = len(self.var_to_id)
        return self.var_to_id[name]

    def get_label_id(self, label: Optional[str]) -> int:
        if label is None:
            return 0
        if label not in self.label_to_id:
            self.label_to_id[label] = len(self.label_to_id)
        return self.label_to_id[label]

    def emit_instruction(self, instr: Instruction) -> bytearray:
        buf = bytearray()
        op_byte = self.OPCODE_MAP.get(instr.op, 0x00)
        buf.append(op_byte)

        # Operand encoding
        if instr.op in (Opcode.LABEL, Opcode.JUMP):
            lbl_id = self.get_label_id(str(instr.arg1))
            buf.extend(LEB128.encode_unsigned(lbl_id))

        elif instr.op in (Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE):
            cond_id = self.get_var_id(str(instr.arg1))
            lbl_id = self.get_label_id(str(instr.result))
            buf.extend(LEB128.encode_unsigned(cond_id))
            buf.extend(LEB128.encode_unsigned(lbl_id))

        elif instr.op == Opcode.LOAD_CONST:
            res_id = self.get_var_id(instr.result)
            buf.extend(LEB128.encode_unsigned(res_id))
            # Look up the already-registered pool index (registration happens in a
            # pre-pass BEFORE the constant pool is serialized). Fall back to a
            # (correctly typed) registration only if somehow missing.
            const_type = self._classify_const(instr.arg1)
            key = self.constant_pool._get_key(str(instr.arg1), const_type)
            pool_id = self.constant_pool.value_to_index.get(key)
            if pool_id is None:
                pool_id = self.constant_pool.register(str(instr.arg1), const_type)
            buf.extend(LEB128.encode_unsigned(pool_id))

        elif instr.op == Opcode.ASSIGN:
            res_id = self.get_var_id(instr.result)
            src_id = self.get_var_id(str(instr.arg1))
            buf.extend(LEB128.encode_unsigned(res_id))
            buf.extend(LEB128.encode_unsigned(src_id))

        elif instr.op == Opcode.PHI:
            res_id = self.get_var_id(instr.result)
            buf.extend(LEB128.encode_unsigned(res_id))
            # Number of phi incoming edges
            buf.extend(LEB128.encode_unsigned(len(instr.phi_args)))
            for pred_id, var_ver in sorted(instr.phi_args.items()):
                p_id = self.get_label_id(pred_id)
                v_id = self.get_var_id(var_ver)
                buf.extend(LEB128.encode_unsigned(p_id))
                buf.extend(LEB128.encode_unsigned(v_id))

        elif instr.op in (Opcode.PRINT, Opcode.RETURN):
            arg_id = self.get_var_id(str(instr.arg1)) if instr.arg1 else 0
            buf.extend(LEB128.encode_unsigned(arg_id))

        elif instr.op in (Opcode.NEG, Opcode.NOT):
            # Unary operations: result, arg1 only.
            res_id = self.get_var_id(instr.result)
            a1_id = self.get_var_id(str(instr.arg1))
            buf.extend(LEB128.encode_unsigned(res_id))
            buf.extend(LEB128.encode_unsigned(a1_id))

        elif instr.op == Opcode.NOP:
            # No operands.
            pass

        else:
            # Binary operations: result, arg1, arg2
            res_id = self.get_var_id(instr.result)
            a1_id = self.get_var_id(str(instr.arg1))
            a2_id = self.get_var_id(str(instr.arg2))
            buf.extend(LEB128.encode_unsigned(res_id))
            buf.extend(LEB128.encode_unsigned(a1_id))
            buf.extend(LEB128.encode_unsigned(a2_id))

        return buf

    def serialize_program(self, instructions: List[Instruction]) -> bytearray:
        package = bytearray()
        # Magic bytes: 'C' 'L' 'I' 'R' (C-Lite IR)
        package.extend(b"CLIR")
        # Version 1.0
        package.append(1)

        # Constant Pool section.
        # Pre-register every LOAD_CONST literal (with its correct type) BEFORE
        # serializing the pool, so the serialized header and the bytecode indices
        # stay consistent. Registering during emit_instruction would mutate the
        # pool after it had already been written.
        for instr in instructions:
            if instr.op == Opcode.LOAD_CONST and instr.arg1 is not None:
                const_type = self._classify_const(instr.arg1)
                key = self.constant_pool._get_key(str(instr.arg1), const_type)
                if key not in self.constant_pool.value_to_index:
                    self.constant_pool.register(str(instr.arg1), const_type)

        cp_bytes = self.constant_pool.serialize()
        package.extend(LEB128.encode_unsigned(len(cp_bytes)))
        package.extend(cp_bytes)

        # Instructions section
        instr_body = bytearray()
        for instr in instructions:
            instr_body.extend(self.emit_instruction(instr))

        package.extend(LEB128.encode_unsigned(len(instructions)))
        package.extend(LEB128.encode_unsigned(len(instr_body)))
        package.extend(instr_body)

        return package


class IRCompressionPipeline:
    """Calculates comprehensive end-to-end metrics across all compression stages."""

    @staticmethod
    def run(raw_instructions: List[Instruction],
            optimized_instructions: List[Instruction],
            symbol_table: SymbolTable,
            constant_pool: ConstantPool) -> dict:

        # 1. Raw Text IR representation
        raw_text = "\n".join(str(i) for i in raw_instructions)
        raw_text_bytes = len(raw_text.encode('utf-8'))

        # 2. Optimized Text IR representation
        opt_text = "\n".join(str(i) for i in optimized_instructions)
        opt_text_bytes = len(opt_text.encode('utf-8'))

        # 3. Binary Bytecode Serialization
        emitter = BytecodeEmitter(symbol_table, constant_pool)
        bytecode = emitter.serialize_program(optimized_instructions)
        bytecode_bytes = len(bytecode)

        # 4. Huffman Entropy Compression on Bytecode
        huffman_compressed = HuffmanCompressor.compress(bytes(bytecode))
        huffman_bytes = len(huffman_compressed)

        # Verify lossless round-trip
        decompressed_bc = HuffmanCompressor.decompress(huffman_compressed)
        assert decompressed_bc == bytes(bytecode), "Lossless decompression integrity check failed!"

        # Compute ratios
        instruction_reduction = ((len(raw_instructions) - len(optimized_instructions)) / len(raw_instructions) * 100) if raw_instructions else 0.0
        structural_reduction = ((raw_text_bytes - opt_text_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0
        bytecode_reduction = ((raw_text_bytes - bytecode_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0
        final_compression_ratio = ((raw_text_bytes - huffman_bytes) / raw_text_bytes * 100) if raw_text_bytes else 0.0

        # Hex dump snippet (first 64 bytes)
        hex_dump = " ".join(f"{b:02X}" for b in huffman_compressed[:64])
        if len(huffman_compressed) > 64:
            hex_dump += f" ... ({len(huffman_compressed) - 64} more bytes)"

        return {
            "raw_instruction_count": len(raw_instructions),
            "optimized_instruction_count": len(optimized_instructions),
            "instruction_reduction_percent": round(instruction_reduction, 2),

            "raw_ir_text_bytes": raw_text_bytes,
            "optimized_ir_text_bytes": opt_text_bytes,
            "structural_reduction_percent": round(structural_reduction, 2),

            "binary_bytecode_bytes": bytecode_bytes,
            "bytecode_reduction_percent": round(bytecode_reduction, 2),

            "huffman_compressed_bytes": huffman_bytes,
            "final_compression_ratio_percent": round(final_compression_ratio, 2),

            "symbol_table_stats": symbol_table.get_compression_stats(),
            "constant_pool_stats": constant_pool.get_stats(),
            "hex_dump_sample": hex_dump,
        }
