from app.schemas.chat import ConversationTurn


class ContextBuilder:
    """Build a compact conversation context for the agent."""

    def build_context(
        self,
        history: list[ConversationTurn],
        current_message: str,
        *,
        summary: str | None = None,
        long_term_memories: list[str] | None = None,
        recent_turns: int = 4,
    ) -> str | None:
        if not history and not summary and not long_term_memories:
            return None

        sections: list[str] = []
        if summary:
            sections.append(f"Conversation summary:\n{summary}")

        if long_term_memories:
            memory_lines = [f"- {memory}" for memory in long_term_memories]
            sections.append("Long-term memory:\n" + "\n".join(memory_lines))

        recent_history = history[-max(1, recent_turns) :]
        if recent_history:
            lines = []
            for turn in recent_history:
                role = "User" if turn.role == "user" else "Assistant"
                lines.append(f"{role}: {turn.message}")
            sections.append("Recent turns:\n" + "\n".join(lines))

        sections.append(f"Current user message:\nUser: {current_message}")
        return "\n\n".join(sections)
