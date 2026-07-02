import re

from app.schemas.news import NewsArticleRead, NewsEntity, NewsInsightResponse


class NewsInsightService:
    """新闻独立分析服务。"""

    DRIVER_ALIASES = {
        "max verstappen": "Max Verstappen",
        "verstappen": "Max Verstappen",
        "lewis hamilton": "Lewis Hamilton",
        "hamilton": "Lewis Hamilton",
        "lando norris": "Lando Norris",
        "norris": "Lando Norris",
        "charles leclerc": "Charles Leclerc",
        "leclerc": "Charles Leclerc",
        "oscar piastri": "Oscar Piastri",
        "piastri": "Oscar Piastri",
        "george russell": "George Russell",
        "russell": "George Russell",
        "fernando alonso": "Fernando Alonso",
        "alonso": "Fernando Alonso",
        "carlos sainz": "Carlos Sainz",
        "sainz": "Carlos Sainz",
        "adrian newey": "Adrian Newey",
        "newey": "Adrian Newey",
    }

    TEAM_ALIASES = {
        "red bull": "Red Bull Racing",
        "red bull racing": "Red Bull Racing",
        "ferrari": "Ferrari",
        "mclaren": "McLaren",
        "mercedes": "Mercedes",
        "aston martin": "Aston Martin",
        "williams": "Williams",
        "alpine": "Alpine",
        "haas": "Haas",
        "sauber": "Sauber",
        "audi": "Audi",
        "cadillac": "Cadillac",
    }

    CIRCUIT_ALIASES = {
        "silverstone": "Silverstone",
        "spa": "Spa-Francorchamps",
        "spa-francorchamps": "Spa-Francorchamps",
        "monza": "Monza",
        "monaco": "Monaco",
        "barcelona": "Barcelona-Catalunya",
        "hungaroring": "Hungaroring",
        "interlagos": "Interlagos",
    }

    CATEGORY_RULES = (
        (
            "driver_market",
            "车手动向",
            ("contract", "future", "seat", "transfer", "move", "stay", "one-team driver", "career"),
        ),
        (
            "race_weekend",
            "比赛周末动态",
            ("practice", "qualifying", "sprint", "grand prix", "race weekend", "session", "weather"),
        ),
        (
            "technical",
            "技术与赛车开发",
            ("upgrade", "floor", "plank", "technical", "wing", "aerodynamic", "ride height", "power unit"),
        ),
        (
            "team_operations",
            "车队运营与管理",
            ("team principal", "management", "boss", "factory", "strategy team", "operations"),
        ),
        (
            "commercial",
            "商业与品牌活动",
            ("store", "pop-up", "sponsor", "partnership", "livery", "launch", "event"),
        ),
        (
            "race_control",
            "赛会控制与处罚",
            ("red flag", "yellow flag", "safety car", "vsc", "penalty", "stewards", "investigation", "unsafe release"),
        ),
    )

    DIRECT_RULE_TERMS = (
        "red flag",
        "yellow flag",
        "safety car",
        "virtual safety car",
        "vsc",
        "penalty",
        "stewards",
        "investigation",
        "unsafe release",
        "disqualification",
        "parc ferme",
        "technical infringement",
        "plank",
        "ride height",
    )

    POSSIBLE_RULE_TERMS = (
        "strategy",
        "protest",
        "incident",
        "contact",
        "collision",
        "appeal",
        "directive",
    )

    SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")

    def analyze(self, article: NewsArticleRead) -> NewsInsightResponse:
        corpus = self._build_corpus(article)
        category_key, category_label = self._classify_article(corpus)
        entities = self._extract_entities(corpus)
        key_points = self._extract_key_points(article)
        summary = self._build_summary(article, key_points)
        rule_relevance, rule_relevance_reason = self._classify_rule_relevance(corpus, category_key)

        return NewsInsightResponse(
            article=article,
            category_key=category_key,
            category_label=category_label,
            summary=summary,
            key_points=key_points,
            entities=entities,
            rule_relevance=rule_relevance,
            rule_relevance_reason=rule_relevance_reason,
        )

    def _build_corpus(self, article: NewsArticleRead) -> str:
        return " ".join(
            [
                article.title,
                article.summary or "",
                article.content or "",
                " ".join(article.tags),
            ]
        ).lower()

    def _classify_article(self, corpus: str) -> tuple[str, str]:
        if any(term in corpus for term in self.DIRECT_RULE_TERMS):
            return "race_control", "赛会控制与处罚"

        best_match: tuple[str, str, int] | None = None

        for category_key, category_label, keywords in self.CATEGORY_RULES:
            score = sum(1 for keyword in keywords if keyword in corpus)
            if score == 0:
                continue
            if best_match is None or score > best_match[2]:
                best_match = (category_key, category_label, score)

        if best_match is None:
            return "general_news", "综合新闻"

        return best_match[0], best_match[1]

    def _extract_entities(self, corpus: str) -> list[NewsEntity]:
        entities: list[NewsEntity] = []
        entities.extend(self._collect_entities(corpus, self.DRIVER_ALIASES, "driver"))
        entities.extend(self._collect_entities(corpus, self.TEAM_ALIASES, "team"))
        entities.extend(self._collect_entities(corpus, self.CIRCUIT_ALIASES, "circuit"))
        return entities

    def _collect_entities(self, corpus: str, aliases: dict[str, str], entity_type: str) -> list[NewsEntity]:
        found_names: list[str] = []
        for alias, normalized in aliases.items():
            if alias in corpus and normalized not in found_names:
                found_names.append(normalized)

        return [NewsEntity(entity_type=entity_type, name=name) for name in found_names]

    def _extract_key_points(self, article: NewsArticleRead) -> list[str]:
        source_text = article.content or article.summary or article.title
        sentences = [
            sentence.strip()
            for sentence in self.SENTENCE_SPLIT_PATTERN.split(source_text)
            if sentence.strip()
        ]
        if not sentences:
            return [article.title]

        key_points: list[str] = []
        for sentence in sentences[:3]:
            normalized = " ".join(sentence.split())
            if normalized and normalized not in key_points:
                key_points.append(normalized)

        return key_points

    def _build_summary(self, article: NewsArticleRead, key_points: list[str]) -> str:
        if article.summary:
            return article.summary
        if key_points:
            return key_points[0]
        return article.title

    def _classify_rule_relevance(self, corpus: str, category_key: str) -> tuple[str, str]:
        direct_terms = [term for term in self.DIRECT_RULE_TERMS if term in corpus]
        if direct_terms:
            return "direct", f"新闻直接包含规则或裁判相关术语：{', '.join(direct_terms[:3])}"

        possible_terms = [term for term in self.POSSIBLE_RULE_TERMS if term in corpus]
        if possible_terms or category_key in {"technical", "race_weekend"}:
            if possible_terms:
                return "possible", f"新闻可能涉及规则背景，命中了术语：{', '.join(possible_terms[:3])}"
            return "possible", "新闻属于比赛周末或技术动态，后续可能需要结合规则解释。"

        return "none", "新闻主要属于资讯或人物动态，不需要默认关联 FIA 规则检索。"
