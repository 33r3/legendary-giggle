from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/raw.db"
    ingest_webhook_token: str = "changeme"
    game_seed: str = "dev-local"
    regions_content_dir: str = "./content/regions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
