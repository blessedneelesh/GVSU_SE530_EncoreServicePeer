import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv

# 1. Import your Base
from app.db.base import Base

# 2. Force Alembic to read every single model file right now
from app.models.user import User
from app.models.auth import Role, UserRole, RefreshToken, RevokedToken
from app.models.concert import Concert
from app.models.invoice import Invoice
from app.models.comment import Comment

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point target_metadata to your Base
target_metadata = Base.metadata

# Inject the DATABASE_URL directly into the Alembic configuration section
config_section = config.get_section(config.config_ini_section, {})
config_section["sqlalchemy.url"] = os.getenv("DATABASE_URL")

def run_migrations_offline() -> None:
    url = config_section.get("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()