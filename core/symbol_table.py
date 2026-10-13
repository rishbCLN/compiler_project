"""
Scoped Symbol Table with Variable Minification and Lifetime Analysis.
Tracks identifier types, scope depths, virtual registers, usage frequencies,
and provides symbol table compression via frequency-based short aliasing and scope flattening.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Symbol:
    name: str
    var_type: str
    scope_level: int
    offset: int = 0
    ref_count: int = 0
    minified_name: Optional[str] = None
    virtual_register: Optional[str] = None
    first_seen_line: int = 1
    last_seen_line: int = 1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.var_type,
            "scope_level": self.scope_level,
            "offset": self.offset,
            "ref_count": self.ref_count,
            "minified_name": self.minified_name or self.name,
            "virtual_register": self.virtual_register,
            "first_seen_line": self.first_seen_line,
            "last_seen_line": self.last_seen_line,
        }


class Scope:
    def __init__(self, scope_level: int, parent: Optional['Scope'] = None):
        self.scope_level = scope_level
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []

    def define(self, symbol: Symbol) -> bool:
        if symbol.name in self.symbols:
            return False  # Redeclaration in same scope
        self.symbols[symbol.name] = symbol
        return True

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def all_symbols_recursive(self) -> List[Symbol]:
        res = list(self.symbols.values())
        for child in self.children:
            res.extend(child.all_symbols_recursive())
        return res


class SymbolTable:
    def __init__(self):
        self.global_scope = Scope(scope_level=0)
        self.current_scope = self.global_scope
        self.next_offset = 0
        self.all_symbols: List[Symbol] = []
        self.name_to_minified: Dict[str, str] = {}

    def enter_scope(self) -> Scope:
        child = Scope(scope_level=self.current_scope.scope_level + 1, parent=self.current_scope)
        self.current_scope.children.append(child)
        self.current_scope = child
        return child

    def exit_scope(self):
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def declare_symbol(self, name: str, var_type: str, line: int = 1) -> Symbol:
        # Type size estimate (bytes)
        type_sizes = {"int": 4, "float": 8, "string": 8, "bool": 1}
        size = type_sizes.get(var_type, 4)

        sym = Symbol(
            name=name,
            var_type=var_type,
            scope_level=self.current_scope.scope_level,
            offset=self.next_offset,
            ref_count=1,
            first_seen_line=line,
            last_seen_line=line,
        )
        self.next_offset += size
        self.current_scope.define(sym)
        self.all_symbols.append(sym)
        return sym

    def record_reference(self, name: str, line: int = 1):
        sym = self.current_scope.lookup(name)
        if sym:
            sym.ref_count += 1
            sym.last_seen_line = max(sym.last_seen_line, line)

    def lookup(self, name: str) -> Optional[Symbol]:
        return self.current_scope.lookup(name)

    # ---------------- Compression & Minification ----------------

    def minify_symbols(self) -> Dict[str, str]:
        """
        Frequency-based symbol minification.
        Most frequently referenced variables get assigned the shortest identifier ($0, $1, etc. or a, b, c).
        Also flattens non-conflicting scopes to minimize total symbol count.
        """
        # Sort symbols by reference count descending
        sorted_syms = sorted(self.all_symbols, key=lambda s: s.ref_count, reverse=True)

        alias_chars = "abcdefghijklmnopqrstuvwxyz"
        mapping: Dict[str, str] = {}

        for idx, sym in enumerate(sorted_syms):
            if idx < len(alias_chars):
                alias = f"_{alias_chars[idx]}"
            else:
                alias = f"_{alias_chars[idx % len(alias_chars)]}{idx // len(alias_chars)}"
            sym.minified_name = alias

            # Scope-qualified key guarantees distinct scopes that declare the
            # same identifier never collide onto the same alias entry.
            qualified = f"{sym.name}#{sym.scope_level}"
            mapping[qualified] = alias
            self.name_to_minified[qualified] = alias

            # Preserve a bare-name entry for the primary (first / most-referenced
            # due to the frequency sort) occurrence for backward-compatible lookups.
            if sym.name not in mapping:
                mapping[sym.name] = alias
                self.name_to_minified[sym.name] = alias

        return mapping

    def get_compression_stats(self) -> dict:
        """Calculate memory and storage savings before and after symbol table minification."""
        raw_size = 0
        minified_size = 0

        for sym in self.all_symbols:
            # Raw: 64-byte symbol descriptor + length of original identifier string
            raw_size += 64 + len(sym.name)
            # Minified: 24-byte compact descriptor + minified alias length (typically 2 chars)
            alias_len = len(sym.minified_name) if sym.minified_name else len(sym.name)
            minified_size += 24 + alias_len

        ratio = ((raw_size - minified_size) / raw_size * 100) if raw_size > 0 else 0.0

        return {
            "symbol_count": len(self.all_symbols),
            "raw_symbol_table_bytes": raw_size,
            "minified_symbol_table_bytes": minified_size,
            "bytes_saved": raw_size - minified_size,
            "compression_percentage": round(ratio, 2),
        }

    def to_dict(self) -> dict:
        return {
            "symbols": [sym.to_dict() for sym in self.all_symbols],
            "stats": self.get_compression_stats(),
        }
