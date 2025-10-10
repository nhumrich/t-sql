import re
import string
from typing import NamedTuple, Tuple, Any, List, Dict, Iterable
from string.templatelib import Template, Interpolation

from tsql.styles import ParamStyle, QMARK

default_style = QMARK

def set_style(style: type[ParamStyle]):
    global default_style
    default_style = style


class Parameter:
    _expression: str
    _value: Any

    def __init__(self, expression: str, value: Any):
        self._value = value
        self._expression = expression

    @property
    def value(self):
        return self._value

    """ Used as a placeholder for parameters. """
    def __str__(self):
        return "$?"

    def __repr__(self):
        return f"Parameter('{self._expression}', {self._value!r})"


class RenderedQuery(NamedTuple):
    sql: str
    values: Tuple[str, ...]|List[str]|Dict[str, Any]


class TSQL:
    _sql_parts: list[str|Parameter]

    def __init__(self, template_string: Template):
        self._sql_parts = self._sqlize(template_string)

    def render(self, style:ParamStyle = None) -> RenderedQuery:
        if style is None:
            style = default_style
        result = ''
        if style is None:
            style = default_style

        style_instance = style()
        iterator = iter(style_instance)
        next(iterator)
        for i, part in enumerate(self._sql_parts):
            if isinstance(part, Parameter):
                 result += iterator.send((part._expression, part._value))
            else:
                result += part

        return RenderedQuery(result, style_instance.params)


    @property
    def _sql(self) -> str:
        return ''.join(map(str, self._sql_parts))

    @property
    def _values(self) -> list[str]:
        return [v.value for v in self._sql_parts if isinstance(v, Parameter)]

    @classmethod
    def _check_literal(cls, val: str):
        if not isinstance(val, str) or not val.isidentifier():
            raise ValueError(f"Invalid literal {val}")
        return val

    @classmethod
    def _sqlize(cls, val: Interpolation|Template|Any) -> list[str|Parameter]:
        if isinstance(val, Interpolation):
            value = val.value
            formatter = string.Formatter()
            # first, run convert object if specified
            if val.conversion:
                value = formatter.convert_field(value, val.conversion)

            match val.format_spec, value:
                case 'literal', str():
                    cls._check_literal(value)
                    return [value]
                case 'unsafe', str():
                    return [value]
                case 'as_values', dict():
                    return as_values(value)._sql_parts
                case 'as_set', dict():
                    return as_set(value)._sql_parts
                case '', TSQL():
                    return val.value._sql_parts
                case "", Template():
                    return TSQL(value)._sql_parts
                case '', None:
                    return [Parameter(val.expression, None)]
                # case 'as_array', list():
                #     return [None]
                case _, tuple():
                    inner: list[str|Parameter] = ['(']
                    for i, v in enumerate(value):
                        if i > 0:
                            inner.append(',')
                        inner.append(Parameter(val.expression + f'_{i}', v))
                    inner.append(')')
                    return inner
                case _, str():
                    return [Parameter(val.expression, formatter.format_field(value, val.format_spec))]
                case _, bytes():
                    return [Parameter(val.expression, value)]
                case _, int():
                    return [Parameter(val.value, val.value)]


            return [Parameter(val.expression, formatter.format_field(value, val.format_spec))]

        if isinstance(val, Template):
            result = []
            for item in val:
                if isinstance(item, Interpolation):
                    result.extend(cls._sqlize(item))
                else:
                    result.append(re.sub(r'\s+', ' ', item))
            return result

        raise ValueError(f"UNSAFE {val}") # this shouldnt happen and is for debugging


def t_join(part: Template, collection: Iterable[Template|TSQL]):
    final = t''
    for i, section in enumerate(collection):
        if i == 0:
            final = section
        else:
            final += part + section
    return final



def as_values(value_dict: dict[str, Any]):
    """Convert a dictionary to SQL column list and VALUES clause"""
    keys = list(value_dict.keys())
    values = list(value_dict.values())

    # Build column list: (col1, col2, col3)
    column_parts = ['(']
    for i, key in enumerate(keys):
        if i > 0:
            column_parts.append(', ')
        column_parts.append(key)
    column_parts.append(')')

    # Build values list: (?, ?, ?)
    value_parts = [' VALUES (']
    for i, value in enumerate(values):
        if i > 0:
            value_parts.append(', ')
        value_parts.append(Parameter(f'value_{i}', value))
    value_parts.append(')')

    # Create TSQL object manually
    tsql_obj = TSQL.__new__(TSQL)
    tsql_obj._sql_parts = column_parts + value_parts
    return tsql_obj


def as_set(value_dict: dict[str, Any]):
    """Convert a dictionary to SQL SET clause for UPDATE statements"""
    keys = list(value_dict.keys())
    values = list(value_dict.values())

    # Build SET clause: col1 = ?, col2 = ?, col3 = ?
    set_parts = []
    for i, (key, value) in enumerate(zip(keys, values)):
        if i > 0:
            set_parts.append(', ')
        set_parts.append(key)
        set_parts.append(' = ')
        set_parts.append(Parameter(f'value_{i}', value))

    # Create TSQL object manually
    tsql_obj = TSQL.__new__(TSQL)
    tsql_obj._sql_parts = set_parts
    return tsql_obj


def render(query: Template|TSQL, style=None) -> RenderedQuery:
    if not isinstance(query, TSQL):
        query = TSQL(query)

    return query.render(style=style)


def select(table, ids:str|int|list[str|int]=None, *, columns=None):
    """Helper function to build basic SELECT queries"""

    if not columns:
        t_columns = t'*'
    else:
        t_columns = t_join(t', ', [t'{c:literal}' for c in columns])

    where_clause = t""
    if ids is not None:
        match ids:
            case list():
                where_clause = t" WHERE id in {tuple(ids)}"
            case tuple():
                where_clause = t" WHERE id in {ids}"
            case int():
                where_clause = t" WHERE id = {ids}"
            case str():
                where_clause = t" WHERE id = {ids}"

    return TSQL(t'SELECT {t_columns} FROM {table:literal}{where_clause}')


def insert(table: str, values: dict[str, Any], ignore_conflict=False):
    """Helper function to build INSERT queries"""

    if not isinstance(values, dict):
        raise TypeError("values must be a dict")

    conflict_clause = t""
    if ignore_conflict:
        conflict_clause = t" ON CONFLICT DO NOTHING"

    return TSQL(t"INSERT INTO {table:literal} {values:as_values}{conflict_clause} RETURNING *")


def update(table: str, values: dict[str, Any], id: str):
    """Helper function to build UPDATE queries for a single row"""

    if not isinstance(values, dict):
        raise ValueError("values must be a dictionary")
    
    return TSQL(t"UPDATE {table:literal} SET {values:as_set} WHERE id = {id} RETURNING *")

