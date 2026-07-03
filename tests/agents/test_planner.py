from app.agents.planner import LLMQueryPlanner


class StubIntentRouter:
    def route(self, message: str, fallback_intent: str | None = None) -> str:
        if "红旗" in message:
            return "regulation"
        if "积分榜" in message or "车队" in message:
            return "race"
        return "general"


class StubToolDispatcher:
    def build_plan(self, intent: str, message: str) -> dict:
        plans = {
            "regulation": {"tool_name": "regulation_tool", "action": "ask", "params": {"question": message}},
            "race": {"tool_name": "race_tool", "action": "get_driver_standings", "params": {}},
            "general": {"tool_name": "general_tool", "action": "answer", "params": {"question": message}},
        }
        return plans[intent]


class StubLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_max_tokens: int | None = None
        self.last_timeout: float | None = None

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        self.last_max_tokens = max_tokens
        self.last_timeout = timeout
        return self.response


class FailingLLMClient:
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        raise RuntimeError("boom")


def test_planner_uses_llm_plan_when_valid() -> None:
    llm_client = StubLLMClient('{"intent":"general","action":"answer","params":{}}')
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=llm_client,
    )

    plan = planner.plan("解释一下 DRS 规则争议")

    assert plan["intent"] == "general"
    assert plan["tool_name"] == "general_tool"
    assert plan["params"]["question"] == "解释一下 DRS 规则争议"
    assert llm_client.last_max_tokens == 160
    assert llm_client.last_timeout == 4.0


def test_planner_keeps_casual_general_messages_on_heuristics() -> None:
    llm_client = StubLLMClient('{"intent":"regulation","action":"ask","params":{}}')
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=llm_client,
    )

    plan = planner.plan("你好")

    assert plan["intent"] == "general"
    assert plan["tool_name"] == "general_tool"
    assert llm_client.last_max_tokens is None


def test_planner_uses_llm_to_route_ambiguous_rule_question_to_regulation() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"regulation","action":"ask","params":{}}'),
    )

    plan = planner.plan("维修通道白线能不能压")

    assert plan["intent"] == "regulation"
    assert plan["tool_name"] == "regulation_tool"
    assert plan["action"] == "ask"
    assert plan["params"]["question"] == "维修通道白线能不能压"


def test_planner_does_not_call_llm_for_high_confidence_heuristic_race_query() -> None:
    llm_client = StubLLMClient('{"intent":"general","action":"answer","params":{}}')
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=llm_client,
    )

    plan = planner.plan("车队积分榜第一是谁")

    assert plan["intent"] == "race"
    assert plan["tool_name"] == "race_tool"
    assert llm_client.last_max_tokens is None


def test_planner_falls_back_to_heuristics_when_llm_fails() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=FailingLLMClient(),
    )

    plan = planner.plan("红旗是什么？")

    assert plan["intent"] == "regulation"
    assert plan["tool_name"] == "regulation_tool"
    assert plan["action"] == "ask"


def test_planner_rejects_invalid_llm_action_and_falls_back() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"race","action":"unsupported","params":{}}'),
    )

    plan = planner.plan("现在哪只车队是第一名")

    assert plan["intent"] == "race"
    assert plan["tool_name"] == "race_tool"


def test_planner_supports_news_insights_with_article_id() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"news","action":"get_insights","params":{"article_id":"42"}}'),
    )

    plan = planner.plan("分析新闻 42")

    assert plan["intent"] == "news"
    assert plan["tool_name"] == "news_tool"
    assert plan["action"] == "get_insights"
    assert plan["params"]["article_id"] == 42


def test_planner_rejects_news_article_action_without_id_and_falls_back() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"news","action":"get_rules_analysis","params":{}}'),
    )

    plan = planner.plan("分析这篇新闻和规则的关系")

    assert plan["intent"] == "general"
    assert plan["tool_name"] == "general_tool"
