import argparse

from app.db.init_db import init_db
from app.services.news_backfill_service import NewsBackfillService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Formula1 news details for existing articles.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of articles to backfill.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all matched Formula1 articles instead of only those with missing content.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    service = NewsBackfillService()
    updated_articles = service.backfill_formula1_articles(
        limit=args.limit,
        only_missing_content=not args.all,
    )

    print(f"Backfilled {len(updated_articles)} Formula1 articles.")
    for article in updated_articles:
        print(f"- {article.id}: {article.title}")


if __name__ == "__main__":
    main()
