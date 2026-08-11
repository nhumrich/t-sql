"""`Column`'s four name fields are composed into SQL text, so each must be an identifier.

`Column.__str__` builds `schema.table.column` plus ` AS alias`, and the whole string is
rendered as SQL text rather than parameterized. Two plain-`str` paths reach it from
request data: a BI or export UI where the user labels their own output columns
(`as_()`), and a generic query endpoint that names a table and column (`Column(...)`).
The constructor is the gate — every field must be a single unqualified identifier.

`'*'` stays legal as a column name because `Table.ALL` is `Column(table_name, '*')`.
"""

import json

import pytest

from tsql.query_builder import Column, Table


class Users(Table):
    id: Column
    username: Column
    email: Column


class Orders(Table):
    id: Column
    user_id: Column
    total: Column


def test_export_label_from_user_input_raises():
    """A BI/export UI cannot smuggle an extra column through a user-supplied label"""
    request = json.loads('{"label": "total, (SELECT password FROM secrets) AS leaked"}')

    with pytest.raises(ValueError):
        Orders.total.as_(request['label'])


def test_generic_query_endpoint_column_from_user_input_raises():
    """A generic query endpoint cannot smuggle a UNION through a column name"""
    request = json.loads(
        '{"table": "users", "column": "id FROM users UNION SELECT password FROM secrets--"}'
    )

    with pytest.raises(ValueError):
        Column(request['table'], request['column'])


def test_alias_with_subquery_exfiltration_raises():
    """A subquery payload in an alias is rejected"""
    with pytest.raises(ValueError):
        Users.id.as_('x, (SELECT password FROM secrets)')


def test_alias_escaping_into_a_new_clause_raises():
    """An alias cannot open a new FROM clause"""
    with pytest.raises(ValueError):
        Users.id.as_('x FROM secrets--')


def test_alias_with_stacked_statement_raises():
    """A stacked statement in an alias is rejected"""
    with pytest.raises(ValueError):
        Users.id.as_('x; DROP TABLE users --')


def test_table_name_from_user_input_raises():
    """A payload in a Column's table name is rejected"""
    with pytest.raises(ValueError):
        Column('users; DROP TABLE secrets--', 'id')


def test_schema_from_user_input_raises():
    """A payload in a Column's schema is rejected"""
    with pytest.raises(ValueError):
        Column('users', 'id', schema='public; DROP TABLE secrets--')


def test_dotted_table_name_raises():
    """A table name is one part of a qualified name, so the schema goes in schema=

    A dotted table name was never an injection — every part is identifier-checked — but
    it let one value choose a schema the query never meant to reach. `schema=` is where
    the qualifier goes, and the renderer writes the dot.
    """
    with pytest.raises(ValueError):
        class Scoped(Table, table_name='public.users'):
            id: Column


def test_dotted_table_name_on_a_column_raises():
    """The same dotted name passed straight to Column"""
    with pytest.raises(ValueError):
        Column('public.users', 'id')


def test_dotted_schema_raises():
    """A cross-database qualifier is the same shape and the same answer"""
    with pytest.raises(ValueError):
        Column('users', 'id', schema='mydb.public')


def test_schema_qualifier_renders_through_the_schema_field():
    """The supported way to write what a dotted table name used to say"""
    sql, _ = Users.select(Column('users', 'id', schema='public')).render()

    assert 'public.users.id' in sql


def test_dotted_table_name_with_a_payload_part_raises():
    """A payload in a dotted name is rejected along with the dot"""
    with pytest.raises(ValueError):
        Column('public.users; DROP TABLE secrets--', 'id')


def test_dotted_table_name_with_a_quoted_part_raises():
    """A quoted part is not an identifier"""
    with pytest.raises(ValueError):
        Column('"public".users', 'id')


def test_table_name_with_empty_part_raises():
    """An empty part is not an identifier"""
    with pytest.raises(ValueError):
        Column('public..users', 'id')


def test_table_name_with_trailing_dot_raises():
    """A trailing dot leaves an empty part"""
    with pytest.raises(ValueError):
        Column('users.', 'id')


def test_table_name_with_too_many_parts_raises():
    """A table name is a single identifier whatever the part count"""
    with pytest.raises(ValueError):
        Column('a.b.c.d', 'id')


def test_star_is_not_a_valid_table_name_part():
    """'*' is a column name, never part of a table name"""
    with pytest.raises(ValueError):
        Column('users.*', 'id')


def test_dotted_column_name_raises():
    """A column name is the last part of a qualified name, so it is a single identifier"""
    with pytest.raises(ValueError):
        Column('users', 'users.id')


def test_dotted_alias_raises():
    """An alias names a new column, so it is a single identifier"""
    with pytest.raises(ValueError):
        Users.id.as_('users.id')


def test_star_alias_raises():
    """'*' is a column name, never an alias"""
    with pytest.raises(ValueError):
        Users.id.as_('*')


def test_empty_alias_raises():
    """An empty alias is not a valid identifier"""
    with pytest.raises(ValueError):
        Users.id.as_('')


def test_non_string_alias_raises():
    """A non-str alias is rejected rather than stringified into the SQL"""
    with pytest.raises(ValueError):
        Users.id.as_(1)


def test_str_subclass_cannot_launder_a_payload_through_dunder_str():
    """The stored name comes from the real str buffer, not from an overridable __str__

    A subclass whose buffer passes isidentifier() while __str__ returns something else
    would otherwise get its payload stored verbatim and rendered.
    """
    class Sneaky(str):
        def __str__(self):
            return 'id FROM secrets--'

    column = Column('users', Sneaky('id'))

    assert column.column_name == 'id'
    sql, _ = Users.select(column).render()
    assert sql == 'SELECT users.id FROM users'


def test_error_message_names_the_bad_value():
    """The rejection names what was supplied so the caller can find it"""
    with pytest.raises(ValueError) as exc_info:
        Users.id.as_('x FROM secrets--')

    assert 'x FROM secrets--' in str(exc_info.value)


def test_error_message_does_not_suggest_unsafe():
    """The rejection must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        Users.id.as_('x FROM secrets--')

    assert 'unsafe' not in str(exc_info.value).lower()


def test_valid_alias_still_renders():
    """An ordinary identifier alias is unaffected"""
    sql, params = Users.select(Users.email.as_('contact_email')).render()

    assert sql == 'SELECT users.email AS contact_email FROM users'
    assert params == []


def test_valid_alias_renders_in_group_by():
    """An identifier alias still renders unchanged in GROUP BY"""
    sql, _ = Users.select(Users.id).group_by(Users.id.as_('grouped')).render()

    assert 'GROUP BY users.id AS grouped' in sql


def test_valid_alias_renders_in_order_by():
    """An identifier alias still renders unchanged in ORDER BY"""
    sql, _ = Users.select(Users.id).order_by(Users.id.as_('sorted')).render()

    assert 'ORDER BY users.id AS sorted ASC' in sql


def test_table_all_is_still_legal():
    """Table.ALL is Column(table_name, '*'), so '*' remains a valid column name"""
    sql, _ = Users.select(Users.ALL).render()

    assert sql == 'SELECT users.* FROM users'


def test_star_column_can_be_constructed_directly():
    """Constructing the star column directly is the same legal case as Table.ALL"""
    sql, _ = Users.select(Column('users', '*')).render()

    assert sql == 'SELECT users.* FROM users'


def test_column_without_table_name_is_legal():
    """A Column declared as a class-body sentinel carries no table name yet"""
    assert Column(column_name='systemvar').column_name == 'systemvar'


def test_remapped_column_name_still_works():
    """The documented column-remapping pattern is unaffected"""
    class Remapped(Table, table_name='my_table'):
        system_var: Column = Column(column_name='systemvar')

    sql, params = Remapped.select(Remapped.system_var).where(
        Remapped.system_var == 'test'
    ).render()

    assert 'my_table.systemvar' in sql
    assert params == ['test']


def test_schema_qualified_column_still_renders():
    """A schema-qualified column is unaffected"""
    class Scoped(Table, table_name='users', schema='public'):
        id: Column

    sql, _ = Scoped.select(Scoped.id).render()

    assert 'public.users.id' in sql
