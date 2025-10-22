"""Tests for error message clarity and helpfulness"""
import pytest
import tsql


def test_literal_non_string_gets_parameterized():
    """Non-string values with :literal format spec just get parameterized (not an error)"""
    # This is actually fine behavior - the :literal format spec is ignored for non-strings
    # and they just get parameterized normally
    sql, params = tsql.render(t"SELECT * FROM table WHERE id = {123:literal}")
    assert sql == "SELECT * FROM table WHERE id = ?"
    assert params == [123]


def test_literal_too_many_parts_error():
    """Too many parts should show expected count and list all parts"""
    table = "a.b.c.d"
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "too many parts" in error_msg
    assert "expected at most 3" in error_msg
    assert "got 4" in error_msg
    assert "'a'" in error_msg and "'b'" in error_msg and "'c'" in error_msg and "'d'" in error_msg


def test_literal_empty_string_error():
    """Empty string should explain it's not a valid identifier and show examples"""
    table = ""
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "empty string is not a valid identifier" in error_msg
    assert "users" in error_msg or "public.users" in error_msg  # Should show examples


def test_literal_invalid_identifier_error():
    """Invalid identifiers should show which parts are invalid and explain rules"""
    table = "my-table"  # Hyphens not allowed
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "invalid identifier" in error_msg
    assert "'my-table'" in error_msg
    assert "valid Python identifier" in error_msg
    assert "letters, digits, underscores" in error_msg


def test_literal_starts_with_digit_error():
    """Identifiers starting with digits should be caught with helpful message"""
    table = "123users"
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "invalid identifier" in error_msg
    assert "'123users'" in error_msg
    assert "valid Python identifier" in error_msg


def test_literal_special_chars_error():
    """Special characters should be caught and suggest :unsafe if needed"""
    table = "users@prod"  # @ not allowed
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "invalid identifier" in error_msg
    assert "'users@prod'" in error_msg
    assert ":unsafe" in error_msg  # Suggests alternative


def test_literal_qualified_name_with_invalid_part():
    """Qualified names with one invalid part should identify which part is bad"""
    table = "public.my-table"  # Second part has hyphen
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert "invalid identifier" in error_msg
    assert "'my-table'" in error_msg  # Should identify the bad part
    # Should NOT complain about 'public' since it's valid


def test_literal_sql_keyword_suggestion():
    """Error for SQL keywords should suggest :unsafe workaround"""
    # Note: SQL keywords like 'select' are actually valid Python identifiers,
    # so this tests the general suggestion about :unsafe for special cases
    table = "table-name"
    with pytest.raises(ValueError) as exc_info:
        tsql.render(t"SELECT * FROM {table:literal}")

    error_msg = str(exc_info.value)
    assert ":unsafe" in error_msg
    assert "caution" in error_msg
