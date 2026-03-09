from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")


def _coerce_sqlalchemy_database_url(url: str) -> str:
    # Render may run newer Python versions where psycopg2 wheels are not available.
    # We standardize on psycopg (psycopg3) for Postgres.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url

engine = create_engine(
    _coerce_sqlalchemy_database_url(DATABASE_URL),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
