"""`Condition(left, operator, right)` renders `operator` into the SQL text.

`Condition` is public and its `operator` parameter is a plain `str` that reaches the
SQL verbatim. The `?field=&op=&value=` filter API is a common REST shape, so an app
can plumb request data straight into it. Only the operator set the builders actually
emit is accepted; anything else is a t-string Template passed to `where()`.
"""

import json

import pytest

from tsql.query_builder import Column, Condition, Table


class Users(Table):
    id: Column
    username: Column
    age: Column


def test_filter_api_operator_from_user_input_raises():
    """The ?field=&op=&value= filter API cannot smuggle a predicate through op="""
    request = json.loads('{"field": "id", "op": "= 1 OR 1=1 --", "value": "5"}')
    column = getattr(Users, request['field'])

    with pytest.raises(ValueError):
        Condition(column, request['op'], request['value'])


def test_operator_with_stacked_statement_raises():
    """A stacked statement in the operator is rejected"""
    with pytest.raises(ValueError):
        Condition(Users.id, '= 1; DROP TABLE users --', 5)


def test_operator_with_subquery_exfiltration_raises():
    """A subquery payload in the operator is rejected"""
    with pytest.raises(ValueError):
        Condition(Users.id, 'IN (SELECT password FROM secrets) --', 5)


def test_operator_stranding_the_bound_parameter_raises():
    """A commented-out operator strands the bound value, so the predicate is attacker-owned"""
    with pytest.raises(ValueError):
        Condition(Users.id, '> 0 --', 5)


def test_empty_operator_raises():
    """An empty operator is not in the allowlist"""
    with pytest.raises(ValueError):
        Condition(Users.id, '', 5)


def test_non_string_operator_raises():
    """A non-str operator is rejected rather than stringified into the SQL"""
    with pytest.raises(ValueError):
        Condition(Users.id, 1, 5)


@pytest.mark.parametrize('operator', [
    'IS', 'IS NOT', '=', '!=', '<', '<=', '>', '>=',
    'IN', 'NOT IN', 'LIKE', 'NOT LIKE', 'ILIKE', 'NOT ILIKE',
    'BETWEEN', 'NOT BETWEEN',
])
def test_operators_the_builders_emit_are_accepted(operator):
    """Every operator the Column API itself produces stays valid"""
    assert Condition(Users.id, operator, 5).operator == operator


def test_operator_is_normalized_to_upper_case():
    """Casing and surrounding whitespace are normalized"""
    assert Condition(Users.id, 'like', 'a%').operator == 'LIKE'
    assert Condition(Users.id, '  =  ', 5).operator == '='


def test_unsupported_sql_operator_raises():
    """An operator the builders never emit is rejected even though it is real SQL"""
    with pytest.raises(ValueError):
        Condition(Users.id, 'IS DISTINCT FROM', 5)


def test_error_message_names_the_bad_value():
    """The rejection names what was supplied so the caller can find it"""
    with pytest.raises(ValueError) as exc_info:
        Condition(Users.id, '= 1 OR 1=1 --', 5)

    assert '= 1 OR 1=1 --' in str(exc_info.value)


def test_error_message_does_not_suggest_unsafe():
    """The rejection must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        Condition(Users.id, '= 1 OR 1=1 --', 5)

    assert 'unsafe' not in str(exc_info.value).lower()


def test_column_api_conditions_still_render():
    """The normal Column dunder API is unaffected"""
    sql, params = Users.select().where(Users.age >= 21).render()

    assert 'WHERE users.age >= ?' in sql
    assert params == [21]


def test_template_is_the_escape_hatch_for_arbitrary_predicates():
    """An operator the allowlist rejects is still expressible as a Template"""
    sql, params = Users.select().where(t'users.age IS DISTINCT FROM {21}').render()

    assert 'WHERE (users.age IS DISTINCT FROM ?)' in sql
    assert params == [21]
