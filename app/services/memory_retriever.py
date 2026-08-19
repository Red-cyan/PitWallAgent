from __future__ import annotations

import hashlib
import logging
import math
from typing import Protocol

from app.config.settings import settings
from app.services.memory_service import LongTermMemory


class MemoryEmbedder(Protocol):
    """记忆向量化所需的最小接口，与 BGE 服务对齐。"""

    def embed_query(self, query: str) -> list[float]: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class SemanticMemoryRetriever:
    """基于向量的长时记忆召回。

    用 BGE-M3 把查询与记忆内容分别向量化，按余弦相似度排序，
    替代原先的词典重叠打分；记忆向量按 (owner, memory_id) 进程内缓存。
    语义路径不可用时返回 None，由调用方回退到词典打分，保证确定性降级。
    """

    _memory_embedding_cache: dict[str, list[float]] = {}
    _cache_limit = 2000

    def __init__(self, embedder: MemoryEmbedder | None = None) -> None:
        self._embedder = embedder
        self._embedder_failed = False
        self.logger = logging.getLogger("pitwall.memory_retriever")

    @property
    def enabled(self) -> bool:
        return settings.memory_vector_retrieval_enabled

    def retrieve(
        self,
        query: str,
        memories: list[LongTermMemory],
        top_k: int,
    ) -> list[LongTermMemory] | None:
        """返回语义召回的 top_k 记忆；不可用时返回 None 以触发词法回退。"""
        if not self.enabled or not memories or top_k < 1:
            return None

        embedder = self._get_embedder()
        if embedder is None:
            return None

        try:
            query_vector = embedder.embed_query(query)
        except Exception:
            self.logger.warning("memory semantic query embedding failed; fallback to lexical")
            return None

        scored: list[tuple[float, LongTermMemory]] = []
        for memory in memories:
            vector = self._memory_vector(embedder, memory)
            if vector is None:
                continue
            similarity = self._cosine_similarity(query_vector, vector)
            scored.append((similarity + memory.confidence * 0.05, memory))

        if not scored:
            return None

        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return [memory for _, memory in scored[:top_k]]

    def _memory_vector(
        self,
        embedder: MemoryEmbedder,
        memory: LongTermMemory,
    ) -> list[float] | None:
        # 缓存键含内容指纹：constraint/fact 类记忆覆盖内容后 memory_id 不变，
        # 若仅按 (owner, memory_id) 缓存会持续命中旧向量，导致召回结果与持久化内容不一致。
        digest = hashlib.sha1(memory.content.encode("utf-8")).hexdigest()[:12]
        key = f"{memory.owner_id}:{memory.memory_id}:{digest}"
        cached = self._memory_embedding_cache.get(key)
        if cached is not None:
            return cached
        try:
            vector = embedder.embed_texts([memory.content])[0]
        except Exception:
            self.logger.warning("memory content embedding failed for %s", key)
            return None
        if len(self._memory_embedding_cache) >= self._cache_limit:
            self._memory_embedding_cache.clear()
        self._memory_embedding_cache[key] = vector
        return vector

    def _get_embedder(self) -> MemoryEmbedder | None:
        if self._embedder is not None:
            return self._embedder
        if self._embedder_failed:
            return None
        try:
            from app.rag.embedding.factory import build_embedding_service

            return build_embedding_service()
        except Exception:
            self._embedder_failed = True
            return None

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        norm_left = math.sqrt(sum(a * a for a in left))
        norm_right = math.sqrt(sum(b * b for b in right))
        if norm_left == 0 or norm_right == 0:
            return 0.0
        return dot / (norm_left * norm_right)
