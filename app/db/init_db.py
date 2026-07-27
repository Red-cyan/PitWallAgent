from alembic import command
from alembic.config import Config


def init_db() -> None:
    """Upgrade the database to the latest versioned schema."""

    command.upgrade(Config("alembic.ini"), "head")
