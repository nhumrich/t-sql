# tsql
SQL queries for python t-strings


## Examples:

```python

# basic
name = 'billy'
query = t'select * from users where name={name}'
print(tsql.render(query))
# select * from users where name = ?
# select * from users where name = $1
# select * from users where name = 'billy'

# preventing injection
name = "billy ' and 1=1 --"
# select * from users where name = ?
# select * from users where name = $1
# select * from users where name = 'billy '' and 1=1 --'


# with unsafe
table = tsql.unsafe(input('what table would you like to query?'))
col = input('what column are we filtering?')
val = input('whats the value of the filter')
query = t'select * from {table} where {col:unsafe}={val}'

# with safe literals
query = t'select * from {table:literal} where {col:l}={val}'

# convert list to tuple notation
ids = [1, 2, 3]
query = t'select * from users where id IN {ids}'
# select * from users where id i (1, 2, 3)

# convert datetime to sql timestamps

# convert None to NULL

# convert dictionaries to JSON

# helper methods

# select
tsql.select()

# join (joins multiple t-strings together)
tsql.join()

# insert
tsql.insert()

# update values on a single row
tsql.update(table, values: Dict[str, str], id, id_column_name='id')

# updateMany  - update many values on many rows
tsql.updateMany(table, values: Dict[str, Dict[str, str]], id_column='id')


```