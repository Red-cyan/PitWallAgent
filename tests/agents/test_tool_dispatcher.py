from app.agents.tool_dispatcher import ToolDispatcher


class StubNewsTool:
    def invoke(self, **kwargs):
        class Result:
            tool_name = "news_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


class StubRaceTool:
    def invoke(self, **kwargs):
        class Result:
            tool_name = "race_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


class StubRegulationTool:
    def invoke(self, **kwargs):
        class Result:
            tool_name = "regulation_tool"
            success = True
            payload = kwargs
            error = None

        return Result()


def test_tool_dispatcher_uses_news_tool() -> None:
    dispatcher = ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
    )

    result = dispatcher.dispatch(intent="news", message="今天有什么新闻？")

    assert result.tool_name == "news_tool"
    assert result.payload["action"] == "list_recent"


def test_tool_dispatcher_uses_race_tool_for_next_race() -> None:
    dispatcher = ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
    )

    result = dispatcher.dispatch(intent="race", message="下一站比赛是什么时候？")

    assert result.tool_name == "race_tool"
    assert result.payload["action"] == "get_next_race"


def test_tool_dispatcher_uses_regulation_tool() -> None:
    dispatcher = ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
    )

    result = dispatcher.dispatch(intent="regulation", message="红旗是什么？")

    assert result.tool_name == "regulation_tool"
    assert result.payload["question"] == "红旗是什么？"
