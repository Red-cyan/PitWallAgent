from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AgentQueryResponse


class StubAgentService:
    def handle_query(self, message: str) -> AgentQueryResponse:
        return AgentQueryResponse(
            intent="regulation",
            tool_name="regulation_tool",
            success=True,
            result={"message": message, "answer": "stub answer"},
            error=None,
        )


def test_agent_query_routes_request(monkeypatch) -> None:
    from app.api import agent

    monkeypatch.setattr(agent, "agent_service", StubAgentService())
    client = TestClient(app)

    response = client.post(
        "/api/agent/query",
        json={"message": "红旗是什么？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "regulation"
    assert body["tool_name"] == "regulation_tool"
    assert body["result"]["answer"] == "stub answer"


def test_agent_query_rejects_empty_message() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/agent/query",
        json={"message": ""},
    )

    assert response.status_code == 422
