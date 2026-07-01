from app.rag.embedding.base import EmbeddingService
from app.rag.embedding.bge_service import BgeEmbeddingService


def build_embedding_service() -> EmbeddingService:
    """构建默认向量服务。"""

    return BgeEmbeddingService()
