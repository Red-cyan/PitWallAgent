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


def test_planner_parses_multi_step_plan() -> None:
    llm_response = (
        '{"steps":['
        '{"intent":"news","action":"search","params":{"query":"norris penalty"},"output_key":"news_hit"},'
        '{"intent":"regulation","action":"ask","params":{"question":"$ref:news_hit.summary"},"output_key":"rule_check"}'
        "]}"
    )
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient(llm_response),
    )

    plan = planner.plan("诺里斯最近的新闻，他上次违反了什么规则")

    assert plan["intent"] == "news"
    assert plan["tool_name"] == "news_tool"
    assert plan["action"] == "search"
    assert len(plan["steps"]) == 2

    first, second = plan["steps"]
    assert first["output_key"] == "news_hit"
    assert first["params"]["query"] == "norris penalty"
    assert second["intent"] == "regulation"
    assert second["tool_name"] == "regulation_tool"
    assert second["action"] == "ask"
    # 显式 $ref 引用不被 question 注入覆盖
    assert second["params"]["question"] == "$ref:news_hit.summary"


def test_planner_multi_step_injects_question_for_ask_steps() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient(
            '{"steps":['
            '{"intent":"news","action":"list_recent","params":{},"output_key":"a"},'
            '{"intent":"regulation","action":"ask","params":{},"output_key":"b"}'
            "]}"
        ),
    )

    plan = planner.plan("最新新闻里有什么规则问题")

    assert len(plan["steps"]) == 2
    assert plan["steps"][0]["params"]["limit"] == 5
    assert plan["steps"][1]["params"]["question"] == "最新新闻里有什么规则问题"


def test_planner_rejects_invalid_multi_step_and_falls_back() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient(
            '{"steps":['
            '{"intent":"news","action":"search","params":{},"output_key":"a"},'
            '{"intent":"race","action":"unsupported","params":{},"output_key":"b"}'
            "]}"
        ),
    )

    plan = planner.plan("车队积分榜第一是谁")

    # 非法多步计划 → 回退启发式（race 单步）
    assert plan["intent"] == "race"
    assert plan["tool_name"] == "race_tool"
    assert plan["action"] == "get_driver_standings"
    assert len(plan["steps"]) == 1


def test_planner_reassigns_duplicate_output_keys() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient(
            '{"steps":['
            '{"intent":"news","action":"list_recent","params":{},"output_key":"dup"},'
            '{"intent":"news","action":"list_recent","params":{},"output_key":"dup"}'
            "]}"
        ),
    )

    plan = planner.plan("最近有什么新闻，再说一次")

    keys = [step["output_key"] for step in plan["steps"]]
    assert keys[0] == "dup"
    assert keys[1] == "step_1"
    assert len(set(keys)) == 2


def test_planner_multi_intent_signal_uses_larger_token_budget() -> None:
    llm_client = StubLLMClient('{"intent":"general","action":"answer","params":{}}')
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=llm_client,
    )

    planner.plan("诺里斯最近的新闻，他上次违反了什么规则")

    assert llm_client.last_max_tokens == 320


def test_planner_heuristic_plan_always_has_steps() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"general","action":"answer","params":{}}'),
    )

    plan = planner.plan("车队积分榜第一是谁")

    assert plan["intent"] == "race"
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["intent"] == "race"
    assert plan["steps"][0]["tool_name"] == "race_tool"
    assert plan["steps"][0]["output_key"] == "step_0"


def test_planner_accepts_ref_article_id_in_multi_step_plan() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient(
            '{"steps":['
            '{"intent":"news","action":"search","params":{"query":"norris"},"output_key":"hit"},'
            '{"intent":"news","action":"get_article","params":{"article_id":"$ref:hit.articles.0.id"},"output_key":"article"}'
            "]}"
        ),
    )

    # $ref 引用在规划期不校验为整数，避免多步计划整体失败
    plan = planner.plan("诺里斯最近的新闻")

    assert len(plan["steps"]) == 2
    assert plan["steps"][1]["params"]["article_id"] == "$ref:hit.articles.0.id"
