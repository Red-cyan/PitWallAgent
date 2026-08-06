import os
from typing import Any, Protocol, cast

from app.config.settings import settings
from app.rag.embedding.base import EmbeddingService


class SentenceTransformerModel(Protocol):
    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int,
        normalize_embeddings: bool,
        convert_to_numpy: bool,
        show_progress_bar: bool,
    ) -> Any:
        ...


class BgeEmbeddingService(EmbeddingService):
    """基于 BGE-M3 的本地向量服务。"""

    _model_cache: dict[tuple[str, str], SentenceTransformerModel] = {}

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        if settings.hf_token:
            os.environ["HF_TOKEN"] = settings.hf_token
            os.environ["HUGGINGFACE_HUB_TOKEN"] = settings.hf_token
        if settings.hf_home:
            os.environ["HF_HOME"] = settings.hf_home
        if settings.hf_hub_cache:
            os.environ["HF_HUB_CACHE"] = settings.hf_hub_cache
        if settings.transformers_cache:
            os.environ["TRANSFORMERS_CACHE"] = settings.transformers_cache
        if settings.sentence_transformers_home:
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = settings.sentence_transformers_home

        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or settings.regulation_embedding_model
        self.device = device or settings.regulation_embedding_device
        cache_key = (self.model_name, self.device)

        if cache_key not in self._model_cache:
            self._model_cache[cache_key] = cast(
                SentenceTransformerModel,
                SentenceTransformer(self.model_name, device=self.device),
            )

        self.model = self._model_cache[cache_key]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            batch_size=settings.regulation_embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return cast(Any, embeddings).tolist()

    def embed_query(self, query: str) -> list[float]:
        """生成检索查询向量，按 BGE 官方建议附加查询指令前缀。

        BGE-M3 在文档与查询上使用一致的稠密编码，查询侧附加指令可提升
        retrieval 效果；文档向量在入库时已固定，不再重复附加。
        """
        instruction = settings.regulation_embedding_query_instruction
        if not instruction or query.startswith(instruction):
            return self.embed_texts([query])[0]
        return self.embed_texts([f"{instruction}{query}"])[0]
