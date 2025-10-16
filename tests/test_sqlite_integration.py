import aiosqlite
import pytest

import tsql
import tsql.styles
from tsql.query_builder import Table


@pytest.fixture
async def conn():
    # Use in-memory database for tests
    connection = await aiosqlite.connect(':memory:')

    await connection.execute("""
        CREATE TABLE test_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            active INTEGER,
            salary REAL
        )
    """)
    await connection.commit()

    yield connection

    await connection.close()


async def test_insert_with_returning(conn):
    """Test INSERT with RETURNING (SQLite 3.35+)"""
    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        email: str

    query = TestUsers.insert(name='Alice', email='alice@example.com').returning()
    sql, params = query.render()

    assert 'RETURNING *' in sql

    cursor = await conn.execute(sql, params)
    row = await cursor.fetchone()

    # Should get the inserted row back
    assert row[1] == 'Alice'  # name
    assert row[2] == 'alice@example.com'  # email


async def test_on_conflict_do_nothing(conn):
    """Test ON CONFLICT DO NOTHING (SQLite)"""
    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        email: str

    # Insert first row
    query1 = TestUsers.insert(name='Alice', email='alice@example.com')
    sql1, params1 = query1.render()

    await conn.execute(sql1, params1)
    await conn.commit()

    # Try to insert duplicate email with ON CONFLICT DO NOTHING
    query2 = TestUsers.insert(name='Bob', email='alice@example.com').on_conflict_do_nothing()
    sql2, params2 = query2.render()

    assert 'ON CONFLICT DO NOTHING' in sql2

    await conn.execute(sql2, params2)
    await conn.commit()

    # Should still only have one row
    cursor = await conn.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 1

    # Verify it's the first row
    cursor = await conn.execute("SELECT name FROM test_users WHERE email = ?", ('alice@example.com',))
    name = (await cursor.fetchone())[0]
    assert name == 'Alice'


async def test_on_conflict_update(conn):
    """Test ON CONFLICT DO UPDATE (SQLite upsert)"""
    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        email: str
        age: int

    # Insert first row
    query1 = TestUsers.insert(name='Alice', email='alice@example.com', age=30).returning()
    sql1, params1 = query1.render()

    cursor = await conn.execute(sql1, params1)
    await cursor.fetchone()  # Consume the result
    await conn.commit()

    # Insert with duplicate email, but update on conflict
    query2 = TestUsers.insert(name='Alice Updated', email='alice@example.com', age=31).on_conflict_update(conflict_on='email').returning()
    sql2, params2 = query2.render()

    assert 'ON CONFLICT (email)' in sql2
    assert 'DO UPDATE SET' in sql2
    assert 'EXCLUDED.name' in sql2
    assert 'RETURNING *' in sql2

    cursor = await conn.execute(sql2, params2)
    row = await cursor.fetchone()
    await conn.commit()

    # Should return updated row
    assert row[1] == 'Alice Updated'
    assert row[3] == 31

    # Should still only have one row
    cursor = await conn.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 1


async def test_update_with_returning(conn):
    """Test UPDATE with RETURNING (SQLite 3.35+)"""
    # Insert a row first
    await conn.execute(
        "INSERT INTO test_users (name, email, age) VALUES (?, ?, ?)",
        ('Alice', 'alice@example.com', 30)
    )
    await conn.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        age: int

    # Update with RETURNING
    query = TestUsers.update(age=31).where(TestUsers.name == 'Alice').returning()
    sql, params = query.render()

    assert 'RETURNING *' in sql

    cursor = await conn.execute(sql, params)
    row = await cursor.fetchone()
    await conn.commit()

    # Should return updated row
    assert row[3] == 31  # age column


async def test_delete_with_returning(conn):
    """Test DELETE with RETURNING (SQLite 3.35+)"""
    # Insert a row first
    await conn.execute(
        "INSERT INTO test_users (name, email, age) VALUES (?, ?, ?)",
        ('Alice', 'alice@example.com', 30)
    )
    await conn.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str

    # Delete with RETURNING
    query = TestUsers.delete().where(TestUsers.name == 'Alice').returning()
    sql, params = query.render()

    assert 'RETURNING *' in sql

    cursor = await conn.execute(sql, params)
    row = await cursor.fetchone()
    await conn.commit()

    # Should return deleted row
    assert row[1] == 'Alice'

    # Verify deletion
    cursor = await conn.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 0


async def test_update_without_returning(conn):
    """Test UPDATE without RETURNING clause"""
    # Insert a row first
    await conn.execute(
        "INSERT INTO test_users (name, email, age) VALUES (?, ?, ?)",
        ('Alice', 'alice@example.com', 30)
    )
    await conn.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        age: int

    # Update without RETURNING
    query = TestUsers.update(age=31).where(TestUsers.name == 'Alice')
    sql, params = query.render()

    # Should NOT have RETURNING clause
    assert 'RETURNING' not in sql

    await conn.execute(sql, params)
    await conn.commit()

    # Verify update
    cursor = await conn.execute("SELECT age FROM test_users WHERE name = ?", ('Alice',))
    age = (await cursor.fetchone())[0]
    assert age == 31


async def test_sql_injection_protection(conn):
    """Test that SQL injection is prevented"""
    malicious_name = "'; DROP TABLE test_users; --"
    age = 25

    query, params = tsql.render(
        t"INSERT INTO test_users (name, age) VALUES ({malicious_name}, {age})"
    )

    # Should be parameterized
    assert params == [malicious_name, 25]
    assert 'DROP TABLE' not in query

    await conn.execute(query, params)
    await conn.commit()

    # Verify table still exists and has the data
    cursor = await conn.execute("SELECT name FROM test_users WHERE age = ?", (25,))
    row = await cursor.fetchone()
    assert row[0] == "'; DROP TABLE test_users; --"


async def test_escaped_style(conn):
    """Test ESCAPED style with SQLite"""
    values = {
        'name': "John O'Connor",
        'email': 'john@example.com',
        'age': 30
    }

    query, params = tsql.render(
        t"INSERT INTO test_users {values:as_values}",
        style=tsql.styles.ESCAPED
    )

    # Verify no parameters (ESCAPED embeds values)
    assert params == []
    assert "John O''Connor" in query  # Single quote should be escaped

    await conn.execute(query)
    await conn.commit()

    # Verify data was inserted
    cursor = await conn.execute("SELECT name FROM test_users WHERE name = ?", ("John O'Connor",))
    row = await cursor.fetchone()
    assert row[0] == "John O'Connor"


async def test_helper_functions(conn):
    """Test simple helper functions work with SQLite"""
    # Test insert
    query = tsql.insert('test_users', name='Bob', email='bob@example.com', age=25)
    sql, params = query.render()

    await conn.execute(sql, params)
    await conn.commit()

    # Test select
    query = tsql.select('test_users', columns=['name', 'age'])
    sql, params = query.render()

    cursor = await conn.execute(sql, params)
    row = await cursor.fetchone()
    assert row[0] == 'Bob'
    assert row[1] == 25

    # Test update
    query = tsql.update('test_users', 1, age=26)
    sql, params = query.render()

    await conn.execute(sql, params)
    await conn.commit()

    # Verify update
    cursor = await conn.execute("SELECT age FROM test_users WHERE id = 1")
    age = (await cursor.fetchone())[0]
    assert age == 26

    # Test delete
    query = tsql.delete('test_users', 1)
    sql, params = query.render()

    await conn.execute(sql, params)
    await conn.commit()

    # Verify deletion
    cursor = await conn.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 0


async def test_query_builder_select(conn):
    """Test query builder SELECT features"""
    # Insert some test data
    await conn.execute(
        "INSERT INTO test_users (name, email, age) VALUES (?, ?, ?)",
        ('Alice', 'alice@example.com', 30)
    )
    await conn.execute(
        "INSERT INTO test_users (name, email, age) VALUES (?, ?, ?)",
        ('Bob', 'bob@example.com', 25)
    )
    await conn.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        age: int

    # Test WHERE clause
    query = TestUsers.select(TestUsers.name, TestUsers.age).where(TestUsers.age > 26)
    sql, params = query.render()

    cursor = await conn.execute(sql, params)
    rows = await cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == 'Alice'

    # Test ORDER BY
    query = TestUsers.select().order_by(TestUsers.age.desc())
    sql, params = query.render()

    cursor = await conn.execute(sql, params)
    rows = await cursor.fetchall()

    assert len(rows) == 2
    assert rows[0][1] == 'Alice'  # Older person first
    assert rows[1][1] == 'Bob'

    # Test LIMIT
    query = TestUsers.select().limit(1)
    sql, params = query.render()

    cursor = await conn.execute(sql, params)
    rows = await cursor.fetchall()

    assert len(rows) == 1
