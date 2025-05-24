import tsql

def test_merge():
    pass


def test_as_values():
    values = {
        'a': 1,
        'b': 'abc'
    }
    result = tsql.render(t"INSERT INTO test {values:as_values}")
    assert result[0] == "INSERT INTO test (?,?) VALUES (?,?)"


def test_insert():
    pass


def test_update():
    pass


def test_update_many():
    pass


def test_as_setters():
    pass


def test_select():
    pass