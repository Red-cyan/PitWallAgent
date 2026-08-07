import re


class IntentRouter:
    NEWS_STRONG_KEYWORDS = (
        "news",
        "headline",
        "新闻",
        "围场",
        "动态",
        "消息",
        "资讯",
    )
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
    STRATEGY_KEYWORDS = (
        "strategy",
        "pit now",
        "pit stop",
        "tyre",
        "tire",
        "degradation",
        "pit under",
        "undercut",
        "overcut",
        "track position",
        "box now",
        "should pit",
        "策略",
        "进站",
        "进坑",
        "轮胎",
        "衰退",
        "赛道位置",
        "是否该进站",
        "该不该进站",
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
        "赛程",
        "赛历",
        "比赛",
        "大奖赛",
        "积分榜",
        "积分",
        "车手",
        "车队",
        "排名",
        "排第",
        "榜首",
        "第一名",
        "领跑",
        "领先",
        "夺冠",
        "赢了",
        "获胜",
        "获胜者",
        "谁赢",
        "维斯塔潘",
        "诺里斯",
        "勒克莱尔",
        "拉塞尔",
        "汉密尔顿",
        "皮亚斯特里",
        "法拉利",
        "迈凯伦",
        "红牛",
        "梅奔",
        "下一站",
        "下一场",
        "上一站",
        "上一场",
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
        "pit lane speed",
        "pit lane speeding",
        "speeding in the pit lane",
        "dangerous driving",
        "driving infringement",
        "penalty",
        "stewards",
        "investigation",
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
        "那呢",
        "然后呢",
        "这个呢",
        "那个呢",
        "他",
        "她",
        "它",
        "这篇",
        "这条",
        "这个",
        "那个",
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

        if self._contains_any(normalized, self.NEWS_STRONG_KEYWORDS):
            return "news"

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
            "呢",
            "然后",
            "然后呢",
            "那",
            "那呢",
            "这个",
            "那个",
        }:
            return True

        if len(stripped) <= 18 and any(
            token in stripped
            for token in ("呢", "他", "她", "它", "这", "那")
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
        "规则",
        "条例",
        "技术指令",
    )
