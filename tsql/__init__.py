import re
import string
import datetime
import logging
from typing import NamedTuple, Tuple, Any, List, Dict, Iterable, Union, TYPE_CHECKING
from string.templatelib import Template, Interpolation

from tsql.styles import ParamStyle, QMARK

logger = logging.getLogger(__name__)

# Pre-compile regex for whitespace collapsing to avoid cache lookup overhead
_WHITESPACE_RE = re.compile(r'\s+')

if TYPE_CHECKING:
    from tsql.query_builder import QueryBuilder

default_style = QMARK

def set_style(style: type[ParamStyle]):
    global default_style
    logger.debug("Setting default parameter style to: %s", style.__name__)
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
        logger.debug("Rendering query with style: %s", style.__name__)
        result = ''

        style_instance = style()
        iterator = iter(style_instance)
        next(iterator)
        for i, part in enumerate(self._sql_parts):
            if isinstance(part, Parameter):
                 result += iterator.send((part._expression, part._value))
            else:
                result += part

        logger.debug("Rendered SQL: %s", result)
        logger.debug("Parameters (%d): %s", len(style_instance.params), style_instance.params)
        return RenderedQuery(result, style_instance.params)


    @property
    def _sql(self) -> str:
        return ''.join(map(str, self._sql_parts))

    @property
    def _values(self) -> list[str]:
        return [v.value for v in self._sql_parts if isinstance(v, Parameter)]

    @classmethod
    def _check_literal(cls, val: str):
        if not isinstance(val, str):
            raise ValueError(
                f"Invalid literal {val!r}: literals must be strings, got {type(val).__name__}. "
                f"Use {{value}} without :literal to parameterize non-string values."
            )

        # Allow qualified identifiers (table.column, schema.table.column)
        parts = val.split('.')

        if len(parts) > 3:
            raise ValueError(
                f"Invalid literal {val!r}: too many parts (expected at most 3 for schema.table.column, got {len(parts)}). "
                f"Parts: {', '.join(repr(p) for p in parts)}"
            )

        # Check for empty string or empty parts
        if not val or any(not p for p in parts):
            raise ValueError(
                f"Invalid literal {val!r}: empty string is not a valid identifier. "
                f"Literals must be valid Python identifiers (e.g., 'users', 'public.users', 'schema.table.column')."
            )

        invalid_parts = [p for p in parts if not p.isidentifier()]
        if invalid_parts:
            raise ValueError(
                f"Invalid literal {val!r}: contains invalid identifier(s): {', '.join(repr(p) for p in invalid_parts)}. "
                f"Each part must be a valid Python identifier (letters, digits, underscores; cannot start with digit). "
                f"If you need special characters or SQL keywords, consider using {{value:unsafe}} with caution."
            )
        return val

    @classmethod
    def _sqlize(cls, val: Interpolation|Template|Any) -> list[str|Parameter]:
        if isinstance(val, Interpolation):
            value = val.value
            formatter = string.Formatter()
            # first, run convert object if specified
            if val.conversion:
                value = formatter.convert_field(value, val.conversion)

            logger.debug("Processing interpolation: expression=%r, format_spec=%r, value_type=%s",
                        val.expression, val.format_spec, type(value).__name__)

            match val.format_spec, value:
                case 'literal', str():
                    logger.debug("Validating literal: %r", value)
                    cls._check_literal(value)
                    logger.debug("Literal validated, inlining: %r", value)
                    return [value]
                case 'unsafe', str():
                    logger.debug("Using unsafe inline value: %r", value)
                    return [value]
                case 'as_values', dict():
                    return as_values(value)._sql_parts
                case 'as_set', dict():
                    return as_set(value)._sql_parts
                case '', TSQL():
                    return val.value._sql_parts
                case "", Template():
                    return TSQL(value)._sql_parts
                case '', x if hasattr(x, 'to_tsql'):
                    logger.debug("Inlining QueryBuilder object: %s", type(x).__name__)
                    return x.to_tsql()._sql_parts
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
                    return [Parameter(val.expression, val.value)]
                case '', datetime.datetime() | datetime.date() | datetime.time() | datetime.timedelta():
                    return [Parameter(val.expression, value)]
                case _, _:
                    return [Parameter(val.expression, formatter.format_field(value, val.format_spec))]

        if isinstance(val, Template):
            result = []
            for item in val:
                if isinstance(item, Interpolation):
                    result.extend(cls._sqlize(item))
                else:
                    result.append(_WHITESPACE_RE.sub(' ', item))
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
    if not value_dict:
        raise ValueError("as_values requires at least one column-value pair")

    keys = list(value_dict.keys())
    values = list(value_dict.values())

    # Validate all keys are valid identifiers
    for key in keys:
        if not isinstance(key, str) or not key.isidentifier():
            raise ValueError(f"Invalid column name: {key!r}")

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

        # Handle special types that should be inlined as SQL
        if isinstance(value, Template):
            # Inline the Template by processing it through _sqlize
            value_parts.extend(TSQL._sqlize(value))
        elif isinstance(value, TSQL):
            # Inline the TSQL object's parts directly
            value_parts.extend(value._sql_parts)
        elif hasattr(value, 'to_tsql'):
            # Handle QueryBuilder objects
            value_parts.extend(value.to_tsql()._sql_parts)
        else:
            # Normal value - create Parameter
            value_parts.append(Parameter(f'value_{i}', value))
    value_parts.append(')')

    # Create TSQL object manually
    tsql_obj = TSQL.__new__(TSQL)
    tsql_obj._sql_parts = column_parts + value_parts
    return tsql_obj


def as_set(value_dict: dict[str, Any]):
    """Convert a dictionary to SQL SET clause for UPDATE statements"""
    if not value_dict:
        raise ValueError("as_set requires at least one column-value pair")

    keys = list(value_dict.keys())
    values = list(value_dict.values())

    # Validate all keys are valid identifiers
    for key in keys:
        if not isinstance(key, str) or not key.isidentifier():
            raise ValueError(f"Invalid column name: {key!r}")

    # Build SET clause: col1 = ?, col2 = ?, col3 = ?
    set_parts = []
    for i, (key, value) in enumerate(zip(keys, values)):
        if i > 0:
            set_parts.append(', ')
        set_parts.append(key)
        set_parts.append(' = ')

        # Handle special types that should be inlined as SQL
        if isinstance(value, Template):
            # Inline the Template by processing it through _sqlize
            set_parts.extend(TSQL._sqlize(value))
        elif isinstance(value, TSQL):
            # Inline the TSQL object's parts directly
            set_parts.extend(value._sql_parts)
        elif hasattr(value, 'to_tsql'):
            # Handle QueryBuilder objects
            set_parts.extend(value.to_tsql()._sql_parts)
        else:
            # Normal value - create Parameter
            set_parts.append(Parameter(f'value_{i}', value))

    # Create TSQL object manually
    tsql_obj = TSQL.__new__(TSQL)
    tsql_obj._sql_parts = set_parts
    return tsql_obj


# Type alias for safe, parameterized queries
TSQLQuery = Union[TSQL, Template, 'QueryBuilder']
"""Type alias representing safe, parameterized SQL queries.

This type includes all valid ways to construct safe queries in tsql:
- TSQL: Rendered t-string queries
- Template: Raw t-string templates (PEP 750)
- QueryBuilder: Type-safe query builder objects

Use this type to ensure functions only accept safe, parameterized queries
and never raw strings that could be vulnerable to SQL injection.

Examples:
    Accept any safe query type::

        def execute_query(query: TSQLQuery) -> None:
            sql, params = render(query)
            cursor.execute(sql, params)

    Type checking prevents unsafe usage::

        execute_query(t"SELECT * FROM users WHERE id = {user_id}")  # OK
        execute_query(select("users"))  # OK
        execute_query(User.select().where(User.id == 1))  # OK
        execute_query("SELECT * FROM users")  # Type error!
"""


def render(query: TSQLQuery, style=None) -> RenderedQuery:
    """Render a safe query to SQL and parameters.

    Args:
        query: A TSQLQuery (TSQL, Template, or QueryBuilder)
        style: Optional parameter style (defaults to global default_style)

    Returns:
        RenderedQuery with sql string and parameter values

    Raises:
        TypeError: If query is a raw string (use t-strings instead)
    """
    # Handle QueryBuilder (duck typing to avoid circular import)
    if hasattr(query, 'to_tsql') and callable(query.to_tsql):
        query = query.to_tsql()

    if isinstance(query, str):
        raise TypeError(
            "Cannot render raw strings - they are vulnerable to SQL injection. "
            "Use t-strings instead: t'SELECT * FROM users WHERE id = {user_id}'"
        )

    if not isinstance(query, TSQL):
        query = TSQL(query)

    return query.render(style=style)


# Simple helper functions (database-agnostic)

def select(table: str, ids: str | int | list[str | int] = None, *, columns: list[str] = None) -> TSQL:
    """Helper function to build basic SELECT queries

    Args:
        table: Table name
        ids: Optional ID or list of IDs to filter by
        columns: Optional list of column names to select (defaults to *)

    Returns:
        TSQL object representing the SELECT query
    """
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


def insert(table: str, **values: Any) -> TSQL:
    """Helper function to build basic INSERT queries

    Args:
        table: Table name
        **values: Column names and values as keyword arguments

    Returns:
        TSQL object representing the INSERT query

    Example:
        insert('users', id=1, name='Alice')
        Or with dict unpacking: insert('users', **my_dict)
    """
    if not values:
        raise ValueError("insert requires at least one column value")

    return TSQL(t"INSERT INTO {table:literal} {values:as_values}")


def update(table: str, id: str | int, **values: Any) -> TSQL:
    """Helper function to build UPDATE queries for a single row

    Args:
        table: Table name
        id: ID value to update
        **values: Column names and values to update as keyword arguments

    Returns:
        TSQL object representing the UPDATE query

    Example:
        update('users', 123, name='Bob', age=35)
        Or with dict unpacking: update('users', 123, **my_dict)
    """
    if not values:
        raise ValueError("update requires at least one column value")

    return TSQL(t"UPDATE {table:literal} SET {values:as_set} WHERE id = {id}")


def delete(table: str, id: str | int) -> TSQL:
    """Helper function to build DELETE queries for a single row

    Args:
        table: Table name
        id: ID value to delete

    Returns:
        TSQL object representing the DELETE query
    """
    return TSQL(t"DELETE FROM {table:literal} WHERE id = {id}")


from tsql.query_builder import UnsafeQueryError
from tsql.type_processor import TypeProcessor
from tsql.row import Row

__all__ = [
    'TSQL',
    'TSQLQuery',
    'render',
    't_join',
    'select',
    'insert',
    'update',
    'delete',
    'set_style',
    'UnsafeQueryError',
    'TypeProcessor',
    'Row',
]

