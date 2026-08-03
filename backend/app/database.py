from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///storage/"):
        database_path = settings.storage_dir / url.removeprefix("sqlite:///storage/")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path.as_posix()}"
    if url.startswith("sqlite:///runtime/"):
        database_path = Path(__file__).resolve().parents[1] / "runtime" / url.removeprefix("sqlite:///runtime/")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path.as_posix()}"
    return url


database_url = _database_url()
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    poolclass=StaticPool if database_url == "sqlite:///:memory:" else None,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def initialize_database() -> None:
    from app import domain_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
