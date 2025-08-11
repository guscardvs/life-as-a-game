from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.script import ScriptDirectory
from escudeiro.autodiscovery import (
    RuntimeAutoDiscovery,
    runtime_child_of,
    runtime_instance_of,
)
from sqlalchemy import Table, engine_from_config, pool

from app.settings import DATABASE_CONFIG, ROOT
from app.utils.database import AbstractEntity

_child_validator = runtime_child_of(AbstractEntity)
_instance_validator = runtime_instance_of(Table)


def _multivalidate(val: Any) -> bool:
    """Validate if the value is a child of Entity or an instance of Table."""
    return _child_validator(val) or _instance_validator(val)


# env.py
def process_revision_directives(
    context: Any, __revision__: Any, directives: Any
):
    # extract Migration
    migration_script = directives[0]
    # extract current head revision
    head_revision = ScriptDirectory.from_config(
        context.config
    ).get_current_head()

    if head_revision is None:
        # edge case with first migration
        new_rev_id = 1
    else:
        # default branch with incrementation
        last_rev_id = int(head_revision.lstrip("0"))
        new_rev_id = last_rev_id + 1
    # fill zeros up to 4 digits: 1 -> 0001
    migration_script.rev_id = f"{new_rev_id:04}"


_ = RuntimeAutoDiscovery(_multivalidate, ROOT, exclude=("utils",)).asdict
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = AbstractEntity.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = DATABASE_CONFIG.make_uri(is_asyncio=False).encode()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    config.set_main_option(
        "sqlalchemy.url",
        DATABASE_CONFIG.make_uri(is_asyncio=False).encode(),
    )
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
