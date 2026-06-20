from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"
    storyscape_data_dir: Path = Path("data")
    storyscape_books_config: Path = Path("samples/books.yml")
    storyscape_task_queue_db: Path = Path(".storyscape/task_queue.sqlite3")
    storyscape_log_dir: Path = Path("logs")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
