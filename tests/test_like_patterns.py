"""Tests for LIKE pattern format specs."""

import pytest
import tsql
from tsql.styles import QMARK, NUMERIC, NAMED, FORMAT, PYFORMAT, NUMERIC_DOLLAR


class TestLikePatternBasics:
    """Test basic LIKE pattern functionality."""

    def test_like_contains_pattern(self):
        """Test %like% format spec produces contains pattern."""
        search = "john"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}")

        assert sql == "SELECT * FROM users WHERE name LIKE ? ESCAPE '\\'"
        assert params == ['%john%']

    def test_like_prefix_pattern(self):
        """Test like% format spec produces starts-with pattern."""
        search = "admin"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:like%}")

        assert sql == "SELECT * FROM users WHERE name LIKE ? ESCAPE '\\'"
        assert params == ['admin%']

    def test_like_suffix_pattern(self):
        """Test %like format spec produces ends-with pattern."""
        search = ".com"
        sql, params = tsql.render(t"SELECT * FROM emails WHERE address LIKE {search:%like}")

        assert sql == "SELECT * FROM emails WHERE address LIKE ? ESCAPE '\\'"
        assert params == ['%.com']


class TestWildcardEscaping:
    """Test that wildcards are properly escaped."""

    def test_escapes_percent_wildcard(self):
        """Test that % is escaped to \\%."""
        search = "50%"
        sql, params = tsql.render(t"SELECT * FROM products WHERE discount LIKE {search:%like%}")

        assert params == ['%50\\%%']

    def test_escapes_underscore_wildcard(self):
        """Test that _ is escaped to \\_."""
        search = "user_name"
        sql, params = tsql.render(t"SELECT * FROM logs WHERE field LIKE {search:%like%}")

        assert params == ['%user\\_name%']

    def test_escapes_backslash(self):
        """Test that \\ is escaped to \\\\."""
        search = "C:\\Users"
        sql, params = tsql.render(t"SELECT * FROM paths WHERE path LIKE {search:%like%}")

        assert params == ['%C:\\\\Users%']

    def test_escapes_all_wildcards_together(self):
        """Test multiple wildcards in one value."""
        search = "test_50%\\path"
        sql, params = tsql.render(t"SELECT * FROM mixed WHERE value LIKE {search:%like%}")

        assert params == ['%test\\_50\\%\\\\path%']

    def test_empty_string(self):
        """Test empty string produces just the pattern."""
        search = ""
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}")

        assert params == ['%%']


class TestSecurityScenarios:
    """Test that injection attempts are neutralized."""

    def test_prevents_wildcard_injection_contains(self):
        """Test that user can't inject wildcards to expand search."""
        malicious = "%admin"  # Trying to search for anything containing 'admin'
        sql, params = tsql.render(t"SELECT * FROM users WHERE username LIKE {malicious:like%}")

        # Should match literally '%admin' followed by anything
        assert params == ['\\%admin%']

    def test_prevents_full_table_scan(self):
        """Test that % alone doesn't create %%."""
        malicious = "%"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {malicious:%like%}")

        # Should match literally '%' anywhere
        assert params == ['%\\%%']

    def test_prevents_sql_injection_attempt(self):
        """Test that SQL injection attempts are treated as literals."""
        malicious = "%'; DROP TABLE users; --"
        sql, params = tsql.render(t"SELECT * FROM logs WHERE message LIKE {malicious:%like%}")

        # Everything is escaped and parameterized
        assert "DROP TABLE" in params[0]  # Present in parameter value
        assert "DROP TABLE" not in sql  # Not in SQL itself
        assert params == ["%\\%'; DROP TABLE users; --%"]


class TestTypeHandling:
    """Test type conversion and None handling."""

    def test_converts_int_to_string(self):
        """Test that integers are converted to strings."""
        number = 42
        sql, params = tsql.render(t"SELECT * FROM products WHERE code LIKE {number:%like%}")

        assert params == ['%42%']

    def test_converts_float_to_string(self):
        """Test that floats are converted to strings."""
        number = 3.14
        sql, params = tsql.render(t"SELECT * FROM values WHERE val LIKE {number:%like%}")

        assert params == ['%3.14%']

    def test_none_raises_error_contains(self):
        """Test that None raises ValueError for %like%."""
        value = None
        with pytest.raises(ValueError, match="LIKE pattern value cannot be None"):
            tsql.render(t"SELECT * FROM users WHERE name LIKE {value:%like%}")

    def test_none_raises_error_prefix(self):
        """Test that None raises ValueError for like%."""
        value = None
        with pytest.raises(ValueError, match="LIKE pattern value cannot be None"):
            tsql.render(t"SELECT * FROM users WHERE name LIKE {value:like%}")

    def test_none_raises_error_suffix(self):
        """Test that None raises ValueError for %like."""
        value = None
        with pytest.raises(ValueError, match="LIKE pattern value cannot be None"):
            tsql.render(t"SELECT * FROM users WHERE name LIKE {value:%like}")


class TestMultipleParameters:
    """Test queries with multiple LIKE clauses."""

    def test_multiple_like_patterns_in_one_query(self):
        """Test that multiple LIKE patterns work correctly."""
        name = "john"
        email = "gmail"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {name:%like%} OR email LIKE {email:%like}")

        assert sql == "SELECT * FROM users WHERE name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\'"
        assert params == ['%john%', '%gmail']

    def test_mixed_like_patterns(self):
        """Test different pattern types in one query."""
        prefix = "admin"
        suffix = ".com"
        contains = "test"
        sql, params = tsql.render(t"""
            SELECT * FROM data
            WHERE username LIKE {prefix:like%}
            AND email LIKE {suffix:%like}
            AND description LIKE {contains:%like%}
        """)

        assert params == ['admin%', '%.com', '%test%']
        assert sql.count("ESCAPE '\\'") == 3


class TestParameterStyles:
    """Test that LIKE patterns work with different parameter styles."""

    def test_qmark_style(self):
        """Test with ? placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", QMARK)

        assert sql == "SELECT * FROM users WHERE name LIKE ? ESCAPE '\\'"
        assert params == ['%test%']

    def test_numeric_style(self):
        """Test with :1, :2, ... placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", NUMERIC)

        assert sql == "SELECT * FROM users WHERE name LIKE :1 ESCAPE '\\'"
        assert params == ['%test%']

    def test_numeric_dollar_style(self):
        """Test with $1, $2, ... placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", NUMERIC_DOLLAR)

        assert sql == "SELECT * FROM users WHERE name LIKE $1 ESCAPE '\\'"
        assert params == ['%test%']

    def test_named_style(self):
        """Test with :name placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", NAMED)

        assert sql == "SELECT * FROM users WHERE name LIKE :search ESCAPE '\\'"
        assert params == {'search': '%test%'}

    def test_format_style(self):
        """Test with %s placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", FORMAT)

        assert sql == "SELECT * FROM users WHERE name LIKE %s ESCAPE '\\'"
        assert params == ['%test%']

    def test_pyformat_style(self):
        """Test with %(name)s placeholders."""
        search = "test"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}", PYFORMAT)

        assert sql == "SELECT * FROM users WHERE name LIKE %(search)s ESCAPE '\\'"
        assert params == {'search': '%test%'}


class TestCaseSensitivity:
    """Test that LIKE vs ILIKE is orthogonal to pattern specs."""

    def test_like_case_sensitive(self):
        """Test LIKE with pattern."""
        search = "John"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name LIKE {search:%like%}")

        assert "LIKE" in sql
        assert "ILIKE" not in sql
        assert params == ['%John%']

    def test_ilike_case_insensitive(self):
        """Test ILIKE with pattern."""
        search = "John"
        sql, params = tsql.render(t"SELECT * FROM users WHERE name ILIKE {search:%like%}")

        assert "ILIKE" in sql
        assert params == ['%John%']


class TestRealWorldScenarios:
    """Test realistic usage patterns."""

    def test_user_search_box(self):
        """Test typical user search functionality."""
        user_input = "john doe"
        sql, params = tsql.render(t"""
            SELECT id, name, email
            FROM users
            WHERE name ILIKE {user_input:%like%}
            ORDER BY name
        """)

        assert params == ['%john doe%']

    def test_email_domain_filter(self):
        """Test filtering by email domain."""
        domain = "@gmail.com"
        sql, params = tsql.render(t"SELECT * FROM users WHERE email LIKE {domain:%like}")

        assert params == ['%@gmail.com']

    def test_username_prefix_search(self):
        """Test username autocomplete."""
        prefix = "adm"
        sql, params = tsql.render(t"""
            SELECT username
            FROM users
            WHERE username LIKE {prefix:like%}
            LIMIT 10
        """)

        assert params == ['adm%']

    def test_log_message_search_with_special_chars(self):
        """Test searching logs that might contain special characters."""
        search = "Error: 50% complete [user_123]"
        sql, params = tsql.render(t"SELECT * FROM logs WHERE message LIKE {search:%like%}")

        # All special chars should be escaped
        assert params == ['%Error: 50\\% complete [user\\_123]%']
