import pytest
import datetime

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


def test_strips_horizontal_whitespace():
    # Horizontal whitespace (spaces/tabs) is collapsed, but newlines are preserved
    result = tsql.render(t"SELECT		    *    FROM               table")
    assert result[0] == 'SELECT * FROM table'


def test_preserves_newlines_for_sql_comments():
    # Newlines must be preserved so -- style SQL comments work correctly
    query = t"""SELECT * FROM users
-- Filter by active status
WHERE active = true"""
    result = tsql.render(query)
    assert '-- Filter by active status\n' in result[0]
    assert 'WHERE active = true' in result[0]


def test_doesnt_strip_whitespace_in_values():
    user_input = 'Some string\nWith whitespace.    With Formating    that is   \n  just right'
    result = tsql.render(t'INSERT INTO table (vals) VALUES({user_input})')
    assert result[0] == 'INSERT INTO table (vals) VALUES(?)'
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


def test_datetime_preserved_as_native_type():
    """datetime objects should be passed through unchanged, not stringified"""
    dt = datetime.datetime(2025, 10, 21, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc)
    result = tsql.render(t"SELECT * FROM table WHERE created_at > {dt}")
    assert result[0] == "SELECT * FROM table WHERE created_at > ?"
    assert result[1] == [dt]
    assert isinstance(result[1][0], datetime.datetime)


def test_date_preserved_as_native_type():
    """date objects should be passed through unchanged"""
    d = datetime.date(2025, 10, 21)
    result = tsql.render(t"SELECT * FROM table WHERE date_col = {d}")
    assert result[0] == "SELECT * FROM table WHERE date_col = ?"
    assert result[1] == [d]
    assert isinstance(result[1][0], datetime.date)


def test_time_preserved_as_native_type():
    """time objects should be passed through unchanged"""
    t = datetime.time(12, 30, 45)
    result = tsql.render(t"SELECT * FROM table WHERE time_col = {t}")
    assert result[0] == "SELECT * FROM table WHERE time_col = ?"
    assert result[1] == [t]
    assert isinstance(result[1][0], datetime.time)


def test_timedelta_preserved_as_native_type():
    """timedelta objects should be passed through unchanged"""
    td = datetime.timedelta(days=15, hours=3, minutes=30)
    result = tsql.render(t"SELECT * FROM table WHERE interval_col = {td}")
    assert result[0] == "SELECT * FROM table WHERE interval_col = ?"
    assert result[1] == [td]
    assert isinstance(result[1][0], datetime.timedelta)


def test_datetime_with_format_spec_converts_to_string():
    """When a format spec is provided, datetime should be formatted as string"""
    dt = datetime.datetime(2025, 10, 21, 12, 30, 45)
    result = tsql.render(t"SELECT * FROM table WHERE date_str = {dt:%Y-%m-%d}")
    assert result[0] == "SELECT * FROM table WHERE date_str = ?"
    assert result[1] == ['2025-10-21']
    assert isinstance(result[1][0], str)


def test_dict_preserved_as_native_type():
    """Dict values should pass through as dict objects, not strings."""
    my_dict = {'name': 'billy', 'age': 30}
    result = tsql.render(t'INSERT INTO users (data) VALUES ({my_dict})')
    assert result.sql == 'INSERT INTO users (data) VALUES (?)'
    assert result.values == [{'name': 'billy', 'age': 30}]
    assert isinstance(result.values[0], dict)


def test_list_preserved_as_native_type():
    """List values should pass through as list objects, not strings."""
    my_list = [1, 2, 3, 'four']
    result = tsql.render(t'INSERT INTO items (tags) VALUES ({my_list})')
    assert result.sql == 'INSERT INTO items (tags) VALUES (?)'
    assert result.values == [[1, 2, 3, 'four']]
    assert isinstance(result.values[0], list)


def test_set_preserved_as_native_type():
    """Set values should pass through as set objects, not strings."""
    my_set = {1, 2, 3}
    result = tsql.render(t'INSERT INTO items (ids) VALUES ({my_set})')
    assert result.sql == 'INSERT INTO items (ids) VALUES (?)'
    assert isinstance(result.values[0], set)
    assert result.values[0] == {1, 2, 3}


def test_nested_dict_with_list():
    """Nested structures should preserve their types."""
    data = {'tags': ['a', 'b'], 'count': 5}
    result = tsql.render(t'UPDATE users SET meta = {data}')
    assert isinstance(result.values[0], dict)
    assert isinstance(result.values[0]['tags'], list)


def test_empty_collections_preserved():
    """Empty collections should also preserve their types."""
    empty_dict = {}
    empty_list = []
    empty_set = set()

    r1 = tsql.render(t'VALUES ({empty_dict})')
    r2 = tsql.render(t'VALUES ({empty_list})')
    r3 = tsql.render(t'VALUES ({empty_set})')

    assert isinstance(r1.values[0], dict)
    assert isinstance(r2.values[0], list)
    assert isinstance(r3.values[0], set)


def test_custom_object_preserved():
    """Custom objects should pass through for database drivers with custom codecs."""
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    p = Point(3, 4)
    result = tsql.render(t'INSERT INTO coords (loc) VALUES ({p})')
    assert result.sql == 'INSERT INTO coords (loc) VALUES (?)'
    assert isinstance(result.values[0], Point)
    assert result.values[0].x == 3
    assert result.values[0].y == 4


def test_custom_object_with_format_spec_stringifies():
    """Custom objects WITH a format spec should be formatted (stringified)."""
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y
        def __format__(self, spec):
            return f"POINT({self.x},{self.y})"

    p = Point(3, 4)
    result = tsql.render(t'INSERT INTO coords (loc) VALUES ({p:s})')
    assert result.values[0] == "POINT(3,4)"
    assert isinstance(result.values[0], str)



