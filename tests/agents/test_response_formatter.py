from app.agents.response_formatter import AgentResponseFormatter


def test_response_formatter_formats_full_driver_standings() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="当前完整车手积分榜是什么",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "standings": [
                {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                {"position": 2, "driver_name": "George Russell", "team_name": "Mercedes", "points": 131},
            ]
        },
        error=None,
    )

    assert answer.startswith("当前完整车手积分榜：")
    assert "1. Andrea Kimi Antonelli | Mercedes | 171分" in answer
    assert "2. George Russell | Mercedes | 131分" in answer


def test_response_formatter_formats_specific_driver_ranking() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="维斯塔潘排在第几名",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "standings": [
                {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                {"position": 4, "driver_name": "Max Verstappen", "team_name": "Red Bull", "points": 115},
            ]
        },
        error=None,
    )

    assert answer == "Max Verstappen 当前排在车手积分榜第 4 名，所属车队 Red Bull，积分 115。"


def test_response_formatter_resolves_driver_from_conversation_context() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message=(
            "User: 维斯塔潘是谁\n"
            "Assistant: 马克斯·维斯塔潘是 F1 车手。\n"
            "User: 他现在排在积分榜第几"
        ),
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "standings": [
                {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                {"position": 4, "driver_name": "Max Verstappen", "team_name": "Red Bull", "points": 115},
            ]
        },
        error=None,
    )

    assert answer == "Max Verstappen 当前排在车手积分榜第 4 名，所属车队 Red Bull，积分 115。"
