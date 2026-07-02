from pathlib import Path

from app.schemas.rag import RegulationIngestionSummary
from app.schemas.rules import RetrievalDebugResponse, RetrievedChunk
from app.services.knowledge_service import KnowledgeService


class StubRuleRepository:
    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                content="Parc ferme conditions apply after qualifying.",
                score=11.0,
                document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                article="ARTICLE 40",
                section="Section B",
                page=20,
            )
        ]

    def debug_retrieval(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=question,
            normalized_question=question,
            rewritten_queries=[],
            retrieval_queries=[question],
            extracted_phrases=[],
            expanded_keywords=[],
            preferred_sections=["Section B"],
            retrieved_chunks=self.search_relevant_chunks(question, top_k=top_k),
        )


class StubIngestionService:
    def ingest_corpus(
        self,
        raw_dir: str | Path = "data/regulations/raw",
        output_path: str | Path = "data/regulations/processed/chunks.json",
        *,
        persist_json: bool = True,
        persist_db: bool = True,
        include_embeddings: bool = True,
    ) -> RegulationIngestionSummary:
        return RegulationIngestionSummary(
            document_count=1,
            chunk_count=5,
            embedded_chunk_count=5 if include_embeddings else 0,
            output_path=str(output_path) if persist_json else None,
            documents=[],
        )


def test_knowledge_service_delegates_retrieval() -> None:
    service = KnowledgeService(
        rule_repository=StubRuleRepository(),
        ingestion_service=StubIngestionService(),
    )

    chunks = service.retrieve_regulation_chunks("What is parc ferme?")
    debug = service.debug_regulation_retrieval("What is parc ferme?")

    assert len(chunks) == 1
    assert chunks[0].section == "Section B"
    assert debug.preferred_sections == ["Section B"]


def test_knowledge_service_delegates_ingestion() -> None:
    service = KnowledgeService(
        rule_repository=StubRuleRepository(),
        ingestion_service=StubIngestionService(),
    )

    summary = service.ingest_regulations(include_embeddings=False)

    assert summary.document_count == 1
    assert summary.embedded_chunk_count == 0
