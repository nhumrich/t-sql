# t-sql

A lightweight SQL templating library that leverages Python 3.14's t-strings (PEP 750).
(Note: This library has absolutely nothing to do with Microsoft SQLServer)

t-sql provides a safe way to write SQL queries using Python's template strings (t-strings) while preventing SQL injection attacks through multiple parameter styling options.

## ⚠️ Python Version Requirement
This library requires Python 3.14+

t-sql is built specifically to take advantage of the new t-string feature introduced in PEP 750, which is only available in Python 3.14+.

## Installing

```bash
# with pip
pip install t-sql

# with uv
uv add t-sql
```

## Quick Start

```python
import tsql

# Basic usage
name = 'billy'
query = t'select * from users where name={name}'

# Render with default QMARK style
sql, params = tsql.render(query)
# ('select * from users where name = ?', ['billy'])

# Or use a different parameter style
sql, params = tsql.render(query, style=tsql.styles.NUMERIC_DOLLAR)
# ('select * from users where name = $1', ['billy'])
```

## Parameter Styles

- **QMARK** (default): Uses `?` placeholders
- **NUMERIC**: Uses `:1`, `:2`, etc. placeholders
- **NAMED**: Uses `:name` placeholders
- **FORMAT**: Uses `%s` placeholders
- **PYFORMAT**: Uses `%(name)s` placeholders
- **NUMERIC_DOLLAR**: Uses `$1`, `$2`, etc. (PostgreSQL native)
- **ESCAPED**: Escapes values directly into SQL (no parameters)

## Core Features

### SQL Injection Prevention

```python
# SQL injection prevention works automatically
name = "billy ' and 1=1 --"
sql, params = tsql.render(t'select * from users where name={name}')
# Even with ESCAPED style, quotes are properly escaped
sql, _ = tsql.render(t'select * from users where name={name}', style=tsql.styles.ESCAPED)
# ("select * from users where name = 'billy '' and 1=1 --'", [])
```

### Format-spec helpers

#### Literal

For table/column names that can't be parameterized:

```python
table = "users"
col = "name"
val = "billy"
query = t'select * from {table:literal} where {col:literal}={val}'
sql, params = tsql.render(query)
# ('select * from users where name = ?', ['billy'])
```

#### unsafe

For cases where you need to bypass safety (use with extreme caution):

```python
dynamic_where = "age > 18 AND active = true"
sql, params = tsql.render(t"SELECT * FROM users WHERE {dynamic_where:unsafe}")
```

#### as_values

Formats a dictionary for INSERT statements:

```python
values = {'id': 'abc123', 'name': 'bob', 'email': 'bob@example.com'}
sql, params = tsql.render(t"INSERT INTO users {values:as_values}")
# ('INSERT INTO users (id, name, email) VALUES (?, ?, ?)', ['abc123', 'bob', 'bob@example.com'])
```

#### as_set

Formats a dictionary for UPDATE statements:

```python
values = {'name': 'joe', 'email': 'joe@example.com'}
sql, params = tsql.render(t"UPDATE users SET {values:as_set} WHERE id='abc123'")
# ('UPDATE users SET name = ?, email = ? WHERE id='abc123'', ['joe', 'joe@example.com'])
```

### Helper Functions

t-sql provides several convenience functions for common SQL operations:

#### t_join

Joins multiple t-strings together:

```python
import tsql

min_age = 18
parts = [t"SELECT *", t"FROM users", t"WHERE age > {min_age}"]
query = tsql.t_join(t" ", parts)
sql, params = tsql.render(query)
# ('SELECT * FROM users WHERE age > ?', [18])
```

#### select

Quick SELECT queries:

```python
# Select all columns
query = tsql.select('users')
sql, params = query.render()
# ('SELECT * FROM users', [])

# Select specific columns
query = tsql.select('users', columns=['name', 'email'])
sql, params = query.render()
# ('SELECT name, email FROM users', [])

# With WHERE clause
query = tsql.select('users', columns=['name', 'email'], where={'age': 18})
sql, params = query.render()
# ('SELECT name, email FROM users WHERE age = ?', [18])
```

#### insert

Quick INSERT queries:

```python
values = {'id': 'abc123', 'name': 'bob', 'email': 'bob@example.com'}
query = tsql.insert('users', values)
sql, params = query.render()
# ('INSERT INTO users (id, name, email) VALUES (?, ?, ?)', ['abc123', 'bob', 'bob@example.com'])
```

#### update

Quick UPDATE queries:

```python
# Update by ID
query = tsql.update('users', {'email': 'new@example.com'}, id_value='abc123')
sql, params = query.render()
# ('UPDATE users SET email = ? WHERE id = ?', ['new@example.com', 'abc123'])

# Update with custom WHERE
query = tsql.update('users', {'email': 'new@example.com'}, where={'age': 25})
sql, params = query.render()
# ('UPDATE users SET email = ? WHERE age = ?', ['new@example.com', 25])
```

#### delete

Quick DELETE queries:

```python
# Delete by ID
query = tsql.delete('users', id_value='abc123')
sql, params = query.render()
# ('DELETE FROM users WHERE id = ?', ['abc123'])

# Delete with custom WHERE
query = tsql.delete('users', where={'age': 18})
sql, params = query.render()
# ('DELETE FROM users WHERE age = ?', [18])
```

**Note:** These helper functions return query builder objects, so you can chain additional methods:

```python
query = tsql.select('users').where(t'age > {min_age}').limit(10)
sql, params = query.render()
```

# Query Builder

For a more structured approach, t-sql includes an optional query builder with a fluent interface and type-safe column references.

## Basic Usage

```python
from tsql.query_builder import Table, Column

class Users(Table):
    id: Column
    username: Column
    email: Column
    age: Column

# Simple SELECT
query = Users.select(Users.id, Users.username)
sql, params = query.render()
# ('SELECT users.id, users.username FROM users', [])

# With WHERE clause
query = Users.select().where(Users.age > 18)
sql, params = query.render()
# ('SELECT * FROM users WHERE users.age > ?', [18])

# Multiple conditions (ANDed together)
query = (Users.select(Users.username, Users.email)
         .where(Users.age > 18)
         .where(Users.email != None))
```

**Table Names:** The table name defaults to the lowercase class name. To specify a custom name:

```python
class UserAccount(Table, table_name='user_accounts'):
    id: Column
    username: Column
```

## Joins

```python
class Posts(Table):
    id: Column
    user_id: Column
    title: Column

# INNER JOIN
query = (Posts.select(Posts.title, Users.username)
         .join(Users, on=Posts.user_id == Users.id)
         .where(Posts.id > 100))

# LEFT JOIN
query = (Posts.select()
         .left_join(Users, on=Posts.user_id == Users.id))
```

## Query Features

```python
# IN clause
query = Users.select().where(Users.id.in_([1, 2, 3]))

# LIKE clause
query = Users.select().where(Users.username.like('%john%'))

# ORDER BY
query = Posts.select().order_by(Posts.id)
query = Posts.select().order_by((Posts.id, 'DESC'))

# LIMIT and OFFSET
query = Posts.select().limit(10).offset(20)

# GROUP BY and HAVING
query = (Posts.select()
         .group_by(Posts.user_id)
         .having(t'COUNT(*) > {min_count}'))
```

## Write Operations

The query builder supports INSERT, UPDATE, and DELETE with database-agnostic conflict handling.

### INSERT

```python
# Basic insert
values = {'id': 'abc123', 'username': 'john', 'email': 'john@example.com'}
query = Users.insert(values)
sql, params = query.render()
# ('INSERT INTO users (id, username, email) VALUES (?, ?, ?)', ['abc123', 'john', 'john@example.com'])

# INSERT with RETURNING (Postgres/SQLite)
query = Users.insert(values).returning()
sql, params = query.render()
# ('INSERT INTO users (id, username, email) VALUES (?, ?, ?) RETURNING *', [...])

# INSERT IGNORE (MySQL)
query = Users.insert(values).ignore()
sql, params = query.render()
# ('INSERT IGNORE INTO users (id, username, email) VALUES (?, ?, ?)', [...])

# ON CONFLICT DO NOTHING (Postgres/SQLite)
query = Users.insert(values).on_conflict_do_nothing()
# ('INSERT INTO users (...) VALUES (...) ON CONFLICT DO NOTHING', [...])

# ON CONFLICT DO NOTHING with specific conflict target (Postgres/SQLite)
query = Users.insert(values).on_conflict_do_nothing(conflict_on='email')
# ('INSERT INTO users (...) VALUES (...) ON CONFLICT (email) DO NOTHING', [...])

# ON CONFLICT DO UPDATE (Postgres/SQLite upsert)
query = Users.insert(values).on_conflict_update(conflict_on='id')
# ('INSERT INTO users (...) VALUES (...)
#   ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, email = EXCLUDED.email', [...])

# ON CONFLICT with custom update
query = Users.insert(values).on_conflict_update(
    conflict_on='id',
    update={'username': 'updated_name'}
)

# ON DUPLICATE KEY UPDATE (MySQL)
query = Users.insert(values).on_duplicate_key_update()
# ('INSERT INTO users (...) VALUES (...)
#   ON DUPLICATE KEY UPDATE id = VALUES(id), username = VALUES(username), ...', [...])

# Chain multiple modifiers
query = (Users.insert(values)
         .on_conflict_update(conflict_on='id')
         .returning('id', 'username'))
```

### UPDATE

```python
# Basic update (no WHERE = updates all rows!)
query = Users.update({'email': 'newemail@example.com'})
sql, params = query.render()
# ('UPDATE users SET email = ?', ['newemail@example.com'])

# UPDATE with WHERE
query = Users.update({'email': 'newemail@example.com'}).where(Users.id == 'abc123')
sql, params = query.render()
# ('UPDATE users SET email = ? WHERE users.id = ?', ['newemail@example.com', 'abc123'])

# Multiple WHERE conditions
query = (Users.update({'email': 'newemail@example.com'})
         .where(Users.id == 'abc123')
         .where(Users.age > 18))

# With RETURNING (Postgres/SQLite)
query = (Users.update({'email': 'new@example.com'})
         .where(Users.id == 'abc123')
         .returning())
# ('UPDATE users SET email = ? WHERE users.id = ? RETURNING *', [...])
```

### DELETE

```python
# Basic delete (no WHERE = deletes all rows!)
query = Users.delete()
sql, params = query.render()
# ('DELETE FROM users', [])

# DELETE with WHERE
query = Users.delete().where(Users.id == 'abc123')
sql, params = query.render()
# ('DELETE FROM users WHERE users.id = ?', ['abc123'])

# Multiple conditions
query = Users.delete().where(Users.age < 18).where(Users.active == False)

# With RETURNING (Postgres/SQLite)
query = Users.delete().where(Users.id == 'abc123').returning()
# ('DELETE FROM users WHERE users.id = ? RETURNING *', ['abc123'])
```

## Database Compatibility

The query builder is database-agnostic - all methods are available regardless of which database you're using. It's your responsibility to use the appropriate methods for your database:

**PostgreSQL:**
- ✅ `.returning()` - RETURNING clause
- ✅ `.on_conflict_do_nothing()` - ON CONFLICT DO NOTHING
- ✅ `.on_conflict_update()` - ON CONFLICT DO UPDATE with EXCLUDED.*
- ❌ `.ignore()` - Not supported
- ❌ `.on_duplicate_key_update()` - Not supported

**MySQL:**
- ❌ `.returning()` - Not supported (MySQL limitation)
- ✅ `.ignore()` - INSERT IGNORE
- ✅ `.on_duplicate_key_update()` - ON DUPLICATE KEY UPDATE with VALUES()
- ❌ `.on_conflict_do_nothing()` - Not supported
- ❌ `.on_conflict_update()` - Not supported

**SQLite:**
- ✅ `.returning()` - RETURNING clause (SQLite 3.35+)
- ✅ `.on_conflict_do_nothing()` - ON CONFLICT DO NOTHING
- ✅ `.on_conflict_update()` - ON CONFLICT DO UPDATE
- ❌ `.ignore()` - Not supported
- ❌ `.on_duplicate_key_update()` - Not supported

If you use an unsupported method, your database will raise a syntax error when you execute the query.

## Mixing Query Builder with T-Strings

You can combine the query builder with raw t-strings for complex logic:

```python
from tsql.query_builder import Table, Column

class Users(Table):
    id: Column
    name: Column
    age: Column
    email: Column

# Start with query builder
query = Users.select(Users.id, Users.name, Users.email)

# Add structured condition
query = query.where(Users.age > 18)

# Add complex t-string condition for OR logic
search_term = "john"
name_col = str(Users.name)
email_col = str(Users.email)
complex_condition = t"{name_col:literal} LIKE '%' || {search_term} || '%' OR {email_col:literal} LIKE '%' || {search_term} || '%'"
query = query.where(complex_condition)

sql, params = query.render()
# SELECT users.id, users.name, users.email FROM users
# WHERE users.age > ? AND (users.name LIKE '%' || ? || '%' OR users.email LIKE '%' || ? || '%')
# params: [18, 'john', 'john']
```

Note: T-string conditions passed to `.where()` are automatically wrapped in parentheses to ensure proper operator precedence.

## SQLAlchemy & Alembic Integration

The query builder can integrate with SQLAlchemy's metadata system for alembic autogenerate:

```bash
pip install t-sql[sqlalchemy]
# or
uv add t-sql --optional sqlalchemy
```

### Two Ways to Define Columns

**1. Simple Column annotations** (for query builder only):

```python
from tsql import Table, Column

class Users(Table):
    id: Column
    name: Column
    age: Column
```

**2. SQLAlchemy Column objects** (for alembic integration):

```python
from sqlalchemy import MetaData, Column, String, Integer, ForeignKey
from tsql.query_builder import Table

metadata = MetaData()

class Users(Table, metadata=metadata):
    id = Column(String, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))
    age = Column(Integer)

# Use for alembic
target_metadata = metadata

# Use for queries (works identically!)
query = Users.select().where(Users.age > 18)
```

You can mix both approaches:

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql.functions import now

class Events(Table, metadata=metadata):
    id = Column(String, primary_key=True)
    topic: Column  # Simple annotation - becomes nullable String column
    created_at = Column(DateTime, server_default=now())
```

## Schema Support

```python
class Users(Table, schema='public'):
    id: Column
    name: Column
```

Or with custom table name and schema:

```python
class Users(Table, table_name='user_accounts', schema='public'):
    id: Column
    name: Column
```

# Rendering Queries

All query types (t-strings, TSQL objects, and QueryBuilder objects) can be rendered using `tsql.render()`:

```python
import tsql
from tsql.query_builder import Table, Column

class Users(Table):
    id: Column
    name: Column

# All of these work with tsql.render():
sql, params = tsql.render(t"SELECT * FROM users WHERE id = {user_id}")
sql, params = tsql.render(Users.select().where(Users.id == user_id))
sql, params = tsql.render(tsql.select('users', user_id))

# Or call .render() directly on TSQL/QueryBuilder objects:
query = Users.select().where(Users.age > 18)
sql, params = query.render()
```

# Type Safety & Preventing SQL Injection

This library should ideally be used in middleware or library code to enforce safe query construction. Use the `TSQLQuery` type to prevent raw strings:

```python
from tsql import TSQLQuery, render

def execute_sql_query(query: TSQLQuery):
    """Only accepts safe, parameterized queries"""
    sql, params = render(query)
    return sql_engine.execute(sql, params)

# Type checker allows these:
execute_sql_query(t"SELECT * FROM users WHERE id = {user_id}")  # ✓
execute_sql_query(Users.select())  # ✓
execute_sql_query(tsql.select('users'))  # ✓

# Type checker rejects raw strings:
execute_sql_query("SELECT * FROM users")  # ✗ Type error!
```

The `TSQLQuery` type is a union of `TSQL`, `Template` (t-strings), and `QueryBuilder`, ensuring all queries are safe from SQL injection.
