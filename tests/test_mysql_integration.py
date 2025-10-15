import aiomysql
import os
import pytest
import warnings

import tsql
import tsql.styles
from tsql.query_builder import Table


# Test configuration
DATABASE_CONFIG = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'port': int(os.getenv("MYSQL_PORT", "3307")),
    'user': os.getenv("MYSQL_USER", "testuser"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'db': os.getenv("MYSQL_DB", "testdb"),
}


@pytest.fixture
async def conn():
    connection = await aiomysql.connect(**DATABASE_CONFIG)
    cursor = await connection.cursor()

    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            age INT,
            active BOOLEAN,
            salary DECIMAL(10,2)
        )
    """)
    await cursor.execute("DELETE FROM test_users")
    await connection.commit()

    yield connection, cursor

    await cursor.execute("DROP TABLE IF EXISTS test_users")
    await connection.commit()
    await cursor.close()
    connection.close()


async def test_insert_with_escaped_style(conn):
    """Test INSERT with ESCAPED style (MySQL-specific)"""
    connection, cursor = conn

    values = {
        'name': "John O'Connor",
        'email': 'john@example.com',
        'age': 30,
        'active': True,
        'salary': 75000.50
    }

    query, params = tsql.render(
        t"INSERT INTO test_users {values:as_values}",
        style=tsql.styles.ESCAPED
    )

    # Verify no parameters (ESCAPED embeds values)
    assert params == []
    assert "John O''Connor" in query  # Single quote should be escaped

    await cursor.execute(query)
    await connection.commit()

    # Verify data was inserted
    await cursor.execute("SELECT * FROM test_users WHERE name = %s", ("John O'Connor",))
    row = await cursor.fetchone()
    assert row[1] == "John O'Connor"  # name column
    assert row[3] == 30  # age column


async def test_insert_ignore(conn):
    """Test INSERT IGNORE (MySQL-specific)"""
    connection, cursor = conn

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        email: str

    # Insert first row
    query1 = TestUsers.insert(name='Alice', email='alice@example.com')
    sql1, params1 = query1.render(style=tsql.styles.FORMAT)

    await cursor.execute(sql1, params1)
    await connection.commit()

    # Try to insert duplicate email with INSERT IGNORE
    query2 = TestUsers.insert(name='Bob', email='alice@example.com').ignore()
    sql2, params2 = query2.render(style=tsql.styles.FORMAT)

    assert 'INSERT IGNORE' in sql2

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message="Duplicate entry.*")
        await cursor.execute(sql2, params2)
        await connection.commit()

    # Should still only have one row (first insert)
    await cursor.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 1

    # Verify it's the first row
    await cursor.execute("SELECT name FROM test_users WHERE email = %s", ('alice@example.com',))
    name = (await cursor.fetchone())[0]
    assert name == 'Alice'


async def test_on_duplicate_key_update(conn):
    """Test ON DUPLICATE KEY UPDATE (MySQL-specific)"""
    connection, cursor = conn

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        email: str
        age: int

    # Insert first row
    query1 = TestUsers.insert(name='Alice', email='alice@example.com', age=30)
    sql1, params1 = query1.render(style=tsql.styles.FORMAT)

    await cursor.execute(sql1, params1)
    await connection.commit()

    # Insert with duplicate email, but update on conflict
    query2 = TestUsers.insert(name='Alice Updated', email='alice@example.com', age=31).on_duplicate_key_update()
    sql2, params2 = query2.render(style=tsql.styles.FORMAT)

    assert 'ON DUPLICATE KEY UPDATE' in sql2
    assert 'AS new' in sql2
    assert 'new.name' in sql2 or 'new.age' in sql2

    await cursor.execute(sql2, params2)
    await connection.commit()

    # Should still only have one row (updated)
    await cursor.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 1

    # Verify it was updated
    await cursor.execute("SELECT name, age FROM test_users WHERE email = %s", ('alice@example.com',))
    row = await cursor.fetchone()
    assert row[0] == 'Alice Updated'
    assert row[1] == 31


async def test_update_without_returning(conn):
    """Test UPDATE without RETURNING (MySQL doesn't support RETURNING)"""
    connection, cursor = conn

    # Insert a row first
    await cursor.execute(
        "INSERT INTO test_users (name, email, age) VALUES (%s, %s, %s)",
        ('Alice', 'alice@example.com', 30)
    )
    await connection.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str
        age: int

    # Update without RETURNING
    query = TestUsers.update(age=31).where(TestUsers.name == 'Alice')
    sql, params = query.render(style=tsql.styles.FORMAT)

    # Should NOT have RETURNING clause
    assert 'RETURNING' not in sql

    await cursor.execute(sql, params)
    await connection.commit()

    # Verify update
    await cursor.execute("SELECT age FROM test_users WHERE name = %s", ('Alice',))
    age = (await cursor.fetchone())[0]
    assert age == 31


async def test_delete_without_returning(conn):
    """Test DELETE without RETURNING (MySQL doesn't support RETURNING)"""
    connection, cursor = conn

    # Insert a row first
    await cursor.execute(
        "INSERT INTO test_users (name, email, age) VALUES (%s, %s, %s)",
        ('Alice', 'alice@example.com', 30)
    )
    await connection.commit()

    class TestUsers(Table, table_name='test_users'):
        id: int
        name: str

    # Delete without RETURNING
    query = TestUsers.delete().where(TestUsers.name == 'Alice')
    sql, params = query.render(style=tsql.styles.FORMAT)

    # Should NOT have RETURNING clause
    assert 'RETURNING' not in sql

    await cursor.execute(sql, params)
    await connection.commit()

    # Verify deletion
    await cursor.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 0


async def test_sql_injection_protection(conn):
    """Test that SQL injection is prevented"""
    connection, cursor = conn

    malicious_name = "'; DROP TABLE test_users; --"
    age = 25

    query, params = tsql.render(
        t"INSERT INTO test_users (name, age) VALUES ({malicious_name}, {age})",
        style=tsql.styles.FORMAT
    )

    # Should be parameterized
    assert params == [malicious_name, 25]
    assert 'DROP TABLE' not in query

    await cursor.execute(query, params)
    await connection.commit()

    # Verify table still exists and has the data
    await cursor.execute("SELECT name FROM test_users WHERE age = %s", (25,))
    row = await cursor.fetchone()
    assert row[0] == "'; DROP TABLE test_users; --"


async def test_helper_functions(conn):
    """Test simple helper functions work with MySQL"""
    connection, cursor = conn

    # Test insert
    query = tsql.insert('test_users', name='Bob', email='bob@example.com', age=25)
    sql, params = query.render(style=tsql.styles.FORMAT)

    await cursor.execute(sql, params)
    await connection.commit()

    # Test select
    query = tsql.select('test_users', columns=['name', 'age'])
    sql, params = query.render()

    await cursor.execute(sql, params)
    row = await cursor.fetchone()
    assert row[0] == 'Bob'
    assert row[1] == 25

    # Test update
    query = tsql.update('test_users', 1, age=26)
    sql, params = query.render(style=tsql.styles.FORMAT)

    await cursor.execute(sql, params)
    await connection.commit()

    # Verify update
    await cursor.execute("SELECT age FROM test_users WHERE id = 1")
    age = (await cursor.fetchone())[0]
    assert age == 26

    # Test delete
    query = tsql.delete('test_users', 1)
    sql, params = query.render(style=tsql.styles.FORMAT)

    await cursor.execute(sql, params)
    await connection.commit()

    # Verify deletion
    await cursor.execute("SELECT COUNT(*) FROM test_users")
    count = (await cursor.fetchone())[0]
    assert count == 0
