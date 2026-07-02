from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatResponse,
    ChatSessionDeleteResponse,
    ChatSessionListResponse,
    ChatSessionSummary,
    ConversationTurn,
)


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
            session=ChatSessionSummary(
                session_id=session_id or "session-001",
                turn_count=2,
                last_intent="race",
                updated_at="2026-07-02T00:00:01Z",
            ),
        )

    def get_history(self, session_id: str) -> ChatHistoryResponse:
        return ChatHistoryResponse(
            session=ChatSessionSummary(
                session_id=session_id,
                turn_count=2,
                last_intent="race",
                updated_at="2026-07-02T00:00:01Z",
            ),
            history=[
                ConversationTurn(
                    role="user",
                    message="下一站比赛是什么？",
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

    def list_sessions(self, limit: int = 20) -> ChatSessionListResponse:
        return ChatSessionListResponse(
            sessions=[
                ChatSessionSummary(
                    session_id="session-002",
                    turn_count=4,
                    last_intent="race",
                    updated_at="2026-07-02T00:00:02Z",
                ),
                ChatSessionSummary(
                    session_id="session-001",
                    turn_count=2,
                    last_intent="news",
                    updated_at="2026-07-02T00:00:01Z",
                ),
            ][:limit]
        )

    def get_session(self, session_id: str) -> ChatSessionSummary | None:
        if session_id == "missing":
            return None
        return ChatSessionSummary(
            session_id=session_id,
            turn_count=2,
            last_intent="race",
            updated_at="2026-07-02T00:00:01Z",
        )

    def delete_session(self, session_id: str) -> ChatSessionDeleteResponse:
        return ChatSessionDeleteResponse(
            session_id=session_id,
            deleted=session_id != "missing",
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
    assert body["session"]["turn_count"] == 2
    assert response.headers["X-PitWall-Endpoint-Mode"] == "primary"


def test_chat_history_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get("/api/chat/session-001/history")

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == "session-001"
    assert body["session"]["last_intent"] == "race"
    assert len(body["history"]) == 2
    assert response.headers["X-PitWall-Endpoint-Mode"] == "primary"


def test_chat_sessions_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get("/api/chat/sessions?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 2
    assert body["sessions"][0]["session_id"] == "session-002"
    assert response.headers["X-PitWall-Endpoint-Mode"] == "primary"


def test_chat_session_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get("/api/chat/session-001")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-001"
    assert body["last_intent"] == "race"


def test_chat_session_returns_404_when_missing(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get("/api/chat/missing")

    assert response.status_code == 404


def test_delete_chat_session_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.delete("/api/chat/session-001")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-001"
    assert body["deleted"] is True


def test_delete_chat_session_returns_404_when_missing(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.delete("/api/chat/missing")

    assert response.status_code == 404


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": ""},
    )

    assert response.status_code == 422
