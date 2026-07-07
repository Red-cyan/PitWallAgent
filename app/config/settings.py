from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目运行配置。"""

    app_name: str = "PitWall Agent"
    app_log_level: str = "INFO"
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "DEEPSEEK_API_KEY"),
    )
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 1
    llm_max_tokens: int | None = 700
    llm_planner_enabled: bool = True
    llm_planner_max_tokens: int = 160
    llm_planner_timeout_seconds: float = 4.0
    query_rewrite_max_tokens: int = 180
    query_rewrite_timeout_seconds: float = 4.0
    hf_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"),
    )
    hf_home: str | None = None
    hf_hub_cache: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"),
    )
    transformers_cache: str | None = None
    sentence_transformers_home: str | None = None
    regulation_embedding_model: str = "BAAI/bge-m3"
    regulation_embedding_batch_size: int = 8
    regulation_embedding_device: str = "cpu"
    formula1_feed_url: str = "https://www.formula1.com/en/latest/all.xml"
    news_request_timeout_seconds: float = 10.0
    news_user_agent: str = "PitWall-Agent/0.1"
    race_data_base_url: str = "https://api.jolpi.ca/ergast/f1"
    race_request_timeout_seconds: float = 3.0
    race_cache_ttl_seconds: int = 300
    race_default_season: str = "current"
    session_backend: str = "memory"
    session_history_max_turns: int = 20
    session_ttl_seconds: int = 86400
    memory_recent_turns: int = 4
    memory_context_token_budget: int = 1200
    memory_summary_token_budget: int = 260
    memory_compaction_token_threshold: int = 1600
    memory_long_term_enabled: bool = True
    memory_long_term_backend: str = "memory"
    memory_long_term_ttl_seconds: int = 2592000
    memory_long_term_top_k: int = 3
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_url: str | None = Field(default=None)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pitwall"
    postgres_user: str = "pitwall"
    postgres_password: str = "pitwall"
    regulation_embedding_dim: int = 1024
    database_url: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url

        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def resolved_cors_allow_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
