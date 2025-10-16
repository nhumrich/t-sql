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


def test_column_name_remapping():
    """Test that Column(column_name=...) allows remapping Python attribute to DB column name"""
    class MyTable(Table, table_name='my_table'):
        id: Column
        system_var: Column = Column(column_name='systemvar')

    # Verify that the Python attribute name is 'system_var'
    assert isinstance(MyTable.system_var, Column)
    assert MyTable.system_var.table_name == 'my_table'

    # But the DB column name is 'systemvar'
    assert MyTable.system_var.column_name == 'systemvar'

    # Verify it works in queries
    query = MyTable.select(MyTable.system_var).where(MyTable.system_var == 'test')
    sql, params = query.render()

    # The SQL should use 'systemvar', not 'system_var'
    assert 'my_table.systemvar' in sql
    assert 'system_var' not in sql
    assert params == ['test']


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
    query = Users.select().order_by(Users.id.desc())
    sql, params = query.render()

    assert 'ORDER BY users.id DESC' in sql


def test_order_by_multiple():
    """Test ORDER BY with multiple columns"""
    query = Users.select().order_by(Users.username, Users.id.desc())
    sql, params = query.render()

    assert 'ORDER BY users.username ASC, users.id DESC' in sql


def test_order_by_asc_method():
    """Test ORDER BY with .asc() method"""
    query = Users.select().order_by(Users.username.asc())
    sql, params = query.render()

    assert 'ORDER BY users.username ASC' in sql


def test_order_by_desc_method():
    """Test ORDER BY with .desc() method"""
    query = Users.select().order_by(Users.id.desc())
    sql, params = query.render()

    assert 'ORDER BY users.id DESC' in sql


def test_order_by_mixed_methods():
    """Test ORDER BY with mixed .asc() and .desc() methods"""
    query = Users.select().order_by(Users.username.asc(), Users.id.desc())
    sql, params = query.render()

    assert 'ORDER BY users.username ASC, users.id DESC' in sql


def test_order_by_mixed_syntax():
    """Test ORDER BY with mixed method calls and bare columns"""
    query = Users.select().order_by(Users.username, Users.id.desc())
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
             .order_by(Posts.id.desc())
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
    """Test that SelectQueryBuilder.to_tsql() returns a TSQL object"""
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


def test_schema_in_column_string():
    """Test that Column includes schema in string representation"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    col = Accounts.id
    assert str(col) == 'other.accounts.id'
    assert col.schema == 'other'


def test_schema_in_select():
    """Test that SELECT includes schema in table name"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    query = Accounts.select(Accounts.id, Accounts.name)
    sql, params = query.render()

    assert 'SELECT other.accounts.id, other.accounts.name' in sql
    assert 'FROM other.accounts' in sql


def test_schema_in_insert():
    """Test that INSERT includes schema in table name"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    query = Accounts.insert(id='1', name='Test Account')
    sql, params = query.render()

    assert 'INSERT INTO other.accounts' in sql
    assert params == ['1', 'Test Account']


def test_schema_in_update():
    """Test that UPDATE includes schema in table name"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    query = Accounts.update(name='Updated Account').where(Accounts.id == '1')
    sql, params = query.render()

    assert 'UPDATE other.accounts SET' in sql
    assert 'WHERE other.accounts.id = ?' in sql


def test_schema_in_delete():
    """Test that DELETE includes schema in table name"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    query = Accounts.delete().where(Accounts.id == '1')
    sql, params = query.render()

    assert 'DELETE FROM other.accounts' in sql
    assert 'WHERE other.accounts.id = ?' in sql


def test_schema_in_join():
    """Test that JOIN includes schema in table name"""
    class OtherAccounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    class Transactions(Table, table_name='transactions', schema='other'):
        id: Column
        account_id: Column
        amount: Column

    query = (Transactions.select(Transactions.id, OtherAccounts.name)
             .join(OtherAccounts, Transactions.account_id == OtherAccounts.id))
    sql, params = query.render()

    assert 'SELECT other.transactions.id, other.accounts.name' in sql
    assert 'FROM other.transactions' in sql
    assert 'INNER JOIN other.accounts ON other.transactions.account_id = other.accounts.id' in sql


def test_schema_mixed_with_no_schema():
    """Test that tables with schema can join with tables without schema"""
    class SchemaTable(Table, table_name='schematbl', schema='myschema'):
        id: Column

    class NoSchemaTable(Table, table_name='noschematbl'):
        id: Column
        ref_id: Column

    query = (NoSchemaTable.select(NoSchemaTable.id, SchemaTable.id)
             .join(SchemaTable, NoSchemaTable.ref_id == SchemaTable.id))
    sql, params = query.render()

    assert 'SELECT noschematbl.id, myschema.schematbl.id' in sql
    assert 'FROM noschematbl' in sql
    assert 'INNER JOIN myschema.schematbl ON noschematbl.ref_id = myschema.schematbl.id' in sql


def test_schema_with_column_alias():
    """Test that schema works with column aliases"""
    class Accounts(Table, table_name='accounts', schema='other'):
        id: Column
        name: Column

    query = Accounts.select(Accounts.id.as_('account_id'), Accounts.name.as_('account_name'))
    sql, params = query.render()

    assert 'SELECT other.accounts.id AS account_id, other.accounts.name AS account_name' in sql
    assert 'FROM other.accounts' in sql


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
             .order_by(Posts.user_id.desc())
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
    query = Users.insert(username='bob', email='bob@example.com')
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'username' in sql and 'email' in sql
    assert 'VALUES' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == ['bob', 'bob@example.com']


def test_table_insert_with_returning():
    """Test table.insert() with RETURNING"""
    query = Users.insert(username='bob', email='bob@example.com').returning()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'RETURNING *' in sql
    assert params == ['bob', 'bob@example.com']


def test_table_insert_ignore():
    """Test table.insert() with ignore (MySQL)"""
    query = Users.insert(username='bob', email='bob@example.com').ignore()
    sql, params = query.render()

    assert 'INSERT IGNORE INTO users' in sql
    assert params == ['bob', 'bob@example.com']


def test_table_insert_on_conflict_do_nothing():
    """Test table.insert() with ON CONFLICT DO NOTHING (Postgres/SQLite)"""
    query = Users.insert(username='bob', email='bob@example.com').on_conflict_do_nothing()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT DO NOTHING' in sql


def test_table_insert_on_conflict_update():
    """Test table.insert() with ON CONFLICT UPDATE (Postgres/SQLite upsert)"""
    query = Users.insert(email='bob@example.com', username='bob').on_conflict_update(conflict_on='email')
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT (email)' in sql
    assert 'DO UPDATE SET' in sql
    assert 'username = EXCLUDED.username' in sql


def test_table_insert_on_duplicate_key_update():
    """Test table.insert() with ON DUPLICATE KEY UPDATE (MySQL)"""
    query = Users.insert(email='bob@example.com', username='bob').on_duplicate_key_update()
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'AS new' in sql
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert 'email = new.email' in sql
    assert 'username = new.username' in sql


def test_table_insert_chained_with_returning():
    """Test chaining conflict handling with RETURNING"""
    query = (Users.insert(email='bob@example.com', username='bob')
             .on_conflict_update(conflict_on='email')
             .returning('id', 'username'))
    sql, params = query.render()

    assert 'INSERT INTO users' in sql
    assert 'ON CONFLICT (email)' in sql
    assert 'DO UPDATE SET' in sql
    assert 'RETURNING id, username' in sql


def test_table_update_with_where():
    """Test table.update() with WHERE clause"""
    builder = Users.update(username='bob_updated').where(Users.id == 5)
    assert isinstance(builder, UpdateBuilder)

    sql, params = builder.render()

    assert 'UPDATE users SET' in sql
    assert 'username = ?' in sql
    assert 'WHERE users.id = ?' in sql
    assert 'RETURNING' not in sql  # No RETURNING by default
    assert params == ['bob_updated', 5]


def test_table_update_multiple_conditions():
    """Test table.update() with multiple WHERE conditions"""
    builder = (Users.update(username='bob_updated', email='new@example.com')
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
    builder = Users.update(username='bob_updated').where(Users.id == 5).returning()
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
    builder = Users.update(username='adult').where(t"age >= {min_age}")

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
    """Test IN with a subquery (SelectQueryBuilder)"""
    subquery = Users.select(Users.id).where(Users.username.like('%admin%'))
    query = Posts.select().where(Posts.user_id.in_(subquery))
    sql, params = query.render()

    assert 'WHERE posts.user_id IN (SELECT' in sql
    assert 'users.username LIKE ?' in sql
    assert params == ['%admin%']


def test_not_in_with_subquery():
    """Test NOT IN with a subquery (SelectQueryBuilder)"""
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


def test_insert_with_static_default():
    """Test that static default values are applied when column is omitted"""
    from sqlalchemy import MetaData, Column as SAColumn, String

    metadata = MetaData()

    class Articles(Table, table_name='articles', metadata=metadata):
        id = SAColumn(String, primary_key=True)
        title = SAColumn(String)
        status = SAColumn(String, default='draft')

    query = Articles.insert(id='123', title='Test Article')
    sql, params = query.render()

    assert 'INSERT INTO articles' in sql
    assert 'status' in sql
    assert params == ['123', 'Test Article', 'draft']


def test_insert_with_callable_default():
    """Test that callable defaults are invoked when column is omitted"""
    from sqlalchemy import MetaData, Column as SAColumn, String

    metadata = MetaData()

    class Articles(Table, table_name='articles', metadata=metadata):
        id = SAColumn(String, primary_key=True, default=lambda: 'generated_id')
        title = SAColumn(String)

    query = Articles.insert(title='Test Article')
    sql, params = query.render()

    assert 'INSERT INTO articles' in sql
    assert 'id' in sql
    assert 'generated_id' in params
    assert 'Test Article' in params


def test_insert_overrides_default():
    """Test that user-provided values override defaults"""
    from sqlalchemy import MetaData, Column as SAColumn, String

    metadata = MetaData()

    class Articles(Table, table_name='articles', metadata=metadata):
        id = SAColumn(String, primary_key=True)
        status = SAColumn(String, default='draft')

    query = Articles.insert(id='123', status='published')
    sql, params = query.render()

    assert 'INSERT INTO articles' in sql
    assert params == ['123', 'published']


def test_insert_without_metadata_ignores_defaults():
    """Test that defaults are only applied when metadata is present"""
    class SimpleTable(Table, table_name='simple'):
        id: Column
        name: Column

    query = SimpleTable.insert(id='1', name='test')
    sql, params = query.render()

    assert 'INSERT INTO simple' in sql
    assert params == ['1', 'test']


def test_update_with_onupdate_default():
    """Test that onupdate defaults are applied during UPDATE"""
    from sqlalchemy import MetaData, Column as SAColumn, String
    from datetime import datetime

    metadata = MetaData()

    class Articles(Table, table_name='articles', metadata=metadata):
        id = SAColumn(String, primary_key=True)
        title = SAColumn(String)
        updated_at = SAColumn(String, onupdate=lambda: 'updated_timestamp')

    query = Articles.update(title='Updated Title').where(Articles.id == '123')
    sql, params = query.render()

    assert 'UPDATE articles SET' in sql
    assert 'updated_at' in sql
    assert 'updated_timestamp' in params
    assert 'Updated Title' in params


def test_update_overrides_onupdate():
    """Test that user-provided values override onupdate defaults"""
    from sqlalchemy import MetaData, Column as SAColumn, String

    metadata = MetaData()

    class Articles(Table, table_name='articles', metadata=metadata):
        id = SAColumn(String, primary_key=True)
        title = SAColumn(String)
        updated_at = SAColumn(String, onupdate=lambda: 'auto_timestamp')

    query = Articles.update(title='Updated', updated_at='manual_timestamp').where(Articles.id == '123')
    sql, params = query.render()

    assert 'UPDATE articles SET' in sql
    assert 'manual_timestamp' in params
    assert 'auto_timestamp' not in params


def test_conflict_cols_validation():
    """Test that conflict_cols are validated for SQL injection"""
    import pytest

    # Test with malicious conflict column
    query = Users.insert(username='bob', email='bob@example.com')
    builder = query.on_conflict_do_nothing(conflict_on="id); DROP TABLE users; --")

    with pytest.raises(ValueError, match="Invalid conflict column name"):
        builder.render()

    # Test with valid conflict column (should work)
    query2 = Users.insert(username='bob', email='bob@example.com')
    builder2 = query2.on_conflict_do_nothing(conflict_on="id")
    sql, params = builder2.render()

    assert 'ON CONFLICT (id) DO NOTHING' in sql


def test_returning_cols_validation_insert():
    """Test that returning_cols in INSERT are validated"""
    import pytest

    # Test with malicious returning column
    query = Users.insert(username='bob', email='bob@example.com')
    builder = query.returning("id; DROP TABLE users CASCADE; --")

    with pytest.raises(ValueError, match="Invalid RETURNING column name"):
        builder.render()

    # Test with valid returning columns (should work)
    query2 = Users.insert(username='bob', email='bob@example.com')
    builder2 = query2.returning("id", "username")
    sql, params = builder2.render()

    assert 'RETURNING id, username' in sql

    # Test that RETURNING * works (special case)
    query3 = Users.insert(username='bob', email='bob@example.com')
    builder3 = query3.returning()  # Defaults to *
    sql3, params3 = builder3.render()

    assert 'RETURNING *' in sql3


def test_returning_cols_validation_update():
    """Test that returning_cols in UPDATE are validated"""
    import pytest

    # Test with malicious returning column
    query = Users.update(username='hacked')
    builder = query.returning("id, (SELECT password FROM admin_users LIMIT 1) AS stolen")

    with pytest.raises(ValueError, match="Invalid RETURNING column name"):
        builder.render()

    # Test with valid returning columns (should work)
    query2 = Users.update(username='updated')
    builder2 = query2.where(Users.id == 5).returning("id", "username")
    sql, params = builder2.render()

    assert 'RETURNING id, username' in sql


def test_returning_cols_validation_delete():
    """Test that returning_cols in DELETE are validated"""
    import pytest

    # Test with malicious returning column
    query = Users.delete()
    builder = query.returning("* FROM users; DROP TABLE secrets; --")

    with pytest.raises(ValueError, match="Invalid RETURNING column name"):
        builder.render()

    # Test with valid returning columns (should work)
    query2 = Users.delete()
    builder2 = query2.where(Users.id == 5).returning("id")
    sql, params = builder2.render()

    assert 'RETURNING id' in sql


def test_conflict_cols_list_validation():
    """Test that lists of conflict_cols are all validated"""
    import pytest

    # Test with one valid and one malicious column
    query = Users.insert(username='bob', email='bob@example.com')
    builder = query.on_conflict_update(conflict_on=["id", "email'); DROP TABLE users; --"])

    with pytest.raises(ValueError, match="Invalid conflict column name"):
        builder.render()

    # Test with all valid columns (should work)
    query2 = Users.insert(username='bob', email='bob@example.com')
    builder2 = query2.on_conflict_update(conflict_on=["id", "email"])
    sql, params = builder2.render()

    assert 'ON CONFLICT (id, email)' in sql
