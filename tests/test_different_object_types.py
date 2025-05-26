import tsql
import tsql.styles


def test_none_stays_a_none_when_parameterized():
    val = None
    id_ = 'something'
    result = tsql.render(t"UPDATE users SET name = {val} WHERE id = {id_}")
    assert result[0] == "UPDATE users SET name = ? WHERE id = ?"
    assert result[1] == [None, 'something']


def test_converts_none_to_null_when_escaped():
    val = None
    id_ = 'something'
    result = tsql.render(t"UPDATE users SET name = {val} WHERE id = {id_}", style=tsql.styles.ESCAPED)
    assert result[0] == "UPDATE users SET name = NULL WHERE id = 'something'"
    assert result[1] == []