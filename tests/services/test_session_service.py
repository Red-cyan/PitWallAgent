from app.schemas.agent import AgentQueryResponse
from app.services.session_service import SessionService


def test_session_service_creates_session_and_tracks_history() -> None:
    service = SessionService()

    session = service.get_or_create_session()
    service.append_user_message(session.session_id, "下一站比赛是什么？")
    service.append_agent_response(
        session.session_id,
        AgentQueryResponse(
            intent="race",
            tool_name="race_tool",
            success=True,
            final_answer="下一站比赛是 British Grand Prix。",
            result={},
            error=None,
        ),
    )

    history = service.get_history(session.session_id)

    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert service.get_last_intent(session.session_id) == "race"
