from app.agents.intent_router import IntentRouter


def test_intent_router_routes_regulation_queries() -> None:
    router = IntentRouter()

    assert router.route("红旗是什么？") == "regulation"
    assert router.route("维修区超速是什么") == "regulation"
    assert router.route("危险驾驶是什么") == "regulation"
    assert router.route("赛会干事会怎么处罚危险驾驶") == "regulation"


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
    assert router.route("他现在排第几？", fallback_intent="race") == "race"
    assert router.route("前5名是谁", fallback_intent="race") == "race"
    assert router.route("我问你第5名啊，不是第一名", fallback_intent="race") == "race"
    assert router.route("？", fallback_intent="race") == "race"


def test_intent_router_does_not_treat_explicit_rank_query_as_context_follow_up() -> None:
    router = IntentRouter()

    assert router.looks_like_follow_up("车手积分榜第4名是哪位") is False
    assert router.route("车手积分榜第4名是哪位", fallback_intent="regulation") == "race"
