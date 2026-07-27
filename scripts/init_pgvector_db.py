# ruff: noqa: E402
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import init_db


def main() -> None:
    init_db()
    print("Database upgraded to the latest Alembic revision.")


if __name__ == "__main__":
    main()
