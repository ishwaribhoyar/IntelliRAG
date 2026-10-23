"""Shared database session — engine, SessionLocal, get_db.

This module is the single source of truth for DB connectivity.
Supports PostgreSQL (production & configured local) and SQLite (local fallback).
"""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL, BASE_DIR

logger = logging.getLogger(__name__)


def _init_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})

    # Attempt PostgreSQL connection
    try:
        pg_engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        # Test connectivity
        with pg_engine.connect():
            pass
        logger.info("[DB] Connected successfully to PostgreSQL: %s", pg_engine.url.render_as_string(hide_password=True))
        return pg_engine
    except Exception as e:
        logger.warning(
            "[DB WARNING] Failed to connect to PostgreSQL (%s): %s. "
            "Falling back to local SQLite for development.",
            url.split("@")[-1] if "@" in url else url,
            e,
        )
        sqlite_url = f"sqlite:///{BASE_DIR / 'learning_engine.db'}"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = _init_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
