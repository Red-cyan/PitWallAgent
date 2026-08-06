from typing import Any, cast

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


def build_dispatcher() -> ToolDispatcher:
    return ToolDispatcher(
        news_tool=cast(Any, StubNewsTool()),
        race_tool=cast(Any, StubRaceTool()),
        regulation_tool=cast(Any, StubRegulationTool()),
        general_tool=cast(Any, StubGeneralTool()),
    )


def test_tool_dispatcher_builds_news_plan() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="news", message="今天有什么新闻？")

    assert plan["tool_name"] == "news_tool"
    assert plan["action"] == "list_recent"


def test_tool_dispatcher_routes_topic_news_to_search() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="news", message="关于迈凯伦的最新消息")

    assert plan["tool_name"] == "news_tool"
    assert plan["action"] == "search"
    assert "迈凯伦" in plan["params"]["query"]


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


def test_tool_dispatcher_routes_bare_team_names_to_constructor_standings() -> None:
    dispatcher = build_dispatcher()

    for team in ("法拉利", "红牛", "迈凯伦", "Ferrari", "Red Bull"):
        plan = dispatcher.build_plan(intent="race", message=team)

        assert plan["tool_name"] == "race_tool"
        assert plan["action"] == "get_constructor_standings"


def test_tool_dispatcher_routes_result_queries_to_race_results() -> None:
    dispatcher = build_dispatcher()

    for message in (
        "谁赢了上一站",
        "英国站冠军是谁",
        "维斯塔潘上一站第几名",
        "昨天比赛结果怎么样",
        "谁赢得了比赛",
        "谁夺冠了",
        "上一场比赛谁赢了",
        "哪支车队拿下了冠军",
    ):
        plan = dispatcher.build_plan(intent="race", message=message)

        assert plan["tool_name"] == "race_tool"
        assert plan["action"] == "get_race_results"


def test_tool_dispatcher_keeps_schedule_question_out_of_results() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="race", message="上一站比赛是什么时候？")

    assert plan["action"] == "get_previous_race"


def test_tool_dispatcher_builds_race_plan_for_next_race_time_question() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="race", message="比赛日期和具体时间是多少")

    assert plan["tool_name"] == "race_tool"
    assert plan["action"] == "get_next_race"


def test_tool_dispatcher_builds_race_plan_for_constructor_leader_question() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="race", message="现在哪只车队是第一名")

    assert plan["tool_name"] == "race_tool"
    assert plan["action"] == "get_constructor_standings"


def test_tool_dispatcher_builds_general_plan() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="general", message="你好")

    assert plan["tool_name"] == "general_tool"
    assert plan["action"] == "answer"
    assert plan["params"]["question"] == "你好"


def test_tool_dispatcher_executes_regulation_plan() -> None:
    dispatcher = build_dispatcher()

    plan = dispatcher.build_plan(intent="regulation", message="红旗是什么？")
    result = dispatcher.execute_plan(plan)

    assert result.tool_name == "regulation_tool"
    assert result.payload["question"] == "红旗是什么？"
