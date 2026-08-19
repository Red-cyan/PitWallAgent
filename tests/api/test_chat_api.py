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

# 合法会话 ID：服务端 uuid4().hex 生成 32 位十六进制
SESSION_ONE = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
SESSION_TWO = "b1b2c3d4e5f60718293a4b5c6d7e8f91"
MISSING_ID = "00000000000000000000000000000000"


class StubChatService:
    def handle_chat(
        self, message: str, session_id: str | None = None, user_id: str | None = None
    ) -> ChatResponse:
        return ChatResponse(
            session_id=session_id or SESSION_ONE,
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
                session_id=session_id or SESSION_ONE,
                turn_count=2,
                last_intent="race",
                updated_at="2026-07-02T00:00:01Z",
            ),
        )

    def stream_chat(
        self, message: str, session_id: str | None = None, user_id: str | None = None
    ):
        response = self.handle_chat(
            message=message, session_id=session_id, user_id=user_id
        )
        yield {
            "event": "session_started",
            "data": {"session_id": response.session_id},
        }
        yield {
            "event": "status",
            "data": {"session_id": response.session_id, "message": "thinking"},
        }
        yield {
            "event": "message_delta",
            "data": {"session_id": response.session_id, "delta": "streamed "},
        }
        yield {
            "event": "message_completed",
            "data": response.model_dump(mode="json"),
        }

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
                    session_id=SESSION_TWO,
                    turn_count=4,
                    last_intent="race",
                    updated_at="2026-07-02T00:00:02Z",
                ),
                ChatSessionSummary(
                    session_id=SESSION_ONE,
                    turn_count=2,
                    last_intent="news",
                    updated_at="2026-07-02T00:00:01Z",
                ),
            ][:limit]
        )

    def get_session(self, session_id: str) -> ChatSessionSummary | None:
        if session_id == MISSING_ID:
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
            deleted=session_id != MISSING_ID,
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
    assert body["session_id"] == SESSION_ONE
    assert body["response"]["intent"] == "race"
    assert body["response"]["tool_name"] == "race_tool"
    assert body["history"][1]["intent"] == "race"
    assert body["session"]["turn_count"] == 2
    assert response.headers["X-PitWall-Endpoint-Mode"] == "primary"


def test_chat_history_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get(f"/api/chat/{SESSION_ONE}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == SESSION_ONE
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
    assert body["sessions"][0]["session_id"] == SESSION_TWO
    assert response.headers["X-PitWall-Endpoint-Mode"] == "primary"


def test_chat_session_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get(f"/api/chat/{SESSION_ONE}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == SESSION_ONE
    assert body["last_intent"] == "race"


def test_chat_session_returns_404_when_missing(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.get(f"/api/chat/{MISSING_ID}")

    assert response.status_code == 404


def test_delete_chat_session_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.delete(f"/api/chat/{SESSION_ONE}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == SESSION_ONE
    assert body["deleted"] is True


def test_delete_chat_session_returns_404_when_missing(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.delete(f"/api/chat/{MISSING_ID}")

    assert response.status_code == 404


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": ""},
    )

    assert response.status_code == 422


def test_chat_stream_routes_request(monkeypatch) -> None:
    from app.api import chat

    monkeypatch.setattr(chat, "chat_service", StubChatService())
    client = TestClient(app)

    response = client.post(
        "/api/chat/stream",
        json={"message": "Who leads the championship?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: session_started" in response.text
    assert response.text.index("event: session_started") < response.text.index(
        "event: message_completed"
    )
    assert "event: status" in response.text
    assert "event: message_delta" in response.text
    assert "event: message_completed" in response.text


def test_chat_stream_allows_cors_preflight() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/chat/stream",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
