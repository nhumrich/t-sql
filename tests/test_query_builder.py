import tsql
from tsql.query_builder import table, Column, Condition


@table('users')
class Users:
    id: int
    username: str
    email: str
    created_at: str


@table('posts')
class Posts:
    id: int
    user_id: int
    title: str
    body: str


@table('comments')
class Comments:
    id: int
    post_id: int
    user_id: int
    content: str


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
    @table('users', schema='public')
    class SchemaUsers:
        id: int

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
