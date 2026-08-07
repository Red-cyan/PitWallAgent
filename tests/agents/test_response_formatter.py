from app.agents.response_formatter import AgentResponseFormatter


def build_race(round_number: int, name: str, country: str, race_time: str) -> dict:
    return {
        "season": 2026,
        "round_number": round_number,
        "grand_prix_name": name,
        "circuit_name": "Silverstone Circuit" if "British" in name else "Red Bull Ring",
        "country": country,
        "start_date": "2026-07-03T11:30:00Z",
        "end_date": race_time,
        "sessions": [
            {"name": "Practice 1", "start_time": "2026-07-03T11:30:00Z"},
            {"name": "Qualifying", "start_time": "2026-07-04T14:00:00Z"},
            {"name": "Race", "start_time": race_time},
        ],
        "source": "stub",
    }


def test_response_formatter_formats_full_schedule() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="今年完整赛历是什么",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "action": "list_schedule",
            "schedule": [
                build_race(8, "Austrian Grand Prix", "Austria", "2026-06-28T13:00:00Z"),
                build_race(9, "British Grand Prix", "United Kingdom", "2026-07-05T14:00:00Z"),
            ],
        },
        error=None,
    )

    assert answer.startswith("当前完整赛历：")
    assert "R8 Austrian Grand Prix" in answer
    assert "R9 British Grand Prix" in answer
    assert "2026-07-05 22:00 CST" in answer


def test_response_formatter_formats_next_race_with_session_times() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="比赛日期和具体时间是多少",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "action": "get_next_race",
            "race": build_race(9, "British Grand Prix", "United Kingdom", "2026-07-05T14:00:00Z"),
        },
        error=None,
    )

    assert "下一站比赛" in answer
    assert "British Grand Prix" in answer
    assert "Silverstone Circuit" in answer
    assert "2026-07-05 22:00 CST" in answer
    assert "Qualifying 2026-07-04 22:00 CST" in answer


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


def test_response_formatter_formats_top_constructor_standings() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="车队积分榜前五名是谁",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "standings": [
                {"position": 1, "team_name": "Mercedes", "points": 302},
                {"position": 2, "team_name": "Ferrari", "points": 204},
                {"position": 3, "team_name": "McLaren", "points": 159},
                {"position": 4, "team_name": "Red Bull", "points": 115},
                {"position": 5, "team_name": "Williams", "points": 64},
                {"position": 6, "team_name": "Aston Martin", "points": 52},
            ]
        },
        error=None,
    )

    assert answer.startswith("当前车队积分榜前 5 名：")
    assert "1. Mercedes | 302分" in answer
    assert "5. Williams | 64分" in answer
    assert "6. Aston Martin" not in answer


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


def test_response_formatter_does_not_fallback_to_first_when_position_missing() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="车队积分榜第5名是谁",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "standings": [
                {"position": 1, "team_name": "Mercedes", "points": 302},
                {"position": 2, "team_name": "Ferrari", "points": 204},
                {"position": 3, "team_name": "McLaren", "points": 159},
            ]
        },
        error=None,
    )

    assert answer == "当前只获取到前 3 名车队积分榜数据，无法确认第 5 名。"
    assert "Mercedes，积分 302" not in answer


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


def test_response_formatter_formats_news_insights() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="分析新闻 42",
        intent="news",
        tool_name="news_tool",
        success=True,
        result={
            "insights": {
                "summary": "这篇新闻关注迈凯伦升级。",
                "key_points": ["升级集中在底板", "车队预计排位受益"],
            }
        },
        error=None,
    )

    assert answer == "这篇新闻关注迈凯伦升级。 关键点：升级集中在底板；车队预计排位受益。"


def test_response_formatter_formats_race_results_with_winner_and_podium() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="谁赢了",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "race_result": {
                "grand_prix_name": "Austrian Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 25},
                    {"position": 2, "driver_name": "Charles Leclerc", "team_name": "Ferrari", "points": 18},
                    {"position": 3, "driver_name": "Max Verstappen", "team_name": "Red Bull", "points": 15},
                ],
            }
        },
        error=None,
    )

    assert "Andrea Kimi Antonelli" in answer
    assert "赢得 Austrian Grand Prix" in answer
    assert "Charles Leclerc" in answer


def test_response_formatter_highlights_requested_driver_in_results() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="勒克莱尔上一站第几名",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "race_result": {
                "grand_prix_name": "Austrian Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 25},
                    {"position": 2, "driver_name": "Charles Leclerc", "team_name": "Ferrari", "points": 18},
                ],
            }
        },
        error=None,
    )

    assert answer == "Charles Leclerc（Ferrari）在 Austrian Grand Prix 获得第 2 名。"


def test_response_formatter_appends_live_api_source_label() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="谁赢了",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "source": "jolpica_api",
            "fetched_at": "2026-08-06T12:00:00+00:00",
            "race_result": {
                "grand_prix_name": "Hungarian Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Lando Norris", "team_name": "McLaren", "points": 25},
                ],
            },
        },
        error=None,
    )

    assert "Lando Norris" in answer
    assert "数据源：Jolpica API" in answer


def test_response_formatter_discloses_local_seed_source() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="谁赢了",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "source": "local_seed",
            "race_result": {
                "grand_prix_name": "British Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 25},
                ],
            },
        },
        error=None,
    )

    assert "本地示例数据，仅演示用" in answer


def test_response_formatter_discloses_cached_source_with_timestamp() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="谁赢了",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "source": "jolpica_cached",
            "fetched_at": "2026-08-06T12:00:00+00:00",
            "race_result": {
                "grand_prix_name": "Hungarian Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Lando Norris", "team_name": "McLaren", "points": 25},
                ],
            },
        },
        error=None,
    )

    assert "Jolpica API 缓存" in answer
    assert "缓存时间" in answer


def test_response_formatter_omits_source_label_for_unknown_source() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="谁赢了",
        intent="race",
        tool_name="race_tool",
        success=True,
        result={
            "race_result": {
                "grand_prix_name": "Austrian Grand Prix",
                "results": [
                    {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 25},
                ],
            }
        },
        error=None,
    )

    assert "数据源：" not in answer
