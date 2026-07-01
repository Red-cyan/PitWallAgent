from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目运行配置。"""

    app_name: str = "PitWall Agent"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pitwall"
    postgres_user: str = "pitwall"
    postgres_password: str = "pitwall"
    regulation_embedding_dim: int = 1536
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
