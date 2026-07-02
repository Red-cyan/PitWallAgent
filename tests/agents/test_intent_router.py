from app.agents.intent_router import IntentRouter


def test_intent_router_routes_regulation_queries() -> None:
    router = IntentRouter()

    assert router.route("红旗是什么？") == "regulation"


def test_intent_router_routes_race_queries() -> None:
    router = IntentRouter()

    assert router.route("下一站比赛是什么时候？") == "race"
    assert router.route("车手积分榜第二名是谁？") == "race"
    assert router.route("上一站大奖赛是什么？") == "race"


def test_intent_router_routes_news_queries_by_default() -> None:
    router = IntentRouter()

    assert router.route("今天F1有什么新闻？") == "news"


def test_intent_router_uses_fallback_intent_for_follow_up() -> None:
    router = IntentRouter()

    assert router.route("那呢？", fallback_intent="race") == "race"
