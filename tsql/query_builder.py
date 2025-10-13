from typing import Any, List, Optional, Union
from string.templatelib import Template
from functools import wraps
from datetime import datetime

from tsql import TSQL, t_join, insert as tsql_insert, upsert as tsql_upsert, delete as tsql_delete, as_set

# Optional SQLAlchemy support
try:
    from sqlalchemy import MetaData, Table as SATable, Column as SAColumn
    from sqlalchemy import Integer, String, Boolean, DateTime, Float, ForeignKey as SAForeignKey
    from sqlalchemy.sql.schema import Column as SAColumnType
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    SAColumnType = None


class Column:
    """Represents a bound column (table + column name) for building queries"""

    def __init__(self, table_name: str, column_name: str, python_type: type = None):
        self.table_name = table_name
        self.column_name = column_name
        self.python_type = python_type

    def __str__(self) -> str:
        return f"{self.table_name}.{self.column_name}"

    def __repr__(self) -> str:
        return f"Column({self.table_name!r}, {self.column_name!r})"

    def __eq__(self, other) -> 'Condition':
        if other is None:
            return Condition(self, 'IS', None)
        return Condition(self, '=', other)

    def __ne__(self, other) -> 'Condition':
        if other is None:
            return Condition(self, 'IS NOT', None)
        return Condition(self, '!=', other)

    def __lt__(self, other) -> 'Condition':
        return Condition(self, '<', other)

    def __le__(self, other) -> 'Condition':
        return Condition(self, '<=', other)

    def __gt__(self, other) -> 'Condition':
        return Condition(self, '>', other)

    def __ge__(self, other) -> 'Condition':
        return Condition(self, '>=', other)

    def in_(self, values: list) -> 'Condition':
        """Create an IN condition"""
        return Condition(self, 'IN', tuple(values))

    def like(self, pattern: str) -> 'Condition':
        """Create a LIKE condition"""
        return Condition(self, 'LIKE', pattern)


class ColumnDescriptor:
    """Descriptor that creates Column objects when accessed on Table instances"""

    def __init__(self, column_name: str, python_type: type = None):
        self.column_name = column_name
        self.python_type = python_type

    def __set_name__(self, owner, name):
        self.column_name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return Column(obj.table_name, self.column_name, self.python_type)


class Condition:
    """Represents a WHERE clause condition"""

    def __init__(self, left: Column, operator: str, right: Any):
        self.left = left
        self.operator = operator
        self.right = right

    def to_tsql(self) -> Template:
        """Convert condition to a t-string fragment"""
        left_str = str(self.left)

        if self.right is None:
            null_str = f"{left_str} {self.operator} NULL"
            return t'{null_str:unsafe}'

        if self.operator == 'IN':
            right_val = self.right
            return t'{left_str:unsafe} {self.operator:unsafe} {right_val}'

        if isinstance(self.right, Column):
            right_str = str(self.right)
            col_comparison = f"{left_str} {self.operator} {right_str}"
            return t'{col_comparison:unsafe}'

        if isinstance(self.right, Template):
            return t'{left_str:unsafe} {self.operator:unsafe} {self.right}'

        right_val = self.right
        return t'{left_str:unsafe} {self.operator:unsafe} {right_val}'

    def __repr__(self) -> str:
        return f"Condition({self.left!r}, {self.operator!r}, {self.right!r})"


class Join:
    """Represents a JOIN clause"""

    def __init__(self, table: 'Table', condition: Condition, join_type: str = 'INNER'):
        self.table = table
        self.condition = condition
        self.join_type = join_type

    def to_tsql(self) -> Template:
        """Convert join to a t-string fragment"""
        table_name = self.table.table_name
        join_type = self.join_type
        condition_tsql = self.condition.to_tsql()
        return t'{join_type:unsafe} JOIN {table_name:literal} ON {condition_tsql}'


class UpdateBuilder:
    """Fluent interface for building UPDATE queries"""

    def __init__(self, base_table: 'Table', values: dict[str, Any]):
        self.base_table = base_table
        self.values = values
        self._conditions: List[Union[Condition, Template]] = []

    def where(self, condition: Union[Condition, Template]) -> 'UpdateBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)"""
        self._conditions.append(condition)
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        table_name = self.base_table.table_name
        values_dict = self.values
        parts.append(t'UPDATE {table_name:literal} SET {values_dict:as_set}')

        if self._conditions:
            where_parts = []
            for cond in self._conditions:
                if isinstance(cond, Template):
                    where_parts.append(t'({cond})')
                else:
                    where_parts.append(cond.to_tsql())
            combined_where = t_join(t' AND ', where_parts)
            parts.append(t'WHERE {combined_where}')

        parts.append(t'RETURNING *')

        return TSQL(t_join(t' ', parts))

    def render(self, style=None):
        """Convenience method to render the query directly"""
        return self.to_tsql().render(style)

    def __repr__(self) -> str:
        """Show the rendered SQL query for debugging"""
        try:
            query, params = self.to_tsql().render()
            if params:
                return f"UpdateBuilder(\n  SQL: {query}\n  Params: {params}\n)"
            return f"UpdateBuilder({query})"
        except Exception as e:
            return f"UpdateBuilder(<error rendering: {e}>)"


class DeleteBuilder:
    """Fluent interface for building DELETE queries"""

    def __init__(self, base_table: 'Table'):
        self.base_table = base_table
        self._conditions: List[Union[Condition, Template]] = []

    def where(self, condition: Union[Condition, Template]) -> 'DeleteBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)"""
        self._conditions.append(condition)
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        table_name = self.base_table.table_name
        parts.append(t'DELETE FROM {table_name:literal}')

        if self._conditions:
            where_parts = []
            for cond in self._conditions:
                if isinstance(cond, Template):
                    where_parts.append(t'({cond})')
                else:
                    where_parts.append(cond.to_tsql())
            combined_where = t_join(t' AND ', where_parts)
            parts.append(t'WHERE {combined_where}')

        parts.append(t'RETURNING *')

        return TSQL(t_join(t' ', parts))

    def render(self, style=None):
        """Convenience method to render the query directly"""
        return self.to_tsql().render(style)

    def __repr__(self) -> str:
        """Show the rendered SQL query for debugging"""
        try:
            query, params = self.to_tsql().render()
            if params:
                return f"DeleteBuilder(\n  SQL: {query}\n  Params: {params}\n)"
            return f"DeleteBuilder({query})"
        except Exception as e:
            return f"DeleteBuilder(<error rendering: {e}>)"


class QueryBuilder:
    """Fluent interface for building SQL queries"""

    def __init__(self, base_table: 'Table'):
        self.base_table = base_table
        self._columns: Optional[List[Column]] = None
        self._conditions: List[Condition] = []
        self._joins: List[Join] = []
        self._group_by_columns: List[Column] = []
        self._having_conditions: List[Union[Condition, Template]] = []
        self._order_by_columns: List[tuple[Column, str]] = []
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None

    def select(self, *columns: Column) -> 'QueryBuilder':
        """Specify columns to select"""
        self._columns = list(columns) if columns else None
        return self

    def where(self, condition: Union[Condition, Template]) -> 'QueryBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)

        Accepts either Condition objects from query builder or raw t-string Templates
        """
        self._conditions.append(condition)
        return self

    def join(self, table: 'Table', on: Condition, join_type: str = 'INNER') -> 'QueryBuilder':
        """Add a JOIN clause"""
        self._joins.append(Join(table, on, join_type))
        return self

    def left_join(self, table: 'Table', on: Condition) -> 'QueryBuilder':
        """Add a LEFT JOIN clause"""
        return self.join(table, on, 'LEFT')

    def right_join(self, table: 'Table', on: Condition) -> 'QueryBuilder':
        """Add a RIGHT JOIN clause"""
        return self.join(table, on, 'RIGHT')

    def order_by(self, *columns: Union[Column, tuple[Column, str]]) -> 'QueryBuilder':
        """Add ORDER BY clause. Pass (column, 'DESC') for descending"""
        for col in columns:
            if isinstance(col, tuple):
                self._order_by_columns.append(col)
            else:
                self._order_by_columns.append((col, 'ASC'))
        return self

    def group_by(self, *columns: Column) -> 'QueryBuilder':
        """Add GROUP BY clause"""
        self._group_by_columns.extend(columns)
        return self

    def having(self, condition: Union[Condition, Template]) -> 'QueryBuilder':
        """Add HAVING condition (multiple calls are ANDed together)

        Accepts either Condition objects from query builder or raw t-string Templates
        """
        self._having_conditions.append(condition)
        return self

    def limit(self, n: int) -> 'QueryBuilder':
        """Add LIMIT clause"""
        self._limit_value = n
        return self

    def offset(self, n: int) -> 'QueryBuilder':
        """Add OFFSET clause"""
        self._offset_value = n
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        if self._columns:
            column_names = [str(col) for col in self._columns]
            columns_str = ', '.join(column_names)
            parts.append(t'SELECT {columns_str:unsafe}')
        else:
            parts.append(t'SELECT *')

        table_name = self.base_table.table_name
        parts.append(t'FROM {table_name:literal}')

        for join in self._joins:
            parts.append(join.to_tsql())

        if self._conditions:
            where_parts = []
            for cond in self._conditions:
                if isinstance(cond, Template):
                    where_parts.append(t'({cond})')
                else:
                    where_parts.append(cond.to_tsql())
            combined_where = t_join(t' AND ', where_parts)
            parts.append(t'WHERE {combined_where}')

        if self._group_by_columns:
            group_by_strs = [str(col) for col in self._group_by_columns]
            group_by_str = ', '.join(group_by_strs)
            parts.append(t'GROUP BY {group_by_str:unsafe}')

        if self._having_conditions:
            having_parts = []
            for cond in self._having_conditions:
                if isinstance(cond, Template):
                    having_parts.append(cond)
                else:
                    having_parts.append(cond.to_tsql())
            combined_having = t_join(t' AND ', having_parts)
            parts.append(t'HAVING {combined_having}')

        if self._order_by_columns:
            order_strs = [f"{col} {direction}" for col, direction in self._order_by_columns]
            order_by_str = ', '.join(order_strs)
            parts.append(t'ORDER BY {order_by_str:unsafe}')

        if self._limit_value is not None:
            limit_val = self._limit_value
            parts.append(t'LIMIT {limit_val}')

        if self._offset_value is not None:
            offset_val = self._offset_value
            parts.append(t'OFFSET {offset_val}')

        return TSQL(t_join(t' ', parts))

    def render(self, style=None):
        """Convenience method to render the query directly"""
        return self.to_tsql().render(style)

    def __repr__(self) -> str:
        """Show the rendered SQL query for debugging"""
        try:
            query, params = self.to_tsql().render()
            if params:
                return f"QueryBuilder(\n  SQL: {query}\n  Params: {params}\n)"
            return f"QueryBuilder({query})"
        except Exception as e:
            return f"QueryBuilder(<error rendering: {e}>)"


# Python type to SQLAlchemy type mapping (for simple type annotations)
if HAS_SQLALCHEMY:
    PYTHON_TO_SA = {
        int: Integer,
        str: String,
        bool: Boolean,
        datetime: DateTime,
        float: Float,
    }


def table(name: str, *, metadata: Optional[Any] = None, schema: Optional[str] = None):
    """Decorator to define a table with columns

    Args:
        name: Table name
        metadata: SQLAlchemy MetaData object for alembic integration (optional)
        schema: Database schema name (optional)

    Supports two ways to define columns:
    1. Type annotations: `id: int` (creates basic nullable column)
    2. SQLAlchemy Column: `id = Column(String, primary_key=True)` (full SA support)
    """
    def decorator(cls):
        cls.table_name = name
        cls.schema = schema

        annotations = getattr(cls, '__annotations__', {})
        sa_columns = []

        # Collect all potential column fields
        all_fields = {}

        # First, get annotated fields
        for field_name, field_type in annotations.items():
            all_fields[field_name] = {
                'type': field_type,
                'value': getattr(cls, field_name, None)
            }

        # Then, add any SA Column attributes that weren't annotated
        if HAS_SQLALCHEMY:
            for field_name in dir(cls):
                if field_name.startswith('_'):
                    continue
                field_value = getattr(cls, field_name, None)
                if isinstance(field_value, SAColumnType):
                    if field_name not in all_fields:
                        all_fields[field_name] = {
                            'type': None,
                            'value': field_value
                        }

        # Process all fields
        for field_name, field_info in all_fields.items():
            field_type = field_info['type']
            field_value = field_info['value']

            # Check if it's a SQLAlchemy Column object
            if HAS_SQLALCHEMY and isinstance(field_value, SAColumnType):
                # Use the SA Column directly
                if metadata is not None:
                    # Make a copy of the column with the field name
                    sa_col = field_value._copy()
                    sa_col.name = field_name
                    sa_columns.append(sa_col)

                # Create query builder ColumnDescriptor
                setattr(cls, field_name, ColumnDescriptor(field_name, field_type))
                continue

            # Otherwise, handle type annotations with helper classes
            if field_type is None:
                # No type annotation and not a SA Column, skip
                continue

            # Create query builder ColumnDescriptor
            setattr(cls, field_name, ColumnDescriptor(field_name, field_type))

            # Create SQLAlchemy column if metadata provided
            if metadata is not None and HAS_SQLALCHEMY:
                sa_type = PYTHON_TO_SA.get(field_type, String)()
                sa_columns.append(SAColumn(field_name, sa_type))

        # Create SQLAlchemy Table if metadata provided
        if metadata is not None and HAS_SQLALCHEMY:
            cls._sa_table = SATable(name, metadata, *sa_columns, schema=schema)

        original_init = cls.__init__ if hasattr(cls, '__init__') else lambda self: None

        def new_init(self):
            original_init(self)

        cls.__init__ = new_init

        def select(self, *columns: Column) -> QueryBuilder:
            """Start building a SELECT query"""
            builder = QueryBuilder(self)
            if columns:
                builder.select(*columns)
            return builder

        def insert(self, values: dict[str, Any], ignore_conflict: bool = False) -> TSQL:
            """Insert a row into the table

            Args:
                values: Dictionary of column names and values
                ignore_conflict: If True, adds ON CONFLICT DO NOTHING

            Returns:
                TSQL object representing the INSERT query
            """
            return tsql_insert(self.table_name, values, ignore_conflict=ignore_conflict)

        def upsert(self, values: dict[str, Any], conflict_on: str | list[str] | Column | list[Column]) -> TSQL:
            """Upsert (INSERT ... ON CONFLICT DO UPDATE) a row

            Args:
                values: Dictionary of column names and values
                conflict_on: Column name(s) or Column object(s) that define the conflict constraint

            Returns:
                TSQL object representing the UPSERT query
            """
            # Convert Column objects to strings
            if isinstance(conflict_on, Column):
                conflict_on = conflict_on.column_name
            elif isinstance(conflict_on, list):
                conflict_on = [col.column_name if isinstance(col, Column) else col for col in conflict_on]

            return tsql_upsert(self.table_name, values, conflict_on=conflict_on)

        def update(self, values: dict[str, Any]) -> UpdateBuilder:
            """Start building an UPDATE query

            Args:
                values: Dictionary of column names and values to update

            Returns:
                UpdateBuilder for adding WHERE conditions
            """
            return UpdateBuilder(self, values)

        def delete(self) -> DeleteBuilder:
            """Start building a DELETE query

            Returns:
                DeleteBuilder for adding WHERE conditions
            """
            return DeleteBuilder(self)

        cls.select = select
        cls.insert = insert
        cls.upsert = upsert
        cls.update = update
        cls.delete = delete

        # Return an instance instead of the class
        return cls()
    return decorator
