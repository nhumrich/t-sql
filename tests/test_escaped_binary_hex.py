"""
Test the hybrid ESCAPED style behavior with binary data
"""
import tsql
import tsql.styles


def test_escaped_hex_with_mixed_types():
    """Test that ESCAPED style handles mixed data types correctly"""

    # Mix of different data types including binary
    filename = "test.bin"
    size = 1024
    active = True
    binary_data = b"'; DROP TABLE files; --"

    result = tsql.render(
        t"INSERT INTO files (name, size, active, data) VALUES ({filename}, {size}, {active}, {binary_data})",
        style=tsql.styles.ESCAPED
    )

    # Should escape strings, numbers, bools and convert binary to hex literal
    expected_hex = binary_data.hex()
    expected_query = f"INSERT INTO files (name, size, active, data) VALUES ('test.bin', 1024, TRUE, '\\x{expected_hex}')"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped


def test_escaped_hex_multiple_binary_values():
    """Test ESCAPED style with multiple binary values"""

    binary1 = b"first'; DROP TABLE test; --"
    binary2 = b"second'; DELETE FROM users; --"
    name = "test"

    result = tsql.render(
        t"INSERT INTO files (name, data1, data2) VALUES ({name}, {binary1}, {binary2})",
        style=tsql.styles.ESCAPED
    )

    # Should convert both binary values to hex literals
    hex1 = binary1.hex()
    hex2 = binary2.hex()
    expected_query = f"INSERT INTO files (name, data1, data2) VALUES ('test', '\\x{hex1}', '\\x{hex2}')"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped


def test_escaped_hex_binary_with_quotes():
    """Test that binary data with quotes is safely converted to hex"""

    # Binary data containing various injection attempts
    malicious_binary = b"'; DELETE FROM users WHERE '1'='1'; --"
    safe_string = "normal string"

    result = tsql.render(
        t"UPDATE files SET name = {safe_string}, data = {malicious_binary} WHERE id = 1",
        style=tsql.styles.ESCAPED
    )

    expected_hex = malicious_binary.hex()
    expected_query = f"UPDATE files SET name = 'normal string', data = '\\x{expected_hex}' WHERE id = 1"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped


def test_escaped_all_string_no_hybrid():
    """Test that pure string queries remain fully escaped (no parameters)"""

    name = "file.txt"
    content = "some content"

    result = tsql.render(
        t"INSERT INTO files (name, content) VALUES ({name}, {content})",
        style=tsql.styles.ESCAPED
    )

    # Should be fully escaped with no parameters
    expected_query = "INSERT INTO files (name, content) VALUES ('file.txt', 'some content')"
    assert result[0] == expected_query
    assert result[1] == []


def test_escaped_string_injection_still_escaped():
    """Test that string injection attempts are still properly escaped"""

    malicious_string = "'; DROP TABLE users; --"

    result = tsql.render(
        t"SELECT * FROM users WHERE name = {malicious_string}",
        style=tsql.styles.ESCAPED
    )

    # String should be escaped, no parameters
    expected_query = "SELECT * FROM users WHERE name = '''; DROP TABLE users; --'"
    assert result[0] == expected_query
    assert result[1] == []


def test_escaped_binary_only_hex():
    """Test ESCAPED style with only binary data (pure hex literal)"""

    binary_data = b"binary content with '; injection"

    result = tsql.render(
        t"INSERT INTO files (data) VALUES ({binary_data})",
        style=tsql.styles.ESCAPED
    )

    # Should be fully escaped as hex literal
    expected_hex = binary_data.hex()
    expected_query = f"INSERT INTO files (data) VALUES ('\\x{expected_hex}')"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped


def test_escaped_empty_binary_data():
    """Test ESCAPED style with empty binary data"""

    empty_binary = b""
    name = "empty.bin"

    result = tsql.render(
        t"INSERT INTO files (name, data) VALUES ({name}, {empty_binary})",
        style=tsql.styles.ESCAPED
    )

    expected_query = "INSERT INTO files (name, data) VALUES ('empty.bin', '\\x')"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped


def test_escaped_binary_with_null_bytes():
    """Test ESCAPED style with binary data containing null bytes"""

    binary_with_nulls = b"data\x00with\x00nulls\x00'; DROP TABLE test; --"

    result = tsql.render(
        t"INSERT INTO files (data) VALUES ({binary_with_nulls})",
        style=tsql.styles.ESCAPED
    )

    expected_hex = binary_with_nulls.hex()
    expected_query = f"INSERT INTO files (data) VALUES ('\\x{expected_hex}')"
    assert result[0] == expected_query
    assert result[1] == []  # No parameters - fully escaped