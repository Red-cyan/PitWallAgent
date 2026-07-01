import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.db.engine import engine


def main() -> None:
    target_dim = settings.regulation_embedding_dim

    with engine.begin() as connection:
        connection.execute(text("UPDATE regulation_chunks SET embedding = NULL"))
        connection.execute(
            text(
                "ALTER TABLE regulation_chunks "
                f"ALTER COLUMN embedding TYPE vector({target_dim})"
            )
        )

    print(f"Resized regulation_chunks.embedding to vector({target_dim}).")


if __name__ == "__main__":
    main()
