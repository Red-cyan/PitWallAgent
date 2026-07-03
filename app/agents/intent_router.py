import re


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
        "pit",
        "tyre",
        "tire",
        "degradation",
        "pit under",
        "undercut",
        "overcut",
        "track position",
        "box now",
        "should pit",
        "\u7b56\u7565",
        "\u8fdb\u7ad9",
        "\u8fdb\u5751",
        "\u8f6e\u80ce",
        "\u8870\u9000",
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
        "\u6392\u7b2c",
        "\u699c\u9996",
        "\u7b2c\u4e00\u540d",
        "\u9886\u8dd1",
        "\u9886\u5148",
        "\u7ef4\u65af\u5854\u6f58",
        "\u8bfa\u91cc\u65af",
        "\u52d2\u514b\u83b1\u5c14",
        "\u62c9\u585e\u5c14",
        "\u6c49\u5bc6\u5c14\u987f",
        "\u76ae\u4e9a\u65af\u7279\u91cc",
        "\u6cd5\u62c9\u5229",
        "\u8fc8\u51ef\u4f26",
        "\u7ea2\u725b",
        "\u6885\u5954",
        "\u4e0b\u4e00\u7ad9",
        "\u4e0b\u4e00\u573a",
        "\u4e0a\u4e00\u7ad9",
        "\u4e0a\u4e00\u573a",
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
        "pit lane speed",
        "pit lane speeding",
        "speeding in the pit lane",
        "dangerous driving",
        "driving infringement",
        "penalty",
        "stewards",
        "investigation",
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
        "维修区超速",
        "维修区限速",
        "维修区速度",
        "维修区通道",
        "危险驾驶",
        "危险返回赛道",
        "不安全驾驶",
        "罚时",
        "罚退",
        "处罚",
        "赛会干事",
        "干事调查",
        "事故调查",
        "sectiona",
        "section a",
        "sectionb",
        "section b",
        "sectionc",
        "section c",
        "大体规则",
        "规则是什么样",
        "分几部分",
    )
    FOLLOW_UP_KEYWORDS = (
        "\u90a3\u5462",
        "\u7136\u540e\u5462",
        "\u8fd9\u4e2a\u5462",
        "\u90a3\u4e2a\u5462",
        "\u4ed6",
        "\u5979",
        "\u5b83",
        "\u8fd9\u7bc7",
        "\u8fd9\u6761",
        "\u8fd9\u4e2a",
        "\u90a3\u4e2a",
        "what about",
        "how about",
        "and that",
        "then what",
        "it ",
        "he ",
        "she ",
        "that ",
        "this ",
    )

    def route(self, message: str, fallback_intent: str | None = None) -> str:
        normalized = message.lower().strip()

        if self._contains_any(normalized, self._EXPLICIT_REGULATION_KEYWORDS):
            return "regulation"

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
        if stripped in {"?", "？", "??", "？？"}:
            return True

        if self._has_explicit_domain_signal(stripped):
            return False

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

        if len(stripped) <= 18 and any(
            token in stripped
            for token in ("\u5462", "\u4ed6", "\u5979", "\u5b83", "\u8fd9", "\u90a3")
        ):
            return True

        if re.search(r"(前\s*\d+\s*名|前[一二三四五六七八九十]+名|第\s*\d+\s*名|第[一二三四五六七八九十]+名)", stripped):
            return True

        if any(token in stripped for token in ("不是第一", "不是第1", "我问你", "刚才问的是")):
            return True

        return any(keyword in stripped for keyword in self.FOLLOW_UP_KEYWORDS)

    def _contains_any(self, message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)

    def _has_explicit_domain_signal(self, message: str) -> bool:
        return (
            self._contains_any(message, self.NEWS_KEYWORDS)
            or self._contains_any(message, self.STRATEGY_KEYWORDS)
            or self._contains_any(message, self.REGULATION_KEYWORDS)
            or self._contains_any(message, self.RACE_KEYWORDS)
            or self._contains_any(message, self._EXPLICIT_REGULATION_KEYWORDS)
        )

    _EXPLICIT_REGULATION_KEYWORDS = (
        "regulation",
        "rule",
        "rules",
        "technical directive",
        "\u89c4\u5219",
        "\u6761\u4f8b",
        "\u6280\u672f\u6307\u4ee4",
    )
