import argparse

from app.db.init_db import init_db
from app.services.formula1_rss_source import Formula1RSSSource
from app.services.news_ingestion_service import NewsIngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Formula1 RSS news and save them into PostgreSQL.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of articles to ingest.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    source = Formula1RSSSource()
    service = NewsIngestionService()
    saved_articles = service.ingest(source=source, limit=args.limit)

    print(f"Ingested {len(saved_articles)} Formula1 articles.")
    for article in saved_articles:
        print(f"- {article.title} | {article.article_url}")


if __name__ == "__main__":
    main()
