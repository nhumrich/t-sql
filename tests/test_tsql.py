import pytest

import tsql
import tsql.styles

def test_has_no_values():
    q = t'hello'
    result = tsql.TSQL(q)
    assert result._sql == 'hello'
    assert len(result._values) == 0


def test_has_correct_values():
    val = 'there'
    q = t'hello {val}'
    result = tsql.TSQL(q)
    assert result._sql == 'hello $?'
    assert not result._values == ["'there'"]


def test_merges_literals_with_hint():
    val = 'there'
    q = t'hello {val:literal}'
    result = tsql.TSQL(q)
    assert len(result._values) == 0
    assert result._sql == 'hello there'


def test_merges_literals_using_exsiting_tstring():
    val = t'there'
    q = t'hello {val}'
    result = tsql.TSQL(q)
    assert len(result._values) == 0
    assert result._sql == 'hello there'


def test_strips_literal_whitespace():
    result = tsql.render(t"SELECT             \n * \n FROM               table")
    assert result[0] == 'SELECT * FROM table'


def test_doesnt_strip_whitespace_in_values():
    user_input = 'Some string\nWith whitespace.    With Formating    that is   \n  just right'
    result = tsql.render(t'INSERT \n INTO table (vals) VALUES({user_input})')
    assert result[0] == f'INSERT INTO table (vals) VALUES(?)'
    assert result[1] == [user_input]


def test_correct_final_query_with_literals():
    table = "users"
    col = "name"
    result = tsql.render(t'select id, {col:literal} from {table:literal}')
    assert result[0] == 'select id, name from users'
    assert result[1] == []


def test_disallows_bad_literals():
    table = "users'"
    col = "name"
    with pytest.raises(ValueError):  # TODO: change to appropriate error
        result = tsql.render(t'select id, {col:literal} from {table:literal}')


def test_query_with_values():
    val1 = 1
    val2 = 'f'
    result = tsql.render(t"SELECT * FROM table WHERE a={val1} AND b={val2}")
    assert result[0] == "SELECT * FROM table WHERE a=? AND b=?"
    assert result[1] == [1, 'f']


def test_query_with_array_values():
    val = ['a', 'b', 'c']
    result = tsql.render(t"INSERT INTO table (vals) VALUES({val})")
    assert result[0] == """INSERT INTO table (vals) VALUES(?)"""


def test_writes_correct_query_with_literal_and_value():
    column = 'name'
    table = 'users'
    val1 = 1
    val2 = 'f'
    result = tsql.render(t"SELECT id,{column:literal} FROM {table:literal} WHERE a={val1} and {column:literal}={val2}")
    assert result[0] == "SELECT id,name FROM users WHERE a=? and name=?"


def test_writes_correct_query_with_embedded_tstring():
    column = 'name'
    table = 'users'
    val1 = 1
    val2 = 'f'
    where_clause = t"WHERE a={val1} and b={val2}"
    result = tsql.render(t"SELECT id,{column:literal} FROM {table:literal} {where_clause}")
    assert result[0] == "SELECT id,name FROM users WHERE a=? and b=?"


def test_writes_correct_query_with_embedded_tstring_at_beginning():
    column = 'name'
    table = t'{"users":literal}'
    val1 = 1
    val2 = 'f'
    select_clause = t"SELECT id,{column:literal} FROM"
    where_clause = t"WHERE a={val1} and b={val2}"
    result = tsql.render(t"{select_clause} {table} {where_clause}")
    assert result[0] == "SELECT id,name FROM users WHERE a=? and b=?"


def test_prevents_sql_injection():
    val = "abc' OR 1=1;--"
    result = tsql.render(t"SELECT * FROM table WHERE col={val}")
    assert result[0] == "SELECT * FROM table WHERE col=?"





