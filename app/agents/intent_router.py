class IntentRouter:
    """基于规则的最小意图路由器。"""

    NEWS_KEYWORDS = (
        "news",
        "today",
        "paddock",
        "headline",
        "latest",
        "新闻",
        "今天",
        "围场",
        "动态",
        "消息",
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
        "constructors",
        "赛程",
        "赛历",
        "比赛",
        "大奖赛",
        "积分榜",
        "积分",
        "车手榜",
        "车队榜",
        "车手排名",
        "车队排名",
        "下一站",
        "上一站",
        "排位",
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
        "规则",
        "条例",
        "红旗",
        "黄旗",
        "安全车",
        "虚拟安全车",
        "封闭维修区",
        "底板",
        "技术规则",
        "比赛规则",
    )
    FOLLOW_UP_KEYWORDS = (
        "那呢",
        "然后呢",
        "这个呢",
        "那个呢",
        "what about",
        "how about",
        "and that",
        "then what",
    )

    def route(self, message: str, fallback_intent: str | None = None) -> str:
        normalized = message.lower()

        if self._contains_any(normalized, self.REGULATION_KEYWORDS):
            return "regulation"

        if self._contains_any(normalized, self.RACE_KEYWORDS):
            return "race"

        if self._contains_any(normalized, self.NEWS_KEYWORDS):
            return "news"

        if fallback_intent and self._looks_like_follow_up(normalized):
            return fallback_intent

        return "news"

    def _contains_any(self, message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)

    def _looks_like_follow_up(self, message: str) -> bool:
        stripped = message.strip()
        if stripped in {"呢", "然后", "然后呢", "那", "那呢", "这个", "那个"}:
            return True

        if len(stripped) <= 12 and "呢" in stripped:
            return True

        return any(keyword in stripped for keyword in self.FOLLOW_UP_KEYWORDS)
