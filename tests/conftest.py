from app.config.settings import settings


settings.session_backend = "memory"
settings.redis_url = None


def pytest_runtest_setup(item):
    settings.session_backend = "memory"
    settings.redis_url = None
