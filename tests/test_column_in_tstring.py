"""A `Column` splices into a t-string directly, as the replacement for `str(col):literal`.

Mixing builder columns into a raw t-string used to mean `str(Users.name)` plus `:literal`.
A literal is now a single identifier, so the dots in `users.name` have to come from the
query rather than from the value — which is exactly what the Column itself knows how to
write. Splicing the Column needs no format spec and cannot be handed a payload.
"""

import pytest

from tsql.query_builder import Column, Table


class Users(Table):
    id: Column
    name: Column
    age: Column


class Scoped(Table, table_name='users', schema='public'):
    id: Column


def test_column_splices_as_a_qualified_reference():
    """The documented mixing pattern, with the Column in place of str(col):literal"""
    search = 'john'
    sql, params = Users.select(Users.id).where(
        t"{Users.name} LIKE '%' || {search} || '%'"
    ).render()

    assert "(users.name LIKE '%' || ? || '%')" in sql
    assert params == ['john']


def test_schema_qualified_column_splices_with_both_dots():
    """A schema-qualified column writes all three parts"""
    sql, _ = Scoped.select(Scoped.id).where(t'{Scoped.id} IS NOT NULL').render()

    assert 'public.users.id IS NOT NULL' in sql


def test_column_without_table_name_splices_bare():
    """A class-body sentinel carries no table, so it renders as the column alone"""
    sql, _ = Users.select(Users.id).where(t'{Column(column_name="systemvar")} > 0').render()

    assert 'systemvar > 0' in sql


def test_aliased_column_splices_with_its_alias():
    """An alias is part of what the column names, so a SELECT-list splice keeps it"""
    sql, _ = Users.select(t'{Users.name.as_("contact")}').render()

    assert sql == 'SELECT users.name AS contact FROM users'


def test_bare_aliased_column_in_where_raises():
    """An alias is a SELECT output name, so it is not a predicate"""
    with pytest.raises(ValueError):
        Users.select().where(Users.name.as_('contact')).render()
