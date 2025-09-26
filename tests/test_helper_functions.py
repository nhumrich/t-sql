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
    values = {
        'name': 'Alice',
        'age': 25,
        'active': True
    }
    
    query = tsql.insert('users', values)
    result = tsql.render(query)
    
    assert "INSERT INTO users" in result[0]
    assert "name" in result[0] and "age" in result[0] and "active" in result[0]
    assert "VALUES" in result[0]
    assert 'Alice' in result[1]
    assert 25 in result[1]
    assert True in result[1]


def test_update():
    values = {
        'name': 'Bob Updated',
        'age': 35
    }
    
    query = tsql.update('users', values, 123)
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