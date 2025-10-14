import tempfile
import shutil
from pathlib import Path
from textwrap import dedent
import re

import pytest
from sqlalchemy import MetaData, Column, String, Integer, Boolean, ForeignKey, TIMESTAMP, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata

from tsql.query_builder import Table


@pytest.fixture
def temp_alembic_env():
    temp_dir = tempfile.mkdtemp()
    alembic_dir = Path(temp_dir) / "alembic"
    alembic_dir.mkdir()
    versions_dir = alembic_dir / "versions"
    versions_dir.mkdir()

    env_py = alembic_dir / "env.py"
    env_py.write_text(dedent("""
        from alembic import context
        from sqlalchemy import engine_from_config, pool

        config = context.config
        target_metadata = config.attributes.get('target_metadata', None)

        def run_migrations_offline():
            context.configure(
                url=config.get_main_option("sqlalchemy.url"),
                target_metadata=target_metadata,
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
            )
            with context.begin_transaction():
                context.run_migrations()

        def run_migrations_online():
            connectable = config.attributes.get('connection', None)
            if connectable is None:
                connectable = engine_from_config(
                    config.get_section(config.config_ini_section),
                    prefix="sqlalchemy.",
                    poolclass=pool.NullPool,
                )

            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata
                )
                with context.begin_transaction():
                    context.run_migrations()

        if context.is_offline_mode():
            run_migrations_offline()
        else:
            run_migrations_online()
    """))

    script_py = alembic_dir / "script.py.mako"
    script_py.write_text(dedent('''
        """${message}"""
        from alembic import op
        import sqlalchemy as sa
        ${imports if imports else ""}

        revision = ${repr(up_revision)}
        down_revision = ${repr(down_revision)}
        branch_labels = ${repr(branch_labels)}
        depends_on = ${repr(depends_on)}

        def upgrade():
            ${upgrades if upgrades else "pass"}

        def downgrade():
            ${downgrades if downgrades else "pass"}
    '''))

    alembic_ini = Path(temp_dir) / "alembic.ini"
    alembic_ini.write_text(dedent(f"""
        [alembic]
        script_location = {alembic_dir}
        sqlalchemy.url = sqlite:///:memory:

        [loggers]
        keys = root

        [handlers]
        keys = console

        [formatters]
        keys = generic

        [logger_root]
        level = WARN
        handlers = console

        [handler_console]
        class = StreamHandler
        args = (sys.stderr,)
        level = NOTSET
        formatter = generic

        [formatter_generic]
        format = %(levelname)-5.5s [%(name)s] %(message)s
    """))

    yield temp_dir, alembic_ini

    shutil.rmtree(temp_dir)


def test_alembic_detects_new_table_with_annotations(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Users(Table, table_name='users', metadata=metadata):
        id: int
        name: str
        email: str
        age: int

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    assert len(diff) > 0

    add_table_ops = [op for op in diff if op[0] == 'add_table']
    assert len(add_table_ops) == 1

    table = add_table_ops[0][1]
    assert table.name == 'users'
    assert 'id' in [c.name for c in table.columns]
    assert 'name' in [c.name for c in table.columns]
    assert 'email' in [c.name for c in table.columns]
    assert 'age' in [c.name for c in table.columns]


def test_alembic_detects_new_table_with_sa_columns(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Posts(Table, table_name='posts', metadata=metadata):
        id = Column(String, primary_key=True)
        title = Column(String(255), nullable=False)
        content = Column(String)
        published = Column(Boolean, server_default='false')

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    add_table_ops = [op for op in diff if op[0] == 'add_table']
    assert len(add_table_ops) == 1

    table = add_table_ops[0][1]
    assert table.name == 'posts'

    id_col = next(c for c in table.columns if c.name == 'id')
    assert id_col.primary_key

    title_col = next(c for c in table.columns if c.name == 'title')
    assert not title_col.nullable


def test_alembic_detects_mixed_table_definition(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True)

    class Comments(Table, table_name='comments', metadata=metadata):
        id = Column(String, primary_key=True)
        post_id: str
        user_id = Column(String, ForeignKey('users.id'))
        content: str
        upvotes: int
        created_at = Column(TIMESTAMP, nullable=False)

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    add_table_ops = [op for op in diff if op[0] == 'add_table']
    assert len(add_table_ops) == 2

    table = next(op[1] for op in add_table_ops if op[1].name == 'comments')
    assert table.name == 'comments'

    column_names = [c.name for c in table.columns]
    assert 'id' in column_names
    assert 'post_id' in column_names
    assert 'user_id' in column_names
    assert 'content' in column_names
    assert 'upvotes' in column_names
    assert 'created_at' in column_names

    user_id_col = next(c for c in table.columns if c.name == 'user_id')
    assert len(list(user_id_col.foreign_keys)) == 1


def test_alembic_detects_column_additions(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa_text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))

    class Users(Table, table_name='users', metadata=metadata):
        id: int
        name: str
        email: str
        age: int

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    add_column_ops = [op for op in diff if op[0] == 'add_column']
    assert len(add_column_ops) == 2

    added_column_names = [op[3].name for op in add_column_ops]
    assert 'email' in added_column_names
    assert 'age' in added_column_names


def test_alembic_detects_column_removals(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa_text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, old_field TEXT, deprecated TEXT)"))

    class Users(Table, table_name='users', metadata=metadata):
        id: int
        name: str

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    remove_column_ops = [op for op in diff if op[0] == 'remove_column']
    assert len(remove_column_ops) == 2

    removed_column_names = [op[3].name for op in remove_column_ops]
    assert 'old_field' in removed_column_names
    assert 'deprecated' in removed_column_names


def test_alembic_no_spurious_changes_for_identical_schema(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(Integer, primary_key=True)
        name = Column(String)
        email = Column(String)

    metadata.create_all(engine)

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    assert len(diff) == 0


def test_alembic_handles_foreign_keys_correctly(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Users(Table, table_name='users', metadata=metadata):
        id = Column(String, primary_key=True)

    class Posts(Table, table_name='posts', metadata=metadata):
        id = Column(String, primary_key=True)
        user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'))
        title: str

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    add_table_ops = [op for op in diff if op[0] == 'add_table']
    assert len(add_table_ops) == 2

    posts_table = next(op[1] for op in add_table_ops if op[1].name == 'posts')
    user_id_col = next(c for c in posts_table.columns if c.name == 'user_id')

    fks = list(user_id_col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == 'users'


def test_alembic_with_schema_parameter(temp_alembic_env):
    temp_dir, alembic_ini = temp_alembic_env
    metadata = MetaData()
    engine = create_engine("sqlite:///:memory:")

    class Users(Table, table_name='users', metadata=metadata, schema='public'):
        id: int
        name: str

    cfg = Config(str(alembic_ini))
    cfg.attributes['target_metadata'] = metadata
    cfg.attributes['connection'] = engine

    with engine.begin() as connection:
        mc = MigrationContext.configure(connection)
        diff = compare_metadata(mc, metadata)

    add_table_ops = [op for op in diff if op[0] == 'add_table']
    assert len(add_table_ops) == 1

    table = add_table_ops[0][1]
    assert table.schema == 'public'


from sqlalchemy import text as sa_text