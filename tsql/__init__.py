import re
import string
from typing import NamedTuple, Tuple, Any, Literal, Final, List, Dict
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
        print(self._sql_parts)
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

    @classmethod
    def _sqlize(cls, val: Interpolation|Template|Any) -> list[str|Parameter]:
        if isinstance(val, Interpolation):
            value = val.value
            formatter = string.Formatter()
            # first, run convert object if specified
            if val.conversion:
                value = formatter.convert_field(value, val.conversion)

            print('i', val.format_spec, value, type(value))
            match val.format_spec, value:
                case 'literal', str():
                    cls._check_literal(value)
                    return [value]
                case 'unsafe', str():
                    return [value]
                case 'as_values', dict():
                    return as_values(value)._sql_parts
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
                case _, int():
                    return [Parameter(val.value, val.value)]


            return [Parameter(val.expression, formatter.format_field(value, val.format_spec))]

        if isinstance(val, Template):
            print('t', val)
            result = []
            for item in val:
                if isinstance(item, Interpolation):
                    result.extend(cls._sqlize(item))
                else:
                    result.append(re.sub(r'\s+', ' ', item))
            return result

        raise ValueError(f"UNSAFE {val}") # this shouldnt happen and is for debugging


def as_values(value_dict: dict[str, Any]):
    return TSQL(t"{tuple([t"{k:literal}" for k in value_dict.keys()])}"
                  " VALUES "
                  t"{tuple([t"{i}" for i in value_dict.values()])}")


def render(query: Template|TSQL, style=None) -> RenderedQuery:
    if not isinstance(query, TSQL):
        query = TSQL(query)

    return query.render(style=style)


# def as_array(values: list[str]) -> TSQL:
#     return

