"""
Constant Pool Manager with Literal Deduplication (Interning) and Compression.
Tracks literals across the compilation unit, maps duplicates to unique pool indices,
and quantifies compression ratios achieved by literal pooling.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
import struct


@dataclass
class ConstantEntry:
    index: int
    value: Any
    const_type: str  # int, float, string, bool
    occurrences: int = 1
    raw_size_bytes: int = 4

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "value": self.value,
            "type": self.const_type,
            "occurrences": self.occurrences,
            "raw_size_bytes": self.raw_size_bytes,
        }


class ConstantPool:
    def __init__(self):
        self.entries: List[ConstantEntry] = []
        # Value + Type -> Index mapping for O(1) deduplication
        self.value_to_index: Dict[str, int] = {}
        self.total_raw_occurrences = 0
        self.total_raw_bytes = 0

    def _get_key(self, value: Any, const_type: str) -> str:
        return f"{const_type}:{value}"

    def _calculate_size(self, value: Any, const_type: str) -> int:
        if const_type == "int":
            return 4
        elif const_type == "float":
            return 8
        elif const_type == "bool":
            return 1
        elif const_type == "string":
            return 4 + len(str(value).encode('utf-8'))  # length prefix + utf-8 bytes
        return 4

    def register(self, value: Any, const_type: str) -> int:
        """
        Registers a constant in the pool.
        If the constant already exists, increments occurrence count and returns existing index.
        Otherwise, allocates a new index.
        """
        key = self._get_key(value, const_type)
        entry_size = self._calculate_size(value, const_type)
        self.total_raw_occurrences += 1
        self.total_raw_bytes += entry_size

        if key in self.value_to_index:
            idx = self.value_to_index[key]
            self.entries[idx].occurrences += 1
            return idx

        idx = len(self.entries)
        entry = ConstantEntry(
            index=idx,
            value=value,
            const_type=const_type,
            occurrences=1,
            raw_size_bytes=entry_size,
        )
        self.entries.append(entry)
        self.value_to_index[key] = idx
        return idx

    def get_entry(self, index: int) -> Optional[ConstantEntry]:
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None

    def get_stats(self) -> dict:
        """Calculate storage metrics before and after constant pooling/deduplication."""
        deduplicated_bytes = sum(entry.raw_size_bytes for entry in self.entries)
        # Add index table overhead (2 bytes per unique entry)
        pool_overhead = len(self.entries) * 2
        total_pool_bytes = deduplicated_bytes + pool_overhead

        raw_bytes = self.total_raw_bytes
        net_bytes_saved = raw_bytes - total_pool_bytes  # may be negative on tiny inputs
        savings = max(0, net_bytes_saved)
        ratio = (savings / raw_bytes * 100) if raw_bytes > 0 else 0.0
        net_ratio = (net_bytes_saved / raw_bytes * 100) if raw_bytes > 0 else 0.0

        return {
            "total_occurrences": self.total_raw_occurrences,
            "unique_constants": len(self.entries),
            "raw_constants_bytes": raw_bytes,
            "deduplicated_pool_bytes": total_pool_bytes,
            "pool_overhead_bytes": pool_overhead,
            "bytes_saved": savings,
            "net_bytes_saved": net_bytes_saved,
            "compression_percentage": round(ratio, 2),
            # Honest net ratio: negative when pool/index overhead exceeds the raw
            # literal footprint (common for very small programs with few repeats).
            "net_compression_percentage": round(net_ratio, 2),
            "overhead_exceeds_savings": net_bytes_saved < 0,
        }

    def serialize(self) -> bytearray:
        """
        Binary serialization of the constant pool.
        Format:
        [Entry Count: 2 bytes]
        For each entry:
          [Type Tag: 1 byte (0=int, 1=float, 2=bool, 3=string)]
          [Data: variable according to type]
        """
        buf = bytearray()
        buf.extend(struct.pack(">H", len(self.entries)))

        type_tags = {"int": 0, "float": 1, "bool": 2, "string": 3}

        for entry in self.entries:
            tag = type_tags.get(entry.const_type, 0)
            buf.append(tag)
            if entry.const_type == "int":
                buf.extend(struct.pack(">i", int(entry.value)))
            elif entry.const_type == "float":
                buf.extend(struct.pack(">d", float(entry.value)))
            elif entry.const_type == "bool":
                buf.append(1 if entry.value else 0)
            elif entry.const_type == "string":
                encoded = str(entry.value).encode('utf-8')
                buf.extend(struct.pack(">H", len(encoded)))
                buf.extend(encoded)

        return buf

    def to_dict(self) -> dict:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "stats": self.get_stats(),
        }
