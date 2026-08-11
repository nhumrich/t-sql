"""Wildcards on the string column path are deliberately rejected; Templates carry them.

`select()`, `group_by()`, `order_by()` and `distinct_on()` route plain `str` columns
through `:literal`, which accepts only identifiers. `'*'` is not one, so it raises --
on purpose. A column list assembled from strings is exactly where a wildcard should
not be accepted silently; reaching for a Template makes the wildcard deliberate.

`t'*'`, `Table.ALL`, and omitting `select()` altogether are the three supported ways
to select every column. These tests pin that down, because the rejection is easy to
mistake for an oversight -- two `with_cte` docstring examples once made exactly that
mistake and did not run.
"""

import pytest

import tsql
from tsql.query_builder import Column, SelectQueryBuilder, Table


class Users(Table):
    id: Column
    username: Column


def test_string_star_is_rejected():
    """A bare '*' string column is not an identifier and is rejected"""
    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('users').select('*').render()


def test_qualified_string_star_is_rejected():
    """'users.*' is rejected for the same reason"""
    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('users').select('users.*').render()


def test_string_expression_is_rejected():
    """Function-call syntax on the string path is the injection surface and stays rejected"""
    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('orders').select('COUNT(*)').render()


def test_rejection_points_at_templates():
    """The error tells the caller how to get a wildcard, so the rejection is actionable"""
    with pytest.raises(ValueError) as exc_info:
        SelectQueryBuilder.from_table('users').select('*').render()

    error = str(exc_info.value)
    assert 'Template' in error
    assert "t'*'" in error


def test_star_via_template():
    """t'*' is the supported wildcard on the string builder"""
    sql, params = SelectQueryBuilder.from_table('users').select(t'*').render()

    assert sql == 'SELECT * FROM users'
    assert params == []


def test_qualified_star_via_template():
    """t'users.*' selects every column of one table"""
    sql, _ = SelectQueryBuilder.from_table('users').select(t'users.*').render()

    assert sql == 'SELECT users.* FROM users'


def test_star_template_mixed_with_string_columns():
    """A Template wildcard composes with ordinary validated string columns"""
    sql, _ = SelectQueryBuilder.from_table('users').select(t'*', 'id').render()

    assert sql == 'SELECT *, id FROM users'


def test_omitting_select_yields_star():
    """Selecting nothing already means every column"""
    sql, _ = SelectQueryBuilder.from_table('users').render()

    assert sql == 'SELECT * FROM users'


def test_table_all_yields_qualified_star():
    """Table.ALL is the Table-path equivalent"""
    sql, _ = Users.select(Users.ALL).render()

    assert sql == 'SELECT users.* FROM users'


def test_expression_via_template():
    """A SQL expression is expressible as a Template"""
    sql, _ = (SelectQueryBuilder.from_table('orders')
              .select('user_id', t'COUNT(*)')
              .group_by('user_id')
              .render())

    assert sql == 'SELECT user_id, COUNT(*) FROM orders GROUP BY user_id'


@pytest.mark.parametrize('method', ['group_by', 'order_by', 'distinct_on'])
def test_string_star_is_rejected_consistently(method):
    """Every string column path treats '*' the same way select() does"""
    query = SelectQueryBuilder.from_table('users')

    with pytest.raises(ValueError):
        getattr(query, method)('*').render()


def test_with_cte_multiple_ctes_docstring_example_runs():
    """The worked example in with_cte's docstring must actually execute"""
    query = (
        SelectQueryBuilder.from_table('filtered')
        .with_cte('jennifers', Users.select().where(Users.username == 'Jennifer'))
        .with_cte('filtered', t'SELECT id FROM jennifers WHERE age > 18')
        .select(t'*')
    )
    sql, params = query.render()

    assert sql.startswith('WITH jennifers AS (')
    assert 'filtered AS (SELECT id FROM jennifers WHERE age > 18)' in sql
    assert sql.endswith('SELECT * FROM filtered')
    assert params == ['Jennifer']


def test_with_cte_recursive_docstring_example_runs():
    """The recursive worked example in with_cte's docstring must actually execute"""
    query = (
        SelectQueryBuilder.from_table('tree')
        .with_cte('tree', t'''
            SELECT id, name, parent_id FROM categories WHERE parent_id IS NULL
            UNION ALL
            SELECT c.id, c.name, c.parent_id FROM categories c
            JOIN tree t ON c.parent_id = t.id
        ''', recursive=True)
        .select(t'*')
    )
    sql, params = query.render()

    assert sql.startswith('WITH RECURSIVE tree AS (')
    assert sql.endswith('SELECT * FROM tree')
    assert params == []


def test_literal_spec_still_rejects_star_directly():
    """The :literal spec itself is unchanged -- FROM *, aliases and CTE names still reject it"""
    with pytest.raises(ValueError):
        tsql.render(t'SELECT id FROM {"*":literal}')

    with pytest.raises(ValueError):
        SelectQueryBuilder.from_table('*').select('id').render()
