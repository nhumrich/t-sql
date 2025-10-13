# tsql

A lightweight SQL templating library that leverages Python 3.14's t-strings (PEP 750).

TSQL provides a safe way to write SQL queries using Python's template strings (t-strings) while preventing SQL injection attacks through multiple parameter styling options.

## ⚠️ Python Version Requirement
This library requires Python 3.14+

TSQL is built specifically to take advantage of the new t-string feature introduced in PEP 750, which is only available in Python 3.14+.

## Installing

```
# with pip
pip install t-sql

# with uv
uv add t-sql
```

## using

```
import tsql

tsql.render(t"select * from users where name={name)")
```

## Parameter Styles

- **QMARK** (default): Uses `?` placeholders
- **NUMERIC**: Uses `:1`, `:2`, etc. placeholders  
- **NAMED**: Uses `:name` placeholders
- **FORMAT**: Uses `%s` placeholders
- **PYFORMAT**: Uses `%(name)s` placeholders
- **NUMERIC_DOLLAR**: Uses `$1`, `$2`, etc. (PostgreSQL native)
- **ESCAPED**: Escapes values directly into SQL (no parameters)

## Examples:

```python

# Basic usage with different parameter styles
import tsql
import tsql.styles

name = 'billy'
query = t'select * from users where name={name}'

# Default QMARK style
print(tsql.render(query))
# ('select * from users where name = ?', ['billy'])

# PostgreSQL native style
print(tsql.render(query, style=tsql.styles.NUMERIC_DOLLAR))
# ('select * from users where name = $1', ['billy'])

# ESCAPED style (no parameters)
print(tsql.render(query, style=tsql.styles.ESCAPED))
# ("select * from users where name = 'billy'", [])

# SQL injection prevention
name = "billy ' and 1=1 --"
print(tsql.render(query, style=tsql.styles.ESCAPED))
# ("select * from users where name = 'billy '' and 1=1 --'", [])

```

## Format-spec helpers

There are some built-in format spec helpers that can change the way some 
parts of the library work. 

### Literal 
One common example is you may want to set the name
of a column dynamically. By using the `literal` format spec, the value will
be sanitized against a valid literal and put straight into the sql query since 
you cannot parameterize that part of a query, example:

```python
query = t'select * from {table:literal} where {col:literal}={val}'
```

or, a full example:
```python

# with a like clause
min_age = 30
search_column = "name"
pattern = "O'Brien"
is_active = True
tsql.render(t"SELECT * FROM test_users WHERE age >= {min_age} AND {search_column:literal} LIKE '%' || {pattern} || '%' AND active = {is_active}")
```

### unsafe
You may want to do advanced things that may otherwise be considered unsfe. 
This is okay if you can be sure that a user is not providing input. Like maybe
you care storing a query for some reason.
As per the name, this can open you up to sql injection and should be used with 
extreme caution.
You can use the "unsafe" format spec for these
cases:
```python
dynamic_where = input('type where clause')
tsql.render(t"SELECT * FROM users WHERE {dynamic_where:unsafe}")
```

### as_values

The spec `:as_values` formats a dictionary into the format:
`(key1, key2, ...) VALUES (value1, value2, ...)` for uses in insert statements.

### as_set

The spec `:as_set` formats a dictionary into the format:
`key1='?', key2='?'` for uses in update statements.

### traditional format_spec

All other format specs should be handled as they would in a normal f-string. 

## Included helper methods

```python
# select
tsql.select('table', 'abc123')
# SELECT * FROM table WHERE id='abc123'

# select with multiple ids and specific columns
tsql.select('users', ['abc123', 'def456'], columns=['name', 'age'])
# SELECT name, age FROM users WHERE id in ('abc123', 'def456')


# t_join (joins multiple t-strings together like .join on a str)
tsql.t_join(t" ", [t"hello", t"there"])
# t"hello there"


# insert
table = 'users'
values = {'id': 'abc123', 'name': 'bob', 'email': 'bob@example.com'}
tsql.insert(table, values)
# INSERT INTO users (id, name, email) VALUES ('abc123', 'bob', 'bob@example.com')

# insert with ignore_conflict
tsql.insert(table, values, ignore_conflict=True)
# INSERT INTO users (id, name, email) VALUES ('abc123', 'bob', 'bob@example.com') ON CONFLICT DO NOTHING RETURNING *

# upsert (insert or update on conflict)
values = {'id': 'abc123', 'name': 'joe', 'email': 'joe@example.com'}
tsql.upsert(table, values, conflict_on='id')
# INSERT INTO users (id, name, email) VALUES ('abc123', 'joe', 'joe@example.com')
# ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email RETURNING *

# upsert with multiple conflict columns
tsql.upsert(table, values, conflict_on=['email', 'name'])
# ON CONFLICT (email, name) DO UPDATE SET ...

# update values on a single row
table = 'users'
values = {'name': 'joe', 'email': 'joe@example.com'}
tsql.update(table, values, id='abc123')
# UPDATE users SET name='joe', email='joe@example.com' WHERE id='abc123' RETURNING *

# delete a single row
tsql.delete(table, id='abc123')
# DELETE FROM users WHERE id = 'abc123'
```

# Query Builder

For a more structured approach to building queries, TSQL includes an optional query builder that provides a fluent interface with type-safe column references.

## Basic Usage

```python
from tsql.query_builder import table

@table('users')
class Users:
    id: int
    username: str
    email: str
    created_at: str

# Decorator returns instance - use directly!
query = Users.select(Users.id, Users.username)
sql, params = query.render()
# SELECT users.id, users.username FROM users

# With WHERE clause
query = Users.select().where(Users.id > 100)
sql, params = query.render()
# SELECT * FROM users WHERE users.id > ?
# params: [100]

# Multiple WHERE conditions (ANDed together)
query = (Users.select(Users.username, Users.email)
         .where(Users.id > 10)
         .where(Users.email != None))
sql, params = query.render()
# SELECT users.username, users.email FROM users WHERE users.id > ? AND users.email IS NOT NULL
```

## Joins

```python
@table('posts')
class Posts:
    id: int
    user_id: int
    title: str
    body: str

@table('comments')
class Comments:
    id: int
    post_id: int
    user_id: int
    content: str

# INNER JOIN
query = (Posts.select(Posts.title, Users.username)
         .join(Users, Posts.user_id == Users.id)
         .where(Posts.id > 100))
sql, params = query.render()
# SELECT posts.title, users.username FROM posts INNER JOIN users ON posts.user_id = users.id WHERE posts.id > ?

# LEFT JOIN with multiple tables
query = (Comments.select(Comments.content, Posts.title, Users.username)
         .join(Posts, Comments.post_id == Posts.id)
         .left_join(Users, Comments.user_id == Users.id))
```

## Additional Features

```python
# IN clause
query = Users.select().where(Users.id.in_([1, 2, 3]))

# LIKE clause
query = Users.select().where(Users.username.like('%john%'))

# ORDER BY
query = Posts.select().order_by(Posts.created_at)
query = Posts.select().order_by((Posts.id, 'DESC'))

# LIMIT
query = Posts.select().limit(10)

# Complex query
query = (Posts.select(Posts.title, Users.username)
         .join(Users, Posts.user_id == Users.id)
         .where(Posts.id > 100)
         .where(Users.id >= 5)
         .order_by((Posts.id, 'DESC'))
         .limit(20))
```

## Write Operations

The query builder supports INSERT, UPDATE, UPSERT, and DELETE operations:

```python
# INSERT
values = {'id': 'abc123', 'username': 'john', 'email': 'john@example.com'}
query = Users.insert(values)
sql, params = query.render()
# INSERT INTO users (id, username, email) VALUES (?, ?, ?) RETURNING *

# INSERT with conflict handling (ignore)
query = Users.insert(values, ignore_conflict=True)
sql, params = query.render()
# INSERT INTO users (id, username, email) VALUES (?, ?, ?) ON CONFLICT DO NOTHING RETURNING *

# UPSERT (INSERT ... ON CONFLICT DO UPDATE)
values = {'id': 'abc123', 'username': 'john_updated', 'email': 'john@example.com'}
query = Users.upsert(values, conflict_on='id')
sql, params = query.render()
# INSERT INTO users (id, username, email) VALUES (?, ?, ?)
# ON CONFLICT (id) DO UPDATE SET username=EXCLUDED.username, email=EXCLUDED.email RETURNING *

# UPSERT with multiple conflict columns
query = Users.upsert(values, conflict_on=['email', 'username'])
# Can also use Column objects: conflict_on=Users.id or conflict_on=[Users.email, Users.username]

# UPDATE with WHERE conditions
query = Users.update({'email': 'newemail@example.com'}).where(Users.id == 'abc123')
sql, params = query.render()
# UPDATE users SET email=? WHERE users.id = ? RETURNING *

# UPDATE with multiple conditions
query = (Users.update({'email': 'newemail@example.com'})
         .where(Users.id == 'abc123')
         .where(Users.username == 'john'))

# DELETE with WHERE conditions
query = Users.delete().where(Users.id == 'abc123')
sql, params = query.render()
# DELETE FROM users WHERE users.id = ? RETURNING *

# DELETE with multiple conditions
query = Users.delete().where(Users.id > 100).where(Users.email == None)
```

All write operations return `RETURNING *` by default to retrieve the affected rows.

## Advanced Mixed Query (Query Builder + T-Strings)

You can combine the query builder's structured approach with raw t-string conditions for complex logic:

```python
from tsql.query_builder import table
from sqlalchemy import MetaData, Column, String, Integer

metadata = MetaData()

@table('users', metadata=metadata)
class Users:
    id = Column(String, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    email = Column(String)

# Start with query builder for the base query
query = Users.select(Users.id, Users.name, Users.email)

# Add simple conditions with query builder
query = query.where(Users.age > 18)

# Add complex logic with t-strings for advanced conditions
search_term = "john"
min_age = 25
name_col = str(Users.name)
email_col = str(Users.email)
age_col = str(Users.age)

# Build advanced t-string condition with OR logic
advanced_condition = t"{name_col:literal} LIKE '%' || {search_term} || '%' OR {email_col:literal} LIKE '%' || {search_term} || '%'"

# Mix it into the query builder (t-string conditions are automatically wrapped in parentheses)
query = query.where(advanced_condition)

sql, params = query.render()
# SELECT users.id, users.name, users.email FROM users
# WHERE users.age > ? AND (users.name LIKE '%' || ? || '%' OR users.email LIKE '%' || ? || '%')
# params: [18, 'john', 'john']
```

**Important:** When using t-string conditions with `.where()`, they are automatically wrapped in parentheses to ensure proper operator precedence when combined with other conditions using AND. This prevents issues when your t-string contains OR operators.

This approach lets you use the query builder for structure and safety, while dropping down to t-strings when you need custom SQL logic that the query builder doesn't support.

### Schema Support

```python
@table('users', schema='public')
class Users:
    id: int
    name: str
```

## SQLAlchemy & Alembic Integration

The query builder can integrate with SQLAlchemy's metadata system, allowing alembic autogenerate to work while maintaining the clean query builder syntax.

First, install with SQLAlchemy support:
```bash
pip install t-sql[sqlalchemy]
# or
uv add t-sql --optional sqlalchemy
```

### Two Ways to Define Columns

**1. Simple type annotations** (no alembic needed):
```python
from tsql.query_builder import table

@table('users')  # No metadata = query builder only
class Users:
    id: int
    name: str
    age: int

# Decorator returns an instance - no need to instantiate!
query = Users.select(Users.name).where(Users.age > 18)
```

**2. SQLAlchemy Column objects** (for alembic integration - **recommended**):
```python
from sqlalchemy import MetaData, Column, String, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.sql.functions import now
from tsql.query_builder import table

metadata = MetaData()

@table('users', metadata=metadata)
class Users:
    id = Column(String, primary_key=True, default=lambda: gen_id())
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100))
    created_ts = Column(TIMESTAMP(timezone=True), server_default=now(), nullable=False)

@table('posts', metadata=metadata)
class Posts:
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title = Column(String(500))
```

**You can mix both approaches**:
```python
@table('events', metadata=metadata)
class Events:
    id = Column(String, primary_key=True, default=lambda: gen_id("e"))  # Full SA
    topic: str  # Simple - becomes nullable String column
    created_ts = Column(TIMESTAMP(timezone=True), server_default=now())
```

### Using the Query Builder

```python
# For alembic (in your models.py or env.py)
target_metadata = metadata

# For queries - use decorated classes directly (they're already instances!)
query = (Posts.select(Posts.title, Users.name)
         .join(Users, Posts.user_id == Users.id)
         .where(Users.age > 18))

sql, params = query.render()
```

### Why Use SQLAlchemy Column?

Using `Column(...)` directly gives you:
- ✅ Full SQLAlchemy feature support (server defaults, computed columns, custom types, etc.)
- ✅ `ondelete` cascade rules on foreign keys
- ✅ Custom types like `JSONB`, `TIMESTAMP(timezone=True)`, `TypeDecorator`
- ✅ Callable defaults: `default=lambda: gen_id()`
- ✅ Server defaults: `server_default=now()`
- ✅ Column comments
- ✅ Everything SQLAlchemy supports

### How It Works

When you provide a `metadata` parameter to `@table()`, the decorator:
1. Detects SQLAlchemy `Column` objects and uses them directly
2. Creates query builder Column descriptors for fluent syntax
3. Registers tables to metadata for alembic

This means:
- Alembic autogenerate works perfectly
- Query builder gives you type-safe queries
- Single source of truth for your schema
- SQLAlchemy is optional - query builder works standalone

# Note on usage

This library should ideally be used inside middleware or library code
right before making an actual query. It can be used to enforce
using t-strings and prevent using raw strings.

For example:

```
from string.templatelib import Template

import tsql

def execute_sql_query(query):
    if not isinstance(query, Template):
        raise TypeError('Cannot make a query without using t-strings')
        
    
    return sql_engine.execute(*tsql.render(query))

```
