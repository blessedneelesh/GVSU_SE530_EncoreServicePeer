import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv

# 1. Add project root to python path to prevent import failures in WSL
sys.path.append(os.getcwd())

# 2. Load your .env file
load_dotenv()

# 3. Import your Base
from app.db.base import Base

# 4. Force Alembic to read every single model file right now
from app.models.user import User
from app.models.auth import Role, UserRole, RefreshToken, RevokedToken
from app.models.concert import Concert
from app.models.invoice import Invoice
from app.models.comment import Comment

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 5. Safely grab and format the DATABASE_URL
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL is completely missing! Check your .env file.")

# Enforce psycopg2 driver to prevent crashes
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")



# Inject it into Alembic
config.set_main_option("sqlalchemy.url", db_url)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
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
        config.get_section(config.config_ini_section, {}),
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