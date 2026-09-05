"""
Unit tests for Scoped Symbol Table and Constant Pool Deduplication.
"""

from core.symbol_table import SymbolTable
from core.constant_pool import ConstantPool


def test_symbol_table_scopes():
    st = SymbolTable()
    s1 = st.declare_symbol("global_var", "int")
    assert st.lookup("global_var") is not None

    st.enter_scope()
    s2 = st.declare_symbol("local_var", "float")
    assert st.lookup("local_var") is not None
    assert st.lookup("global_var") is not None

    st.exit_scope()
    assert st.lookup("local_var") is None
    assert st.lookup("global_var") is not None


def test_symbol_minification():
    st = SymbolTable()
    st.declare_symbol("long_counter_variable", "int")
    st.declare_symbol("temporary_buffer_pointer", "string")
    st.record_reference("long_counter_variable")
    st.record_reference("long_counter_variable")

    mapping = st.minify_symbols()
    assert "long_counter_variable" in mapping
    # Most referenced variable gets assigned first short alias
    assert mapping["long_counter_variable"] == "_a"

    stats = st.get_compression_stats()
    assert stats["compression_percentage"] > 0


def test_constant_pool_deduplication():
    cp = ConstantPool()
    idx1 = cp.register("optimization", "string")
    idx2 = cp.register("optimization", "string")
    idx3 = cp.register(42, "int")

    # Duplicate string must return identical index
    assert idx1 == idx2
    assert idx3 != idx1
    assert len(cp.entries) == 2
    assert cp.total_raw_occurrences == 3

    stats = cp.get_stats()
    assert stats["bytes_saved"] > 0
