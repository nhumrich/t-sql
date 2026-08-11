"""The identifier and operand gates must hold against a lying `str` subclass.

Every gate that renders a name into the SQL text uses unbound `str` methods, so a
subclass cannot override `strip`/`upper`/`isidentifier`/`__eq__`/`__str__` to pass the
check while its real buffer carries a payload. `Condition`'s left operand is gated by
type instead: it is composed into SQL text, so it must be a real `Column`.
"""

import pytest

from tsql.query_builder import (
    Column,
    Condition,
    DeleteBuilder,
    SelectQueryBuilder,
    Table,
    UpdateBuilder,
)


class Users(Table):
    id: Column
    username: Column
    age: Column


class Orders(Table):
    id: Column
    user_id: Column
    total: Column


class LyingIdentifier(str):
    """Real buffer carries a payload; every gate-relevant method lies"""

    def isidentifier(self):
        return True

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return str.__hash__(self)

    def __str__(self):
        return 'id'

    def split(self, *args, **kwargs):
        return ['id']


# --- Condition.left ---------------------------------------------------------

def test_condition_left_from_user_input_raises():
    """The ?field=&op=&value= filter API cannot smuggle a predicate through field"""
    with pytest.raises(ValueError):
        Condition('id FROM secrets--', '=', 5)


def test_condition_left_with_boolean_bypass_raises():
    """An OR payload in the left operand is rejected"""
    with pytest.raises(ValueError):
        Condition('1=1 OR users.is_admin', '=', True)


def test_condition_left_template_raises():
    """A Template is not a Column; where() is the route for a raw predicate"""
    with pytest.raises(ValueError):
        Condition(t'users.id', '=', 1)


def test_condition_left_none_raises():
    """None would render the literal text 'None'"""
    with pytest.raises(ValueError):
        Condition(None, '=', 1)


def test_condition_left_error_names_the_bad_value():
    """The rejection names what was supplied"""
    with pytest.raises(ValueError) as exc_info:
        Condition('id FROM secrets--', '=', 5)

    assert 'id FROM secrets--' in str(exc_info.value)


def test_condition_left_error_does_not_suggest_unsafe():
    """The rejection must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        Condition('id FROM secrets--', '=', 5)

    assert 'unsafe' not in str(exc_info.value).lower()


def test_condition_with_a_real_column_still_works():
    """The documented Condition usage is unaffected"""
    sql, params = Users.select().where(Condition(Users.age, '>=', 21)).render()

    assert 'WHERE users.age >= ?' in sql
    assert params == [21]


def test_column_to_column_condition_still_works():
    """A Column on both sides is unaffected"""
    sql, _ = Orders.select(Orders.id).join(Users, Condition(Orders.user_id, '=', Users.id)).render()

    assert 'ON orders.user_id = users.id' in sql


def test_aliased_column_as_left_operand_still_works():
    """An aliased Column is still a Column"""
    sql, params = Users.select().where(Condition(Users.age.as_('years'), '>=', 21)).render()

    assert params == [21]
    assert 'users.age' in sql


# --- RETURNING '*' guard ----------------------------------------------------

def test_returning_star_guard_is_not_bypassed_by_dunder_eq():
    """The '*' short-circuit must compare buffers, not call the element's __eq__"""
    with pytest.raises(ValueError):
        (Users.insert(id=1)
         .returning(LyingIdentifier('id, (SELECT password FROM secrets)'))
         .render())


def test_update_returning_star_guard_is_not_bypassed_by_dunder_eq():
    """UpdateBuilder's RETURNING guard has the same requirement"""
    with pytest.raises(ValueError):
        (UpdateBuilder.table('users', {'username': 'x'})
         .all_rows()
         .returning(LyingIdentifier('id, (SELECT password FROM secrets)'))
         .render())


def test_delete_returning_star_guard_is_not_bypassed_by_dunder_eq():
    """DeleteBuilder's RETURNING guard has the same requirement"""
    with pytest.raises(ValueError):
        (DeleteBuilder.from_table('users')
         .all_rows()
         .returning(LyingIdentifier('id, (SELECT password FROM secrets)'))
         .render())


def test_returning_star_still_works():
    """RETURNING * remains the documented wildcard"""
    sql, _ = Users.insert(id=1).returning('*').render()

    assert 'RETURNING *' in sql


def test_returning_named_columns_still_works():
    """Ordinary RETURNING columns are unaffected"""
    sql, _ = Users.insert(id=1).returning('id', 'username').render()

    assert 'RETURNING id, username' in sql


# --- the remaining hand-rolled gates ---------------------------------------

def test_returning_column_subclass_cannot_lie_about_isidentifier():
    """RETURNING validation must not trust an overridable isidentifier()"""
    with pytest.raises(ValueError):
        Users.insert(id=1).returning('id', LyingIdentifier('x FROM secrets--')).render()


def test_conflict_column_subclass_cannot_lie_about_isidentifier():
    """ON CONFLICT column validation must not trust an overridable isidentifier()"""
    with pytest.raises(ValueError):
        (Users.insert(id=1)
         .on_conflict_do_nothing(LyingIdentifier('id) DO UPDATE SET is_admin=true --'))
         .render())


def test_cte_name_subclass_cannot_lie_about_isidentifier():
    """CTE name validation must not trust an overridable isidentifier()"""
    with pytest.raises(ValueError):
        (SelectQueryBuilder.from_table('c')
         .with_cte(LyingIdentifier('c AS (SELECT password FROM secrets) --'), t'SELECT 1')
         .render())


def test_literal_format_spec_cannot_be_lied_to():
    """`:literal` is the gate for every string-builder name, so it uses unbound str too

    It is the last validator a lying subclass could reach: `select()`, `from_table()`,
    `group_by()`, `order_by()` and `distinct_on()` all route their plain-str names here.
    """
    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('users').select(
            LyingIdentifier('id, (SELECT password FROM secrets)')
        ).render()


def test_literal_renders_the_real_buffer_not_dunder_str():
    """A subclass whose buffer is a valid identifier renders that buffer verbatim"""
    class Sneaky(str):
        def __str__(self):
            return 'id, (SELECT password FROM secrets)'

    sql, _ = SelectQueryBuilder.from_table('users').select(Sneaky('id')).render()

    assert sql == 'SELECT id FROM users'


def test_valid_conflict_and_cte_names_still_work():
    """The ordinary identifier cases are unaffected"""
    sql, _ = Users.insert(id=1).on_conflict_do_nothing('id').render()
    assert 'ON CONFLICT (id) DO NOTHING' in sql

    sql, _ = (SelectQueryBuilder.from_table('recent')
              .with_cte('recent', t'SELECT 1')
              .render())
    assert 'WITH recent AS (SELECT 1)' in sql
