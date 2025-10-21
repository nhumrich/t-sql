import json
import pytest
from tsql import TypeProcessor
from tsql.query_builder import Table, SAColumn

try:
    from sqlalchemy import Integer, String, MetaData
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class EncryptedString(TypeProcessor):
    """Simple encryption simulator for testing"""

    def __init__(self, key: str):
        self.key = key

    def process_bind_param(self, value):
        if value is None:
            return None
        return f"encrypted_{value}_{self.key}"

    def process_result_value(self, value):
        if value is None:
            return None
        if value.startswith(f"encrypted_") and value.endswith(f"_{self.key}"):
            return value[len(f"encrypted_"):-len(f"_{self.key}")]
        return value


class JSONType(TypeProcessor):
    """JSON serialization for testing"""

    def process_bind_param(self, value):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_insert_with_type_processor():
    """Test that type processors are applied during INSERT"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))
        metadata_ = SAColumn(String, type_processor=JSONType())

    # Build insert query
    query = User.insert(id=1, ssn="123-45-6789", metadata_={"foo": "bar"})
    sql, params = query.render()

    # Check that values were transformed
    assert params[1] == "encrypted_123-45-6789_secret123"
    assert params[2] == '{"foo": "bar"}'


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_update_with_type_processor():
    """Test that type processors are applied during UPDATE"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    # Build update query
    query = User.update(ssn="new-ssn").where(User.id == 1)
    sql, params = query.render()

    # Check that value was transformed
    assert "encrypted_new-ssn_secret123" in params


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_where_clause_with_type_processor():
    """Test that type processors are applied in WHERE clauses"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    # Build select query with WHERE
    query = User.select().where(User.ssn == "123-45-6789")
    sql, params = query.render()

    # Check that value was transformed
    assert params[0] == "encrypted_123-45-6789_secret123"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_in_clause_with_type_processor():
    """Test that type processors are applied to IN clause values"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    # Build select query with IN
    query = User.select().where(User.ssn.in_(["123-45-6789", "987-65-4321"]))
    sql, params = query.render()

    # Check that values were transformed
    assert params[0] == "encrypted_123-45-6789_secret123"
    assert params[1] == "encrypted_987-65-4321_secret123"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_between_with_type_processor():
    """Test that type processors are applied to BETWEEN values"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        score = SAColumn(Integer, type_processor=EncryptedString(key="secret123"))

    # Build select query with BETWEEN
    query = User.select().where(User.score.between(10, 20))
    sql, params = query.render()

    # Check that values were transformed
    assert params[0] == "encrypted_10_secret123"
    assert params[1] == "encrypted_20_secret123"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_map_results():
    """Test that map_results applies type processors to query results"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))
        metadata_ = SAColumn(String, type_processor=JSONType())

    # Simulate database results
    rows = [
        {"id": 1, "ssn": "encrypted_123-45-6789_secret123", "metadata_": '{"foo": "bar"}'},
        {"id": 2, "ssn": "encrypted_987-65-4321_secret123", "metadata_": '{"baz": "qux"}'},
    ]

    # Build query and map results
    query = User.select()
    transformed_rows = query.map_results(rows)

    # Check that values were decrypted/deserialized
    assert transformed_rows[0]["ssn"] == "123-45-6789"
    assert transformed_rows[0]["metadata_"] == {"foo": "bar"}
    assert transformed_rows[1]["ssn"] == "987-65-4321"
    assert transformed_rows[1]["metadata_"] == {"baz": "qux"}


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_null_handling():
    """Test that NULL values are passed through to processors"""
    metadata = MetaData()

    class NullAwareProcessor(TypeProcessor):
        def process_bind_param(self, value):
            if value is None:
                return "NULL_MARKER"
            return value

        def process_result_value(self, value):
            if value == "NULL_MARKER":
                return None
            return value

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        optional_field = SAColumn(String, type_processor=NullAwareProcessor())

    # Test insert with None
    query = User.insert(id=1, optional_field=None)
    sql, params = query.render()
    assert params[1] == "NULL_MARKER"

    # Test map_results with marker
    rows = [{"id": 1, "optional_field": "NULL_MARKER"}]
    query = User.select()
    transformed_rows = query.map_results(rows)
    assert transformed_rows[0]["optional_field"] is None


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_on_conflict_with_type_processor():
    """Test that type processors are applied in ON CONFLICT UPDATE"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    # Build insert with on_conflict_update
    query = User.insert(id=1, ssn="123-45-6789").on_conflict_update(
        conflict_on="id",
        update={"ssn": "new-ssn"}
    )
    sql, params = query.render()

    # Check that both insert and update values were transformed
    assert "encrypted_123-45-6789_secret123" in params
    assert "encrypted_new-ssn_secret123" in params


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_comparison_operators_with_type_processor():
    """Test that all comparison operators apply type processors"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        score = SAColumn(Integer, type_processor=EncryptedString(key="secret123"))

    # Test various operators
    ops = [
        (User.score == 100, "encrypted_100_secret123"),
        (User.score != 100, "encrypted_100_secret123"),
        (User.score < 100, "encrypted_100_secret123"),
        (User.score <= 100, "encrypted_100_secret123"),
        (User.score > 100, "encrypted_100_secret123"),
        (User.score >= 100, "encrypted_100_secret123"),
        (User.score.like("10%"), "encrypted_10%_secret123"),
        (User.score.not_like("10%"), "encrypted_10%_secret123"),
    ]

    for condition, expected_value in ops:
        query = User.select().where(condition)
        sql, params = query.render()
        assert expected_value in params, f"Failed for condition: {condition}"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_type_processor_not_applied_to_column_comparisons():
    """Test that type processors are NOT applied when comparing columns to columns"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))
        backup_ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    # Build query comparing two columns
    query = User.select().where(User.ssn == User.backup_ssn)
    sql, params = query.render()

    # No parameters should be generated (column-to-column comparison)
    assert len(params) == 0
    assert "user.ssn = user.backup_ssn" in sql


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_map_results_with_joins_and_aliases():
    """Test that map_results handles JOINs and column aliases correctly"""
    metadata = MetaData()

    class User(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        name = SAColumn(String(100))
        ssn = SAColumn(String(255), type_processor=EncryptedString(key="secret123"))

    class Profile(Table, metadata=metadata):
        id = SAColumn(Integer, primary_key=True)
        user_id = SAColumn(Integer)
        metadata_col = SAColumn(String(255), type_processor=JSONType())

    # Test with explicit columns including alias
    query = (
        User.select(User.id, User.name, User.ssn.as_('social'), Profile.metadata_col)
        .join(Profile, on=User.id == Profile.user_id)
    )

    # Simulate database rows (using the format that EncryptedString produces)
    rows = [
        {
            "id": 1,
            "name": "Alice",
            "social": "encrypted_123-45-6789_secret123",  # Aliased column
            "metadata_col": '{"key": "value"}'
        }
    ]

    results = query.map_results(rows)

    # Check aliased column was decrypted
    assert results[0]["social"] == "123-45-6789"
    assert results[0].social == "123-45-6789"  # Test attribute access
    # Check joined table column was deserialized
    assert results[0]["metadata_col"] == {"key": "value"}
    assert results[0].metadata_col == {"key": "value"}  # Test attribute access

    # Test with SELECT * (should process all columns from all tables)
    query_star = User.select().join(Profile, on=User.id == Profile.user_id)

    rows_star = [
        {
            "id": 1,
            "name": "Alice",
            "ssn": "encrypted_987-65-4321_secret123",
            "user_id": 1,
            "metadata_col": '{"foo": "bar"}'
        }
    ]

    results_star = query_star.map_results(rows_star)

    # Both processors should be applied
    assert results_star[0]["ssn"] == "987-65-4321"
    assert results_star[0].ssn == "987-65-4321"  # Test attribute access
    assert results_star[0]["metadata_col"] == {"foo": "bar"}
    assert results_star[0].metadata_col == {"foo": "bar"}  # Test attribute access
