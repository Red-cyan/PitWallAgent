from pathlib import Path
from typing import Any

from app.repositories.rule_repository import RuleRepository
from app.schemas.rag import RegulationIngestionSummary
from app.schemas.rules import ActiveCorpusResponse, RetrievalDebugResponse, RetrievedChunk
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
        try:
            return self.rule_repository.search_relevant_chunks(question, top_k)
        except TypeError:
            return self.rule_repository.search_relevant_chunks(question)

    def debug_regulation_retrieval(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        try:
            return self.rule_repository.debug_retrieval(question, top_k)
        except TypeError:
            return self.rule_repository.debug_retrieval(question)

    def get_active_corpus(self) -> ActiveCorpusResponse | None:
        return self.rule_repository.get_active_corpus()

    def ingest_regulations(
        self,
        raw_dir: str | Path = "data/regulations/raw",
        output_path: str | Path = "data/regulations/processed/chunks.json",
        *,
        persist_json: bool = True,
        persist_db: bool = True,
        include_embeddings: bool = True,
        corpus_version: str | None = None,
        validate_only: bool = False,
        emit_markdown: bool = False,
        activate: bool = False,
    ) -> RegulationIngestionSummary:
        kwargs: dict[str, Any] = {
            "raw_dir": raw_dir,
            "output_path": output_path,
            "persist_json": persist_json,
            "persist_db": persist_db,
            "include_embeddings": include_embeddings,
        }
        if corpus_version is not None:
            kwargs["corpus_version"] = corpus_version
        if validate_only:
            kwargs["validate_only"] = True
        if emit_markdown:
            kwargs["emit_markdown"] = True
        if activate:
            kwargs["activate"] = True
        return self.ingestion_service.ingest_corpus(
            **kwargs,
        )
