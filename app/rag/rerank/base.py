from abc import ABC, abstractmethod


class Reranker(ABC):
    """查询-文档相关性打分接口。"""

    @abstractmethod
    def score(self, query: str, texts: list[str]) -> list[float]:
        """返回每个 text 相对 query 的相关性分数，顺序与 texts 一一对应。"""
