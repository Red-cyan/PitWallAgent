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
    )
    RACE_KEYWORDS = (
        "schedule",
        "calendar",
        "grand prix",
        "next race",
        "standings",
        "championship",
        "赛程",
        "赛历",
        "下一站",
        "积分榜",
    )
    REGULATION_KEYWORDS = (
        "regulation",
        "rule",
        "parc ferme",
        "unsafe release",
        "red flag",
        "safety car",
        "plank",
        "规则",
        "红旗",
        "安全车",
        "封闭维修",
        "底板",
    )

    def route(self, message: str) -> str:
        normalized = message.lower()

        if any(keyword in normalized for keyword in self.REGULATION_KEYWORDS):
            return "regulation"

        if any(keyword in normalized for keyword in self.RACE_KEYWORDS):
            return "race"

        if any(keyword in normalized for keyword in self.NEWS_KEYWORDS):
            return "news"

        return "news"
