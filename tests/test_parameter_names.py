"""Tests for parameter name generation with NAMED and PYFORMAT styles.

This tests SECURITY-2: ensuring complex expression names don't break SQL syntax
or cause issues with parameter name generation.
"""
import tsql
from tsql.styles import NAMED, PYFORMAT


def test_simple_variable_name():
    """Simple variable names should work fine."""
    user_input = "test"
    query = t"SELECT * FROM users WHERE name = {user_input}"

    # NAMED style - returns dict
    sql, params = tsql.render(query, style=NAMED)
    assert sql == "SELECT * FROM users WHERE name = :user_input"
    assert params == {"user_input": "test"}

    # PYFORMAT style - returns dict
    sql, params = tsql.render(query, style=PYFORMAT)
    assert sql == "SELECT * FROM users WHERE name = %(user_input)s"
    assert params == {"user_input": "test"}


def test_dict_access_expression():
    """Dictionary access like data['key'] creates complex expression names."""
    data = {'key': 'value'}
    query = t"SELECT * FROM users WHERE name = {data['key']}"

    # NAMED style - should sanitize to :data__key__
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert sql == "SELECT * FROM users WHERE name = :data__key__"
    assert params == {"data__key__": 'value'}

    # PYFORMAT style - should sanitize to %(data__key__)s
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert sql == "SELECT * FROM users WHERE name = %(data__key__)s"
    assert params == {"data__key__": 'value'}


def test_attribute_access_expression():
    """Attribute access like obj.attr creates dotted expression names."""
    class User:
        name = "Alice"

    obj = User()
    query = t"SELECT * FROM users WHERE name = {obj.name}"

    # NAMED style - should sanitize to :obj_name
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert sql == "SELECT * FROM users WHERE name = :obj_name"
    assert params == {"obj_name": 'Alice'}

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert sql == "SELECT * FROM users WHERE name = %(obj_name)s"
    assert params == {"obj_name": 'Alice'}


def test_function_call_expression():
    """Function calls like func() create complex expression names."""
    def get_name():
        return "Bob"

    query = t"SELECT * FROM users WHERE name = {get_name()}"

    # NAMED style - should sanitize to :get_name__
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert sql == "SELECT * FROM users WHERE name = :get_name__"
    assert params == {"get_name__": 'Bob'}

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert sql == "SELECT * FROM users WHERE name = %(get_name__)s"
    assert params == {"get_name__": 'Bob'}


def test_complex_expression_with_operators():
    """Complex expressions with operators."""
    a = 5
    b = 3
    query = t"SELECT * FROM users WHERE age = {a + b}"

    # NAMED style - should sanitize to :a___b
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert sql == "SELECT * FROM users WHERE age = :a___b"
    assert params == {"a___b": 8}

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert sql == "SELECT * FROM users WHERE age = %(a___b)s"
    assert params == {"a___b": 8}


def test_method_chain_expression():
    """Method chaining creates very complex expression names."""
    text = "  Alice  "
    query = t"SELECT * FROM users WHERE name = {text.strip().lower()}"

    # NAMED style
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert 'alice' in params.values()

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert 'alice' in params.values()


def test_list_index_expression():
    """List indexing like items[0] creates indexed expression names."""
    items = ['first', 'second', 'third']
    query = t"SELECT * FROM users WHERE name = {items[0]}"

    # NAMED style
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert 'first' in params.values()

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert 'first' in params.values()


def test_ternary_expression():
    """Ternary/conditional expressions."""
    age = 25
    query = t"SELECT * FROM users WHERE category = {'adult' if age >= 18 else 'minor'}"

    # NAMED style
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert 'adult' in params.values()

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert 'adult' in params.values()


def test_multiple_complex_expressions():
    """Multiple complex expressions in one query - ensure unique parameter names."""
    data = {'first': 'Alice', 'last': 'Smith'}
    query = t"SELECT * FROM users WHERE first_name = {data['first']} AND last_name = {data['last']}"

    # NAMED style
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert set(params.values()) == {'Alice', 'Smith'}

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert set(params.values()) == {'Alice', 'Smith'}


def test_expression_with_quotes():
    """Expression containing quotes (from dict keys with quotes)."""
    data = {"user's name": "Bob"}
    key = "user's name"
    query = t"SELECT * FROM users WHERE name = {data[key]}"

    # NAMED style
    sql, params = tsql.render(query, style=NAMED)
    print(f"NAMED SQL: {sql}")
    print(f"NAMED params: {params}")
    assert 'Bob' in params.values()

    # PYFORMAT style
    sql, params = tsql.render(query, style=PYFORMAT)
    print(f"PYFORMAT SQL: {sql}")
    print(f"PYFORMAT params: {params}")
    assert 'Bob' in params.values()
