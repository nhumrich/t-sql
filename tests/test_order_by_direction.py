import pytest

from tsql.query_builder import Table, Column, OrderByClause, SelectQueryBuilder


class Users(Table):
    id: Column
    username: Column
    email: Column
    created_at: Column


def test_direction_with_stacked_statement_raises():
    """A stacked-statement payload in direction= is rejected"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction='ASC; SELECT 1')


def test_direction_with_subquery_exfiltration_raises():
    """The blind-exfiltration subquery payload in direction= is rejected"""
    payload = 'ASC, (SELECT CASE WHEN EXISTS (SELECT 1 FROM tenants) THEN 1 ELSE 0 END)'
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction=payload)


def test_direction_with_comment_raises():
    """A trailing SQL comment in direction= is rejected"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction='ASC-- ')


def test_direction_empty_string_raises():
    """An empty direction is rejected"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction='')


def test_direction_function_call_raises():
    """A function call in direction= is rejected"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction='RANDOM()')


def test_direction_non_string_raises():
    """A non-string direction is rejected"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction=1)


def test_direction_with_nulls_last_raises():
    """direction='DESC NULLS LAST' is an accepted break — use .nulls_last() instead"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction='DESC NULLS LAST')


class _LyingStr(str):
    """A str subclass whose comparison and normalization methods all claim to be valid"""

    def strip(self, *args):
        return self

    def upper(self):
        return self

    def __eq__(self, other):
        return True

    def __hash__(self):
        return hash('ASC')

    def split(self, *args, **kwargs):
        return ['ASC']

    def isidentifier(self):
        return True


def test_direction_str_subclass_cannot_spoof_validation():
    """A str subclass is judged on its real buffer, not its overridden methods"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id, direction=_LyingStr('ASC; DROP TABLE users;--'))


def test_nulls_str_subclass_cannot_spoof_validation():
    """A str subclass cannot smuggle a payload through the nulls validator"""
    with pytest.raises(ValueError):
        OrderByClause(Users.id, 'ASC', _LyingStr('NULLS LAST; DROP TABLE users;--'))


def test_str_subclass_with_valid_value_is_normalized_to_plain_str():
    """A str subclass carrying a genuinely valid value renders the plain constant"""
    sql, _ = Users.select().order_by(Users.id, direction=_LyingStr('desc')).render()

    assert 'ORDER BY users.id DESC' in sql


def test_mutated_nulls_attribute_is_revalidated_at_render():
    """Mutating .nulls after construction cannot smuggle raw SQL into the render"""
    clause = Users.id.desc()
    clause.nulls = 'NULLS LAST; DROP TABLE users;--'

    with pytest.raises(ValueError):
        Users.select().order_by(clause).render()


def test_mutated_direction_attribute_is_revalidated_at_render():
    """Mutating .direction after construction cannot smuggle raw SQL into the render"""
    clause = Users.id.desc()
    clause.direction = 'DESC; DROP TABLE users;--'

    with pytest.raises(ValueError):
        Users.select().order_by(clause).render()


def test_direction_validated_even_when_unused():
    """direction= is validated eagerly, even if every column carries its own direction"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.id.desc(), Users.username.asc(), direction=None)


def test_direction_validated_with_no_columns():
    """direction= is validated even when no columns are passed"""
    with pytest.raises(ValueError):
        Users.select().order_by(direction='ASC; SELECT 1')


def test_order_by_clause_validates_directly():
    """OrderByClause rejects a bad direction at construction"""
    with pytest.raises(ValueError):
        OrderByClause('col', 'ASC; DROP TABLE users--')


def test_nulls_kwarg_rejects_injection():
    """The public nulls= kwarg is validated, not just the convenience methods"""
    with pytest.raises(ValueError):
        OrderByClause(Users.id, 'ASC', 'NULLS LAST; DROP TABLE users--')


def test_nulls_kwarg_rejects_arbitrary_string():
    """Any nulls value outside the two constants is rejected"""
    with pytest.raises(ValueError):
        OrderByClause(Users.id, 'ASC', 'nulls sideways')


def test_nulls_kwarg_accepts_constants():
    """The two valid NULLS constants are accepted through the kwarg"""
    assert OrderByClause(Users.id, 'ASC', 'NULLS FIRST').nulls == 'NULLS FIRST'
    assert OrderByClause(Users.id, 'ASC', 'NULLS LAST').nulls == 'NULLS LAST'


def test_nulls_error_message_does_not_suggest_unsafe():
    """The nulls rejection message must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        OrderByClause(Users.id, 'ASC', 'NULLS LAST; DROP TABLE users--')

    assert 'unsafe' not in str(exc_info.value).lower()


def test_string_column_path_validates_direction():
    """The string-column render path also validates direction"""
    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('users').order_by('username', direction='ASC; SELECT 1')


def test_column_object_path_validates_direction():
    """The Column-object render path also validates direction"""
    with pytest.raises(ValueError):
        Users.select().order_by(Users.username, direction='ASC, (SELECT 1)')


def test_error_message_does_not_suggest_unsafe():
    """The rejection message must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        Users.select().order_by(Users.id, direction='ASC; SELECT 1')

    assert 'unsafe' not in str(exc_info.value).lower()


def test_direction_asc():
    """direction='ASC' renders"""
    sql, _ = Users.select().order_by(Users.username, direction='ASC').render()

    assert 'ORDER BY users.username ASC' in sql


def test_direction_desc():
    """direction='DESC' renders"""
    sql, _ = Users.select().order_by(Users.username, direction='DESC').render()

    assert 'ORDER BY users.username DESC' in sql


def test_direction_lowercase_normalized():
    """Lowercase direction is normalized to upper case"""
    sql, _ = Users.select().order_by(Users.username, direction='desc').render()

    assert 'ORDER BY users.username DESC' in sql


def test_direction_surrounding_whitespace_normalized():
    """Surrounding whitespace in direction is stripped"""
    sql, _ = Users.select().order_by(Users.username, direction=' desc ').render()

    assert 'ORDER BY users.username DESC' in sql


def test_string_column_with_direction():
    """String columns with direction= still work"""
    sql, _ = SelectQueryBuilder.from_table('users').order_by('username', direction='DESC').render()

    assert 'ORDER BY username DESC' in sql


def test_nulls_last():
    """.desc().nulls_last() renders NULLS LAST"""
    sql, _ = Users.select().order_by(Users.id.desc().nulls_last()).render()

    assert 'ORDER BY users.id DESC NULLS LAST' in sql


def test_nulls_first():
    """.asc().nulls_first() renders NULLS FIRST"""
    sql, _ = Users.select().order_by(Users.id.asc().nulls_first()).render()

    assert 'ORDER BY users.id ASC NULLS FIRST' in sql


def test_nulls_mixed_multi_column():
    """Mixed nulls and plain clauses render in order"""
    sql, _ = Users.select().order_by(
        Users.username.desc().nulls_last(),
        Users.id.asc(),
    ).render()

    assert 'ORDER BY users.username DESC NULLS LAST, users.id ASC' in sql


def test_no_nulls_call_has_no_trailing_space():
    """A clause without a nulls call renders exactly as before, with no stray space"""
    sql, _ = Users.select().order_by(Users.id.desc()).limit(5).render()

    assert 'ORDER BY users.id DESC LIMIT' in sql


def test_order_by_accumulates_across_calls():
    """Chained order_by() calls accumulate columns rather than replacing them"""
    sql, _ = Users.select().order_by(Users.id.desc()).order_by(Users.username.asc()).render()

    assert 'ORDER BY users.id DESC, users.username ASC' in sql


def test_clause_reusable_across_queries():
    """One OrderByClause can be passed to several builders"""
    clause = Users.id.desc().nulls_last()

    first, _ = Users.select().order_by(clause).render()
    second, _ = Users.select(Users.username).order_by(clause).render()

    assert 'ORDER BY users.id DESC NULLS LAST' in first
    assert 'ORDER BY users.id DESC NULLS LAST' in second


def test_nulls_last_returns_new_object():
    """nulls_last() does not mutate the original clause"""
    clause = Users.id.desc()
    with_nulls = clause.nulls_last()

    assert with_nulls is not clause
    assert clause.nulls is None
    assert with_nulls.nulls == 'NULLS LAST'


def test_nulls_first_returns_new_object():
    """nulls_first() does not mutate the original clause"""
    clause = Users.id.asc()
    with_nulls = clause.nulls_first()

    assert with_nulls is not clause
    assert clause.nulls is None
    assert with_nulls.nulls == 'NULLS FIRST'


def test_template_order_by_still_verbatim():
    """Template fragments are emitted verbatim, including NULLS ordering"""
    sql, _ = Users.select().order_by(t'created_at DESC NULLS LAST').render()

    assert 'ORDER BY created_at DESC NULLS LAST' in sql


def test_string_column_with_nulls():
    """String columns support nulls ordering via OrderByClause"""
    sql, _ = (
        SelectQueryBuilder.from_table('users')
        .order_by(OrderByClause('username', 'DESC').nulls_last())
        .render()
    )

    assert 'ORDER BY username DESC NULLS LAST' in sql
