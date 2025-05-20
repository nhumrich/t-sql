import abc
from typing import Any, Tuple
from itertools import count


class ParamStyle(abc.ABC):
    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError()

class QMARK(ParamStyle):
    # WHERE name=?
    def __init__(self):
        self.params = []

    def __iter__(self):
        values = []
        _, value = yield
        while True:
            self.params.append(value)
            _, value = yield '?'


class NUMERIC(ParamStyle):
    # WHERE name=:1
    def __iter__(self):
        for i in count():
            expression, value= yield


class NAMED(ParamStyle):
    # WHERE name=:name
    pass

class FORMAT(ParamStyle):
    # WHERE name=%s
    pass

class PYFORMAT(FORMAT):
    # WHERE name=$(name)s
    pass

class NUMERIC_DOLLAR(ParamStyle):
    # WHERE name=$1
    pass

class ESCAPED(ParamStyle):
    # WHERE name='value'
    def __init__(self):
        self.params = []

    def __iter__(self):
        _, value = yield
        while True:
            _, value = yield self._escape_value(value)

    def _escape_value(self, value):
        match value:
            case str():
                return f"'{value.replace("'", "''")}'"
            case None:
                return "NULL"

    def escape(self):
        return