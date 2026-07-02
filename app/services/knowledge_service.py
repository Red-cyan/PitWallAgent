from pathlib import Path

from app.repositories.rule_repository import RuleRepository
from app.schemas.rag import RegulationIngestionSummary
from app.schemas.rules import RetrievalDebugResponse, RetrievedChunk
from app.services.regulation_ingestion_service import RegulationIngestionService


class KnowledgeService:
    def __init__(
        self,
        rule_repository: RuleRepository | None = None,
        ingestion_service: RegulationIngestionService | None = None,
    ) -> None:
        self.rule_repository = rule_repository or RuleRepository()
        self.ingestion_service = ingestion_service or RegulationIngestionService()

    def retrieve_regulation_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        return self.rule_repository.search_relevant_chunks(question=question, top_k=top_k)

    def debug_regulation_retrieval(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        return self.rule_repository.debug_retrieval(question=question, top_k=top_k)

    def ingest_regulations(
        self,
        raw_dir: str | Path = "data/regulations/raw",
        output_path: str | Path = "data/regulations/processed/chunks.json",
        *,
        persist_json: bool = True,
        persist_db: bool = True,
        include_embeddings: bool = True,
    ) -> RegulationIngestionSummary:
        return self.ingestion_service.ingest_corpus(
            raw_dir=raw_dir,
            output_path=output_path,
            persist_json=persist_json,
            persist_db=persist_db,
            include_embeddings=include_embeddings,
        )
