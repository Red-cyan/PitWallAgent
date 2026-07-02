from app.agents.intent_router import IntentRouter


def test_intent_router_routes_regulation_queries() -> None:
    router = IntentRouter()

    assert router.route("红旗是什么？") == "regulation"


def test_intent_router_routes_race_queries() -> None:
    router = IntentRouter()

    assert router.route("下一站比赛是什么时候？") == "race"
    assert router.route("现在谁是车手积分榜第一名") == "race"
    assert router.route("现在哪只车队是第一名") == "race"


def test_intent_router_defaults_to_general_for_non_matching_queries() -> None:
    router = IntentRouter()

    assert router.route("你好") == "general"


def test_intent_router_uses_news_when_explicitly_requested() -> None:
    router = IntentRouter()

    assert router.route("今天 F1 有什么新闻？") == "news"


def test_intent_router_uses_fallback_intent_for_follow_up() -> None:
    router = IntentRouter()

    assert router.route("那呢？", fallback_intent="race") == "race"
