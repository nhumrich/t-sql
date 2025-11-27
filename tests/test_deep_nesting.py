"""Tests for deep template nesting, CTEs, subqueries, and complex query composition"""
import pytest
import tsql
from tsql import TSQL
from tsql.query_builder import Table, Column
from tsql import styles


class Users(Table):
    id: Column
    username: Column
    email: Column
    created_at: Column


class Posts(Table):
    id: Column
    user_id: Column
    title: Column
    content: Column


class Comments(Table):
    id: Column
    post_id: Column
    user_id: Column
    content: Column


def test_simple_subquery_in_where():
    """Test basic subquery nesting with t-strings"""
    min_id = 100
    subquery = t"SELECT MAX(id) FROM users WHERE id > {min_id}"
    query = t"SELECT * FROM posts WHERE user_id = ({subquery})"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert sql == "SELECT * FROM posts WHERE user_id = (SELECT MAX(id) FROM users WHERE id > ?)"
    assert params == [100]


def test_subquery_in_select():
    """Test subquery in SELECT clause"""
    user_id = 42
    subquery = t"SELECT COUNT(*) FROM posts WHERE user_id = {user_id}"
    query = t"SELECT username, ({subquery}) as post_count FROM users WHERE id = {user_id}"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "SELECT username, (SELECT COUNT(*) FROM posts WHERE user_id = ?) as post_count" in sql
    assert params == [42, 42]


def test_nested_subqueries_three_levels():
    """Test three levels of nested subqueries"""
    user_id = 123

    # Level 3: innermost query
    innermost = t"SELECT post_id FROM comments WHERE user_id = {user_id}"
    # Level 2: middle query
    middle = t"SELECT user_id FROM posts WHERE id IN ({innermost})"
    # Level 1: outer query
    outer = t"SELECT username FROM users WHERE id IN ({middle})"

    sql, params = tsql.render(outer, style=styles.QMARK)

    assert "SELECT username FROM users WHERE id IN (SELECT user_id FROM posts WHERE id IN (SELECT post_id FROM comments WHERE user_id = ?))" in sql
    assert params == [123]


def test_simple_cte():
    """Test basic CTE (Common Table Expression)"""
    min_posts = 5
    cte = t"WITH active_users AS (SELECT user_id, COUNT(*) as post_count FROM posts GROUP BY user_id HAVING COUNT(*) > {min_posts})"
    query = t"{cte} SELECT u.username FROM users u JOIN active_users au ON u.id = au.user_id"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WITH active_users AS" in sql
    assert "HAVING COUNT(*) > ?" in sql
    assert params == [5]


def test_multiple_ctes():
    """Test multiple CTEs chained together"""
    min_posts = 10
    min_comments = 5

    cte1 = t"active_posters AS (SELECT user_id FROM posts GROUP BY user_id HAVING COUNT(*) > {min_posts})"
    cte2 = t"active_commenters AS (SELECT user_id FROM comments GROUP BY user_id HAVING COUNT(*) > {min_comments})"
    query = t"WITH {cte1}, {cte2} SELECT DISTINCT u.username FROM users u JOIN active_posters ap ON u.id = ap.user_id JOIN active_commenters ac ON u.id = ac.user_id"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WITH active_posters AS" in sql
    assert "active_commenters AS" in sql
    assert params == [10, 5]


def test_cte_referencing_previous_cte():
    """Test CTE that references another CTE"""
    threshold = 100

    cte1 = t"popular_posts AS (SELECT id, user_id FROM posts WHERE id > {threshold})"
    cte2 = t"top_users AS (SELECT user_id, COUNT(*) as count FROM popular_posts GROUP BY user_id)"
    query = t"WITH {cte1}, {cte2} SELECT u.username, tu.count FROM users u JOIN top_users tu ON u.id = tu.user_id"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WITH popular_posts AS" in sql
    assert "top_users AS" in sql
    assert "FROM popular_posts" in sql
    assert params == [threshold]


def test_query_builder_in_subquery():
    """Test mixing query builder with t-string subquery"""
    user_id = 42

    # Use query builder for inner query
    subquery = Users.select(Users.id).where(Users.username == "admin")

    # Embed in t-string
    outer = t"SELECT * FROM posts WHERE user_id IN ({subquery})"

    sql, params = tsql.render(outer, style=styles.QMARK)

    assert "SELECT users.id FROM users WHERE users.username = ?" in sql
    assert "SELECT * FROM posts WHERE user_id IN" in sql
    assert params == ["admin"]


def test_tstring_in_query_builder_where():
    """Test t-string condition in query builder WHERE clause"""
    max_id = 1000
    username = "alice"

    # T-string condition
    condition = t"id < {max_id} OR username = {username}"

    query = Users.select().where(condition)
    sql, params = query.render(style=styles.QMARK)

    assert "WHERE (id < ? OR username = ?)" in sql
    assert params == [1000, "alice"]


def test_query_builder_with_subquery_builder():
    """Test query builder with another query builder as subquery"""
    # Inner query builder
    active_users = Users.select(Users.id).where(Users.created_at > "2024-01-01")

    # Outer query builder using inner as condition
    posts_query = Posts.select().where(t"user_id IN ({active_users})")

    sql, params = posts_query.render(style=styles.QMARK)

    # SELECT with no columns specified defaults to SELECT *
    assert "SELECT * FROM posts" in sql
    assert "WHERE (user_id IN (SELECT users.id FROM users WHERE users.created_at > ?))" in sql
    assert params == ["2024-01-01"]


def test_deeply_nested_mixed_composition():
    """Test complex nesting mixing query builders and t-strings"""
    # Level 4: query builder
    comment_authors = Users.select(Users.id).where(Users.username == "alice")

    # Level 3: t-string using query builder
    commented_posts = t"SELECT post_id FROM comments WHERE user_id IN ({comment_authors})"

    # Level 2: query builder using t-string
    posts_with_comments = Posts.select(Posts.user_id).where(t"id IN ({commented_posts})")

    # Level 1: final t-string query
    final_query = t"SELECT username FROM users WHERE id IN ({posts_with_comments})"

    sql, params = tsql.render(final_query, style=styles.QMARK)

    # Verify the nesting structure exists
    assert "SELECT username FROM users WHERE id IN" in sql
    assert "SELECT posts.user_id FROM posts WHERE (id IN" in sql
    assert "SELECT post_id FROM comments WHERE user_id IN" in sql
    assert "SELECT users.id FROM users WHERE users.username = ?" in sql
    assert params == ["alice"]


def test_cte_with_query_builder():
    """Test CTE containing a query builder"""
    # Build CTE content with query builder
    active_users_query = Users.select(Users.id, Users.username).where(Users.created_at > "2024-01-01")

    # Use in CTE
    query = t"WITH active_users AS ({active_users_query}) SELECT au.username, COUNT(p.id) FROM active_users au LEFT JOIN posts p ON au.id = p.user_id GROUP BY au.username"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WITH active_users AS (SELECT users.id, users.username FROM users WHERE users.created_at > ?)" in sql
    assert params == ["2024-01-01"]


def test_cte_chain_with_mixed_types():
    """Test chain of CTEs mixing query builders and t-strings"""
    # First CTE uses query builder
    cte1_query = Users.select(Users.id).where(Users.email != None)

    # Second CTE uses t-string and references first
    user_id = 100
    cte2 = t"post_counts AS (SELECT user_id, COUNT(*) as count FROM posts WHERE user_id > {user_id} GROUP BY user_id)"

    # Final query combines everything
    query = t"WITH verified_users AS ({cte1_query}), {cte2} SELECT vu.id, pc.count FROM verified_users vu JOIN post_counts pc ON vu.id = pc.user_id"

    sql, params = tsql.render(query, style=styles.QMARK)

    # != None is correctly converted to IS NOT NULL (no parameter)
    assert "WITH verified_users AS (SELECT users.id FROM users WHERE users.email IS NOT NULL)" in sql
    assert "post_counts AS (SELECT user_id, COUNT(*) as count FROM posts" in sql
    assert params == [100]


def test_correlated_subquery():
    """Test correlated subquery where inner query references outer query"""
    min_count = 5

    # Correlated subquery - note the reference to outer 'u' table
    query = t"""
        SELECT u.username
        FROM users u
        WHERE (
            SELECT COUNT(*)
            FROM posts p
            WHERE p.user_id = u.id
        ) > {min_count}
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "SELECT COUNT(*)" in sql
    assert "WHERE p.user_id = u.id" in sql
    assert ") > ?" in sql
    assert params == [5]


def test_union_with_nested_queries():
    """Test UNION with nested subqueries"""
    active_threshold = 100
    admin_role = "admin"

    query1 = t"SELECT id, username FROM users WHERE id > {active_threshold}"
    query2 = Users.select(Users.id, Users.username).where(Users.email == admin_role)

    union_query = t"{query1} UNION {query2}"

    sql, params = tsql.render(union_query, style=styles.QMARK)

    assert "SELECT id, username FROM users WHERE id > ?" in sql
    assert "UNION SELECT users.id, users.username FROM users WHERE users.email = ?" in sql
    assert params == [100, "admin"]


def test_exists_with_nested_query():
    """Test EXISTS clause with nested query"""
    user_id = 42

    subquery = Posts.select(Posts.id).where(Posts.user_id == user_id)
    query = t"SELECT username FROM users WHERE EXISTS ({subquery})"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WHERE EXISTS (SELECT posts.id FROM posts WHERE posts.user_id = ?)" in sql
    assert params == [42]


def test_window_function_with_subquery():
    """Test window function with subquery in partition"""
    min_id = 1000

    query = t"""
        SELECT
            username,
            ROW_NUMBER() OVER (
                PARTITION BY (
                    SELECT COUNT(*) FROM posts WHERE user_id = users.id AND id > {min_id}
                )
            ) as rank
        FROM users
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "ROW_NUMBER() OVER" in sql
    assert "PARTITION BY" in sql
    assert params == [1000]


def test_case_expression_with_subqueries():
    """Test CASE expression containing subqueries"""
    threshold = 10

    query = t"""
        SELECT
            username,
            CASE
                WHEN (SELECT COUNT(*) FROM posts WHERE user_id = users.id) > {threshold}
                    THEN 'active'
                ELSE 'inactive'
            END as status
        FROM users
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "CASE" in sql
    assert "WHEN (SELECT COUNT(*)" in sql
    assert "> ?" in sql
    assert "THEN 'active'" in sql
    assert params == [10]


def test_recursive_cte():
    """Test recursive CTE pattern"""
    start_id = 1

    query = t"""
        WITH RECURSIVE user_hierarchy AS (
            SELECT id, username, 0 as level
            FROM users
            WHERE id = {start_id}

            UNION ALL

            SELECT u.id, u.username, uh.level + 1
            FROM users u
            JOIN user_hierarchy uh ON u.id = uh.id + 1
            WHERE uh.level < 10
        )
        SELECT * FROM user_hierarchy
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "WITH RECURSIVE user_hierarchy AS" in sql
    assert "UNION ALL" in sql
    assert params == [1]


def test_five_level_nesting():
    """Stress test with five levels of nesting"""
    val1, val2, val3, val4, val5 = 1, 2, 3, 4, 5

    level5 = t"SELECT id FROM comments WHERE id > {val5}"
    level4 = t"SELECT post_id FROM comments WHERE id IN ({level5}) AND user_id > {val4}"
    level3 = t"SELECT user_id FROM posts WHERE id IN ({level4}) AND title LIKE {val3}"
    level2 = t"SELECT id FROM users WHERE id IN ({level3}) AND email IS NOT NULL AND id > {val2}"
    level1 = t"SELECT username FROM users WHERE id IN ({level2}) AND created_at IS NOT NULL AND id > {val1}"

    sql, params = tsql.render(level1, style=styles.QMARK)

    # Verify all values are captured (order is reversed due to depth-first processing)
    assert params == [5, 4, 3, 2, 1]

    # Verify nesting structure
    assert sql.count("SELECT") == 5
    assert sql.count("WHERE") == 5


def test_lateral_join_with_subquery():
    """Test LATERAL join (PostgreSQL) with subquery"""
    limit = 3

    query = t"""
        SELECT u.username, recent.title
        FROM users u
        LEFT JOIN LATERAL (
            SELECT title
            FROM posts
            WHERE user_id = u.id
            ORDER BY id DESC
            LIMIT {limit}
        ) recent ON true
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "LEFT JOIN LATERAL" in sql
    assert "LIMIT ?" in sql
    assert params == [3]


def test_values_clause_with_nested_select():
    """Test VALUES clause combined with nested SELECT"""
    user_id = 42

    subquery = t"SELECT MAX(id) FROM posts WHERE user_id = {user_id}"
    query = t"""
        INSERT INTO posts (user_id, title)
        SELECT * FROM (
            VALUES (({subquery}), 'New Post')
        ) AS v(user_id, title)
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "VALUES ((SELECT MAX(id) FROM posts WHERE user_id = ?), 'New Post')" in sql
    assert params == [42]


def test_multiple_independent_subqueries():
    """Test query with multiple independent subqueries at same level"""
    threshold1 = 100
    threshold2 = 50
    date = "2024-01-01"

    subquery1 = t"SELECT COUNT(*) FROM posts WHERE user_id = users.id AND id > {threshold1}"
    subquery2 = t"SELECT COUNT(*) FROM comments WHERE user_id = users.id AND id > {threshold2}"

    query = t"""
        SELECT
            username,
            ({subquery1}) as post_count,
            ({subquery2}) as comment_count
        FROM users
        WHERE created_at > {date}
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert sql.count("SELECT COUNT(*)") == 2
    assert params == [100, 50, "2024-01-01"]


def test_array_agg_with_subquery():
    """Test aggregate function with subquery (PostgreSQL syntax)"""
    user_id = 42

    query = t"""
        SELECT
            username,
            ARRAY_AGG((SELECT title FROM posts WHERE id = p.post_id)) as post_titles
        FROM users u
        JOIN posts p ON u.id = p.user_id
        WHERE u.id = {user_id}
        GROUP BY username
    """

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "ARRAY_AGG((SELECT title FROM posts WHERE id = p.post_id))" in sql
    assert params == [42]


def test_with_literal_identifiers_in_nested_queries():
    """Test that :literal format spec works correctly in nested contexts"""
    table_name = "users"
    column_name = "username"
    value = "alice"

    subquery = t"SELECT id FROM {table_name:literal} WHERE {column_name:literal} = {value}"
    query = t"SELECT * FROM posts WHERE user_id IN ({subquery})"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "SELECT id FROM users WHERE username = ?" in sql
    assert params == [value]


def test_complex_real_world_analytics_query():
    """Test realistic complex analytics query with multiple CTEs and nesting"""
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    min_engagement = 10

    # CTE 1: Active users
    active_users = Users.select(Users.id, Users.username).where(Users.created_at >= start_date)

    # CTE 2: Engagement metrics (t-string)
    engagement_cte = t"""
        engagement AS (
            SELECT
                user_id,
                COUNT(DISTINCT post_id) as posts_commented,
                COUNT(*) as total_comments
            FROM comments
            WHERE user_id IN (SELECT id FROM active_users)
            GROUP BY user_id
            HAVING COUNT(*) > {min_engagement}
        )
    """

    # CTE 3: Post stats (mixed)
    post_count_subquery = t"SELECT user_id, COUNT(*) as post_count FROM posts WHERE user_id IN (SELECT id FROM active_users) GROUP BY user_id"

    # Final query
    final = t"""
        WITH active_users AS ({active_users}),
        {engagement_cte},
        post_stats AS ({post_count_subquery})

        SELECT
            au.username,
            COALESCE(ps.post_count, 0) as posts,
            COALESCE(e.total_comments, 0) as comments,
            COALESCE(e.posts_commented, 0) as posts_with_comments
        FROM active_users au
        LEFT JOIN post_stats ps ON au.id = ps.user_id
        LEFT JOIN engagement e ON au.id = e.user_id
        ORDER BY posts DESC, comments DESC
    """

    sql, params = tsql.render(final, style=styles.QMARK)

    # Verify structure
    assert "WITH active_users AS" in sql
    assert "engagement AS" in sql
    assert "post_stats AS" in sql
    assert params == [start_date, min_engagement]

    # Verify all CTEs are present and properly nested
    assert sql.count("SELECT") >= 4  # Multiple selects across CTEs


def test_json_operations_with_subquery():
    """Test JSON operations (PostgreSQL) with nested queries"""
    user_id = 42
    key = "metadata"

    subquery = t"SELECT email FROM users WHERE id = {user_id}"
    query = t"SELECT data->>'{key:literal}' as metadata FROM posts WHERE user_id = ({subquery})"

    sql, params = tsql.render(query, style=styles.QMARK)

    assert "data->>'metadata'" in sql
    assert "WHERE user_id = (SELECT email FROM users WHERE id = ?)" in sql
    assert params == [42]
