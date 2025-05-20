from tsql.styles import QMARK


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

