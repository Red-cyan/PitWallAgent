import argparse
import json
from pathlib import Path

from app.db.engine import SessionLocal
from app.db.init_db import init_db
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleCreate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import news articles from a JSON file.")
    parser.add_argument("input_file", type=Path, help="Path to a JSON file containing article objects.")
    return parser.parse_args()


def load_articles(input_file: Path) -> list[dict]:
    with input_file.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, list):
        raise ValueError("Input JSON must be an array of article objects.")

    return payload


def main() -> None:
    args = parse_args()
    init_db()
    articles = load_articles(args.input_file)

    with SessionLocal() as session:
        repository = NewsRepository(session)
        imported_count = 0

        for item in articles:
            article = NewsArticleCreate.model_validate(item)
            repository.upsert_article(article)
            imported_count += 1

    print(f"Imported {imported_count} articles from {args.input_file}.")


if __name__ == "__main__":
    main()
