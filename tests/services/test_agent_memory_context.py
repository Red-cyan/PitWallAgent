from app.agents.intent_router import IntentRouter
from app.services.agent_service import AgentService
from tests.services.test_agent_service_context import CapturingPlanner, StubToolDispatcher


def test_agent_service_allows_long_term_memory_for_non_follow_up_queries() -> None:
    planner = CapturingPlanner()
    service = AgentService(
        intent_router=IntentRouter(),
        planner=planner,
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    service.handle_query(
        "What is DRS in Formula 1?",
        conversation_context=(
            "Long-term memory:\n"
            "- Remember that I prefer technical strategy details.\n\n"
            "Recent turns:\n"
            "User: Who leads the standings?\n"
            "Assistant: ...\n\n"
            "Current user message:\n"
            "User: What is DRS in Formula 1?"
        ),
    )

    assert "Long-term memory:" in planner.messages[-1]
    assert "technical strategy details" in planner.messages[-1]
    assert "Who leads the standings?" not in planner.messages[-1]
