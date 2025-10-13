"""
Proof-of-concept test demonstrating that tsql actually prevents SQL injection attacks
against a real PostgreSQL database.
"""
import asyncpg
import os
import pytest

import tsql
import tsql.styles

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5454/postgres")


@pytest.fixture
async def conn():
    """Set up test database with sensitive data"""
    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50),
            password VARCHAR(100),
            is_admin BOOLEAN DEFAULT FALSE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            id SERIAL PRIMARY KEY,
            secret_data VARCHAR(255)
        )
    """)

    # Clean up previous data if exsist
    await conn.execute("DELETE FROM users")
    await conn.execute("DELETE FROM secrets")

    # Insert test data
    await conn.execute("""
        INSERT INTO users (username, password, is_admin) VALUES
        ('alice', 'password123', false),
        ('admin', 'supersecret', true)
    """)

    await conn.execute("""
        INSERT INTO secrets (secret_data) VALUES
        ('TOP_SECRET_ADMIN_KEY')
    """)

    yield conn

    # Cleanup
    await conn.execute("DROP TABLE IF EXISTS users")
    await conn.execute("DROP TABLE IF EXISTS secrets")
    await conn.close()


async def test_basic_injection_attack_with_real_database(conn):
    malicious_username = "' OR 1=1 --"
    fake_password = "anything"

    query, params = tsql.render(
        t"SELECT * FROM users WHERE username = {malicious_username} AND password = {fake_password}",
        style=tsql.styles.ESCAPED
    )

    rows = await conn.fetch(query)

    assert len(rows) == 0

async def test_union_injection_attack_with_real_database(conn):
    malicious_username = "' UNION SELECT id, secret_data, 'fake', true FROM secrets --"
    query, params = tsql.render(
        t"SELECT * FROM users WHERE username = {malicious_username}",
        style=tsql.styles.ESCAPED
    )

    rows = await conn.fetch(query)

    assert len(rows) == 0

async def test_stacked_injection_attack_with_real_database(conn):
    malicious_username = "'; DROP TABLE secrets; --"

    query, params = tsql.render(
        t"SELECT * FROM users WHERE username = {malicious_username}",
        style=tsql.styles.ESCAPED
    )

    rows = await conn.fetch(query)
    assert len(rows) == 0

    secret_count = await conn.fetchval("SELECT COUNT(*) FROM secrets")
    assert secret_count == 1


async def test_legitimate_usage_still_works(conn):
    username = "alice"

    query, params = tsql.render(
        t"SELECT * FROM users WHERE username = {username}",
        style=tsql.styles.ESCAPED
    )

    rows = await conn.fetch(query)

    assert len(rows) == 1
    assert rows[0]['username'] == 'alice'
    assert rows[0]['is_admin'] is False


async def test_malicious_data_stored_safely(conn):
    """Verify malicious strings can be safely stored and retrieved as data"""

    # Store what looks like SQL injection as actual data
    malicious_data = "'; DROP TABLE users; --"

    # Insert it safely
    query, params = tsql.render(
        t"INSERT INTO users (username, password, is_admin) VALUES ({malicious_data}, 'test123', false)",
        style=tsql.styles.ESCAPED
    )

    await conn.execute(query)

    # Retrieve it safely
    query, params = tsql.render(
        t"SELECT * FROM users WHERE username = {malicious_data}",
        style=tsql.styles.ESCAPED
    )

    rows = await conn.fetch(query)

    assert len(rows) == 1
    assert rows[0]['username'] == malicious_data

    # Verify the database wasn't compromised
    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    assert user_count == 3  # alice + admin + our malicious_data user



@pytest.mark.parametrize("attack", [
    "' AND (SELECT TOP 1 name FROM sysobjects WHERE xtype='U') > 0 --",
    "' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version()), 0x7e)) --",
    "' AND (SELECT * FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a) --"
])
async def test_error_based_injection_patterns(attack, conn):
    query, params = tsql.render(t"SELECT * FROM users WHERE id = {attack}")
    assert query == "SELECT * FROM users WHERE id = ?"
    assert params == [attack]

    query_escaped, params_escaped = tsql.render(t"SELECT * FROM users WHERE id = {attack}", style=tsql.styles.ESCAPED)
    expected_escaped = attack.replace("'", "''")
    assert query_escaped == f"SELECT * FROM users WHERE id = '{expected_escaped}'"
    assert params_escaped == []
