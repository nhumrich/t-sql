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


def test_sa_column_annotations_are_correct_type():
    """Test that SA Column assignments get correct type annotations for IDE autocomplete"""
    from tsql.query_builder import Column as TsqlColumn

    metadata = MetaData()

    class MyTable(Table, table_name='mytable', metadata=metadata):
        my_column = Column(TIMESTAMP())
        another = Column(Integer())
        text_field = Column(String(100))

    # Verify that __annotations__ has been updated to reflect tsql.Column
    assert 'my_column' in MyTable.__annotations__
    assert 'another' in MyTable.__annotations__
    assert 'text_field' in MyTable.__annotations__

    assert MyTable.__annotations__['my_column'] == TsqlColumn
    assert MyTable.__annotations__['another'] == TsqlColumn
    assert MyTable.__annotations__['text_field'] == TsqlColumn

    # Verify that the columns actually work as tsql.Column objects
    col = MyTable.my_column
    assert isinstance(col, TsqlColumn)
    assert hasattr(col, 'is_null')
    assert hasattr(col, 'asc')
    assert hasattr(col, 'desc')

    # Verify is_null works
    condition = col.is_null()
    assert condition.operator == 'IS'
    assert condition.right is None

def gen_id(prefix):
    """Dummy function for test"""
    return f"{prefix}_123"


def test_table_with_unique_constraint():
    """Test that UniqueConstraint is properly added to SA table"""
    from sqlalchemy import UniqueConstraint

    metadata = MetaData()

    class Clients(Table, table_name='clients', metadata=metadata):
        id = Column(String, primary_key=True)
        tenant_id = Column(String, ForeignKey('tenants.id'))
        email = Column(String, nullable=False)

        constraints = [
            UniqueConstraint('tenant_id', 'email', name='uq_clients_tenant_email')
        ]

    assert 'clients' in metadata.tables
    sa_table = metadata.tables['clients']

    # Find the unique constraint
    unique_constraints = [c for c in sa_table.constraints if isinstance(c, UniqueConstraint)]
    assert len(unique_constraints) == 1

    uc = unique_constraints[0]
    assert uc.name == 'uq_clients_tenant_email'
    assert set(c.name for c in uc.columns) == {'tenant_id', 'email'}

    # Query builder still works
    query = Clients.select(Clients.id, Clients.email)
    sql, params = query.render()
    assert 'SELECT clients.id, clients.email FROM clients' in sql


def test_table_with_check_constraint():
    """Test that CheckConstraint is properly added to SA table"""
    from sqlalchemy import CheckConstraint

    metadata = MetaData()

    class Products(Table, table_name='products', metadata=metadata):
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        price = Column(Integer)

        constraints = [
            CheckConstraint('price > 0', name='ck_products_positive_price')
        ]

    sa_table = metadata.tables['products']

    # Find the check constraint
    check_constraints = [c for c in sa_table.constraints if isinstance(c, CheckConstraint)]
    assert len(check_constraints) == 1

    cc = check_constraints[0]
    assert cc.name == 'ck_products_positive_price'


def test_table_with_multiple_constraints():
    """Test that multiple constraints can be added together"""
    from sqlalchemy import UniqueConstraint, CheckConstraint, Index

    metadata = MetaData()

    class Orders(Table, table_name='orders', metadata=metadata):
        id = Column(String, primary_key=True)
        user_id = Column(String, nullable=False)
        order_number = Column(String, nullable=False)
        amount = Column(Integer)
        status = Column(String)

        constraints = [
            UniqueConstraint('order_number', name='uq_orders_order_number'),
            CheckConstraint('amount >= 0', name='ck_orders_non_negative_amount'),
            Index('ix_orders_user_status', 'user_id', 'status')
        ]

    sa_table = metadata.tables['orders']

    # Verify all constraints are present
    unique_constraints = [c for c in sa_table.constraints if isinstance(c, UniqueConstraint)]
    check_constraints = [c for c in sa_table.constraints if isinstance(c, CheckConstraint)]

    assert len(unique_constraints) == 1
    assert len(check_constraints) == 1

    # Verify index
    assert len(sa_table.indexes) == 1
    idx = list(sa_table.indexes)[0]
    assert idx.name == 'ix_orders_user_status'


def test_table_with_constraints_as_tuple():
    """Test that constraints attribute works with tuple format"""
    from sqlalchemy import UniqueConstraint

    metadata = MetaData()

    class Items(Table, table_name='items', metadata=metadata):
        id = Column(Integer, primary_key=True)
        category = Column(String)
        code = Column(String)

        constraints = (
            UniqueConstraint('category', 'code', name='uq_items_category_code'),
        )

    sa_table = metadata.tables['items']

    unique_constraints = [c for c in sa_table.constraints if isinstance(c, UniqueConstraint)]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == 'uq_items_category_code'


def test_table_with_comment():
    """Test that comment parameter is passed to SQLAlchemy table"""
    metadata = MetaData()

    class Settings(Table, table_name='settings', metadata=metadata, comment='Application settings and configuration'):
        id = Column(Integer, primary_key=True)
        key = Column(String, nullable=False)
        value = Column(String)

    sa_table = metadata.tables['settings']
    assert sa_table.comment == 'Application settings and configuration'


def test_table_with_constraints_and_comment():
    """Test that both constraints and comment work together"""
    from sqlalchemy import UniqueConstraint

    metadata = MetaData()

    class ApiKeys(Table, table_name='api_keys', metadata=metadata, comment='API authentication keys'):
        id = Column(String, primary_key=True)
        user_id = Column(String, nullable=False)
        key_hash = Column(String, nullable=False)

        constraints = [
            UniqueConstraint('key_hash', name='uq_api_keys_key_hash')
        ]

    sa_table = metadata.tables['api_keys']

    assert sa_table.comment == 'API authentication keys'

    unique_constraints = [c for c in sa_table.constraints if isinstance(c, UniqueConstraint)]
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == 'uq_api_keys_key_hash'

    # Query builder still works
    query = ApiKeys.select().where(ApiKeys.user_id == 'user123')
    sql, params = query.render()
    assert 'WHERE api_keys.user_id = ?' in sql
    assert params == ['user123']
