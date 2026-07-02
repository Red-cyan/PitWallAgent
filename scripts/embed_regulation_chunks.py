# ruff: noqa: E402
import argparse
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate embeddings for regulation chunks.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of chunks to process.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate embeddings even if the chunk already has one.",
    )
    return parser.parse_args()


def load_target_records(limit: int | None, overwrite: bool) -> list[RegulationChunkRecord]:
    statement = select(RegulationChunkRecord).order_by(RegulationChunkRecord.id)

    if not overwrite:
        statement = statement.where(RegulationChunkRecord.embedding.is_(None))

    if limit is not None:
        statement = statement.limit(limit)

    with SessionLocal() as session:
        return session.execute(statement).scalars().all()


def chunk_records(
    records: list[RegulationChunkRecord],
    batch_size: int,
) -> list[list[RegulationChunkRecord]]:
    return [records[index : index + batch_size] for index in range(0, len(records), batch_size)]


def update_embeddings(records: list[RegulationChunkRecord], overwrite: bool) -> int:
    if not records:
        return 0

    from app.rag.embedding.factory import build_embedding_service

    embedding_service = build_embedding_service()
    batches = chunk_records(records, settings.regulation_embedding_batch_size)
    updated = 0

    with SessionLocal.begin() as session:
        for batch_index, batch in enumerate(batches, start=1):
            texts = [record.content for record in batch]
            embeddings = embedding_service.embed_texts(texts)

            for record, embedding in zip(batch, embeddings, strict=True):
                db_record = session.get(RegulationChunkRecord, record.id)
                if db_record is None:
                    continue
                if db_record.embedding is not None and not overwrite:
                    continue

                db_record.embedding = embedding
                updated += 1

            print(f"Processed batch {batch_index}/{len(batches)}")

    return updated


def main() -> None:
    args = parse_args()
    records = load_target_records(limit=args.limit, overwrite=args.overwrite)
    updated = update_embeddings(records, overwrite=args.overwrite)

    print(f"Embedding model: {settings.regulation_embedding_model}")
    print(f"Updated embeddings: {updated}")


if __name__ == "__main__":
    main()
