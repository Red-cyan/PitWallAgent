import json
import re

from app.services.llm.client import LLMClient
from app.config.settings import settings


class QueryRewriter:
    """Rewrite user questions into retrieval-friendly English queries."""

    CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
    DOMAIN_GLOSSARY = {
        "红旗": "red flag",
        "黄旗": "yellow flag",
        "安全车": "safety car",
        "虚拟安全车": "virtual safety car VSC",
        "封闭维修区": "parc ferme",
        "封闭维修": "parc ferme",
        "不安全释放": "unsafe release",
        "违规释放": "unsafe release",
        "维修区超速": "pit lane speeding speed limit penalty",
        "维修区限速": "pit lane speed limit",
        "危险驾驶": "dangerous driving stewards penalty",
        "危险返回赛道": "dangerous rejoin track stewards penalty",
        "赛会干事": "stewards investigation penalty",
        "处罚": "penalty sanctions stewards",
        "底板": "plank",
        "木板": "plank",
    }

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def rewrite(self, question: str) -> list[str]:
        if not self._should_rewrite(question):
            return []

        fallback_queries = self._build_heuristic_queries(question)
        try:
            llm_client = self.llm_client or LLMClient()
            response = llm_client.chat(
                messages=self._build_messages(question),
                temperature=0,
                max_tokens=settings.query_rewrite_max_tokens,
                timeout=settings.query_rewrite_timeout_seconds,
            )
            return self._merge_queries(self._parse_response(response), fallback_queries)
        except Exception:
            return fallback_queries

    def _should_rewrite(self, question: str) -> bool:
        return bool(self.CJK_PATTERN.search(question))

    def _build_messages(self, question: str) -> list[dict]:
        glossary_hints = self._build_glossary_hints(question)
        return [
            {
                "role": "system",
                "content": (
                    "You rewrite FIA Formula 1 regulation questions for retrieval."
                    " The domain is motorsport regulations, race control, sporting rules, and technical rules."
                    " Do not interpret short terms using generic business or everyday meanings."
                    " Prefer official FIA terms such as stewards, penalty, pit lane, speed limit,"
                    " unsafe release, track limits, dangerous driving, parc ferme, and race suspension."
                    " Return only JSON with a key named queries."
                    " The value must be an array of 1 to 3 short English search queries."
                    " Focus on exact FIA regulation terminology."
                    ' Example mappings: "红旗" -> "red flag", "安全车" -> "safety car",'
                    ' "虚拟安全车" -> "virtual safety car VSC", "封闭维修" -> "parc ferme".'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"{glossary_hints}\n"
                    'Return JSON like {"queries":["...", "..."]}.'
                    " Prefer Sporting Regulations terms when the question is about race control procedures."
                ),
            },
        ]

    def _build_glossary_hints(self, question: str) -> str:
        matched_hints = [
            f'- "{source}" means "{target}"'
            for source, target in self.DOMAIN_GLOSSARY.items()
            if source in question
        ]
        if not matched_hints:
            return "Known domain hints: none matched."

        hint_lines = "\n".join(matched_hints)
        return f"Known domain hints:\n{hint_lines}"

    def _build_heuristic_queries(self, question: str) -> list[str]:
        queries = [f"{question} FIA Formula 1 regulations"]
        if not self.CJK_PATTERN.search(question):
            return queries

        sporting_tokens = (
            "比赛",
            "车手",
            "驾驶",
            "处罚",
            "罚",
            "赛道",
            "维修区",
            "旗",
            "安全车",
            "干事",
            "阻挡",
            "挡车",
            "超速",
            "事故",
        )
        technical_tokens = (
            "技术",
            "赛车",
            "底板",
            "车身",
            "前翼",
            "后翼",
            "动力单元",
            "尺寸",
            "重量",
            "合规",
        )
        financial_tokens = ("成本", "预算", "财务", "成本帽", "审计")
        operational_tokens = ("测试", "风洞", "仿真", "运营", "人员", "设施")

        if any(token in question for token in sporting_tokens):
            queries.append("FIA Formula 1 Sporting Regulations driver conduct penalties stewards investigation race control")
        if any(token in question for token in technical_tokens):
            queries.append("FIA Formula 1 Technical Regulations car legality bodywork dimensions power unit compliance")
        if any(token in question for token in financial_tokens):
            queries.append("FIA Formula 1 Financial Regulations cost cap reporting audit breach")
        if any(token in question for token in operational_tokens):
            queries.append("FIA Formula 1 Operational Regulations testing wind tunnel simulation personnel restrictions")

        if len(queries) == 1:
            queries.extend(
                [
                    "FIA Formula 1 Sporting Regulations stewards penalties race control",
                    "FIA Formula 1 Technical Regulations car legality compliance",
                ]
            )

        return self._merge_queries(queries, [])

    def _merge_queries(self, primary: list[str], fallback: list[str]) -> list[str]:
        cleaned_queries: list[str] = []
        seen: set[str] = set()
        for query in [*primary, *fallback]:
            normalized = query.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned_queries.append(normalized)
        return cleaned_queries[:4]

    def _parse_response(self, response: str) -> list[str]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return []

        queries = data.get("queries")
        if not isinstance(queries, list):
            return []

        cleaned_queries: list[str] = []
        for query in queries:
            if isinstance(query, str):
                normalized = query.strip()
                if normalized and normalized not in cleaned_queries:
                    cleaned_queries.append(normalized)

        return cleaned_queries[:3]
