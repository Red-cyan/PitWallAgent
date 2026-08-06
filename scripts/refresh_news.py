from __future__ import annotations

import argparse

from app.services.news_ingestion_service import NewsIngestionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh F1 news from RSS sources.")
    parser.add_argument("--limit", type=int, default=20, help="Articles per source.")
    args = parser.parse_args()

    service = NewsIngestionService()
    saved = service.ingest(limit=args.limit)
    print(f"ingested {len(saved)} articles across {len(service.sources)} sources.")
    for article in saved[:10]:
        published = article.published_at.isoformat() if article.published_at else "-"
        print(f"- [{article.source_name}] {published} {article.title[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
