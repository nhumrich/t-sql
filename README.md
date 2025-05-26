# tsql

A lightweight SQL templating library that leverages Python 3.14's t-strings (PEP 750).

TSQL provides a safe way to write SQL queries using Python's template strings (t-strings) while preventing SQL injection attacks through multiple parameter styling options.

## ⚠️ Python Version Requirement
This library requires Python 3.14b1 or newer.

TSQL is built specifically to take advantage of the new t-string feature introduced in PEP 750, which is only available in Python 3.14+.


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
tsql.render(f"SELECT * FROM users WHERE {dynamic_where:unsafe}")
```

### as_values

The spec `:as_values` formats a dictionary into the format:
`(key1, key2, ...) VALUES (value1, value2, ...)` for uses in insert statements.

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

# update values on a single row
table = 'users'
values = {'name': 'joe', 'email': 'joe@example.com'}
tsql.update(table, values, id='abc123')
# UPDATE users SET name='joe', email='joe@example.com' WHERE id='abc123'
```

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