from abc import ABC, abstractmethod


class EmbeddingService(ABC):
    """文本向量服务接口。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。"""

