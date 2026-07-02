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


def build_dispatcher() -> ToolDispatcher:
    return ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
    )


def test_tool_dispatcher_builds_news_plan() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="news", message="今天有什么新闻？")

    assert plan["tool_name"] == "news_tool"
    assert plan["action"] == "list_recent"


def test_tool_dispatcher_builds_race_plan_for_next_race() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="race", message="下一站比赛是什么时候？")

    assert plan["tool_name"] == "race_tool"
    assert plan["action"] == "get_next_race"


def test_tool_dispatcher_builds_race_plan_for_previous_race() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="race", message="上一站比赛是什么？")

    assert plan["tool_name"] == "race_tool"
    assert plan["action"] == "get_previous_race"


def test_tool_dispatcher_executes_regulation_plan() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="regulation", message="红旗是什么？")
    result = dispatcher.execute_plan(plan)

    assert result.tool_name == "regulation_tool"
    assert result.payload["question"] == "红旗是什么？"
