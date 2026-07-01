from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目运行配置。"""

    app_name: str = "PitWall Agent"
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "DEEPSEEK_API_KEY"),
    )
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    regulation_embedding_model: str = "BAAI/bge-m3"
    regulation_embedding_batch_size: int = 8
    regulation_embedding_device: str = "cpu"
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


settings = Settings()
