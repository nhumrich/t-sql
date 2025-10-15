import abc
import re
from itertools import count


class ParamStyle(abc.ABC):
    def __init__(self):
        self.params = []

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError()

    def _init_dict_params(self):
        """Initialize params as dict for named parameter styles."""
        self.params = {}

    @staticmethod
    def _sanitize_param_name(name: str, used_names: set) -> str:
        """Sanitize parameter name to be a valid SQL identifier.

        Preserves readable names when possible, sanitizes complex expressions.
        Handles collisions by appending numbers.
        """
        if name.isidentifier() and name not in used_names:
            return name

        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)

        if not sanitized or not (sanitized[0].isalpha() or sanitized[0] == '_'):
            sanitized = 'param_' + sanitized if sanitized else 'param'

        if sanitized in used_names:
            counter = 1
            while f"{sanitized}_{counter}" in used_names:
                counter += 1
            sanitized = f"{sanitized}_{counter}"

        return sanitized

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
    def __init__(self):
        super().__init__()
        self._init_dict_params()

    def __iter__(self):
        name, value = yield
        used_names = set()
        while True:
            param_name = self._sanitize_param_name(name, used_names)
            used_names.add(param_name)
            self.params[param_name] = value
            name, value = yield f':{param_name}'


class FORMAT(ParamStyle):
    # WHERE name=%s
    def __iter__(self):
        _, value = yield
        while True:
            self.params.append(value)
            _, value = yield '%s'


class PYFORMAT(FORMAT):
    # WHERE name=%(name)s
    def __init__(self):
        super().__init__()
        self._init_dict_params()

    def __iter__(self):
        name, value = yield
        used_names = set()
        while True:
            param_name = self._sanitize_param_name(name, used_names)
            used_names.add(param_name)
            self.params[param_name] = value
            name, value = yield f'%({param_name})s'


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