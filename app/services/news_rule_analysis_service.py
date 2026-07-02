from dataclasses import dataclass

from app.repositories.rule_repository import RuleRepository
from app.schemas.news import NewsArticleRead, NewsRuleAnalysisResponse, RuleTopicMatch
from app.schemas.rules import RetrievedChunk


@dataclass(frozen=True)
class TopicDefinition:
    topic_key: str
    title: str
    keywords: tuple[str, ...]
    suggested_questions: tuple[str, ...]


class NewsRuleAnalysisService:
    """新闻到规则的轻量联动分析服务。"""

    TOPIC_DEFINITIONS = (
        TopicDefinition(
            topic_key="red_flag",
            title="红旗与比赛暂停",
            keywords=("red flag", "race suspended", "session suspended", "红旗", "暂停"),
            suggested_questions=(
                "What is the red flag procedure in Formula 1?",
                "When can the Race Director suspend a session or race?",
            ),
        ),
        TopicDefinition(
            topic_key="safety_car",
            title="安全车与虚拟安全车",
            keywords=("safety car", "virtual safety car", "vsc", "安全车", "虚拟安全车"),
            suggested_questions=(
                "What is the safety car procedure in Formula 1?",
                "What is the virtual safety car procedure in Formula 1?",
            ),
        ),
        TopicDefinition(
            topic_key="unsafe_release",
            title="维修区不安全释放",
            keywords=("unsafe release", "pit lane incident", "pit lane", "不安全释放", "维修区"),
            suggested_questions=(
                "What counts as an unsafe release in Formula 1?",
                "What penalties apply for an unsafe release?",
            ),
        ),
        TopicDefinition(
            topic_key="parc_ferme",
            title="封闭维修区",
            keywords=("parc ferme", "封闭维修", "setup change", "set-up change"),
            suggested_questions=(
                "What are the parc ferme restrictions in Formula 1?",
                "When can a team change car setup under parc ferme conditions?",
            ),
        ),
        TopicDefinition(
            topic_key="stewards_penalty",
            title="赛会干事与处罚",
            keywords=("penalty", "stewards", "investigation", "summoned", "处罚", "调查"),
            suggested_questions=(
                "How do the stewards handle penalties in Formula 1?",
                "What penalty options are available to FIA stewards?",
            ),
        ),
        TopicDefinition(
            topic_key="technical_compliance",
            title="技术合规与底板",
            keywords=("plank", "floor", "ride height", "disqualification", "technical", "底板", "技术违规"),
            suggested_questions=(
                "What are the plank wear limits in Formula 1?",
                "What technical infringements can lead to disqualification in Formula 1?",
            ),
        ),
    )

    def __init__(self, rule_repository: RuleRepository | None = None) -> None:
        self.rule_repository = rule_repository or RuleRepository()

    def analyze(self, article: NewsArticleRead, top_k: int = 3) -> NewsRuleAnalysisResponse:
        matched_topics = self._match_topics(article)
        suggested_questions = self._build_suggested_questions(article, matched_topics)
        related_chunks = self._retrieve_related_chunks(suggested_questions, top_k=top_k)
        analysis_summary = self._build_summary(article, matched_topics, related_chunks)

        return NewsRuleAnalysisResponse(
            article=article,
            matched_topics=matched_topics,
            suggested_questions=suggested_questions,
            related_chunks=related_chunks,
            analysis_summary=analysis_summary,
        )

    def _match_topics(self, article: NewsArticleRead) -> list[RuleTopicMatch]:
        corpus = self._build_corpus(article)
        matched_topics: list[RuleTopicMatch] = []

        for definition in self.TOPIC_DEFINITIONS:
            matched_keywords = [keyword for keyword in definition.keywords if keyword in corpus]
            if not matched_keywords:
                continue

            matched_topics.append(
                RuleTopicMatch(
                    topic_key=definition.topic_key,
                    title=definition.title,
                    reason=f"新闻内容命中了关键词：{', '.join(matched_keywords[:3])}",
                )
            )

        return matched_topics

    def _build_suggested_questions(
        self,
        article: NewsArticleRead,
        matched_topics: list[RuleTopicMatch],
    ) -> list[str]:
        questions: list[str] = []
        topic_map = {definition.topic_key: definition for definition in self.TOPIC_DEFINITIONS}

        for topic in matched_topics:
            definition = topic_map.get(topic.topic_key)
            if definition is None:
                continue
            questions.extend(definition.suggested_questions)

        if not questions:
            headline = article.title.strip()
            questions = [
                f"What Formula 1 sporting or technical rules are relevant to this news: {headline}?",
                f"What FIA Formula 1 regulations could be relevant to the incident described in: {headline}?",
            ]

        deduplicated_questions: list[str] = []
        seen: set[str] = set()
        for question in questions:
            if question in seen:
                continue
            seen.add(question)
            deduplicated_questions.append(question)

        return deduplicated_questions[:4]

    def _retrieve_related_chunks(self, suggested_questions: list[str], top_k: int) -> list[RetrievedChunk]:
        merged_chunks: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()

        for question in suggested_questions[:3]:
            for chunk in self.rule_repository.search_relevant_chunks(question, top_k=top_k):
                if chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.chunk_id)
                merged_chunks.append(chunk)

                if len(merged_chunks) >= top_k:
                    return merged_chunks

        return merged_chunks

    def _build_summary(
        self,
        article: NewsArticleRead,
        matched_topics: list[RuleTopicMatch],
        related_chunks: list[RetrievedChunk],
    ) -> str:
        if matched_topics:
            topic_titles = "、".join(topic.title for topic in matched_topics[:3])
            return f"这条新闻主要关联 {topic_titles}，已生成规则检索问题并召回 {len(related_chunks)} 个相关规则片段。"

        return (
            f"这条新闻未命中明确的预设规则主题，系统已根据标题《{article.title}》"
            f"生成通用规则检索问题，并召回 {len(related_chunks)} 个相关规则片段。"
        )

    def _build_corpus(self, article: NewsArticleRead) -> str:
        parts = [
            article.title,
            article.summary or "",
            article.content or "",
            " ".join(article.tags),
        ]
        return " ".join(parts).lower()
