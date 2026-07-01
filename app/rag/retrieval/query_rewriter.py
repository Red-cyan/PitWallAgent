import json
import re

from app.services.llm.client import LLMClient


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
        "底板": "plank",
        "木板": "plank",
    }

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    def rewrite(self, question: str) -> list[str]:
        if not self._should_rewrite(question):
            return []

        try:
            llm_client = self.llm_client or LLMClient()
            response = llm_client.chat(
                messages=self._build_messages(question),
                temperature=0,
            )
            return self._parse_response(response)
        except Exception:
            return []

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
