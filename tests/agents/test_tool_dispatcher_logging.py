import json
import logging

from app.agents.tool_dispatcher import ToolDispatcher


class StubNewsTool:
    name = "news_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "news_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


class StubRaceTool:
    name = "race_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "race_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


class StubRegulationTool:
    name = "regulation_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "regulation_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


class StubGeneralTool:
    name = "general_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "general_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


def test_tool_dispatcher_emits_structured_logs(caplog) -> None:
    dispatcher = ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
        general_tool=StubGeneralTool(),
    )
    plan = {
        "tool_name": "race_tool",
        "action": "get_next_race",
        "params": {},
    }

    with caplog.at_level(logging.INFO, logger="pitwall.dispatcher"):
        result = dispatcher.execute_plan(plan)

    assert result.tool_name == "race_tool"
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.dispatcher"]
    assert payloads[0]["event"] == "tool_plan_executing"
    assert payloads[-1]["event"] == "tool_plan_completed"
    assert payloads[-1]["success"] is True
