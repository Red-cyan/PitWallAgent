from typing import Any

import pytest

from app.rag.rerank.cross_encoder_service import CrossEncoderReranker
from app.rag.rerank.factory import build_reranker


class FakeCrossEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.pairs: list[list[str]] = []

    def predict(self, pairs: list[list[str]], batch_size: int, show_progress_bar: bool) -> list[float]:
        self.pairs = pairs
        return self.scores


def test_cross_encoder_reranker_scores_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        CrossEncoderReranker,
        "_model_cache",
        {"model": FakeCrossEncoder([0.9, 0.1])},
    )

    reranker = CrossEncoderReranker(model_name="model")
    scores = reranker.score("safety car rule?", ["text a", "text b"])

    assert scores == [0.9, 0.1]
    assert reranker.model.pairs[0] == ["safety car rule?", "text a"]


def test_cross_encoder_reranker_returns_empty_for_no_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        CrossEncoderReranker,
        "_model_cache",
        {"fake-model": FakeCrossEncoder([0.5])},
    )
    monkeypatch.setattr("app.rag.rerank.cross_encoder_service.settings.regulation_rerank_model", "fake-model")

    reranker = CrossEncoderReranker(model_name="fake-model")
    assert reranker.score("query", []) == []


def test_factory_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.rerank.factory.settings.regulation_rerank_enabled", False)
    assert build_reranker() is None


def test_factory_returns_none_on_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from app.rag.rerank import cross_encoder_service

    monkeypatch.setattr("app.rag.rerank.factory.settings.regulation_rerank_enabled", True)

    def _boom() -> Any:
        raise RuntimeError("cannot load model")

    monkeypatch.setattr(cross_encoder_service, "CrossEncoderReranker", _boom)
    monkeypatch.setitem(sys.modules, "app.rag.rerank.cross_encoder_service", cross_encoder_service)
    assert build_reranker() is None
