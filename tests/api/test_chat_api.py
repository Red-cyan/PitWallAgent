from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import ChatResponse, ConversationTurn


class StubChatService:
    def handle_chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        return ChatResponse(
            session_id=session_id or "session-001",
            response=AgentQueryResponse(
                intent="race",
                tool_name="race_tool",
                success=True,
                final_answer="下一站比赛是 British Grand Prix。",
                result={"message": message},
                error=None,
            ),
            history=[
                ConversationTurn(
                    role="user",
                    message=message,
                    created_at="2026-07-02T00:00:00Z",
                ),
                ConversationTurn(
                    role="assistant",
                    message="下一站比赛是 British Grand Prix。",
                    created_at="2026-07-02T00:00:01Z",
                    intent="race",
                    tool_name="race_tool",
                ),
            ],
        )


def test_chat_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": "下一站比赛是什么？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-001"
    assert body["response"]["intent"] == "race"
    assert body["response"]["tool_name"] == "race_tool"
    assert body["history"][1]["intent"] == "race"


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": ""},
    )

    assert response.status_code == 422
