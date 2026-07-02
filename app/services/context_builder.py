from app.schemas.chat import ConversationTurn


class ContextBuilder:
    """构建会话上下文。"""

    def build_context(self, history: list[ConversationTurn], current_message: str) -> str | None:
        if not history:
            return None

        recent_turns = history[-4:]
        lines = []
        for turn in recent_turns:
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.message}")

        lines.append(f"User: {current_message}")
        return "\n".join(lines)
