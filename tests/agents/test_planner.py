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

    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        return self.response


class FailingLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0) -> str:
        raise RuntimeError("boom")


def test_planner_uses_llm_plan_when_valid() -> None:
    planner = LLMQueryPlanner(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        llm_client=StubLLMClient('{"intent":"general","action":"answer","params":{}}'),
    )

    plan = planner.plan("你好")

    assert plan["intent"] == "general"
    assert plan["tool_name"] == "general_tool"
    assert plan["params"]["question"] == "你好"


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
