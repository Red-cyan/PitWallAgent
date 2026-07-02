from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from app.agents.intent_router import IntentRouter
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse
from app.services.agent_service import AgentService


def race(round_number: int, name: str, circuit: str, country: str, race_time: str) -> dict[str, Any]:
    return {
        "season": 2026,
        "round_number": round_number,
        "grand_prix_name": name,
        "circuit_name": circuit,
        "country": country,
        "start_date": "2026-07-03T11:30:00Z",
        "end_date": race_time,
        "sessions": [
            {"name": "Practice 1", "start_time": "2026-07-03T11:30:00Z"},
            {"name": "Qualifying", "start_time": "2026-07-04T14:00:00Z"},
            {"name": "Race", "start_time": race_time},
        ],
        "source": "eval_stub",
    }


class HeuristicPlanner:
    def __init__(self, router: IntentRouter, dispatcher: ToolDispatcher) -> None:
        self.router = router
        self.dispatcher = dispatcher

    def plan(self, message: str, fallback_intent: str | None = None) -> dict[str, Any]:
        lowered = message.lower()
        if "article 42" in lowered or "新闻 42" in message:
            if "规则" in message or "rule" in lowered:
                return {"intent": "news", "tool_name": "news_tool", "action": "get_rules_analysis", "params": {"article_id": 42}}
            if "分析" in message or "insight" in lowered:
                return {"intent": "news", "tool_name": "news_tool", "action": "get_insights", "params": {"article_id": 42}}
            return {"intent": "news", "tool_name": "news_tool", "action": "get_article", "params": {"article_id": 42}}
        intent = self.router.route(message, fallback_intent=fallback_intent)
        plan = self.dispatcher.build_plan(intent=intent, message=message)
        plan["intent"] = intent
        return plan


class EvalToolDispatcher(ToolDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.schedule = [
            race(8, "Austrian Grand Prix", "Red Bull Ring", "Austria", "2026-06-28T13:00:00Z"),
            race(9, "British Grand Prix", "Silverstone Circuit", "United Kingdom", "2026-07-05T14:00:00Z"),
            race(10, "Belgian Grand Prix", "Spa-Francorchamps", "Belgium", "2026-07-19T14:00:00Z"),
        ]

    def execute_plan(self, plan: dict) -> Any:
        action = plan["action"]
        tool_name = plan["tool_name"]

        class Result:
            def __init__(self, payload: dict[str, Any], success: bool = True, error: str | None = None) -> None:
                self.tool_name = tool_name
                self.success = success
                self.payload = payload
                self.error = error

        if tool_name == "race_tool":
            if action == "list_schedule":
                return Result({"action": action, "season": "current", "schedule": self.schedule})
            if action == "get_next_race":
                return Result({"action": action, "season": "current", "race": self.schedule[1]})
            if action == "get_previous_race":
                return Result({"action": action, "season": "current", "race": self.schedule[0]})
            if action == "get_driver_standings":
                return Result(
                    {
                        "action": action,
                        "standings": [
                            {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                            {"position": 2, "driver_name": "George Russell", "team_name": "Mercedes", "points": 131},
                            {"position": 4, "driver_name": "Max Verstappen", "team_name": "Red Bull", "points": 115},
                        ],
                    }
                )
            if action == "get_constructor_standings":
                return Result(
                    {
                        "action": action,
                        "standings": [
                            {"position": 1, "team_name": "Mercedes", "points": 302},
                            {"position": 2, "team_name": "Ferrari", "points": 204},
                            {"position": 3, "team_name": "McLaren", "points": 159},
                        ],
                    }
                )

        if tool_name == "regulation_tool":
            question = plan.get("params", {}).get("question", "")
            if "外星" in question or "alien" in question.lower():
                return Result(
                    {
                        "action": action,
                        "response": {
                            "answer": "未检索到相关 FIA 规则证据。为了避免编造规则，我不能基于当前资料给出确定答案。",
                            "answer_status": "insufficient_evidence",
                            "confidence": "low",
                            "evidence_count": 0,
                            "source_mode": "regulation_rag",
                            "citations": [],
                        },
                    }
                )
            return Result(
                {
                    "action": action,
                    "response": {
                        "answer": "根据 FIA 规则片段，红旗或安全车程序用于控制比赛风险，并应遵循赛事控制指令。关键依据：Section B。",
                        "answer_status": "answered",
                        "confidence": "medium",
                        "evidence_count": 2,
                        "source_mode": "regulation_rag",
                        "citations": [{"document_title": "Section B", "article": "ARTICLE 55", "page": 41}],
                    },
                }
            )

        if tool_name == "news_tool":
            if action == "get_article":
                return Result({"action": action, "article": {"title": "Article 42", "summary": "McLaren brings a floor upgrade."}})
            if action == "get_insights":
                return Result({"action": action, "insights": {"summary": "Article 42 关注 McLaren 升级。", "key_points": ["底板升级", "排位收益"]}})
            if action == "get_rules_analysis":
                return Result({"action": action, "rules_analysis": {"analysis_summary": "Article 42 可能涉及技术规则中的 floor/plank 合规边界。"}})
            return Result({"action": action, "articles": [{"title": "McLaren upgrade"}, {"title": "British GP preview"}, {"title": "Ferrari strategy"}]})

        if tool_name == "strategy_tool":
            return Result(
                {
                    "action": action,
                    "response": {
                        "recommendation": "只有在安全车降低进站损失且轮胎窗口合适时才进站。",
                        "confidence": "low",
                        "facts": ["缺少实时轮胎和交通数据"],
                        "analysis": ["需要把进站损失、轮胎衰退和赛道位置分开判断"],
                        "assumptions": [],
                        "cautions": ["实时赛况会改变判断"],
                    },
                }
            )

        return Result(
            {
                "action": action,
                "response": {
                    "answer": "你好，我可以回答 F1 的赛历、积分榜、规则、新闻、策略和稳定通用知识。",
                    "answer_status": "answered",
                    "confidence": "low",
                    "evidence_count": 0,
                    "source_mode": "general_llm",
                },
            }
        )


@dataclass
class EvalCase:
    name: str
    messages: list[str]
    expected_intent: str
    expected_tool: str
    expected_action: str
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    expected_status: str | None = None


CASES = [
    EvalCase("full-calendar-cn", ["今年完整赛历是什么"], "race", "race_tool", "list_schedule", ["Austrian Grand Prix", "British Grand Prix", "Belgian Grand Prix"]),
    EvalCase("full-calendar-typo", ["今年完整赛历是是什么"], "race", "race_tool", "list_schedule", ["当前完整赛历", "R9 British Grand Prix"]),
    EvalCase("all-schedule-cn", ["所有比赛赛程"], "race", "race_tool", "list_schedule", ["R8", "R10"]),
    EvalCase("season-calendar-en", ["full season calendar"], "race", "race_tool", "list_schedule", ["Austrian Grand Prix", "Belgian Grand Prix"]),
    EvalCase("schedule-cn", ["最新赛程是什么"], "race", "race_tool", "list_schedule", ["近期赛历", "British Grand Prix"]),
    EvalCase("calendar-cn", ["赛历"], "race", "race_tool", "list_schedule", ["近期赛历"]),
    EvalCase("next-race-cn", ["下一场比赛是哪个"], "race", "race_tool", "get_next_race", ["British Grand Prix", "Silverstone Circuit"]),
    EvalCase("next-race-en", ["next race"], "race", "race_tool", "get_next_race", ["British Grand Prix"]),
    EvalCase("previous-race-cn", ["上一站比赛是什么"], "race", "race_tool", "get_previous_race", ["Austrian Grand Prix"]),
    EvalCase("previous-race-en", ["previous race"], "race", "race_tool", "get_previous_race", ["Austrian Grand Prix"]),
    EvalCase("race-time-cn", ["比赛日期和具体时间是多少"], "race", "race_tool", "get_next_race", ["2026-07-05 22:00 CST", "Qualifying"]),
    EvalCase("race-time-en", ["when is the next race"], "race", "race_tool", "get_next_race", ["2026-07-05 22:00 CST"]),
    EvalCase("qualifying-time", ["下一站排位赛时间"], "race", "race_tool", "get_next_race", ["Qualifying 2026-07-04 22:00 CST"]),
    EvalCase("practice-time", ["下一站练习赛几点"], "race", "race_tool", "get_next_race", ["Practice 1"]),
    EvalCase("follow-up-race-time", ["下一场比赛是哪个", "比赛日期和具体时间是多少"], "race", "race_tool", "get_next_race", ["British Grand Prix", "2026-07-05 22:00 CST"]),
    EvalCase("driver-standings-cn", ["车手积分榜"], "race", "race_tool", "get_driver_standings", ["Andrea Kimi Antonelli", "171"]),
    EvalCase("driver-leader-cn", ["现在谁是车手积分榜第一名"], "race", "race_tool", "get_driver_standings", ["Andrea Kimi Antonelli", "第 1 名"]),
    EvalCase("driver-second-cn", ["车手积分榜第二名是谁"], "race", "race_tool", "get_driver_standings", ["George Russell", "第 2 名"]),
    EvalCase("driver-specific-cn", ["维斯塔潘排第几"], "race", "race_tool", "get_driver_standings", ["Max Verstappen", "第 4 名"]),
    EvalCase("driver-standings-en", ["driver standings"], "race", "race_tool", "get_driver_standings", ["Andrea Kimi Antonelli"]),
    EvalCase("constructor-standings-cn", ["车队积分榜"], "race", "race_tool", "get_constructor_standings", ["Mercedes", "302"]),
    EvalCase("constructor-leader-cn", ["现在哪只车队是第一名"], "race", "race_tool", "get_constructor_standings", ["Mercedes", "第 1 名"]),
    EvalCase("constructor-standings-en", ["constructor standings"], "race", "race_tool", "get_constructor_standings", ["Mercedes"]),
    EvalCase("team-specific-cn", ["法拉利车队排第几"], "race", "race_tool", "get_constructor_standings", ["Ferrari", "第 2 名"]),
    EvalCase("team-third-cn", ["车队第三名是谁"], "race", "race_tool", "get_constructor_standings", ["McLaren", "第 3 名"]),
    EvalCase("red-flag-rule", ["红旗规则是什么"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("safety-car-rule", ["安全车规则"], "regulation", "regulation_tool", "ask", ["安全车"], expected_status="answered"),
    EvalCase("parc-ferme-rule", ["parc ferme 是什么规则"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("unsafe-release-rule", ["unsafe release 怎么处罚"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("yellow-flag-rule", ["黄旗规则"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("vsc-rule", ["虚拟安全车规则"], "regulation", "regulation_tool", "ask", ["安全车"], expected_status="answered"),
    EvalCase("plank-rule", ["底板规则"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("technical-directive", ["technical directive 是什么"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
    EvalCase("no-rule-evidence-cn", ["外星维修区规则是什么"], "regulation", "regulation_tool", "ask", ["避免编造规则"], ["ARTICLE"], "insufficient_evidence"),
    EvalCase("no-rule-evidence-en", ["alien pit lane rule"], "regulation", "regulation_tool", "ask", ["避免编造规则"], ["ARTICLE"], "insufficient_evidence"),
    EvalCase("latest-news-cn", ["今天 F1 有什么新闻"], "news", "news_tool", "list_recent", ["McLaren upgrade", "British GP preview"]),
    EvalCase("latest-news-en", ["latest F1 headlines"], "news", "news_tool", "list_recent", ["McLaren upgrade"]),
    EvalCase("article-detail", ["新闻 42 详情"], "news", "news_tool", "get_article", ["Article 42", "floor upgrade"]),
    EvalCase("article-insight", ["分析新闻 42"], "news", "news_tool", "get_insights", ["McLaren", "底板升级"]),
    EvalCase("article-rules", ["新闻 42 和规则有什么关系"], "news", "news_tool", "get_rules_analysis", ["floor/plank"]),
    EvalCase("strategy-safety-car", ["安全车下 Ferrari 要不要进站"], "strategy", "strategy_tool", "analyze", ["置信度：low", "安全车"]),
    EvalCase("strategy-undercut", ["undercut 策略怎么判断"], "strategy", "strategy_tool", "analyze", ["进站损失"]),
    EvalCase("strategy-tyre", ["轮胎衰退严重该不该 pit"], "strategy", "strategy_tool", "analyze", ["轮胎"]),
    EvalCase("strategy-low-context", ["现在应该进站吗"], "strategy", "strategy_tool", "analyze", ["low"], ["高置信度"]),
    EvalCase("strategy-track-position", ["保赛道位置还是进站"], "strategy", "strategy_tool", "analyze", ["赛道位置"]),
    EvalCase("greeting", ["你好啊，你都能做什么"], "general", "general_tool", "answer", ["赛历", "积分榜", "规则"]),
    EvalCase("general-history", ["塞纳为什么伟大"], "general", "general_tool", "answer", ["F1"]),
    EvalCase("correction", ["不对不对"], "general", "general_tool", "answer", ["F1"]),
    EvalCase("broad-f1", ["介绍一下 F1"], "general", "general_tool", "answer", ["F1"]),
    EvalCase("general-no-live-guess", ["现在最新规则是什么"], "regulation", "regulation_tool", "ask", ["Section B"], expected_status="answered"),
]


def build_service() -> AgentService:
    router = IntentRouter()
    dispatcher = EvalToolDispatcher()
    planner = HeuristicPlanner(router=router, dispatcher=dispatcher)
    service = AgentService(
        intent_router=router,
        planner=cast(Any, planner),
        tool_dispatcher=dispatcher,
        response_formatter=AgentResponseFormatter(),
        runtime=None,
    )
    service.runtime = None
    return service


def run_case(service: AgentService, case: EvalCase) -> AgentQueryResponse:
    history: list[tuple[str, str, str | None]] = []
    fallback_intent: str | None = None
    response: AgentQueryResponse | None = None

    for message in case.messages:
        context = None
        if history:
            lines = []
            for user_message, assistant_message, _ in history[-2:]:
                lines.append(f"User: {user_message}")
                lines.append(f"Assistant: {assistant_message}")
            lines.append(f"User: {message}")
            context = "\n".join(lines)
        response = service.handle_query(message, fallback_intent=fallback_intent, conversation_context=context)
        history.append((message, response.final_answer, response.intent))
        fallback_intent = response.intent

    assert response is not None
    return response


def test_golden_agent_quality_cases() -> None:
    service = build_service()

    assert len(CASES) == 50
    for case in CASES:
        response = run_case(service, case)
        assert response.intent == case.expected_intent, case.name
        assert response.tool_name == case.expected_tool, case.name
        assert response.trace["action"] == case.expected_action, case.name
        if case.expected_status:
            assert response.trace["answer_status"] == case.expected_status, case.name
        for expected in case.must_include:
            assert expected in response.final_answer, case.name
        for forbidden in case.must_not_include:
            assert forbidden not in response.final_answer, case.name


def test_pasted_calendar_conversation_regression() -> None:
    service = build_service()
    messages = [
        "最新赛程是什么",
        "今年完整赛历是是什么",
        "下一场比赛是哪个",
        "比赛日期和具体时间是多少",
    ]

    response = run_case(
        service,
        EvalCase(
            name="pasted-calendar-regression",
            messages=messages,
            expected_intent="race",
            expected_tool="race_tool",
            expected_action="get_next_race",
            must_include=["British Grand Prix", "2026-07-05 22:00 CST", "Qualifying"],
        ),
    )

    assert response.trace["action"] == "get_next_race"
