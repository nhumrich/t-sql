"""Test string-based query builders (dynamic table/column names)"""
from tsql.query_builder import SelectQueryBuilder, InsertBuilder, UpdateBuilder, DeleteBuilder


def test_select_from_string_table():
    """Test SELECT query with string table name"""
    query = SelectQueryBuilder.from_table('users').select('id', 'name', 'email')
    sql, params = query.render()

    assert 'SELECT id, name, email' in sql
    assert 'FROM users' in sql
    assert params == []


def test_select_with_schema():
    """Test SELECT with schema qualification"""
    query = SelectQueryBuilder.from_table('users', schema='public').select('id', 'name')
    sql, params = query.render()

    assert 'FROM public.users' in sql


def test_select_with_where_tstring():
    """Test SELECT with t-string WHERE clause"""
    user_id = 123
    status = 'active'
    query = SelectQueryBuilder.from_table('users').select('name').where(t'id = {user_id} AND status = {status}')
    sql, params = query.render()

    assert 'WHERE' in sql
    assert params == [123, 'active']


def test_select_order_by_string():
    """Test ORDER BY with string column names"""
    query = SelectQueryBuilder.from_table('users').select('id', 'name').order_by('created_at', direction='DESC')
    sql, params = query.render()

    assert 'ORDER BY created_at DESC' in sql


def test_select_order_by_multiple():
    """Test ORDER BY with multiple columns (chained calls)"""
    query = SelectQueryBuilder.from_table('users') \
        .select('id', 'name') \
        .order_by('username') \
        .order_by('created_at', direction='DESC')
    sql, params = query.render()

    assert 'ORDER BY username ASC, created_at DESC' in sql


def test_select_group_by_string():
    """Test GROUP BY with string column names"""
    query = SelectQueryBuilder.from_table('orders').select('user_id', t'COUNT(*) as count').group_by('user_id')
    sql, params = query.render()

    assert 'GROUP BY user_id' in sql


def test_select_limit_offset():
    """Test LIMIT and OFFSET with string-based query"""
    query = SelectQueryBuilder.from_table('users').select('id').limit(10).offset(20)
    sql, params = query.render()

    assert 'LIMIT' in sql
    assert 'OFFSET' in sql
    assert params == [10, 20]


def test_insert_into_string_table():
    """Test INSERT with string table name"""
    query = InsertBuilder.into_table('users', {'name': 'Bob', 'email': 'bob@test.com'})
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'name' in sql
    assert 'email' in sql
    assert 'Bob' in params
    assert 'bob@test.com' in params


def test_insert_with_schema():
    """Test INSERT with schema qualification"""
    query = InsertBuilder.into_table('users', {'name': 'Alice'}, schema='public')
    sql, params = query.render()

    assert 'INSERT INTO public.users' in sql


def test_insert_with_returning():
    """Test INSERT with RETURNING clause"""
    query = InsertBuilder.into_table('users', {'name': 'Bob'}).returning('id')
    sql, params = query.render()

    assert 'RETURNING id' in sql


def test_insert_on_conflict_do_nothing():
    """Test INSERT with ON CONFLICT DO NOTHING"""
    query = InsertBuilder.into_table('users', {'email': 'test@example.com'}).on_conflict_do_nothing('email')
    sql, params = query.render()

    assert 'ON CONFLICT' in sql
    assert 'DO NOTHING' in sql


def test_update_string_table():
    """Test UPDATE with string table name"""
    cutoff_date = '2024-01-01'
    query = UpdateBuilder.table('users', {'status': 'inactive'}).where(t'last_login < {cutoff_date}')
    sql, params = query.render()

    assert 'UPDATE users' in sql
    assert 'SET status' in sql
    assert 'WHERE' in sql
    assert 'inactive' in params
    assert '2024-01-01' in params


def test_update_with_schema():
    """Test UPDATE with schema qualification"""
    status = 'active'
    query = UpdateBuilder.table('users', {'status': 'inactive'}, schema='public').where(t'status = {status}')
    sql, params = query.render()

    assert 'UPDATE public.users' in sql


def test_delete_from_string_table():
    """Test DELETE with string table name"""
    cutoff = '2023-01-01'
    query = DeleteBuilder.from_table('users').where(t'created_at < {cutoff}')
    sql, params = query.render()

    assert 'DELETE FROM users' in sql
    assert 'WHERE' in sql
    assert '2023-01-01' in params


def test_delete_with_schema():
    """Test DELETE with schema qualification"""
    user_id = 999
    query = DeleteBuilder.from_table('users', schema='public').where(t'id = {user_id}')
    sql, params = query.render()

    assert 'DELETE FROM public.users' in sql


def test_string_based_prevents_injection():
    """Test that invalid identifiers raise errors via :literal validation"""
    import pytest

    # Invalid table name
    with pytest.raises(ValueError):
        query = SelectQueryBuilder.from_table('users; DROP TABLE users--')
        query.render()

    # Invalid column name
    with pytest.raises(ValueError):
        query = SelectQueryBuilder.from_table('users').select('id; DROP TABLE users--')
        query.render()

    # Invalid schema name (too many dots)
    with pytest.raises(ValueError):
        query = SelectQueryBuilder.from_table('users', schema='a.b.c.d')
        query.render()


def test_mixed_string_and_tstring_columns():
    """Test mixing string columns with t-string expressions"""
    query = SelectQueryBuilder.from_table('users').select('id', 'name', t'UPPER(email) AS email_upper')
    sql, params = query.render()

    assert 'SELECT id, name, UPPER(email) AS email_upper' in sql


def test_string_select_star():
    """Test SELECT * with string-based table"""
    query = SelectQueryBuilder.from_table('users')
    sql, params = query.render()

    assert 'SELECT * FROM users' in sql
