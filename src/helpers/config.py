from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str
    OPENAI_API_KEY: str
    FILE_ALLOWED_TYPES: list[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env")


def get_settings():
    return settings()
