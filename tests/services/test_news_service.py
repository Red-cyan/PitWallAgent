from app.services.news_service import NewsService


def test_news_service_expands_chinese_team_alias_to_english() -> None:
    service = NewsService()

    expanded = service._expand_query_aliases("关于迈凯伦的新闻")

    assert "迈凯伦" in expanded
    assert "McLaren" in expanded


def test_news_service_expands_chinese_driver_alias_to_english() -> None:
    service = NewsService()

    expanded = service._expand_query_aliases("维斯塔潘最新消息")

    assert "维斯塔潘" in expanded
    assert "Max Verstappen" in expanded


def test_news_service_keeps_english_query_unchanged() -> None:
    service = NewsService()

    expanded = service._expand_query_aliases("McLaren upgrade")

    assert expanded == "McLaren upgrade"
