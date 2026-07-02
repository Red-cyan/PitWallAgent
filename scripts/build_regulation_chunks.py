# ruff: noqa: E402
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.knowledge_service import KnowledgeService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the regulation knowledge corpus.")
    parser.add_argument("--raw-dir", default="data/regulations/raw", help="Directory containing raw PDFs.")
    parser.add_argument(
        "--output",
        default="data/regulations/processed/chunks.json",
        help="Output path for the generated chunk manifest.",
    )
    parser.add_argument("--skip-json", action="store_true", help="Skip writing chunks.json.")
    parser.add_argument("--skip-db", action="store_true", help="Skip persisting chunks to the database.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    knowledge_service = KnowledgeService()
    summary = knowledge_service.ingest_regulations(
        raw_dir=args.raw_dir,
        output_path=args.output,
        persist_json=not args.skip_json,
        persist_db=not args.skip_db,
        include_embeddings=not args.skip_embeddings,
    )

    print(f"Documents ingested: {summary.document_count}")
    print(f"Chunks generated: {summary.chunk_count}")
    print(f"Embeddings generated: {summary.embedded_chunk_count}")
    if summary.output_path:
        print(f"Chunk manifest: {summary.output_path}")


if __name__ == "__main__":
    main()
