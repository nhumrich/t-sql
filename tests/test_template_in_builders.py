"""Tests for Template/TSQL values in INSERT/UPDATE builders"""
import pytest
from string.templatelib import Template

import tsql
from tsql import TSQL
from tsql.query_builder import Table, SAColumn
from tsql import styles

# Test tables
class TestTable(Table, table_name='test_table'):
    id = ...
    name = ...
    created_ts = ...
    updated_ts = ...


def test_update_with_template_value():
    """Template values in UPDATE should be inlined, not parameterized"""
    query = TestTable.update(updated_ts=t"NOW()").where(TestTable.id == 123)

    sql, params = query.render(style=styles.QMARK)

    # The Template should be inlined, not parameterized
    assert "NOW()" in sql
    assert sql == "UPDATE test_table SET updated_ts = NOW() WHERE test_table.id = ?"
    # Only the id comparison should be parameterized
    assert params == [123]


def test_insert_with_template_value():
    """Template values in INSERT should be inlined, not parameterized"""
    query = TestTable.insert(name="Alice", created_ts=t"NOW()")

    sql, params = query.render(style=styles.QMARK)

    # The Template should be inlined, not parameterized
    assert "NOW()" in sql
    assert sql == "INSERT INTO test_table (name, created_ts) VALUES (?, NOW())"
    # Only the name should be parameterized
    assert params == ["Alice"]


def test_insert_on_conflict_update_with_template():
    """Template values in ON CONFLICT UPDATE should be inlined"""
    query = (TestTable.insert(id=1, name="Alice", updated_ts=t"NOW()")
             .on_conflict_update('id', update={'updated_ts': t"NOW()"}))

    sql, params = query.render(style=styles.QMARK)

    # Both Templates should be inlined
    assert sql.count("NOW()") == 2
    assert "ON CONFLICT (id) DO UPDATE SET updated_ts = NOW()" in sql


def test_insert_on_duplicate_key_with_template():
    """Template values in ON DUPLICATE KEY UPDATE should be inlined (MySQL)"""
    query = (TestTable.insert(id=1, name="Alice", updated_ts=t"NOW()")
             .on_duplicate_key_update(update={'updated_ts': t"NOW()"}))

    sql, params = query.render(style=styles.QMARK)

    # Both Templates should be inlined
    assert sql.count("NOW()") == 2
    assert "ON DUPLICATE KEY UPDATE updated_ts = NOW()" in sql


def test_update_with_tsql_object():
    """TSQL objects in UPDATE should be inlined"""
    now_expr = TSQL(t"NOW()")
    query = TestTable.update(updated_ts=now_expr).where(TestTable.id == 123)

    sql, params = query.render(style=styles.QMARK)

    assert "NOW()" in sql
    assert params == [123]


def test_update_multiple_template_values():
    """Multiple Template values should all be inlined"""
    query = (TestTable.update(
        created_ts=t"NOW()",
        updated_ts=t"CURRENT_TIMESTAMP",
        name="Bob"
    ).where(TestTable.id == 456))

    sql, params = query.render(style=styles.QMARK)

    # Both SQL expressions should be inlined
    assert "NOW()" in sql
    assert "CURRENT_TIMESTAMP" in sql
    # Only name and id should be parameterized
    assert params == ["Bob", 456]


def test_insert_with_sql_expression_postgres_style():
    """Template with SQL expression should work with different parameter styles"""
    query = TestTable.insert(name="Charlie", created_ts=t"NOW() - INTERVAL '5 minutes'")

    sql, params = query.render(style=styles.NUMERIC_DOLLAR)

    assert "NOW() - INTERVAL '5 minutes'" in sql
    assert sql == "INSERT INTO test_table (name, created_ts) VALUES ($1, NOW() - INTERVAL '5 minutes')"
    assert params == ["Charlie"]
