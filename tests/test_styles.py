from tsql.styles import QMARK, NUMERIC, NAMED, FORMAT, PYFORMAT, NUMERIC_DOLLAR, ESCAPED


def test_qmark_style():
    q = QMARK()
    i = iter(q)
    next(i)
    val1 = i.send(('1', 'a'))
    val2 = i.send(('2', 'b'))
    val3 = i.send(('3', 'c'))

    assert val1 == '?'
    assert val2 == '?'
    assert val3 == '?'
    assert q.params == ['a', 'b', 'c']


def test_numeric_style():
    q = NUMERIC()
    i = iter(q)
    next(i)
    val1 = i.send(('1', 'a'))
    val2 = i.send(('2', 'b'))
    val3 = i.send(('3', 'c'))

    assert val1 == ':1'
    assert val2 == ':2'
    assert val3 == ':3'
    assert q.params == ['a', 'b', 'c']


def test_named_style():
    q = NAMED()
    i = iter(q)
    next(i)
    val1 = i.send(('name', 'a'))
    val2 = i.send(('foo', 'b'))
    val3 = i.send(('bar', 'c'))

    assert val1 == ':name'
    assert val2 == ':foo'
    assert val3 == ':bar'
    assert q.params == {'name': 'a', 'foo': 'b', 'bar': 'c'}


def test_format_style():
    q = FORMAT()
    i = iter(q)
    next(i)
    val1 = i.send(('name', 'a'))
    val2 = i.send(('foo', 'b'))
    val3 = i.send(('bar', 'c'))

    assert val1 == '%s'
    assert val2 == '%s'
    assert val3 == '%s'
    assert q.params == ['a', 'b', 'c']


def test_pyformat_style():
    q = PYFORMAT()
    i = iter(q)
    next(i)
    val1 = i.send(('name', 'a'))
    val2 = i.send(('foo', 'b'))
    val3 = i.send(('bar', 'c'))

    assert val1 == '%(name)s'
    assert val2 == '%(foo)s'
    assert val3 == '%(bar)s'
    assert q.params == {'name': 'a', 'foo': 'b', 'bar': 'c'}


def test_numeric_dollar_style():
    q = NUMERIC_DOLLAR()
    i = iter(q)
    next(i)
    val1 = i.send(('name', 'a'))
    val2 = i.send(('foo', 'b'))
    val3 = i.send(('bar', 'c'))

    assert val1 == '$1'
    assert val2 == '$2'
    assert val3 == '$3'
    assert q.params == ['a', 'b', 'c']


def test_escaped_style():
    q = ESCAPED()
    i = iter(q)
    next(i)
    val1 = i.send(('name', 'test\'value'))
    val2 = i.send(('foo', None))
    val3 = i.send(('bar', 42))
    val4 = i.send(('active', True))
    val5 = i.send(('disabled', False))

    assert val1 == "'test''value'"
    assert val2 == 'NULL'
    assert val3 == '42'
    assert val4 == 'TRUE'
    assert val5 == 'FALSE'
    assert q.params == []


def test_named_style_with_integer_values():
    """Test that NAMED style uses parameter name (not value) for integers"""
    from tsql import render
    from string.templatelib import Template as t

    age = 25
    result = render(t'SELECT * FROM users WHERE age = {age}', style=NAMED)

    assert result.sql == 'SELECT * FROM users WHERE age = :age'
    assert result.values == {'age': 25}


def test_pyformat_style_with_integer_values():
    """Test that PYFORMAT style uses parameter name (not value) for integers"""
    from tsql import render
    from string.templatelib import Template as t

    age = 25
    result = render(t'SELECT * FROM users WHERE age = {age}', style=PYFORMAT)

    assert result.sql == 'SELECT * FROM users WHERE age = %(age)s'
    assert result.values == {'age': 25}

