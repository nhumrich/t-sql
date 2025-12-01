import asyncpg
import datetime
import os
import pytest

import tsql
import tsql.styles


# Test configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5454/postgres")


@pytest.fixture
async def conn():
    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            age INTEGER,
            active BOOLEAN,
            salary DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("DELETE FROM test_users")
    yield conn

    await conn.execute("DROP TABLE IF EXISTS test_users")
    await conn.close()


async def test_escaped_style_with_postgres(conn):
    values = dict(
        name = "John O'Connor",
        age = 30,
        active = True,
        salary = 75000.50
    )

    query, params = tsql.render(
        t"INSERT INTO test_users {values:as_values}",
        style=tsql.styles.ESCAPED
    )

    # Verify no parameters are used (ESCAPED embeds values directly)
    assert params == []
    assert "John O''Connor" in query  # Single quote should be escaped
    assert "30" in query
    assert "TRUE" in query
    assert "75000.5" in query

    await conn.execute(query)

    # Verify data was inserted correctly
    row = await conn.fetchrow("SELECT * FROM test_users WHERE name = $1", "John O'Connor")
    assert row['name'] == "John O'Connor"
    assert row['age'] == 30
    assert row['active'] is True
    assert float(row['salary']) == 75000.50


async def test_numeric_dollar_style_with_asyncpg(conn):
    values = dict(
        name="John O'Connor",
        age=30,
        active=True,
        salary=75000.50
    )

    query, params = tsql.render(
        t"INSERT INTO test_users {values:as_values}",
        style = tsql.styles.NUMERIC_DOLLAR
    )

    assert "$1" in query
    assert "$2" in query
    assert "$3" in query
    assert "'$4" in query

    await conn.execute(query)

    # Verify data was inserted correctly
    row = await conn.fetchrow("SELECT * FROM test_users WHERE name = $1", "John O'Connor")
    assert row['name'] == "John O'Connor"
    assert row['age'] == 30
    assert row['active'] is True
    assert float(row['salary']) == 75000.50


async def test_escaped_prevents_sql_injection_in_db(conn):
    # Attempt SQL injection
    malicious_name = "'; DROP TABLE test_users; --"
    age = 25

    query, params = tsql.render(
        t"INSERT INTO test_users (name, age) VALUES ({malicious_name}, {age})",
        style=tsql.styles.ESCAPED
    )

    assert params == []
    assert "'''; DROP TABLE test_users; --'" in query

    await conn.execute(query)

    # Verify the table still exists and contains the escaped data
    row = await conn.fetchrow("SELECT * FROM test_users WHERE age = $1", 25)
    assert row is not None
    assert row['name'] == "'; DROP TABLE test_users; --"

    # Verify table still exists by querying it
    count = await conn.fetchval("SELECT COUNT(*) FROM test_users")
    assert count == 1


async def test_numeric_dollar_style_with_asyncpg(conn):
    name = "David Wilson"
    age = 33

    query, params = tsql.render(
        t"INSERT INTO test_users (name, age) VALUES ({name}, {age})",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    # NUMERIC_DOLLAR should use $1, $2, etc. which is native to PostgreSQL, and is what asyncpg uses
    assert "$1" in query and "$2" in query
    assert params == ["David Wilson", 33]

    await conn.execute(query, *params)

    # Verify data was inserted correctly
    row = await conn.fetchrow("SELECT * FROM test_users WHERE name = $1", "David Wilson")
    assert row['name'] == "David Wilson"
    assert row['age'] == 33


async def test_escaped_handles_null_values_in_db(conn):
    name = None
    age = 30

    query, params = tsql.render(
        t"INSERT INTO test_users (name, age) VALUES ({name}, {age})",
        style=tsql.styles.ESCAPED
    )

    assert params == []
    assert "NULL" in query
    assert "30" in query

    await conn.execute(query)

    row = await conn.fetchrow("SELECT * FROM test_users WHERE age = $1", 30)
    assert row['name'] is None
    assert row['age'] == 30


async def test_escaped_complex_query_with_db(conn):
    # Insert some test data first
    await conn.execute("""
        INSERT INTO test_users (name, age, active, salary) VALUES 
        ('Alice', 28, true, 65000),
        ('Bob', 35, false, 80000),
        ('Charlie O''Brien', 42, true, 95000)
    """)

    # Query with multiple escaped parameters
    min_age = 30
    pattern = "O'Brien"
    is_active = True

    query, params = tsql.render(
        t"SELECT * FROM test_users WHERE age >= {min_age} AND name LIKE '%' || {pattern} || '%' AND active = {is_active}",
        style=tsql.styles.ESCAPED
    )

    assert params == []
    assert "30" in query
    assert "'O''Brien'" in query  # Single quote should be escaped
    assert "TRUE" in query

    rows = await conn.fetch(query)

    # Should find Charlie O'Brien
    assert len(rows) == 1
    assert rows[0]['name'] == "Charlie O'Brien"
    assert rows[0]['age'] == 42
    assert rows[0]['active'] is True


async def test_compare_escaped_vs_parameterized(conn):
    name = "Test User"
    age = 25
    active = True

    query1, params1 = tsql.render(
        t"INSERT INTO test_users (name, age, active) VALUES ({name}, {age}, {active})",
        style=tsql.styles.ESCAPED
    )
    await conn.execute(query1)

    query2, params2 = tsql.render(
        t"INSERT INTO test_users (name, age, active) VALUES ({name}, {age}, {active})",
        style=tsql.styles.NUMERIC_DOLLAR
    )
    await conn.execute(query2, *params2)

    # Both should produce the same results
    rows = await conn.fetch("SELECT name, age, active FROM test_users ORDER BY id")
    assert len(rows) == 2

    # Both rows should have the same data
    for row in rows:
        assert row['name'] == "Test User"
        assert row['age'] == 25
        assert row['active'] is True


async def test_escaped_handles_union_attack(conn):
    malicious_input = "' UNION SELECT password FROM test_users WHERE '1'='1"
    query, _ = tsql.render(t"SELECT * FROM test_users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    rows = await conn.fetch(query)
    assert len(rows) == 0


async def test_escaped_handles_boolean_injection(conn):
    malicious_input = "' OR '1'='1"
    query, _ = tsql.render(t"SELECT * FROM test_users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    rows = await conn.fetch(query)
    assert len(rows) == 0


async def test_escaped_handles_comment_injection(conn):
    malicious_input = "admin'--"
    query, _ = tsql.render(t"SELECT * FROM test_users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    rows = await conn.fetch(query)
    assert len(rows) == 0


async def test_datetime_comparison_with_asyncpg(conn):
    """Test that datetime objects work correctly with asyncpg (bug fix verification)"""
    # Insert some test data with specific timestamps
    base_time = datetime.datetime.now()

    await conn.execute(
        "INSERT INTO test_users (name, created_at) VALUES ($1, $2), ($3, $4), ($5, $6)",
        'User1', base_time - datetime.timedelta(minutes=30),
        'User2', base_time - datetime.timedelta(minutes=10),
        'User3', base_time - datetime.timedelta(minutes=5)
    )

    # Use a datetime object in a WHERE clause (this was broken before the fix)
    cutoff_time = base_time - datetime.timedelta(minutes=15)

    query, params = tsql.render(
        t"SELECT name FROM test_users WHERE created_at > {cutoff_time}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    # Verify the parameter is still a datetime object (not stringified)
    assert len(params) == 1
    assert isinstance(params[0], datetime.datetime)

    # This should work without asyncpg throwing a DataError
    rows = await conn.fetch(query, *params)

    # Should find User2 and User3 (created within last 15 minutes)
    assert len(rows) == 2
    names = sorted([row['name'] for row in rows])
    assert names == ['User2', 'User3']


async def test_like_pattern_format_specs_with_postgres(conn):
    """Test LIKE pattern format specs with PostgreSQL"""
    # Insert test data with special characters
    await conn.execute(
        "INSERT INTO test_users (name) VALUES ($1), ($2), ($3), ($4)",
        'john_doe', 'john%smith', 'alice', 'admin_50%'
    )

    # Test contains pattern (%like%)
    search = "john"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name LIKE {search:%like%} ORDER BY name",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    assert "ESCAPE '\\'" in sql
    assert params == ['%john%']

    rows = await conn.fetch(sql, *params)

    # Should match both john_doe and john%smith
    assert len(rows) == 2
    names = sorted([row['name'] for row in rows])
    assert names == ['john%smith', 'john_doe']

    # Test prefix pattern (like%)
    prefix = "admin"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name LIKE {prefix:like%}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    assert params == ['admin%']

    rows = await conn.fetch(sql, *params)

    # Should match admin_50%
    assert len(rows) == 1
    assert rows[0]['name'] == 'admin_50%'

    # Test wildcard escaping - searching for literal underscore
    search = "john_"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name LIKE {search:%like%}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    # Should escape the underscore
    assert params == ['%john\\_%']

    rows = await conn.fetch(sql, *params)

    # Should match only john_doe (literal underscore after "john")
    assert len(rows) == 1
    assert rows[0]['name'] == 'john_doe'

    # Test wildcard escaping - searching for literal percent
    search = "50%"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name LIKE {search:%like%}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    # Should escape the percent
    assert params == ['%50\\%%']

    rows = await conn.fetch(sql, *params)

    # Should match admin_50%
    assert len(rows) == 1
    assert rows[0]['name'] == 'admin_50%'

    # Test suffix pattern (%like)
    suffix = "_doe"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name LIKE {suffix:%like}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    # Underscore should be escaped
    assert params == ['%\\_doe']

    rows = await conn.fetch(sql, *params)

    # Should match john_doe
    assert len(rows) == 1
    assert rows[0]['name'] == 'john_doe'

    # Test ILIKE (case-insensitive) works too
    search = "JOHN"
    sql, params = tsql.render(
        t"SELECT name FROM test_users WHERE name ILIKE {search:%like%}",
        style=tsql.styles.NUMERIC_DOLLAR
    )

    rows = await conn.fetch(sql, *params)

    # Should match both john_doe and john%smith (case-insensitive)
    assert len(rows) == 2