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
    assert router.route("谁夺冠了") == "race"
    assert router.route("谁赢得了比赛") == "race"
    assert router.route("上一场比赛谁赢了") == "race"


def test_intent_router_prefers_news_over_race_for_entity_news() -> None:
    router = IntentRouter()

    assert router.route("关于迈凯伦有什么新闻？") == "news"
    assert router.route("诺里斯的最新消息") == "news"
    assert router.route("迈凯伦积分榜") == "race"
    assert router.route("今天几点比赛") == "race"


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


def test_intent_router_routes_pit_lane_phrasings_to_regulation_not_strategy() -> None:
    router = IntentRouter()

    assert router.route("What is an unsafe release from the pit lane?") == "regulation"
    assert router.route("pit lane speeding") == "regulation"
    assert router.route("What is the pit lane speed limit rule?") == "regulation"
    assert router.route("维修区超速是什么") == "regulation"


def test_intent_router_keeps_strategy_phrasings_as_strategy() -> None:
    router = IntentRouter()

    assert router.route("什么时候该进站") == "strategy"
    assert router.route("该不该进站") == "strategy"
    assert router.route("pit stop strategy") == "strategy"
    assert router.route("什么时候进站换胎") == "strategy"
