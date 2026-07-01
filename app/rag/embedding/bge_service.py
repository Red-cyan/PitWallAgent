from sentence_transformers import SentenceTransformer

from app.config.settings import settings
from app.rag.embedding.base import EmbeddingService


class BgeEmbeddingService(EmbeddingService):
    """基于 BGE-M3 的本地向量服务。"""

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or settings.regulation_embedding_model
        self.device = device or settings.regulation_embedding_device
        self.model = SentenceTransformer(self.model_name, device=self.device)

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
        return embeddings.tolist()
