import tsql
from tsql.query_builder import Table, Column, Condition, InsertBuilder, UpdateBuilder, DeleteBuilder


class Users(Table):
    id: Column
    username: Column
    email: Column
    created_at: Column


class Posts(Table):
    id: Column
    user_id: Column
    title: Column
    body: Column


class Comments(Table):
    id: Column
    post_id: Column
    user_id: Column
    content: Column


def test_table_creation():
    """Test that decorator returns instance with Column descriptors"""
    assert isinstance(Users.id, Column)
    assert Users.id.table_name == 'users'
    assert Users.id.column_name == 'id'
    assert Users.username.column_name == 'username'


def test_column_equality():
    """Test Column equality operator"""
    condition = Users.id == 5
    assert isinstance(condition, Condition)
    assert condition.left.column_name == 'id'
    assert condition.operator == '='
    assert condition.right == 5


def test_column_null_comparison():
    """Test that None comparisons use IS/IS NOT"""
    is_null = Users.email == None
    assert is_null.operator == 'IS'
    assert is_null.right is None

    is_not_null = Users.email != None
    assert is_not_null.operator == 'IS NOT'
    assert is_not_null.right is None


def test_column_comparisons():
    """Test all comparison operators"""
    assert (Users.id > 18).operator == '>'
    assert (Users.id >= 18).operator == '>='
    assert (Users.id < 65).operator == '<'
    assert (Users.id <= 65).operator == '<='
    assert (Users.id != 25).operator == '!='


def test_column_in():
    """Test IN operator"""
    condition = Users.id.in_([1, 2, 3])
    assert condition.operator == 'IN'
    assert condition.right == (1, 2, 3)


def test_column_like():
    """Test LIKE operator"""
    condition = Users.username.like('%john%')
    assert condition.operator == 'LIKE'
    assert condition.right == '%john%'


def test_simple_select_all():
    """Test simple SELECT * query"""
    query = Users.select()
    sql, params = query.render()

    assert sql == 'SELECT * FROM users'
    assert params == []


def test_select_specific_columns():
    """Test SELECT with specific columns"""
    query = Users.select(Users.id, Users.username)
    sql, params = query.render()

    assert 'SELECT users.id, users.username' in sql
    assert 'FROM users' in sql
    assert params == []


def test_select_with_where():
    """Test SELECT with WHERE clause"""
    query = Users.select(Users.id, Users.username).where(Users.id == 5)
    sql, params = query.render()

    assert 'SELECT users.id, users.username' in sql
    assert 'FROM users' in sql
    assert 'WHERE' in sql
    assert 'users.id = ?' in sql
    assert params == [5]


def test_select_with_multiple_where():
    """Test that multiple WHERE calls are ANDed together"""
    query = (Users.select(Users.id, Users.username)
             .where(Users.id > 5)
             .where(Users.email == None))
    sql, params = query.render()

    assert 'WHERE' in sql
    assert 'AND' in sql
    assert 'users.id > ?' in sql
    assert 'users.email IS NULL' in sql
    assert params == [5]


def test_where_with_null():
    """Test WHERE with NULL handling"""
    query = Users.select().where(Users.email != None)
    sql, params = query.render()

    assert 'WHERE users.email IS NOT NULL' in sql
    assert params == []


def test_where_with_in():
    """Test WHERE with IN clause"""
    query = Users.select().where(Users.id.in_([1, 2, 3]))
    sql, params = query.render()

    assert 'WHERE users.id IN' in sql
    assert '?' in sql
    assert params == [1, 2, 3]


def test_where_with_like():
    """Test WHERE with LIKE clause"""
    query = Users.select().where(Users.username.like('%john%'))
    sql, params = query.render()

    assert 'WHERE users.username LIKE ?' in sql
    assert params == ['%john%']


def test_simple_join():
    """Test basic INNER JOIN"""
    query = (Posts.select(Posts.title, Users.username)
             .join(Users, Posts.user_id == Users.id))
    sql, params = query.render()

    assert 'SELECT posts.title, users.username' in sql
    assert 'FROM posts' in sql
    assert 'INNER JOIN users ON posts.user_id = users.id' in sql
    assert params == []


def test_join_with_where():
    """Test JOIN with WHERE clause"""
    query = (Posts.select(Posts.title, Users.username)
             .join(Users, Posts.user_id == Users.id)
             .where(Posts.id > 100))
    sql, params = query.render()

    assert 'INNER JOIN users ON posts.user_id = users.id' in sql
    assert 'WHERE posts.id > ?' in sql
    assert params == [100]


def test_left_join():
    """Test LEFT JOIN"""
    query = (Users.select(Users.username, Posts.title)
             .left_join(Posts, Users.id == Posts.user_id))
    sql, params = query.render()

    assert 'LEFT JOIN posts ON users.id = posts.user_id' in sql


def test_order_by():
    """Test ORDER BY clause"""
    query = Users.select().order_by(Users.username)
    sql, params = query.render()

    assert 'ORDER BY users.username ASC' in sql


def test_order_by_desc():
    """Test ORDER BY with DESC"""
    query = Users.select().order_by((Users.id, 'DESC'))
    sql, params = query.render()

    assert 'ORDER BY users.id DESC' in sql


def test_order_by_multiple():
    """Test ORDER BY with multiple columns"""
    query = Users.select().order_by(Users.username, (Users.id, 'DESC'))
    sql, params = query.render()

    assert 'ORDER BY users.username ASC, users.id DESC' in sql


def test_limit():
    """Test LIMIT clause"""
    query = Users.select().limit(10)
    sql, params = query.render()

    assert 'LIMIT ?' in sql
    assert params == [10]


def test_complex_query():
    """Test complex query with multiple clauses"""
    query = (Posts.select(Posts.title, Users.username)
             .join(Users, Posts.user_id == Users.id)
             .where(Posts.id > 100)
             .where(Users.id >= 5)
             .order_by((Posts.id, 'DESC'))
             .limit(20))
    sql, params = query.render()

    assert 'SELECT posts.title, users.username' in sql
    assert 'FROM posts' in sql
    assert 'INNER JOIN users ON posts.user_id = users.id' in sql
    assert 'WHERE posts.id > ?' in sql
    assert 'AND users.id >= ?' in sql
    assert 'ORDER BY posts.id DESC' in sql
    assert 'LIMIT ?' in sql
    assert params == [100, 5, 20]


def test_sql_injection_protection():
    """Test that values are properly parameterized"""
    malicious = "1 OR 1=1; DROP TABLE users; --"

    query = Users.select().where(Users.username == malicious)
    sql, params = query.render()

    assert 'DROP TABLE' not in sql
    assert '?' in sql
    assert params == [malicious]


def test_column_to_column_comparison():
    """Test comparing two columns"""
    condition = Users.id == Posts.user_id
    tsql_template = condition.to_tsql()
    sql, params = tsql.render(tsql_template)

    assert 'users.id = posts.user_id' in sql
    assert params == []


def test_to_tsql_returns_tsql_object():
    """Test that QueryBuilder.to_tsql() returns a TSQL object"""
    query = Users.select(Users.id).where(Users.id > 5)
    tsql_obj = query.to_tsql()

    assert isinstance(tsql_obj, tsql.TSQL)

    sql, params = tsql_obj.render()
    assert 'SELECT users.id' in sql
    assert params == [5]


def test_render_with_style():
    """Test that render() accepts style parameter"""
    query = Users.select().where(Users.id == 5)

    sql, params = query.render(style=tsql.styles.NUMERIC_DOLLAR)
    assert '$1' in sql
    assert params == [5]


def test_schema_support():
    """Test that schema parameter works"""
    class SchemaUsers(Table, table_name='users', schema='public'):
        id: Column

    assert SchemaUsers.table_name == 'users'
    assert SchemaUsers.schema == 'public'


def test_group_by():
    """Test GROUP BY clause"""
    query = Posts.select(Posts.user_id).group_by(Posts.user_id)
    sql, params = query.render()

    assert 'SELECT posts.user_id' in sql
    assert 'GROUP BY posts.user_id' in sql
    assert params == []


def test_group_by_multiple():
    """Test GROUP BY with multiple columns"""
    query = Posts.select(Posts.user_id, Posts.title).group_by(Posts.user_id, Posts.title)
    sql, params = query.render()

    assert 'GROUP BY posts.user_id, posts.title' in sql


def test_having():
    """Test HAVING clause with condition"""
    query = Posts.select(Posts.user_id).group_by(Posts.user_id).having(Posts.id > 5)
    sql, params = query.render()

    assert 'GROUP BY posts.user_id' in sql
    assert 'HAVING posts.id > ?' in sql
    assert params == [5]


def test_having_with_tstring():
    """Test HAVING clause with raw t-string"""
    user_id_col = str(Posts.user_id)
    min_count = 10
    query = (Posts.select(Posts.user_id)
             .group_by(Posts.user_id)
             .having(t'COUNT(*) > {min_count}'))
    sql, params = query.render()

    assert 'HAVING COUNT(*) > ?' in sql
    assert params == [10]


def test_offset():
    """Test OFFSET clause"""
    query = Posts.select().limit(10).offset(20)
    sql, params = query.render()

    assert 'LIMIT ?' in sql
    assert 'OFFSET ?' in sql
    assert params == [10, 20]


def test_complex_aggregation_query():
    """Test complex query with GROUP BY, HAVING, ORDER BY, LIMIT, OFFSET"""
    query = (Posts.select(Posts.user_id)
             .join(Users, Posts.user_id == Users.id)
             .where(Posts.id > 100)
             .group_by(Posts.user_id)
             .having(Posts.id > 5)
             .order_by((Posts.user_id, 'DESC'))
             .limit(10)
             .offset(5))
    sql, params = query.render()

    assert 'SELECT posts.user_id' in sql
    assert 'INNER JOIN users ON posts.user_id = users.id' in sql
    assert 'WHERE posts.id > ?' in sql
    assert 'GROUP BY posts.user_id' in sql
    assert 'HAVING posts.id > ?' in sql
    assert 'ORDER BY posts.user_id DESC' in sql
    assert 'LIMIT ?' in sql
    assert 'OFFSET ?' in sql
    assert params == [100, 5, 10, 5]


def test_where_with_tstring_or_clause():
    """Test that t-string WHERE conditions with OR are wrapped in parentheses"""
    age = 18
    query = (Users.select()
             .where(Users.id > 100)
             .where(t"email ILIKE '%something%' OR email ILIKE '%otherthing%'"))
    sql, params = query.render()

    assert 'WHERE users.id > ?' in sql
    assert "AND (email ILIKE '%something%' OR email ILIKE '%otherthing%')" in sql
    assert params == [100]


def test_where_with_tstring_complex():
    """Test complex t-string WHERE with parameters"""
    search1 = 'john'
    search2 = 'jane'
    query = (Users.select()
             .where(Users.id > 5)
             .where(t"username ILIKE {search1} OR email ILIKE {search2}"))
    sql, params = query.render()

    assert 'WHERE users.id > ?' in sql
    assert 'AND (username ILIKE ? OR email ILIKE ?)' in sql
    assert params == [5, 'john', 'jane']


def test_table_insert():
    """Test table.insert() method"""
    query = Users.insert({'username': 'bob', 'email': 'bob@example.com'})
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'username' in sql and 'email' in sql
    assert 'VALUES' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == ['bob', 'bob@example.com']


def test_table_insert_with_returning():
    """Test table.insert() with RETURNING"""
    query = Users.insert({'username': 'bob', 'email': 'bob@example.com'}).returning()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'RETURNING *' in sql
    assert params == ['bob', 'bob@example.com']


def test_table_insert_ignore():
    """Test table.insert() with ignore (MySQL)"""
    query = Users.insert({'username': 'bob', 'email': 'bob@example.com'}).ignore()
    sql, params = query.render()

    assert 'INSERT IGNORE INTO users' in sql
    assert params == ['bob', 'bob@example.com']


def test_table_insert_on_conflict_do_nothing():
    """Test table.insert() with ON CONFLICT DO NOTHING (Postgres/SQLite)"""
    query = Users.insert({'username': 'bob', 'email': 'bob@example.com'}).on_conflict_do_nothing()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT DO NOTHING' in sql


def test_table_insert_on_conflict_update():
    """Test table.insert() with ON CONFLICT UPDATE (Postgres/SQLite upsert)"""
    query = Users.insert({'email': 'bob@example.com', 'username': 'bob'}).on_conflict_update(conflict_on='email')
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT (email)' in sql
    assert 'DO UPDATE SET' in sql
    assert 'username = EXCLUDED.username' in sql


def test_table_insert_on_duplicate_key_update():
    """Test table.insert() with ON DUPLICATE KEY UPDATE (MySQL)"""
    query = Users.insert({'email': 'bob@example.com', 'username': 'bob'}).on_duplicate_key_update()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'AS new' in sql
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert 'email = new.email' in sql
    assert 'username = new.username' in sql


def test_table_insert_chained_with_returning():
    """Test chaining conflict handling with RETURNING"""
    query = (Users.insert({'email': 'bob@example.com', 'username': 'bob'})
             .on_conflict_update(conflict_on='email')
             .returning('id', 'username'))
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT (email)' in sql
    assert 'DO UPDATE SET' in sql
    assert 'RETURNING id, username' in sql


def test_table_update_with_where():
    """Test table.update() with WHERE clause"""
    builder = Users.update({'username': 'bob_updated'}).where(Users.id == 5)
    assert isinstance(builder, UpdateBuilder)

    sql, params = builder.render()

    assert 'UPDATE users SET' in sql
    assert 'username = ?' in sql
    assert 'WHERE users.id = ?' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == ['bob_updated', 5]


def test_table_update_multiple_conditions():
    """Test table.update() with multiple WHERE conditions"""
    builder = (Users.update({'username': 'bob_updated', 'email': 'new@example.com'})
               .where(Users.id > 10)
               .where(Users.created_at == None))

    sql, params = builder.render()

    assert 'UPDATE users SET' in sql
    assert 'WHERE users.id > ?' in sql
    assert 'AND users.created_at IS NULL' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == ['bob_updated', 'new@example.com', 10]


def test_table_update_with_returning():
    """Test table.update() with RETURNING"""
    builder = Users.update({'username': 'bob_updated'}).where(Users.id == 5).returning()
    sql, params = builder.render()

    assert 'UPDATE users SET' in sql
    assert 'WHERE users.id = ?' in sql
    assert 'RETURNING *' in sql
    assert params == ['bob_updated', 5]


def test_table_delete_with_where():
    """Test table.delete() with WHERE clause"""
    builder = Users.delete().where(Users.id == 5)
    assert isinstance(builder, DeleteBuilder)

    sql, params = builder.render()

    assert 'DELETE FROM users' in sql
    assert 'WHERE users.id = ?' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == [5]


def test_table_delete_multiple_conditions():
    """Test table.delete() with multiple WHERE conditions"""
    builder = (Users.delete()
               .where(Users.id > 100)
               .where(Users.email == None))

    sql, params = builder.render()

    assert 'DELETE FROM users' in sql
    assert 'WHERE users.id > ?' in sql
    assert 'AND users.email IS NULL' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == [100]


def test_table_delete_with_returning():
    """Test table.delete() with RETURNING"""
    builder = Users.delete().where(Users.id == 5).returning()
    sql, params = builder.render()

    assert 'DELETE FROM users' in sql
    assert 'WHERE users.id = ?' in sql
    assert 'RETURNING *' in sql
    assert params == [5]


def test_update_with_t_string_where():
    """Test UpdateBuilder with raw t-string WHERE clause"""
    min_age = 18
    builder = Users.update({'username': 'adult'}).where(t"age >= {min_age}")

    sql, params = builder.render()

    assert 'UPDATE users SET' in sql
    assert 'WHERE (age >= ?)' in sql
    assert params == ['adult', 18]


def test_delete_with_t_string_where():
    """Test DeleteBuilder with raw t-string WHERE clause"""
    pattern = '%test%'
    builder = Users.delete().where(t"email LIKE {pattern}")

    sql, params = builder.render()

    assert 'DELETE FROM users' in sql
    assert 'WHERE (email LIKE ?)' in sql
    assert params == ['%test%']


def test_column_as_method():
    """Test using Column.as_() method for aliases"""
    query = Users.select(
        Users.id,
        Users.username.as_('user'),
        Users.email.as_('contact_email')
    )

    sql, params = query.render()

    assert "SELECT users.id, users.username AS user, users.email AS contact_email" in sql
    assert "FROM users" in sql
    assert params == []


def test_column_as_with_where():
    """Test that aliased columns work with WHERE clauses"""
    query = Users.select(
        Users.id,
        Users.username.as_('user')
    ).where(Users.email == 'test@example.com')

    sql, params = query.render()

    assert "SELECT users.id, users.username AS user" in sql
    assert "WHERE users.email = ?" in sql
    assert params == ['test@example.com']


def test_tstring_alias():
    """Test using raw t-string for column aliases"""
    query = Users.select(
        Users.id,
        Users.email,
        t'users.username AS user'
    )

    sql, params = query.render()

    assert "SELECT users.id, users.email, users.username AS user" in sql
    assert "FROM users" in sql
    assert params == []


def test_mixed_columns_and_tstrings():
    """Test mixing Column objects, aliased Columns, and raw t-strings"""
    query = Users.select(
        Users.id,
        Users.username.as_('user'),
        Users.email,
        t'users.created_at AS created'
    )

    sql, params = query.render()

    assert "SELECT users.id, users.username AS user, users.email, users.created_at AS created" in sql
    assert "FROM users" in sql
    assert params == []


def test_column_without_alias_unchanged():
    """Test that columns without aliases remain unchanged"""
    col1 = Users.username
    aliased_col = Users.username.as_('user')

    # Original column should not have alias
    assert str(col1) == "users.username"
    assert str(aliased_col) == "users.username AS user"

    # Using the original column again should still not have alias
    query = Users.select(col1)
    sql, params = query.render()
    assert "SELECT users.username FROM users" in sql


def test_multiple_queries_with_same_column():
    """Test that aliasing in one query doesn't affect another query"""
    # First query with alias
    query1 = Users.select(Users.username.as_('user'))
    sql1, _ = query1.render()
    assert "username AS user" in sql1

    # Second query without alias
    query2 = Users.select(Users.username)
    sql2, _ = query2.render()
    assert "username AS user" not in sql2
    assert "SELECT users.username FROM users" in sql2


def test_tstring_with_params_in_select():
    """Test that t-strings with parameters work in select"""
    separator = ' - '
    query = Users.select(
        Users.id,
        t'CONCAT(users.username, {separator}, users.email) AS full_info'
    ).where(Users.id > 5)

    sql, params = query.render()

    assert 'CONCAT(users.username, ?, users.email) AS full_info' in sql
    assert 'WHERE users.id > ?' in sql
    assert params == [' - ', 5]


def test_column_is_null_property():
    """Test is_null property"""
    condition = Users.email.is_null
    assert condition.operator == 'IS'
    assert condition.right is None


def test_column_is_not_null_property():
    """Test is_not_null property"""
    condition = Users.email.is_not_null
    assert condition.operator == 'IS NOT'
    assert condition.right is None


def test_where_with_is_null():
    """Test WHERE with is_null"""
    query = Users.select().where(Users.email.is_null)
    sql, params = query.render()

    assert 'WHERE users.email IS NULL' in sql
    assert params == []


def test_where_with_is_not_null():
    """Test WHERE with is_not_null"""
    query = Users.select().where(Users.email.is_not_null)
    sql, params = query.render()

    assert 'WHERE users.email IS NOT NULL' in sql
    assert params == []


def test_column_not_in():
    """Test NOT IN operator"""
    condition = Users.id.not_in([1, 2, 3])
    assert condition.operator == 'NOT IN'
    assert condition.right == (1, 2, 3)


def test_where_with_not_in():
    """Test WHERE with NOT IN clause"""
    query = Users.select().where(Users.id.not_in([1, 2, 3]))
    sql, params = query.render()

    assert 'WHERE users.id NOT IN' in sql
    assert '?' in sql
    assert params == [1, 2, 3]


def test_column_between():
    """Test BETWEEN operator"""
    condition = Users.id.between(10, 50)
    assert condition.operator == 'BETWEEN'
    assert condition.right == (10, 50)


def test_where_with_between():
    """Test WHERE with BETWEEN clause"""
    query = Users.select().where(Users.id.between(10, 50))
    sql, params = query.render()

    assert 'WHERE users.id BETWEEN ? AND ?' in sql
    assert params == [10, 50]


def test_column_not_between():
    """Test NOT BETWEEN operator"""
    condition = Users.id.not_between(10, 50)
    assert condition.operator == 'NOT BETWEEN'
    assert condition.right == (10, 50)


def test_where_with_not_between():
    """Test WHERE with NOT BETWEEN clause"""
    query = Users.select().where(Users.id.not_between(10, 50))
    sql, params = query.render()

    assert 'WHERE users.id NOT BETWEEN ? AND ?' in sql
    assert params == [10, 50]


def test_column_not_like():
    """Test NOT LIKE operator"""
    condition = Users.username.not_like('%john%')
    assert condition.operator == 'NOT LIKE'
    assert condition.right == '%john%'


def test_where_with_not_like():
    """Test WHERE with NOT LIKE clause"""
    query = Users.select().where(Users.username.not_like('%john%'))
    sql, params = query.render()

    assert 'WHERE users.username NOT LIKE ?' in sql
    assert params == ['%john%']


def test_column_ilike():
    """Test ILIKE operator (case-insensitive)"""
    condition = Users.username.ilike('%JOHN%')
    assert condition.operator == 'ILIKE'
    assert condition.right == '%JOHN%'


def test_where_with_ilike():
    """Test WHERE with ILIKE clause"""
    query = Users.select().where(Users.username.ilike('%JOHN%'))
    sql, params = query.render()

    assert 'WHERE users.username ILIKE ?' in sql
    assert params == ['%JOHN%']


def test_column_not_ilike():
    """Test NOT ILIKE operator"""
    condition = Users.username.not_ilike('%JOHN%')
    assert condition.operator == 'NOT ILIKE'
    assert condition.right == '%JOHN%'


def test_where_with_not_ilike():
    """Test WHERE with NOT ILIKE clause"""
    query = Users.select().where(Users.username.not_ilike('%JOHN%'))
    sql, params = query.render()

    assert 'WHERE users.username NOT ILIKE ?' in sql
    assert params == ['%JOHN%']


def test_in_with_subquery():
    """Test IN with a subquery (QueryBuilder)"""
    subquery = Users.select(Users.id).where(Users.username.like('%admin%'))
    query = Posts.select().where(Posts.user_id.in_(subquery))
    sql, params = query.render()

    assert 'WHERE posts.user_id IN (SELECT' in sql
    assert 'users.username LIKE ?' in sql
    assert params == ['%admin%']


def test_not_in_with_subquery():
    """Test NOT IN with a subquery (QueryBuilder)"""
    subquery = Users.select(Users.id).where(Users.username.like('%banned%'))
    query = Posts.select().where(Posts.user_id.not_in(subquery))
    sql, params = query.render()

    assert 'WHERE posts.user_id NOT IN (SELECT' in sql
    assert 'users.username LIKE ?' in sql
    assert params == ['%banned%']


def test_in_with_tstring():
    """Test IN with a raw t-string"""
    query = Users.select().where(Users.id.in_(t'(SELECT user_id FROM admins)'))
    sql, params = query.render()

    assert 'WHERE users.id IN (SELECT user_id FROM admins)' in sql
    assert params == []


def test_complex_query_with_new_operators():
    """Test complex query using multiple new operators"""
    query = (Users.select()
             .where(Users.id.between(1, 100))
             .where(Users.email.is_not_null)
             .where(Users.id.not_in([5, 10, 15]))
             .where(Users.username.ilike('%test%')))
    sql, params = query.render()

    assert 'WHERE users.id BETWEEN ? AND ?' in sql
    assert 'AND users.email IS NOT NULL' in sql
    assert 'AND users.id NOT IN' in sql
    assert 'AND users.username ILIKE ?' in sql
    assert params == [1, 100, 5, 10, 15, '%test%']
