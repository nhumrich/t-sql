"""`join(table, on, join_type=...)` renders `join_type` into the SQL text.

An app that lets a request choose a join kind plumbs a plain `str` straight to the
SQL. Only the four join keywords the typed path can actually express are accepted;
`OUTER` spellings normalize to the bare keyword so the stored value stays a single
identifier, and CROSS/LATERAL joins belong to `join_raw()` because `Join` always
emits an `ON` clause.
"""

import json

import pytest

from tsql.query_builder import Column, Join, Table


class Users(Table):
    id: Column
    username: Column


class Orders(Table):
    id: Column
    user_id: Column
    total: Column


def _join(**kwargs):
    return Orders.select(Orders.id).join(Users, Orders.user_id == Users.id, **kwargs)


def test_join_type_from_user_input_raises():
    """A reporting API cannot smuggle a subquery through join_type="""
    request = json.loads(
        '{"join": "INNER JOIN (SELECT password AS total FROM secrets) x ON 1=1 --"}'
    )

    with pytest.raises(ValueError):
        _join(join_type=request['join'])


def test_join_type_with_stacked_statement_raises():
    """A stacked statement in join_type is rejected"""
    with pytest.raises(ValueError):
        _join(join_type='INNER; DROP TABLE users --')


def test_join_type_with_trailing_comment_raises():
    """A commented-out join_type is rejected"""
    with pytest.raises(ValueError):
        _join(join_type='INNER --')


def test_empty_join_type_raises():
    """An empty join_type is not in the allowlist"""
    with pytest.raises(ValueError):
        _join(join_type='')


def test_non_string_join_type_raises():
    """A non-str join_type is rejected rather than stringified into the SQL"""
    with pytest.raises(ValueError):
        _join(join_type=1)


@pytest.mark.parametrize('join_type', ['INNER', 'LEFT', 'RIGHT', 'FULL'])
def test_supported_join_types_render(join_type):
    """The four join keywords the typed path supports all render"""
    sql, _ = _join(join_type=join_type).render()

    assert f'{join_type} JOIN users ON orders.user_id = users.id' in sql


def test_join_type_is_normalized_to_upper_case():
    """Casing and surrounding whitespace are normalized"""
    sql, _ = _join(join_type='  left  ').render()

    assert 'LEFT JOIN users ON orders.user_id = users.id' in sql


@pytest.mark.parametrize('supplied,emitted', [
    ('LEFT OUTER', 'LEFT'),
    ('RIGHT OUTER', 'RIGHT'),
    ('FULL OUTER', 'FULL'),
])
def test_outer_spellings_normalize_to_the_bare_keyword(supplied, emitted):
    """OUTER is syntactic noise; normalizing keeps the stored value a single identifier"""
    sql, _ = _join(join_type=supplied).render()

    assert f'{emitted} JOIN users ON' in sql
    assert 'OUTER' not in sql


def test_cross_join_type_raises():
    """Join always emits ON, so CROSS could only ever produce invalid SQL"""
    with pytest.raises(ValueError):
        _join(join_type='CROSS')


def test_error_message_names_the_bad_value():
    """The rejection names what was supplied so the caller can find it"""
    with pytest.raises(ValueError) as exc_info:
        _join(join_type='INNER JOIN x ON 1=1 --')

    assert 'INNER JOIN x ON 1=1 --' in str(exc_info.value)


def test_error_message_points_at_join_raw():
    """The escape hatch for a non-standard join is join_raw(), not an unsafe spec"""
    with pytest.raises(ValueError) as exc_info:
        _join(join_type='CROSS')

    assert 'join_raw' in str(exc_info.value)


def test_error_message_does_not_suggest_unsafe():
    """The rejection must not point callers at :unsafe"""
    with pytest.raises(ValueError) as exc_info:
        _join(join_type='INNER JOIN x ON 1=1 --')

    assert 'unsafe' not in str(exc_info.value).lower()


def test_default_join_is_inner():
    """The default join_type is unaffected"""
    sql, _ = _join().render()

    assert 'INNER JOIN users ON orders.user_id = users.id' in sql


def test_left_join_helper_still_works():
    """left_join() is unaffected"""
    sql, _ = Orders.select(Orders.id).left_join(Users, Orders.user_id == Users.id).render()

    assert 'LEFT JOIN users ON orders.user_id = users.id' in sql


def test_right_join_helper_still_works():
    """right_join() is unaffected"""
    sql, _ = Orders.select(Orders.id).right_join(Users, Orders.user_id == Users.id).render()

    assert 'RIGHT JOIN users ON orders.user_id = users.id' in sql


def test_join_raw_still_accepts_cross_join_lateral():
    """join_raw() remains the documented route for CROSS and LATERAL joins"""
    sql, _ = (Orders.select(Orders.id)
              .join_raw(t'CROSS JOIN LATERAL unnest(orders.tags) AS tag')
              .render())

    assert 'CROSS JOIN LATERAL unnest(orders.tags) AS tag' in sql


def test_direct_join_construction_is_validated():
    """Join is public, so its constructor validates too"""
    with pytest.raises(ValueError):
        Join(Users, Orders.user_id == Users.id, 'INNER JOIN x ON 1=1 --')


def test_mutated_join_type_is_revalidated_at_render():
    """Reassigning .join_type after construction cannot smuggle raw SQL into the render"""
    query = _join()
    query._joins[0].join_type = 'INNER JOIN x ON 1=1 --'

    with pytest.raises(ValueError):
        query.render()
