from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your SQLAlchemy Base
from models import Base  # Change this path if needed

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set metadata for autogenerate
target_metadata = Base.metadata
