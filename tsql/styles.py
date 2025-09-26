import abc
from itertools import count


class ParamStyle(abc.ABC):
    def __init__(self):
        self.params = []

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError()

class QMARK(ParamStyle):
    # WHERE name=?
    def __iter__(self):
        _, value = yield
        while True:
            self.params.append(value)
            _, value = yield '?'


class NUMERIC(ParamStyle):
    # WHERE name=:1
    def __iter__(self):
        _, value = yield
        counter = count()
        next(counter) # we want to start at 1, so we burn 0 here
        while c := next(counter):
            self.params.append(value)
            _, value = yield f':{c}'


class NAMED(ParamStyle):
    # WHERE name=:name
    def __iter__(self):
        name, value = yield
        while True:
            self.params.append(value)
            name, value = yield f':{name}'


class FORMAT(ParamStyle):
    # WHERE name=%s
    def __iter__(self):
        _, value = yield
        while True:
            self.params.append(value)
            _, value = yield '%s'


class PYFORMAT(FORMAT):
    # WHERE name=%(name)s
    def __iter__(self):
        name, value = yield
        while True:
            self.params.append(value)
            name, value = yield f'%({name})s'


class NUMERIC_DOLLAR(ParamStyle):
    # WHERE name=$1
    def __iter__(self):
        _, value = yield
        counter = count()
        next(counter)  # we want to start at 1, so we burn 0 here
        while c := next(counter):
            self.params.append(value)
            _, value = yield f'${c}'


class ESCAPED(ParamStyle):
    # WHERE name='value'
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
            case bool():
                return "TRUE" if value else "FALSE"
            case int() | float():
                return str(value)
            case bytes():
                # Convert binary data to hex literal - safe from injection since hex only contains [0-9A-F]
                hex_data = value.hex()
                return f"'\\x{hex_data}'"
            case _:
                # For other types, convert to string and escape
                return f"'{str(value).replace("'", "''")}'"