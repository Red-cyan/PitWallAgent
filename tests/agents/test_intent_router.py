from app.agents.intent_router import IntentRouter


def test_intent_router_routes_regulation_queries() -> None:
    router = IntentRouter()

    assert router.route("红旗是什么？") == "regulation"


def test_intent_router_routes_race_queries() -> None:
    router = IntentRouter()

    assert router.route("下一站比赛是什么时候？") == "race"


def test_intent_router_routes_news_queries_by_default() -> None:
    router = IntentRouter()

    assert router.route("今天F1有什么新闻？") == "news"
