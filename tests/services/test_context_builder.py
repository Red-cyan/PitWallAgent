from datetime import UTC, datetime

from app.schemas.chat import ConversationTurn
from app.services.context_builder import ContextBuilder


def test_context_builder_returns_none_for_empty_history() -> None:
    builder = ContextBuilder()

    context = builder.build_context([], "那呢？")

    assert context is None


def test_context_builder_uses_recent_turns_only() -> None:
    builder = ContextBuilder()
    history = [
        ConversationTurn(role="user", message="第一句", created_at=datetime(2026, 7, 2, 0, 0, tzinfo=UTC)),
        ConversationTurn(role="assistant", message="第二句", created_at=datetime(2026, 7, 2, 0, 1, tzinfo=UTC)),
        ConversationTurn(role="user", message="第三句", created_at=datetime(2026, 7, 2, 0, 2, tzinfo=UTC)),
        ConversationTurn(role="assistant", message="第四句", created_at=datetime(2026, 7, 2, 0, 3, tzinfo=UTC)),
        ConversationTurn(role="user", message="第五句", created_at=datetime(2026, 7, 2, 0, 4, tzinfo=UTC)),
    ]

    context = builder.build_context(history, "第六句")

    assert context is not None
    assert "第一句" not in context
    assert "第二句" in context
    assert "第五句" in context
    assert context.endswith("User: 第六句")
