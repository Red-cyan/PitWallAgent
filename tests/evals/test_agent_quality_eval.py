from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
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
                            {"position": 4, "team_name": "Red Bull", "points": 115},
                            {"position": 5, "team_name": "Williams", "points": 64},
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
            if "SectionA" in question or "Section A" in question:
                return Result(
                    {
                        "action": action,
                        "response": {
                            "answer": "Section A 是 General Provisions，主要讲锦标赛治理、适用原则和总体合规框架。",
                            "answer_status": "answered",
                            "confidence": "medium",
                            "evidence_count": 2,
                            "source_mode": "regulation_overview",
                            "query_type": "section_overview",
                            "citations": [{"document_title": "Section A", "article": "A1.1", "page": 5}],
                            "retrieved_chunks": [{"document_title": "Section A", "article": "A1.1", "page": 5, "score": 1.0}],
                        },
                    }
                )
            if "大体规则" in question or "规则是什么样" in question or "分几部分" in question:
                return Result(
                    {
                        "action": action,
                        "response": {
                            "answer": "2026 FIA F1 Regulations 当前索引大致分为 Section A-F：Section A General Provisions；Section B Sporting；Section C Technical；Section D/E Financial；Section F Operational。",
                            "answer_status": "answered",
                            "confidence": "medium",
                            "evidence_count": 6,
                            "source_mode": "regulation_overview",
                            "query_type": "document_overview",
                            "citations": [{"document_title": "Section A", "article": "A1.1", "page": 5}],
                            "retrieved_chunks": [{"document_title": "Section A", "article": "A1.1", "page": 5, "score": 1.0}],
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



AGENT_CASES_PATH = Path("data/evals/agent_cases.jsonl")


def load_cases(path: Path = AGENT_CASES_PATH) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            try:
                cases.append(
                    EvalCase(
                        name=payload["name"],
                        messages=payload["messages"],
                        expected_intent=payload["expected_intent"],
                        expected_tool=payload["expected_tool"],
                        expected_action=payload["expected_action"],
                        must_include=payload.get("must_include", []),
                        must_not_include=payload.get("must_not_include", []),
                        expected_status=payload.get("expected_answer_status"),
                    )
                )
            except KeyError as exc:
                raise ValueError(f"Invalid eval case at {path}:{line_number}: missing {exc.args[0]}") from exc
    return cases


CASES = load_cases()


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

    assert len(CASES) == 56
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
