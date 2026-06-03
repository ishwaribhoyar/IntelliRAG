"""SQLAlchemy database models and engine setup."""
import logging
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Index, Text
)
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True, index=True)
    username = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    streak = Column(Integer, default=0)
    daily_xp = Column(Integer, default=0)
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Monetization and Tiered Infrastructure Columns
    tier = Column(String, default="free")  # free | premium
    daily_rag_count = Column(Integer, default=0)
    daily_quiz_count = Column(Integer, default=0)
    daily_summary_count = Column(Integer, default=0)
    daily_flashcard_count = Column(Integer, default=0)
    last_request_reset = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_users_daily_xp", "daily_xp"),
    )


class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    filename = Column(String, nullable=True)  # Original uploaded filename
    file_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="processing")  # processing | ready | failed
    error_message = Column(Text, nullable=True)
    processing_stage = Column(String, default="uploaded")  # uploaded|parsed|structured|embedded|indexed
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    processed_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_documents_doc_id", "doc_id"),
        Index("ix_documents_file_hash", "file_hash"),
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    doc_id = Column(String, nullable=False, index=True)
    quiz_type = Column(String, default="quiz")  # quiz | mock_test
    score = Column(Integer, default=0)
    total = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Leaderboard(Base):
    __tablename__ = "leaderboard"

    user_id = Column(String, primary_key=True)
    daily_xp = Column(Integer, default=0)
    last_reset = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_leaderboard_user_id", "user_id"),
    )


class TopicScore(Base):
    """Per-user per-topic accuracy tracking — persistent personalization."""
    __tablename__ = "topic_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    topic = Column(String, nullable=False)
    correct = Column(Integer, default=0)
    total = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_topic_scores_user_topic", "user_id", "topic", unique=True),
    )


class QuizAnswerLog(Base):
    """Per-answer event log for analytics and weakness insights."""
    __tablename__ = "quiz_answer_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    doc_id = Column(String, nullable=False, index=True)
    question_id = Column(String, nullable=False)
    topic = Column(String, nullable=True)
    is_correct = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_quiz_answer_logs_user_created", "user_id", "created_at"),
    )


class EvaluationReport(Base):
    """Persisted evaluation results for proof."""
    __tablename__ = "evaluation_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String, nullable=False, index=True)
    baseline_recall = Column(Float, default=0.0)
    hybrid_recall = Column(Float, default=0.0)
    reranked_recall = Column(Float, default=0.0)
    baseline_mrr = Column(Float, default=0.0)
    hybrid_mrr = Column(Float, default=0.0)
    reranked_mrr = Column(Float, default=0.0)
    not_found_accuracy = Column(Float, default=0.0)
    reranker_improvement_rate = Column(Float, default=0.0)
    chunk_quality_score = Column(Float, default=0.0)
    avg_retrieval_ms = Column(Float, default=0.0)
    avg_rerank_ms = Column(Float, default=0.0)
    avg_llm_ms = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CourseNode(Base):
    """Unified hierarchical knowledge tree per document."""
    __tablename__ = "course_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String, nullable=False, index=True)
    node_id = Column(String, nullable=False)
    parent_node_id = Column(String, nullable=True, index=True)
    level = Column(String, nullable=False)  # subject | unit | topic | subtopic
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    page = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_course_nodes_doc_node", "doc_id", "node_id", unique=True),
        Index("ix_course_nodes_doc_parent_order", "doc_id", "parent_node_id", "sort_order"),
    )


def init_db():
    """Create all tables."""
    # SQLite is strict about `CREATE INDEX` and may throw if the index already exists.
    # Since Render restarts/rehydrates the same DB file on some deploys, make startup idempotent.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        msg = str(e).lower()
        if "already exists" in msg and "create index" in msg:
            logger.warning("Ignoring SQLite index already-exists error during init_db: %s", e)
        else:
            raise

    # If create_all aborted mid-way, some tables (e.g. leaderboard) may be missing.
    # Create any missing ORM tables without re-running conflicting index DDL on existing tables.
    try:
        from sqlalchemy import inspect

        insp = inspect(engine)
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                table.create(bind=engine, checkfirst=True)
                logger.info("Created missing table: %s", table.name)
    except Exception:
        logger.exception("Failed to create missing tables after init_db")

    # Lightweight SQLite migration for new columns (no Alembic in this repo).
    # Only adds columns if they don't exist yet.
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            # 1. Documents table migration
            cols = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
            col_names = {c[1] for c in cols}  # second field is column name

            if "retry_count" not in col_names:
                conn.execute(text("ALTER TABLE documents ADD COLUMN retry_count INTEGER DEFAULT 0"))
            if "last_error" not in col_names:
                conn.execute(text("ALTER TABLE documents ADD COLUMN last_error TEXT"))

            # 2. Users table migration for tiered infrastructure
            users_cols = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            users_col_names = {c[1] for c in users_cols}

            if "tier" not in col_names:
                # Note: col_names is for documents, check users_col_names!
                if "tier" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN tier VARCHAR DEFAULT 'free'"))
                if "daily_rag_count" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN daily_rag_count INTEGER DEFAULT 0"))
                if "daily_quiz_count" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN daily_quiz_count INTEGER DEFAULT 0"))
                if "daily_summary_count" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN daily_summary_count INTEGER DEFAULT 0"))
                if "daily_flashcard_count" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN daily_flashcard_count INTEGER DEFAULT 0"))
                if "last_request_reset" not in users_col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_request_reset VARCHAR"))
    except Exception:
        # Non-fatal: columns will be present in fresh DBs; otherwise, endpoints using them may fail.
        logger.exception("DB migration for retry_count/last_error or users monetization columns failed")
