# ruff: noqa: E402
import json
import re
import sys
from pathlib import Path
from typing import cast

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.schema import Table

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord


CHUNKS_FILE = Path("data/regulations/processed/chunks.json")


def extract_section_code(document_title: str) -> str | None:
    """从文档标题中提取分册编号。"""

    match = re.search(r"Section\s+([A-Z])", document_title)
    if not match:
        return None

    return f"Section {match.group(1)}"


def load_chunks() -> list[dict]:
    with CHUNKS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_rows(chunk_data: list[dict]) -> list[dict]:
    rows: list[dict] = []

    for item in chunk_data:
        rows.append(
            {
                "chunk_id": item["chunk_id"],
                "document_title": item["document_title"],
                "section_code": extract_section_code(item["document_title"]),
                "article": item.get("article"),
                "page": item.get("page"),
                "content": item["content"],
                "embedding": None,
                "metadata": {
                    "source": "fia_regulation_pdf",
                    "ingest_version": 1,
                },
            }
        )

    return rows


def upsert_chunks(rows: list[dict]) -> int:
    if not rows:
        return 0

    table = cast(Table, RegulationChunkRecord.__table__)
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.chunk_id],
        set_={
            "document_title": statement.excluded.document_title,
            "section_code": statement.excluded.section_code,
            "article": statement.excluded.article,
            "page": statement.excluded.page,
            "content": statement.excluded.content,
            "metadata": statement.excluded.metadata,
        },
    )

    with SessionLocal.begin() as session:
        result = cast(CursorResult, session.execute(statement))

    return result.rowcount or 0


def main() -> None:
    chunk_data = load_chunks()
    rows = build_rows(chunk_data)
    affected_rows = upsert_chunks(rows)

    print(f"Imported {len(rows)} chunks into regulation_chunks.")
    print(f"Upsert affected rows: {affected_rows}")


if __name__ == "__main__":
    main()
