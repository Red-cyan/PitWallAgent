from app.config.settings import settings
from app.rag.rerank.base import Reranker


def build_reranker() -> Reranker | None:
    """构建默认重排序服务；未开启或加载失败时返回 None 以便优雅降级。"""

    if not settings.regulation_rerank_enabled:
        return None
    try:
        from app.rag.rerank.cross_encoder_service import CrossEncoderReranker

        return CrossEncoderReranker()
    except Exception:
        return None
