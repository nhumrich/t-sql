import tsql


def test_t_join():
    """Test joining multiple t-string parts together"""
    part1 = t"SELECT *"
    part2 = t"FROM users"
    part3 = t"WHERE active = {True}"
    
    result = tsql.t_join(t' ', [part1, part2, part3])
    rendered = tsql.render(result)

    assert rendered[0] == "SELECT * FROM users WHERE active = ?"
    assert rendered[1] == [True]


def test_as_values():
    """Test the as_values format specifier"""
    values = {
        'name': 'John',
        'age': 30
    }
    result = tsql.render(t"INSERT INTO users {values:as_values}")

    # Should generate INSERT INTO users (name, age) VALUES (?, ?)
    assert "INSERT INTO users" in result[0]
    assert "name" in result[0] and "age" in result[0]
    assert "VALUES" in result[0]
    assert result[1] == ['John', 30]


def test_as_set():
    """Test the as_set format specifier"""
    values = {
        'name': 'John Updated',
        'age': 35
    }
    result = tsql.render(t"UPDATE users SET {values:as_set} WHERE id = {123}")

    # Should generate UPDATE users SET name = ?, age = ? WHERE id = ?
    assert "UPDATE users SET" in result[0]
    assert "name = ?" in result[0]
    assert "age = ?" in result[0]
    assert "WHERE id = ?" in result[0]
    assert result[1] == ['John Updated', 35, 123]


def test_insert():
    """Test the insert helper function"""
    query = tsql.insert('users', name='Alice', age=25, active=True)
    result = tsql.render(query)

    assert "INSERT INTO users" in result[0]
    assert "name" in result[0] and "age" in result[0] and "active" in result[0]
    assert "VALUES" in result[0]
    assert 'Alice' in result[1]
    assert 25 in result[1]
    assert True in result[1]


def test_update():
    query = tsql.update('users', 123, name='Bob Updated', age=35)
    result = tsql.render(query)

    assert "UPDATE users SET" in result[0]
    assert "name = ?" in result[0]
    assert "age = ?" in result[0]
    assert "WHERE id = ?" in result[0]
    assert result[1] == ['Bob Updated', 35, 123]


def test_select_star():
    """Test the select function uses a * when no columns passed in"""
    # Test simple select all
    query1 = tsql.select('users')
    result1 = tsql.render(query1)
    assert result1[0] == "SELECT * FROM users"
    assert result1[1] == []

def test_select_with_columns():
    query2 = tsql.select('users', columns=['name', 'age'])
    result2 = tsql.render(query2)
    assert "SELECT name, age FROM users" == result2[0]


def test_select_with_ids():
    query2 = tsql.select('users', ids=['1', '2'])
    result2 = tsql.render(query2)
    assert "SELECT * FROM users WHERE id in (?,?)" == result2[0]
    assert result2[1] == ['1', '2']

def test_select_complex():
    """Test select with multiple clauses"""
    min_age = 18
    status = 'active'

    query = tsql.select(
        'users', columns=[
        'name', 'email'],
        ids=['a', 'b']
    )

    result = tsql.render(query)

    assert "SELECT name, email FROM users" in result[0]
    assert "WHERE id in (?,?)" in result[0]
    assert result[1] == ['a', 'b']


def test_select_string_id_injection():
    """Test that select() with malicious string id is properly parameterized"""
    malicious_id = "1 OR 1=1"

    result = tsql.select('users', malicious_id)
    query, params = result.render()

    # Should be parameterized, not directly embedded
    assert "1 OR 1=1" not in query
    assert "?" in query
    assert params == [malicious_id]


def test_select_tuple_id_injection():
    """Test that select() with malicious tuple is properly parameterized"""
    malicious_tuple = ("1", "2'; DROP TABLE users; --")

    result = tsql.select('users', malicious_tuple)
    query, params = result.render()

    # Should be parameterized, not directly embedded
    assert "DROP TABLE users" not in query
    assert "?" in query
    assert malicious_tuple[1] in params


def test_select_int_id_safe():
    """Test that select() with int id works correctly"""
    result = tsql.select('users', 42)
    query, params = result.render()

    # Int should be parameterized
    assert "?" in query
    assert params == [42]


def test_delete():
    """Test the delete helper function"""
    query = tsql.delete('users', 123)
    result = tsql.render(query)

    assert "DELETE FROM users" in result[0]
    assert "WHERE id = ?" in result[0]
    assert result[1] == [123]


def test_delete_string_id():
    """Test delete with string ID"""
    query = tsql.delete('users', 'abc-123')
    result = tsql.render(query)

    assert "DELETE FROM users" in result[0]
    assert "WHERE id = ?" in result[0]
    assert result[1] == ['abc-123']