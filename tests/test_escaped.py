import tsql
import tsql.styles


def test_escaped_prevents_basic_sql_injection():
    """Test that ESCAPED style prevents basic SQL injection attempts"""
    malicious_input = "'; DROP TABLE users; --"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = '''; DROP TABLE users; --'"
    assert result[1] == []


def test_escaped_handles_single_quotes():
    """Test proper escaping of single quotes"""
    value = "O'Reilly"
    result = tsql.render(t"SELECT * FROM users WHERE name = {value}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = 'O''Reilly'"
    assert result[1] == []


def test_escaped_handles_multiple_quotes():
    """Test escaping of multiple single quotes"""
    value = "It's a 'test' value"
    result = tsql.render(t"SELECT * FROM users WHERE name = {value}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = 'It''s a ''test'' value'"
    assert result[1] == []


def test_escaped_handles_union_attack():
    """Test prevention of UNION-based injection"""
    malicious_input = "' UNION SELECT password FROM admin_users WHERE '1'='1"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = ''' UNION SELECT password FROM admin_users WHERE ''1''=''1'"
    assert result[1] == []


def test_escaped_handles_boolean_injection():
    """Test prevention of boolean-based injection"""
    malicious_input = "' OR '1'='1"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = ''' OR ''1''=''1'"
    assert result[1] == []


def test_escaped_handles_comment_injection():
    """Test prevention of comment-based injection"""
    malicious_input = "admin'--"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = 'admin''--'"
    assert result[1] == []


def test_escaped_handles_stacked_queries():
    """Test prevention of stacked query injection"""
    malicious_input = "'; INSERT INTO logs (msg) VALUES ('hacked'); --"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = '''; INSERT INTO logs (msg) VALUES (''hacked''); --'"
    assert result[1] == []


def test_escaped_handles_null_bytes():
    """Test handling of null bytes and special characters"""
    malicious_input = "test\x00value"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = 'test\x00value'"
    assert result[1] == []


def test_escaped_handles_empty_string():
    """Test escaping of empty strings"""
    value = ""
    result = tsql.render(t"SELECT * FROM users WHERE name = {value}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = ''"
    assert result[1] == []


def test_escaped_handles_whitespace_injection():
    """Test handling of whitespace-based injection attempts"""
    malicious_input = "  ' OR 1=1 --  "
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE name = '  '' OR 1=1 --  '"
    assert result[1] == []


def test_escaped_handles_numeric_values_safely():
    """Test that numeric values are not quoted and remain safe"""
    user_id = 123
    result = tsql.render(t"SELECT * FROM users WHERE id = {user_id}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE id = 123"
    assert result[1] == []


def test_escaped_prevents_numeric_injection_as_string():
    """Test that numeric-looking strings are still escaped"""
    malicious_input = "123; DROP TABLE users; --"
    result = tsql.render(t"SELECT * FROM users WHERE id = {malicious_input}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE id = '123; DROP TABLE users; --'"
    assert result[1] == []


def test_escaped_handles_boolean_values():
    """Test proper escaping of boolean values"""
    active = True
    inactive = False
    result1 = tsql.render(t"SELECT * FROM users WHERE active = {active}", style=tsql.styles.ESCAPED)
    result2 = tsql.render(t"SELECT * FROM users WHERE active = {inactive}", style=tsql.styles.ESCAPED)
    
    assert result1[0] == "SELECT * FROM users WHERE active = TRUE"
    assert result1[1] == []
    assert result2[0] == "SELECT * FROM users WHERE active = FALSE"
    assert result2[1] == []


def test_escaped_handles_none_values():
    """Test proper handling of None/NULL values"""
    value = None
    result = tsql.render(t"SELECT * FROM users WHERE deleted_at = {value}", style=tsql.styles.ESCAPED)
    assert result[0] == "SELECT * FROM users WHERE deleted_at = NULL"
    assert result[1] == []


def test_escaped_handles_float_values():
    """Test proper escaping of float values"""
    price = 19.99
    result = tsql.render(t"SELECT * FROM products WHERE price = {price}", style=tsql.styles.ESCAPED)
    # Note: floats get converted to strings by the formatter before reaching ESCAPED style
    assert result[0] == "SELECT * FROM products WHERE price = '19.99'"
    assert result[1] == []


def test_escaped_complex_injection_scenario():
    """Test a complex multi-vector injection attempt"""
    malicious_input = "'; DELETE FROM users WHERE 'a'='a'; INSERT INTO users (name) VALUES ('hacker'); --"
    result = tsql.render(t"SELECT * FROM users WHERE name = {malicious_input}", style=tsql.styles.ESCAPED)
    expected = "SELECT * FROM users WHERE name = '''; DELETE FROM users WHERE ''a''=''a''; INSERT INTO users (name) VALUES (''hacker''); --'"
    assert result[0] == expected
    assert result[1] == []


def test_escaped_handles_unicode_and_special_chars():
    """Test handling of unicode and special characters"""
    unicode_value = "测试'值"
    emoji_value = "🚀'test"
    
    result1 = tsql.render(t"SELECT * FROM users WHERE name = {unicode_value}", style=tsql.styles.ESCAPED)
    result2 = tsql.render(t"SELECT * FROM users WHERE name = {emoji_value}", style=tsql.styles.ESCAPED)
    
    assert result1[0] == "SELECT * FROM users WHERE name = '测试''值'"
    assert result1[1] == []
    assert result2[0] == "SELECT * FROM users WHERE name = '🚀''test'"
    assert result2[1] == []


def test_escaped_multiple_values_in_query():
    """Test escaping multiple values in a single query"""
    name = "O'Reilly"
    age = 25
    active = True
    notes = "Has 'admin' privileges"
    
    result = tsql.render(
        t"SELECT * FROM users WHERE name = {name} AND age = {age} AND active = {active} AND notes = {notes}",
        style=tsql.styles.ESCAPED
    )
    
    expected = "SELECT * FROM users WHERE name = 'O''Reilly' AND age = 25 AND active = TRUE AND notes = 'Has ''admin'' privileges'"
    assert result[0] == expected
    assert result[1] == []