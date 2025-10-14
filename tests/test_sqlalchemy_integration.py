import tsql
from tsql.query_builder import Table
from sqlalchemy import MetaData, Column, String, Integer, Boolean, ForeignKey, TIMESTAMP, TypeDecorator
from sqlalchemy.sql.functions import now
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime


def test_table_with_simple_annotations():
    """Test that simple type annotations create SA tables"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata):
        id: int
        name: str
        age: int

    # Decorator returns class with _sa_table
    assert hasattr(Users, '_sa_table')
    assert Users._sa_table.name == 'users'
    assert 'id' in Users._sa_table.c
    assert 'name' in Users._sa_table.c
    assert Users._sa_table in metadata.tables.values()

    # Query builder works directly
    query = Users.select(Users.name).where(Users.age > 18)
    sql, params = query.render()
    assert 'SELECT users.name' in sql
    assert params == [18]


def test_table_without_metadata():
    """Test that @table works without metadata (query builder only)"""
    class Posts(Table, table_name='posts'):
        id: int
        title: str

    assert not hasattr(Posts, '_sa_table')
    assert Posts.id.table_name == 'posts'

    # Query builder still works
    query = Posts.select(Posts.title)
    sql, params = query.render()
    assert 'SELECT posts.title FROM posts' in sql


def test_schema_support():
    """Test that schema parameter works"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata, schema='public'):
        id: int

    assert Users._sa_table.schema == 'public'
    assert Users.schema == 'public'


def test_using_sqlalchemy_column_directly():
    """Test using SQLAlchemy Column objects directly"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True, index=True)
        name = Column(String(255), nullable=False)
        age = Column(Integer, nullable=True)
        active = Column(Boolean, server_default='true')

    # Verify SA table created correctly
    assert 'users' in metadata.tables
    sa_table = metadata.tables['users']

    assert sa_table.c.id.primary_key is True
    assert sa_table.c.name.type.length == 255
    assert sa_table.c.name.nullable is False
    assert sa_table.c.age.nullable is True

    # Verify query builder works directly
    query = Users.select(Users.id, Users.name).where(Users.age > 18)
    sql, params = query.render()

    assert 'SELECT users.id, users.name' in sql
    assert 'WHERE users.age > ?' in sql
    assert params == [18]


def test_mixed_column_definitions():
    """Test mixing type annotations and SA Column objects"""
    metadata = MetaData()

    class Posts(Table, table_name='posts', metadata=metadata):
        # Using SA Column for complex types
        id = Column(String, primary_key=True, default=lambda: 'generated_id')
        # Simple type annotation
        user_id: str
        # Using SA Column for custom types and server defaults
        created_at = Column(TIMESTAMP(timezone=True), server_default=now(), nullable=False)
        # Simple type annotation
        title: str

    assert 'posts' in metadata.tables
    sa_table = metadata.tables['posts']

    assert sa_table.c.id.primary_key is True
    assert sa_table.c.user_id.nullable is True  # Simple annotations are nullable by default
    assert sa_table.c.created_at.nullable is False

    # Query builder works directly
    query = Posts.select(Posts.id, Posts.title)
    sql, params = query.render()

    assert 'SELECT posts.id, posts.title' in sql


def test_sa_column_with_foreign_key():
    """Test SA Column with ForeignKey"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True)

    class Posts(Table, table_name='posts', metadata=metadata):
        id = Column(String, primary_key=True)
        user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
        title = Column(String(500))

    sa_posts = metadata.tables['posts']
    fks = list(sa_posts.c.user_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == 'users.id'

    # Query builder works directly
    query = Posts.select(Posts.title).join(Users, Posts.user_id == Users.id)
    sql, params = query.render()

    assert 'INNER JOIN users ON posts.user_id = users.id' in sql


def test_sa_column_with_custom_type():
    """Test SA Column with custom SQLAlchemy type"""
    class CustomType(TypeDecorator):
        impl = String
        cache_ok = True

    metadata = MetaData()

    class TestTable(Table, table_name='test', metadata=metadata):
        id = Column(Integer, primary_key=True)
        custom_field = Column(CustomType)
        json_field = Column(JSONB)

    sa_table = metadata.tables['test']
    assert isinstance(sa_table.c.custom_field.type, CustomType)

    # Query builder works directly
    query = TestTable.select(TestTable.custom_field, TestTable.json_field)
    sql, params = query.render()

    assert 'SELECT test.custom_field, test.json_field' in sql


def test_complex_real_world_example():
    """Test a complex real-world table definition"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True)

    class Comments(Table, table_name='comments', metadata=metadata):
        id = Column(String, primary_key=True, default=lambda: gen_id('c'))
        post_id = Column(String, ForeignKey('posts.id', ondelete='CASCADE'), index=True)
        user_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
        upvotes: int  # Simple annotation mixed in
        status = Column(String, index=True, nullable=False, server_default='active')
        created_ts = Column(TIMESTAMP(timezone=True), server_default=now(), nullable=False)
        deleted_ts = Column(TIMESTAMP(timezone=True), nullable=True)

    assert 'comments' in metadata.tables
    sa_table = metadata.tables['comments']

    # Verify foreign keys
    assert len(list(sa_table.c.post_id.foreign_keys)) == 1
    assert len(list(sa_table.c.user_id.foreign_keys)) == 1

    # Verify indexes
    assert sa_table.c.post_id.index is True
    assert sa_table.c.status.index is True

    # Query builder works directly
    query = Comments.select(Comments.id, Comments.status).where(Comments.deleted_ts == None)
    sql, params = query.render()

    assert 'WHERE comments.deleted_ts IS NULL' in sql


def test_mixing_query_builder_with_tsql():
    """Test mixing query builder with raw t-string conditions"""
    metadata = MetaData()

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True)
        name = Column(String)
        age = Column(Integer)
        email = Column(String)

    # Build a base query with query builder
    query = Users.select(Users.id, Users.name, Users.email)

    # Add simple query builder condition
    query = query.where(Users.age > 18)

    # Add complex t-string condition for advanced logic
    search_term = "john"
    min_age = 25
    name_col = str(Users.name)
    email_col = str(Users.email)
    age_col = str(Users.age)
    advanced_condition = t"({name_col:literal} LIKE '%' || {search_term} || '%' OR {email_col:literal} LIKE '%' || {search_term} || '%') AND {age_col:literal} >= {min_age}"

    # Mix it into the query builder - just pass the t-string directly!
    query_with_tsql = query.where(advanced_condition)

    sql, params = query_with_tsql.render()

    assert 'SELECT users.id, users.name, users.email' in sql
    assert 'WHERE users.age > ?' in sql
    assert "users.name LIKE '%' || ? || '%'" in sql
    assert "users.email LIKE '%' || ? || '%'" in sql
    assert 'users.age >= ?' in sql
    assert params == [18, 'john', 'john', 25]


def gen_id(prefix):
    """Dummy function for test"""
    return f"{prefix}_123"
