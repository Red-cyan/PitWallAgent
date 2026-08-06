from pathlib import Path

import pytest

from app.config.settings import settings


settings.session_backend = "memory"
settings.redis_url = None
settings.regulation_prefer_database = False
settings.regulation_vector_retrieval_enabled = False
settings.regulation_rerank_enabled = False
settings.llm_api_key = None
settings.llm_planner_enabled = False


def pytest_runtest_setup(item):
    settings.session_backend = "memory"
    settings.redis_url = None
    settings.regulation_prefer_database = False
    settings.regulation_vector_retrieval_enabled = False
    settings.regulation_rerank_enabled = False
    settings.llm_api_key = None
    settings.llm_planner_enabled = False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path)).as_posix()
        if "/infrastructure/" in f"/{path}":
            item.add_marker(pytest.mark.infrastructure)
        elif "/evals/" in f"/{path}":
            item.add_marker(pytest.mark.eval)
        elif "/api/" in f"/{path}" or "/repositories/" in f"/{path}":
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
