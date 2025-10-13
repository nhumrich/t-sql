import asyncpg
import os
import pytest

import tsql
import tsql.styles

# Test configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5454/postgres")


@pytest.fixture
async def conn():
    """Helper to set up a clean test table and return a connection"""
    conn = await asyncpg.connect(DATABASE_URL)

    # Create a test table with sensitive data
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            password VARCHAR(100),
            role VARCHAR(50),
            salary DECIMAL(10,2),
            active BOOLEAN DEFAULT TRUE
        )
    """)

    # Create a sensitive admin table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_secrets (
            id SERIAL PRIMARY KEY,
            secret_key VARCHAR(255),
            admin_password VARCHAR(100)
        )
    """)

    # Clean up existing data
    await conn.execute("DELETE FROM test_users")
    await conn.execute("DELETE FROM admin_secrets")

    # Insert some test data
    await conn.execute("""
        INSERT INTO test_users (name, password, role, salary) VALUES
        ('alice', 'secret123', 'user', 50000),
        ('bob', 'password456', 'user', 60000),
        ('admin', 'supersecret', 'admin', 100000)
    """)

    await conn.execute("""
        INSERT INTO admin_secrets (secret_key, admin_password) VALUES
        ('TOP_SECRET_KEY_123', 'admin_master_password')
    """)

    yield conn

    await conn.execute("DROP TABLE IF EXISTS test_users")
    await conn.execute("DROP TABLE IF EXISTS admin_secrets")
    await conn.close()


async def test_parameterized_injection_protection(conn):
    """Verify parameterized queries properly protect against injection"""

    # Classic injection attempts
    injection_attempts = [
        "' OR 1=1 --",
        "'; DROP TABLE test_users; --",
        "' UNION SELECT secret_key, admin_password, 'hacker', 0, true FROM admin_secrets --",
        "admin'--"
    ]

    for malicious_input in injection_attempts:
        query, params = tsql.render(
            t"SELECT * FROM test_users WHERE name = {malicious_input}",
            style=tsql.styles.NUMERIC_DOLLAR  # Use asyncpg-compatible style
        )

        # Should be parameterized with $1 style
        assert "$1" in query
        assert params == [malicious_input]

        # Execute the parameterized query - should safely find no matching users
        rows = await conn.fetch(query, *params)
        assert len(rows) == 0

        # Verify database integrity - original data should be intact
        user_count = await conn.fetchval("SELECT COUNT(*) FROM test_users")
        admin_count = await conn.fetchval("SELECT COUNT(*) FROM admin_secrets")
        assert user_count == 3  # Original test users
        assert admin_count == 1  # Original admin secret


async def test_escaped_injection_protection(conn):
    """Verify ESCAPED style properly protects against injection"""

    injection_attempts = [
        "' OR 1=1 --",
        "'; DROP TABLE test_users; --",
        "' UNION SELECT secret_key FROM admin_secrets --",
        "admin'--"
    ]

    for malicious_input in injection_attempts:
        query, params = tsql.render(
            t"SELECT * FROM test_users WHERE name = {malicious_input}",
            style=tsql.styles.ESCAPED
        )

        # Should be escaped (no parameters)
        assert params == []
        escaped_input = malicious_input.replace("'", "''")
        assert f"'{escaped_input}'" in query

        # Execute the escaped query - should safely find no matching users
        rows = await conn.fetch(query)
        assert len(rows) == 0

        # Verify database integrity
        user_count = await conn.fetchval("SELECT COUNT(*) FROM test_users")
        admin_count = await conn.fetchval("SELECT COUNT(*) FROM admin_secrets")
        assert user_count == 3
        assert admin_count == 1


async def test_injection_treated_as_literal_data(conn):
    """Verify injection attempts are treated as literal data, not SQL code"""

    # Insert the malicious input as literal data
    malicious_name = "'; DROP TABLE test_users; --"

    # First, insert this as actual data using parameterized query
    insert_query, insert_params = tsql.render(
        t"INSERT INTO test_users (name, role) VALUES ({malicious_name}, 'test')",
        style=tsql.styles.NUMERIC_DOLLAR
    )
    await conn.execute(insert_query, *insert_params)

    # Now search for it using both styles
    for style in [tsql.styles.NUMERIC_DOLLAR, tsql.styles.ESCAPED]:
        query, params = tsql.render(
            t"SELECT * FROM test_users WHERE name = {malicious_name}",
            style=style
        )

        rows = await conn.fetch(query, *params if params else [])

        # Should find exactly 1 row with the malicious string as literal data
        assert len(rows) == 1
        assert rows[0]['name'] == malicious_name
        assert rows[0]['role'] == 'test'

    # Verify the table wasn't dropped by the "injection"
    user_count = await conn.fetchval("SELECT COUNT(*) FROM test_users")
    assert user_count == 4  # 3 original + 1 with malicious name


async def test_boolean_bypass_prevention(conn):
    """Verify OR 1=1 type attacks don't bypass authentication"""

    # Simulate authentication bypass attempt
    username = "nonexistent"
    malicious_password = "' OR 1=1 --"

    for style in [tsql.styles.NUMERIC_DOLLAR, tsql.styles.ESCAPED]:
        query, params = tsql.render(
            t"SELECT * FROM test_users WHERE name = {username} AND password = {malicious_password}",
            style=style
        )

        rows = await conn.fetch(query, *params if params else [])

        # Should return 0 rows - authentication should fail
        assert len(rows) == 0


async def test_admin_escalation_prevention(conn):
    """Verify injection can't escalate privileges to admin"""

    malicious_inputs = [
        "' OR role = 'admin' --",
        "' UNION SELECT * FROM test_users WHERE role = 'admin' --",
        "anything' OR 1=1 --"
    ]

    for malicious_input in malicious_inputs:
        for style in [tsql.styles.NUMERIC_DOLLAR, tsql.styles.ESCAPED]:
            query, params = tsql.render(
                t"SELECT * FROM test_users WHERE name = {malicious_input} AND role = 'user'",
                style=style
            )

            rows = await conn.fetch(query, *params if params else [])

            # Should not return admin users
            for row in rows:
                assert row.get('role') != 'admin'
                assert row.get('name') != 'admin'


async def test_literal_parameter_protection(conn):
    """Verify :literal parameters reject malicious table/column names"""

    malicious_table_names = [
        "test_users; DROP TABLE admin_secrets; --",
        "test_users UNION SELECT * FROM admin_secrets --",
        "test_users' OR 1=1 --"
    ]

    for malicious_table in malicious_table_names:
        # Should raise ValueError before reaching database
        with pytest.raises(ValueError):
            tsql.render(t"SELECT * FROM {malicious_table:literal}")


async def test_stacked_query_prevention(conn):
    """Verify stacked queries can't execute additional commands"""

    malicious_input = "'; INSERT INTO test_users (name, role) VALUES ('hacker', 'admin'); --"

    original_count = await conn.fetchval("SELECT COUNT(*) FROM test_users")

    for style in [tsql.styles.NUMERIC_DOLLAR, tsql.styles.ESCAPED]:
        query, params = tsql.render(
            t"SELECT * FROM test_users WHERE name = {malicious_input}",
            style=style
        )

        rows = await conn.fetch(query, *params if params else [])
        assert len(rows) == 0

    # Verify no hacker user was inserted
    final_count = await conn.fetchval("SELECT COUNT(*) FROM test_users")
    assert final_count == original_count

    # Explicitly check no hacker exists
    hacker_count = await conn.fetchval("SELECT COUNT(*) FROM test_users WHERE name = 'hacker'")
    assert hacker_count == 0