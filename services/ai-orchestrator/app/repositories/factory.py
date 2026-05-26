from pathlib import Path

from app.core.settings import Settings
from app.repositories.base import Repository
from app.repositories.memory import MemoryRepository
from app.repositories.postgres import PostgresRepository


def build_repository(settings: Settings) -> Repository:
    provider = settings.repository_provider.lower()
    if provider == "memory":
        return MemoryRepository()
    if provider == "postgres":
        schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
        return PostgresRepository(settings.postgres_dsn, schema_path)
    raise ValueError(f"Unknown repository provider: {settings.repository_provider}")
