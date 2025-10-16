from typing import Any, List, Optional, Union, ClassVar
from string.templatelib import Template
from datetime import datetime
from abc import ABC, abstractmethod

from tsql import TSQL, t_join

# Optional SQLAlchemy support
try:
    from sqlalchemy import MetaData, Table as SATable, Column as SAColumn
    from sqlalchemy import Integer, String, Boolean, DateTime, Float, ForeignKey as SAForeignKey
    from sqlalchemy.sql.schema import Column as SAColumnType
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    SAColumnType = None


class OrderByClause:
    """Represents a column with an ORDER BY direction (ASC/DESC)"""

    def __init__(self, column: 'Column', direction: str):
        self.column = column
        self.direction = direction.upper()

    def __repr__(self) -> str:
        return f"OrderByClause({self.column!r}, {self.direction!r})"


class Column:
    """Represents a bound column (table + column name) for building queries"""

    def __init__(self, table_name: str = None, column_name: str = None, python_type: type = None, alias: str = None, schema: str = None):
        self.table_name = table_name
        self.column_name = column_name
        self.python_type = python_type
        self.alias = alias
        self.schema = schema

    def __str__(self) -> str:
        if self.schema:
            base = f"{self.schema}.{self.table_name}.{self.column_name}"
        else:
            base = f"{self.table_name}.{self.column_name}"
        if self.alias:
            return f"{base} AS {self.alias}"
        return base

    def __repr__(self) -> str:
        if self.alias:
            return f"Column({self.table_name!r}, {self.column_name!r}, alias={self.alias!r})"
        return f"Column({self.table_name!r}, {self.column_name!r})"

    def as_(self, alias: str) -> 'Column':
        """Create a new Column with an alias for use in SELECT clauses

        Args:
            alias: The alias name for this column

        Returns:
            A new Column object with the alias set

        Example:
            users.select(users.first_name.as_('first'), users.last_name.as_('last'))
        """
        return Column(self.table_name, self.column_name, self.python_type, alias, self.schema)

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

    def in_(self, values: Union[list, tuple, 'Column', Template, 'SelectQueryBuilder']) -> 'Condition':
        """Create an IN condition

        Args:
            values: List/tuple of values, a Column, a Template (t-string), or a SelectQueryBuilder for subqueries
        """
        if isinstance(values, (list, tuple)):
            return Condition(self, 'IN', tuple(values))
        return Condition(self, 'IN', values)

    def not_in(self, values: Union[list, tuple, 'Column', Template, 'SelectQueryBuilder']) -> 'Condition':
        """Create a NOT IN condition

        Args:
            values: List/tuple of values, a Column, a Template (t-string), or a SelectQueryBuilder for subqueries
        """
        if isinstance(values, (list, tuple)):
            return Condition(self, 'NOT IN', tuple(values))
        return Condition(self, 'NOT IN', values)

    def like(self, pattern: str) -> 'Condition':
        """Create a LIKE condition"""
        return Condition(self, 'LIKE', pattern)

    def not_like(self, pattern: str) -> 'Condition':
        """Create a NOT LIKE condition"""
        return Condition(self, 'NOT LIKE', pattern)

    def ilike(self, pattern: str) -> 'Condition':
        """Create an ILIKE condition (case-insensitive, PostgreSQL/SQLite only)"""
        return Condition(self, 'ILIKE', pattern)

    def not_ilike(self, pattern: str) -> 'Condition':
        """Create a NOT ILIKE condition (case-insensitive, PostgreSQL/SQLite only)"""
        return Condition(self, 'NOT ILIKE', pattern)

    def between(self, start: Any, end: Any) -> 'Condition':
        """Create a BETWEEN condition

        Args:
            start: Lower bound value
            end: Upper bound value
        """
        return Condition(self, 'BETWEEN', (start, end))

    def not_between(self, start: Any, end: Any) -> 'Condition':
        """Create a NOT BETWEEN condition

        Args:
            start: Lower bound value
            end: Upper bound value
        """
        return Condition(self, 'NOT BETWEEN', (start, end))

    @property
    def is_null(self) -> 'Condition':
        """Create an IS NULL condition"""
        return Condition(self, 'IS', None)

    @property
    def is_not_null(self) -> 'Condition':
        """Create an IS NOT NULL condition"""
        return Condition(self, 'IS NOT', None)

    def asc(self) -> OrderByClause:
        """Create an ascending ORDER BY clause

        Returns:
            OrderByClause for use in order_by()

        Example:
            Users.select().order_by(Users.username.asc())
        """
        return OrderByClause(self, 'ASC')

    def desc(self) -> OrderByClause:
        """Create a descending ORDER BY clause

        Returns:
            OrderByClause for use in order_by()

        Example:
            Users.select().order_by(Users.created_at.desc())
        """
        return OrderByClause(self, 'DESC')


class Table:
    """Base class for all table definitions. Provides query builder methods.

    Inherit from this class to define a table:

        class Users(Table):
            id: Column
            name: Column
            email: Column

    The table name defaults to the lowercase class name. To specify a custom name:

        class Users(Table, table_name='user_accounts'):
            id: Column

    For SQLAlchemy integration, use SQLAlchemy Column objects:

        from sqlalchemy import Column, Integer, String

        class Users(Table, metadata=metadata, schema='public'):
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
    """
    table_name: ClassVar[str]
    schema: ClassVar[Optional[str]] = None

    def __init_subclass__(cls, table_name: Optional[str] = None, metadata: Optional[Any] = None, schema: Optional[str] = None, **kwargs):
        super().__init_subclass__(**kwargs)

        # Set table_name: use provided name, or default to lowercase class name
        cls.table_name = table_name if table_name is not None else cls.__name__.lower()
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

        # Then, check for Ellipsis (...) assignments, SA Columns, and Column instances
        for field_name in dir(cls):
            if field_name.startswith('_'):
                continue
            field_value = getattr(cls, field_name, None)

            # Check for Ellipsis syntax: id = ...
            if field_value is ...:
                if field_name not in all_fields:
                    all_fields[field_name] = {
                        'type': None,
                        'value': ...
                    }
            # Check for SQLAlchemy Column objects
            elif HAS_SQLALCHEMY and isinstance(field_value, SAColumnType):
                if field_name not in all_fields:
                    all_fields[field_name] = {
                        'type': None,
                        'value': field_value
                    }
            # Check for Column instances (for column_name remapping)
            elif isinstance(field_value, Column):
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

            # Check if it's a Column instance (for column_name remapping)
            if isinstance(field_value, Column):
                # Extract the column_name from the Column instance
                db_column_name = field_value.column_name
                if db_column_name is None:
                    # No column_name specified, use field_name
                    db_column_name = field_name

                # Create query builder ColumnDescriptor with the DB column name
                setattr(cls, field_name, ColumnDescriptor(db_column_name, field_type))

                # Create SQLAlchemy column if metadata provided
                if metadata is not None and HAS_SQLALCHEMY:
                    sa_type = PYTHON_TO_SA.get(field_type, String)()
                    sa_columns.append(SAColumn(db_column_name, sa_type))
                continue

            # Check if it's an Ellipsis (...) declaration
            if field_value is ...:
                # Create query builder ColumnDescriptor
                setattr(cls, field_name, ColumnDescriptor(field_name, None))
                continue

            # Otherwise, handle type annotations
            if field_type is None:
                # No type annotation, Ellipsis, or SA Column - skip
                continue

            # Create query builder ColumnDescriptor for type-annotated fields
            setattr(cls, field_name, ColumnDescriptor(field_name, field_type))

            # Create SQLAlchemy column if metadata provided
            if metadata is not None and HAS_SQLALCHEMY:
                sa_type = PYTHON_TO_SA.get(field_type, String)()
                sa_columns.append(SAColumn(field_name, sa_type))

        # Create SQLAlchemy Table if metadata provided
        if metadata is not None and HAS_SQLALCHEMY:
            cls._sa_table = SATable(cls.table_name, metadata, *sa_columns, schema=schema)

    @classmethod
    def select(cls, *columns: Union['Column', Template]) -> 'SelectQueryBuilder':
        """Start building a SELECT query"""
        builder = SelectQueryBuilder(cls)
        if columns:
            builder.select(*columns)
        return builder

    @classmethod
    def insert(cls, **values: Any) -> 'InsertBuilder':
        """Start building an INSERT query

        Args:
            **values: Column names and values as keyword arguments

        Returns:
            InsertBuilder for adding conflict handling and RETURNING

        Example:
            Users.insert(username='bob', email='bob@example.com')
            Or with dict unpacking: Users.insert(**my_dict)
        """
        return InsertBuilder(cls, values)

    @classmethod
    def update(cls, **values: Any) -> 'UpdateBuilder':
        """Start building an UPDATE query

        Args:
            **values: Column names and values to update as keyword arguments

        Returns:
            UpdateBuilder for adding WHERE conditions

        Example:
            Users.update(username='bob', email='bob@example.com')
            Or with dict unpacking: Users.update(**my_dict)
        """
        return UpdateBuilder(cls, values)

    @classmethod
    def delete(cls) -> 'DeleteBuilder':
        """Start building a DELETE query

        Returns:
            DeleteBuilder for adding WHERE conditions
        """
        return DeleteBuilder(cls)


class ColumnDescriptor:
    """Descriptor that creates Column objects when accessed on Table classes or instances"""

    def __init__(self, column_name: str, python_type: type = None):
        self.column_name = column_name
        self.python_type = python_type

    def __set_name__(self, owner, name):
        self.column_name = name

    def __get__(self, obj, objtype=None) -> Column:
        if objtype is None:
            objtype = type(obj)
        schema = getattr(objtype, 'schema', None)
        return Column(objtype.table_name, self.column_name, self.python_type, schema=schema)


class Condition:
    """Represents a WHERE clause condition"""

    def __init__(self, left: Column, operator: str, right: Any):
        self.left = left
        self.operator = operator
        self.right = right

    def to_tsql(self) -> Template:
        """Convert condition to a t-string fragment"""
        left_str = str(self.left)

        # Handle NULL checks
        if self.right is None:
            null_str = f"{left_str} {self.operator} NULL"
            return t'{null_str:unsafe}'

        # Match on operator type
        match self.operator:
            case 'IN' | 'NOT IN':
                # Check if it's a QueryBuilder (subquery)
                if hasattr(self.right, 'to_tsql'):
                    subquery_tsql = self.right.to_tsql()
                    return t'{left_str:unsafe} {self.operator:unsafe} ({subquery_tsql})'
                # Check if it's a Template (raw t-string)
                elif isinstance(self.right, Template):
                    return t'{left_str:unsafe} {self.operator:unsafe} {self.right}'
                # Check if it's a Column
                elif isinstance(self.right, Column):
                    right_str = str(self.right)
                    return t'{left_str:unsafe} {self.operator:unsafe} ({right_str:unsafe})'
                # Otherwise it's a tuple/list of values
                else:
                    right_val = self.right
                    return t'{left_str:unsafe} {self.operator:unsafe} {right_val}'

            case 'BETWEEN' | 'NOT BETWEEN':
                if isinstance(self.right, tuple) and len(self.right) == 2:
                    start, end = self.right
                    return t'{left_str:unsafe} {self.operator:unsafe} {start} AND {end}'
                else:
                    raise ValueError(f"{self.operator} requires a tuple of (start, end)")

            case _:
                # Default handling for other operators
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
        if self.table.schema:
            table_name = f"{self.table.schema}.{self.table.table_name}"
        else:
            table_name = self.table.table_name
        join_type = self.join_type
        condition_tsql = self.condition.to_tsql()
        return t'{join_type:unsafe} JOIN {table_name:literal} ON {condition_tsql}'


class QueryBuilder(ABC):
    """Abstract base class for all query builders.

    All query builders (SELECT, INSERT, UPDATE, DELETE) implement this interface,
    allowing middleware and query handlers to accept any builder type.
    """

    @abstractmethod
    def to_tsql(self) -> TSQL:
        """Build and return a TSQL object representing the query."""
        ...

    def render(self, style=None) -> tuple[str, list]:
        """Convenience method to render the query directly.

        Args:
            style: Optional parameter style (e.g., QMARK, NUMERIC, etc.)

        Returns:
            Tuple of (sql_string, parameters)
        """
        return self.to_tsql().render(style)


class InsertBuilder(QueryBuilder):
    """Fluent interface for building INSERT queries"""

    def __init__(self, base_table: 'Table', values: dict[str, Any]):
        self.base_table = base_table

        # Apply defaults from SQLAlchemy columns if available
        if HAS_SQLALCHEMY and hasattr(base_table, '_sa_table') and base_table._sa_table is not None:
            merged_values = dict(values)  # Start with user-provided values
            for col in base_table._sa_table.columns:
                # Check if column has a default and wasn't provided by user
                if col.name not in merged_values and col.default is not None:
                    # Get the default value
                    default_arg = col.default.arg
                    if callable(default_arg):
                        # Call it with None context (we don't have execution context here)
                        try:
                            merged_values[col.name] = default_arg(None)
                        except TypeError:
                            # If it fails with TypeError, try calling without arguments
                            merged_values[col.name] = default_arg()
                    else:
                        merged_values[col.name] = default_arg
            self.values = merged_values
        else:
            self.values = values

        self._ignore = False
        self._on_conflict_action: Optional[str] = None
        self._conflict_cols: Optional[List[str]] = None
        self._update_cols: Optional[dict[str, Any]] = None
        self._returning_cols: Optional[List[str]] = None

    def ignore(self) -> 'InsertBuilder':
        """Add INSERT IGNORE (MySQL)"""
        self._ignore = True
        return self

    def on_conflict_do_nothing(self, conflict_on: Optional[Union[str, List[str]]] = None) -> 'InsertBuilder':
        """Add ON CONFLICT DO NOTHING (Postgres/SQLite)

        Args:
            conflict_on: Optional column name(s) for conflict target
        """
        self._on_conflict_action = 'nothing'
        if conflict_on:
            self._conflict_cols = [conflict_on] if isinstance(conflict_on, str) else conflict_on
        return self

    def on_conflict_update(self, conflict_on: Union[str, List[str]], update: Optional[dict[str, Any]] = None) -> 'InsertBuilder':
        """Add ON CONFLICT DO UPDATE (Postgres/SQLite)

        Args:
            conflict_on: Column name(s) that define the conflict constraint
            update: Optional dict of columns to update (defaults to all non-conflict columns using EXCLUDED.*)
        """
        self._on_conflict_action = 'update'
        self._conflict_cols = [conflict_on] if isinstance(conflict_on, str) else conflict_on
        self._update_cols = update
        return self

    def on_duplicate_key_update(self, update: Optional[dict[str, Any]] = None) -> 'InsertBuilder':
        """Add ON DUPLICATE KEY UPDATE (MySQL)

        Args:
            update: Optional dict of columns to update (defaults to all columns using VALUES(*))
        """
        self._on_conflict_action = 'duplicate_key'
        self._update_cols = update
        return self

    def returning(self, *columns: str) -> 'InsertBuilder':
        """Add RETURNING clause (Postgres/SQLite only)

        Args:
            columns: Column names to return, or none for RETURNING *
        """
        self._returning_cols = list(columns) if columns else ['*']
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        if self.base_table.schema:
            table_name = f"{self.base_table.schema}.{self.base_table.table_name}"
        else:
            table_name = self.base_table.table_name
        values_dict = self.values

        # MySQL INSERT IGNORE
        if self._ignore:
            parts.append(t'INSERT IGNORE INTO {table_name:literal} {values_dict:as_values}')
        else:
            parts.append(t'INSERT INTO {table_name:literal} {values_dict:as_values}')

        # Add alias for ON DUPLICATE KEY UPDATE if needed
        if self._on_conflict_action == 'duplicate_key':
            parts.append(t'AS new')

        # ON CONFLICT clauses (Postgres/SQLite)
        if self._on_conflict_action == 'nothing':
            if self._conflict_cols:
                # Validate all conflict columns
                for col in self._conflict_cols:
                    if not isinstance(col, str) or not col.isidentifier():
                        raise ValueError(f"Invalid conflict column name: {col!r}")
                conflict_cols_str = ', '.join(self._conflict_cols)
                parts.append(t'ON CONFLICT ({conflict_cols_str:unsafe}) DO NOTHING')
            else:
                parts.append(t'ON CONFLICT DO NOTHING')
        elif self._on_conflict_action == 'update':
            # Validate all conflict columns
            for col in self._conflict_cols:
                if not isinstance(col, str) or not col.isidentifier():
                    raise ValueError(f"Invalid conflict column name: {col!r}")
            conflict_cols_str = ', '.join(self._conflict_cols)

            # Build UPDATE SET clause
            if self._update_cols:
                # User specified which columns to update
                update_dict = self._update_cols
                parts.append(t'ON CONFLICT ({conflict_cols_str:unsafe}) DO UPDATE SET {update_dict:as_set}')
            else:
                # Default: update all non-conflict columns with EXCLUDED.*
                update_parts = []
                for i, key in enumerate(self.values.keys()):
                    if key not in self._conflict_cols:
                        if i > 0 and update_parts:
                            update_parts.append(', ')
                        update_parts.append(f'{key} = EXCLUDED.{key}')

                if update_parts:
                    update_str = ''.join(update_parts)
                    parts.append(t'ON CONFLICT ({conflict_cols_str:unsafe}) DO UPDATE SET {update_str:unsafe}')
                else:
                    # All columns are conflict columns, just do nothing
                    parts.append(t'ON CONFLICT ({conflict_cols_str:unsafe}) DO NOTHING')

        # MySQL ON DUPLICATE KEY UPDATE
        elif self._on_conflict_action == 'duplicate_key':
            if self._update_cols:
                update_dict = self._update_cols
                parts.append(t'ON DUPLICATE KEY UPDATE {update_dict:as_set}')
            else:
                # Default: update all columns with alias.column (new MySQL syntax)
                update_parts = []
                for i, key in enumerate(self.values.keys()):
                    if i > 0:
                        update_parts.append(', ')
                    update_parts.append(f'{key} = new.{key}')

                update_str = ''.join(update_parts)
                parts.append(t'ON DUPLICATE KEY UPDATE {update_str:unsafe}')

        # RETURNING clause
        if self._returning_cols is not None:
            # Validate all returning columns (skip validation for '*')
            if self._returning_cols != ['*']:
                for col in self._returning_cols:
                    if not isinstance(col, str) or not col.isidentifier():
                        raise ValueError(f"Invalid RETURNING column name: {col!r}")
            returning_str = ', '.join(self._returning_cols)
            parts.append(t'RETURNING {returning_str:unsafe}')

        return TSQL(t_join(t' ', parts))

    def render(self, style=None):
        """Convenience method to render the query directly"""
        return self.to_tsql().render(style)

    def __repr__(self) -> str:
        """Show the rendered SQL query for debugging"""
        try:
            query, params = self.to_tsql().render()
            if params:
                return f"InsertBuilder(\n  SQL: {query}\n  Params: {params}\n)"
            return f"InsertBuilder({query})"
        except Exception as e:
            return f"InsertBuilder(<error rendering: {e}>)"


class UpdateBuilder(QueryBuilder):
    """Fluent interface for building UPDATE queries"""

    def __init__(self, base_table: 'Table', values: dict[str, Any]):
        self.base_table = base_table

        # Apply onupdate defaults from SQLAlchemy columns if available
        if HAS_SQLALCHEMY and hasattr(base_table, '_sa_table') and base_table._sa_table is not None:
            merged_values = dict(values)  # Start with user-provided values
            for col in base_table._sa_table.columns:
                # Check if column has an onupdate and wasn't provided by user
                if col.name not in merged_values and col.onupdate is not None:
                    # Get the onupdate value
                    onupdate_arg = col.onupdate.arg
                    if callable(onupdate_arg):
                        # Call it with None context (we don't have execution context here)
                        try:
                            merged_values[col.name] = onupdate_arg(None)
                        except TypeError:
                            # If it fails with TypeError, try calling without arguments
                            merged_values[col.name] = onupdate_arg()
                    else:
                        merged_values[col.name] = onupdate_arg
            self.values = merged_values
        else:
            self.values = values

        self._conditions: List[Union[Condition, Template]] = []
        self._returning_cols: Optional[List[str]] = None

    def where(self, condition: Union[Condition, Template]) -> 'UpdateBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)"""
        self._conditions.append(condition)
        return self

    def returning(self, *columns: str) -> 'UpdateBuilder':
        """Add RETURNING clause (Postgres/SQLite only)

        Args:
            columns: Column names to return, or none for RETURNING *
        """
        self._returning_cols = list(columns) if columns else ['*']
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        if self.base_table.schema:
            table_name = f"{self.base_table.schema}.{self.base_table.table_name}"
        else:
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

        if self._returning_cols is not None:
            # Validate all returning columns (skip validation for '*')
            if self._returning_cols != ['*']:
                for col in self._returning_cols:
                    if not isinstance(col, str) or not col.isidentifier():
                        raise ValueError(f"Invalid RETURNING column name: {col!r}")
            returning_str = ', '.join(self._returning_cols)
            parts.append(t'RETURNING {returning_str:unsafe}')

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


class DeleteBuilder(QueryBuilder):
    """Fluent interface for building DELETE queries"""

    def __init__(self, base_table: 'Table'):
        self.base_table = base_table
        self._conditions: List[Union[Condition, Template]] = []
        self._returning_cols: Optional[List[str]] = None

    def where(self, condition: Union[Condition, Template]) -> 'DeleteBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)"""
        self._conditions.append(condition)
        return self

    def returning(self, *columns: str) -> 'DeleteBuilder':
        """Add RETURNING clause (Postgres/SQLite only)

        Args:
            columns: Column names to return, or none for RETURNING *
        """
        self._returning_cols = list(columns) if columns else ['*']
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        if self.base_table.schema:
            table_name = f"{self.base_table.schema}.{self.base_table.table_name}"
        else:
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

        if self._returning_cols is not None:
            # Validate all returning columns (skip validation for '*')
            if self._returning_cols != ['*']:
                for col in self._returning_cols:
                    if not isinstance(col, str) or not col.isidentifier():
                        raise ValueError(f"Invalid RETURNING column name: {col!r}")
            returning_str = ', '.join(self._returning_cols)
            parts.append(t'RETURNING {returning_str:unsafe}')

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


class SelectQueryBuilder(QueryBuilder):
    """Fluent interface for building SQL SELECT queries"""

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

    def select(self, *columns: Union[Column, Template]) -> 'SelectQueryBuilder':
        """Specify columns to select

        Args:
            columns: Column objects (optionally with .as_() aliases) or raw t-string Templates

        Examples:
            # Using Column.as_() for aliases
            users.select(users.first_name.as_('first'), users.last_name.as_('last'))

            # Mixing Column objects and raw t-strings
            users.select(users.id, users.email, t'users.first_name AS first')

            # No columns specified selects all (SELECT *)
            users.select()
        """
        self._columns = list(columns) if columns else None
        return self

    def where(self, condition: Union[Condition, Template]) -> 'SelectQueryBuilder':
        """Add a WHERE condition (multiple calls are ANDed together)

        Accepts either Condition objects from query builder or raw t-string Templates
        """
        self._conditions.append(condition)
        return self

    def join(self, table: 'Table', on: Condition, join_type: str = 'INNER') -> 'SelectQueryBuilder':
        """Add a JOIN clause"""
        self._joins.append(Join(table, on, join_type))
        return self

    def left_join(self, table: 'Table', on: Condition) -> 'SelectQueryBuilder':
        """Add a LEFT JOIN clause"""
        return self.join(table, on, 'LEFT')

    def right_join(self, table: 'Table', on: Condition) -> 'SelectQueryBuilder':
        """Add a RIGHT JOIN clause"""
        return self.join(table, on, 'RIGHT')

    def order_by(self, *columns: Union[Column, OrderByClause]) -> 'SelectQueryBuilder':
        """Add ORDER BY clause

        Args:
            columns: Column objects or OrderByClause objects (from .asc()/.desc())

        Examples:
            # Using .asc() and .desc() methods
            Users.select().order_by(Users.username.asc(), Users.id.desc())

            # Bare column defaults to ASC
            Users.select().order_by(Users.username)
        """
        for col in columns:
            if isinstance(col, OrderByClause):
                self._order_by_columns.append((col.column, col.direction))
            else:
                self._order_by_columns.append((col, 'ASC'))
        return self

    def group_by(self, *columns: Column) -> 'SelectQueryBuilder':
        """Add GROUP BY clause"""
        self._group_by_columns.extend(columns)
        return self

    def having(self, condition: Union[Condition, Template]) -> 'SelectQueryBuilder':
        """Add HAVING condition (multiple calls are ANDed together)

        Accepts either Condition objects from query builder or raw t-string Templates
        """
        self._having_conditions.append(condition)
        return self

    def limit(self, n: int) -> 'SelectQueryBuilder':
        """Add LIMIT clause"""
        self._limit_value = n
        return self

    def offset(self, n: int) -> 'SelectQueryBuilder':
        """Add OFFSET clause"""
        self._offset_value = n
        return self

    def to_tsql(self) -> TSQL:
        """Build the final TSQL object"""
        parts: List[Template] = []

        if self._columns:
            # Build column list, handling both Column objects and Template (t-string) objects
            column_parts = []
            for col in self._columns:
                if isinstance(col, Template):
                    column_parts.append(col)
                else:
                    # Column object, convert to string
                    column_parts.append(t'{str(col):unsafe}')

            columns_template = t_join(t', ', column_parts)
            parts.append(t'SELECT {columns_template}')
        else:
            parts.append(t'SELECT *')

        if self.base_table.schema:
            table_name = f"{self.base_table.schema}.{self.base_table.table_name}"
        else:
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
                return f"SelectQueryBuilder(\n  SQL: {query}\n  Params: {params}\n)"
            return f"SelectQueryBuilder({query})"
        except Exception as e:
            return f"SelectQueryBuilder(<error rendering: {e}>)"


# Python type to SQLAlchemy type mapping (for simple type annotations)
if HAS_SQLALCHEMY:
    PYTHON_TO_SA = {
        int: Integer,
        str: String,
        bool: Boolean,
        datetime: DateTime,
        float: Float,
    }
