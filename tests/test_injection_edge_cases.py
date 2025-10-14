import pytest
import tsql
import tsql.styles


def test_literal_injection_prevention():
    malicious_table = "users; DROP TABLE secrets; --"

    with pytest.raises(ValueError):
        tsql.render(t"SELECT * FROM {malicious_table:literal}")


def test_literal_with_quotes_prevention():
    malicious_column = "name'; DROP TABLE users; --"

    with pytest.raises(ValueError):
        tsql.render(t"SELECT {malicious_column:literal} FROM users")


def test_binary_data_injection():
    """Test handling of binary data that might contain SQL"""
    # Binary data that contains SQL-like bytes
    malicious_binary = b"'; DROP TABLE users; --"

    # Test parameterized style (default)
    result = tsql.render(t"INSERT INTO files (data) VALUES ({malicious_binary})")
    assert result[0] == "INSERT INTO files (data) VALUES (?)"
    # Binary data should be passed through as bytes, not converted to string
    assert result[1] == [malicious_binary]
    assert isinstance(result[1][0], bytes)

    # Test ESCAPED style - should convert to safe hex literal (no parameters)
    result_escaped = tsql.render(
        t"INSERT INTO files (data) VALUES ({malicious_binary})",
        style=tsql.styles.ESCAPED
    )
    expected_hex = malicious_binary.hex()
    assert result_escaped[0] == f"INSERT INTO files (data) VALUES ('\\x{expected_hex}')"
    assert result_escaped[1] == []


def test_cross_parameter_injection():
    """Test prevention of injection across multiple parameters"""
    param1 = "'; --"
    param2 = "OR 1=1"

    # Test parameterized style (default)
    result = tsql.render(t"SELECT * FROM users WHERE name = {param1} AND role = {param2}")
    assert result[0] == "SELECT * FROM users WHERE name = ? AND role = ?"
    assert result[1] == [param1, param2]

    # Test ESCAPED style
    result_escaped = tsql.render(t"SELECT * FROM users WHERE name = {param1} AND role = {param2}", style=tsql.styles.ESCAPED)
    expected_param1 = param1.replace("'", "''")
    expected_param2 = param2.replace("'", "''")
    assert result_escaped[0] == f"SELECT * FROM users WHERE name = '{expected_param1}' AND role = '{expected_param2}'"
    assert result_escaped[1] == []


def test_nested_template_injection():
    """Test injection prevention in nested templates"""
    malicious_value = "'; DROP TABLE users; --"
    inner_template = t"WHERE id = {malicious_value}"

    # Test parameterized style (default)
    result = tsql.render(t"SELECT * FROM users {inner_template}")
    assert result[0] == "SELECT * FROM users WHERE id = ?"
    assert result[1] == [malicious_value]

    # Test ESCAPED style
    result_escaped = tsql.render(t"SELECT * FROM users {inner_template}", style=tsql.styles.ESCAPED)
    expected_escaped = malicious_value.replace("'", "''")
    assert result_escaped[0] == f"SELECT * FROM users WHERE id = '{expected_escaped}'"
    assert result_escaped[1] == []


def test_helper_function_injection():
    """Test injection prevention in helper functions"""
    malicious_table = "users; DROP TABLE secrets; --"
    malicious_id = "1; DELETE FROM users; --"

    # This should raise ValueError for malicious table name
    with pytest.raises(ValueError):
        tsql.select(malicious_table, malicious_id)


def test_large_payload_injection():
    """Test handling of very large malicious payloads"""
    large_payload = "'; " + "DROP TABLE users; " * 1000 + "--"

    # Test parameterized style (default)
    result = tsql.render(t"SELECT * FROM users WHERE name = {large_payload}")
    assert result[0] == "SELECT * FROM users WHERE name = ?"
    assert result[1] == [large_payload]

    # Test ESCAPED style
    result_escaped = tsql.render(t"SELECT * FROM users WHERE name = {large_payload}", style=tsql.styles.ESCAPED)
    expected_escaped = large_payload.replace("'", "''")
    assert result_escaped[0] == f"SELECT * FROM users WHERE name = '{expected_escaped}'"
    assert result_escaped[1] == []


def test_encoding_bypass_attempts():
    """Test prevention of encoding-based bypass attempts"""
    encoding_attacks = [
        "'; DROP TABLE users; --",  # Normal
        "\'; DROP TABLE users; --",  # Backslash escaped
        "\\'; DROP TABLE users; --",  # Double backslash
        "%27; DROP TABLE users; --",  # URL encoded single quote
        "&#39; DROP TABLE users; --"  # HTML entity
    ]

    for attack in encoding_attacks:
        # Test parameterized style (default)
        result = tsql.render(t"SELECT * FROM users WHERE name = {attack}")
        assert result[0] == "SELECT * FROM users WHERE name = ?"
        assert result[1] == [attack]

        # Test ESCAPED style
        result_escaped = tsql.render(t"SELECT * FROM users WHERE name = {attack}", style=tsql.styles.ESCAPED)
        expected_escaped = attack.replace("'", "''")
        assert result_escaped[0] == f"SELECT * FROM users WHERE name = '{expected_escaped}'"
        assert result_escaped[1] == []


def test_database_specific_functions():
    """Test prevention of database-specific function injection"""
    db_specific_attacks = [
        "'; SELECT sqlite_version(); --",  # SQLite
        "'; SELECT @@version; --",  # SQL Server/MySQL
        "'; SELECT version(); --",  # PostgreSQL
        "'; SELECT banner FROM v$version; --",  # Oracle
    ]

    for attack in db_specific_attacks:
        # Test parameterized style (default)
        result = tsql.render(t"SELECT * FROM users WHERE id = {attack}")
        assert result[0] == "SELECT * FROM users WHERE id = ?"
        assert result[1] == [attack]

        # Test ESCAPED style
        result_escaped = tsql.render(t"SELECT * FROM users WHERE id = {attack}", style=tsql.styles.ESCAPED)
        expected_escaped = attack.replace("'", "''")
        assert result_escaped[0] == f"SELECT * FROM users WHERE id = '{expected_escaped}'"
        assert result_escaped[1] == []


def test_unsafe_parameter_injection():
    """Test that :unsafe parameters are properly handled (if implemented)"""
    # Note: This assumes :unsafe is implemented - remove if not
    malicious_value = "'; DROP TABLE users; --"

    # :unsafe should allow the value through without parameterization
    # but this is intentionally dangerous and should be used carefully
    result = tsql.render(t"SELECT * FROM users WHERE debug = {malicious_value:unsafe}")
    # This will depend on your :unsafe implementation
    assert "DROP TABLE users" in result[0]  # Should be directly embedded

    # Test ESCAPED style with :unsafe (should behave the same)
    result_escaped = tsql.render(t"SELECT * FROM users WHERE debug = {malicious_value:unsafe}", style=tsql.styles.ESCAPED)
    assert "DROP TABLE users" in result_escaped[0]  # Should be directly embedded


def test_dictionary_key_injection_as_values():
    """Test that malicious dictionary keys in :as_values are rejected"""
    # Classic SQL injection in dictionary key
    malicious_dict = {
        "name); DROP TABLE users; --": "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {malicious_dict:as_values}")

    # Semicolon in key
    malicious_dict2 = {
        "name; DELETE FROM users": "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {malicious_dict2:as_values}")

    # Quote in key
    malicious_dict3 = {
        "name' OR '1'='1": "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {malicious_dict3:as_values}")

    # Comment in key
    malicious_dict4 = {
        "name--": "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {malicious_dict4:as_values}")


def test_dictionary_key_injection_as_set():
    """Test that malicious dictionary keys in :as_set are rejected"""
    # Classic injection attempt in UPDATE
    malicious_dict = {
        "email = 'hacker@evil.com' WHERE 1=1; --": "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"UPDATE users SET {malicious_dict:as_set} WHERE id = 1")

    # Another variant
    malicious_dict2 = {
        "role = 'admin'--": "user"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"UPDATE users SET {malicious_dict2:as_set} WHERE id = 1")


def test_empty_dictionary_as_values():
    """Test that empty dictionaries are rejected in :as_values"""
    empty_dict = {}

    with pytest.raises(ValueError, match="at least one column"):
        tsql.render(t"INSERT INTO users {empty_dict:as_values}")


def test_empty_dictionary_as_set():
    """Test that empty dictionaries are rejected in :as_set"""
    empty_dict = {}

    with pytest.raises(ValueError, match="at least one column"):
        tsql.render(t"UPDATE users SET {empty_dict:as_set} WHERE id = 1")


def test_non_string_dictionary_keys():
    """Test that non-string dictionary keys are rejected"""
    # Integer key
    int_key_dict = {
        123: "value"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {int_key_dict:as_values}")

    # Tuple key
    tuple_key_dict = {
        ("name", "value"): "test"
    }

    with pytest.raises(ValueError, match="Invalid column name"):
        tsql.render(t"INSERT INTO users {tuple_key_dict:as_values}")


def test_valid_dictionary_keys_still_work():
    """Test that valid identifiers still work in dictionaries"""
    # Simple identifier
    valid_dict = {
        "name": "Alice",
        "age": 30
    }

    result = tsql.render(t"INSERT INTO users {valid_dict:as_values}")
    assert "(name, age) VALUES (?, ?)" in result[0]
    assert result[1] == ["Alice", 30]

    # Valid identifiers with underscores
    valid_dict2 = {
        "first_name": "Bob",
        "last_name": "Smith"
    }

    result2 = tsql.render(t"UPDATE users SET {valid_dict2:as_set} WHERE id = 1")
    assert "first_name = ?" in result2[0]
    assert "last_name = ?" in result2[0]
    assert result2[1] == ["Bob", "Smith"]


def test_literal_too_many_parts():
    """Test that literals with more than 3 parts are rejected"""
    # 4 parts should be rejected
    four_part_literal = "a.b.c.d"
    with pytest.raises(ValueError, match="too many parts"):
        tsql.render(t"SELECT * FROM {four_part_literal:literal}")

    # 5 parts should be rejected
    five_part_literal = "a.b.c.d.e"
    with pytest.raises(ValueError, match="too many parts"):
        tsql.render(t"SELECT * FROM {five_part_literal:literal}")

    # Many parts should be rejected
    many_parts_literal = ".".join(["a"] * 10)
    with pytest.raises(ValueError, match="too many parts"):
        tsql.render(t"SELECT * FROM {many_parts_literal:literal}")


def test_literal_valid_parts():
    """Test that literals with 1-3 parts are accepted"""
    # 1 part (simple table name)
    one_part = "users"
    result = tsql.render(t"SELECT * FROM {one_part:literal}")
    assert result[0] == "SELECT * FROM users"
    assert result[1] == []

    # 2 parts (schema.table)
    two_parts = "public.users"
    result = tsql.render(t"SELECT * FROM {two_parts:literal}")
    assert result[0] == "SELECT * FROM public.users"
    assert result[1] == []

    # 3 parts (database.schema.table or schema.table.column)
    three_parts = "mydb.public.users"
    result = tsql.render(t"SELECT * FROM {three_parts:literal}")
    assert result[0] == "SELECT * FROM mydb.public.users"
    assert result[1] == []