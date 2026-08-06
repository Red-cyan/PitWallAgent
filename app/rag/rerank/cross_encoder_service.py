import logging
import os
from typing import Protocol, cast

from app.config.settings import settings
from app.core.logging import log_structured
from app.rag.rerank.base import Reranker


class CrossEncoderModel(Protocol):
    def predict(
        self,
        pairs: list[list[str]],
        batch_size: int,
        show_progress_bar: bool,
    ) -> list[float]:
        ...


class CrossEncoderReranker(Reranker):
    """基于 bge-reranker 交叉编码器的重排序服务。

    模型懒加载并按 (model_name, device) 进程内缓存；仅在显式开启时构建，
    避免在单元测试或非重排场景触发大模型下载。
    """

    _model_cache: dict[str, CrossEncoderModel] = {}

    def __init__(self, model_name: str | None = None) -> None:
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

        from sentence_transformers import CrossEncoder

        self.model_name = model_name or settings.regulation_rerank_model
        if self.model_name not in self._model_cache:
            self._model_cache[self.model_name] = cast(
                CrossEncoderModel,
                CrossEncoder(self.model_name, trust_remote_code=True),
            )
        self.model = self._model_cache[self.model_name]
        self.logger = logging.getLogger("pitwall.rerank")

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        pairs = [[query, text] for text in texts]
        try:
            scores = self.model.predict(
                pairs,
                batch_size=settings.regulation_rerank_batch_size,
                show_progress_bar=False,
            )
        except Exception as exc:
            log_structured(
                self.logger,
                "rerank_failed",
                error_type=exc.__class__.__name__,
            )
            raise
        return [float(score) for score in scores]
