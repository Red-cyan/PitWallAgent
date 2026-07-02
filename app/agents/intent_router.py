class IntentRouter:
    NEWS_KEYWORDS = (
        "news",
        "today",
        "paddock",
        "headline",
        "latest",
        "\u65b0\u95fb",
        "\u4eca\u5929",
        "\u56f4\u573a",
        "\u52a8\u6001",
        "\u6d88\u606f",
    )
    STRATEGY_KEYWORDS = (
        "strategy",
        "pit now",
        "pit stop",
        "pit under",
        "undercut",
        "overcut",
        "track position",
        "box now",
        "should pit",
        "\u7b56\u7565",
        "\u8fdb\u7ad9",
        "\u8fdb\u5751",
        "\u8d5b\u9053\u4f4d\u7f6e",
        "\u662f\u5426\u8be5\u8fdb\u7ad9",
        "\u8be5\u4e0d\u8be5\u8fdb\u7ad9",
    )
    RACE_KEYWORDS = (
        "schedule",
        "calendar",
        "grand prix",
        "race weekend",
        "next race",
        "last race",
        "previous race",
        "standings",
        "championship",
        "drivers",
        "driver",
        "constructors",
        "constructor",
        "team",
        "teams",
        "leader",
        "leading",
        "who leads",
        "who is first",
        "\u8d5b\u7a0b",
        "\u8d5b\u5386",
        "\u6bd4\u8d5b",
        "\u5927\u5956\u8d5b",
        "\u79ef\u5206\u699c",
        "\u79ef\u5206",
        "\u8f66\u624b",
        "\u8f66\u961f",
        "\u6392\u540d",
        "\u699c\u9996",
        "\u7b2c\u4e00\u540d",
        "\u9886\u8dd1",
        "\u9886\u5148",
        "\u4e0b\u4e00\u7ad9",
        "\u4e0a\u4e00\u7ad9",
        "\u6392\u4f4d",
    )
    REGULATION_KEYWORDS = (
        "regulation",
        "rule",
        "parc ferme",
        "unsafe release",
        "red flag",
        "safety car",
        "virtual safety car",
        "vsc",
        "plank",
        "technical directive",
        "\u89c4\u5219",
        "\u6761\u4f8b",
        "\u7ea2\u65d7",
        "\u9ec4\u65d7",
        "\u5b89\u5168\u8f66",
        "\u865a\u62df\u5b89\u5168\u8f66",
        "\u5c01\u95ed\u7ef4\u4fee\u533a",
        "\u5e95\u677f",
        "\u6280\u672f\u89c4\u5219",
        "\u6bd4\u8d5b\u89c4\u5219",
    )
    FOLLOW_UP_KEYWORDS = (
        "\u90a3\u5462",
        "\u7136\u540e\u5462",
        "\u8fd9\u4e2a\u5462",
        "\u90a3\u4e2a\u5462",
        "what about",
        "how about",
        "and that",
        "then what",
    )

    def route(self, message: str, fallback_intent: str | None = None) -> str:
        normalized = message.lower().strip()

        if self._contains_any(normalized, self.STRATEGY_KEYWORDS):
            return "strategy"

        if self._contains_any(normalized, self.REGULATION_KEYWORDS):
            return "regulation"

        if self._contains_any(normalized, self.RACE_KEYWORDS):
            return "race"

        if self._contains_any(normalized, self.NEWS_KEYWORDS):
            return "news"

        if fallback_intent and self.looks_like_follow_up(normalized):
            return fallback_intent

        return "general"

    def looks_like_follow_up(self, message: str) -> bool:
        stripped = message.strip().lower()
        if stripped in {
            "\u5462",
            "\u7136\u540e",
            "\u7136\u540e\u5462",
            "\u90a3",
            "\u90a3\u5462",
            "\u8fd9\u4e2a",
            "\u90a3\u4e2a",
        }:
            return True

        if len(stripped) <= 12 and "\u5462" in stripped:
            return True

        return any(keyword in stripped for keyword in self.FOLLOW_UP_KEYWORDS)

    def _contains_any(self, message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)
