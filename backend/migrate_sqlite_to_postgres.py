"""Migrate data from SQLite (learning_engine.db) to PostgreSQL.

Usage:
    cd backend
    python migrate_sqlite_to_postgres.py

    Or specify custom PostgreSQL connection:
    python migrate_sqlite_to_postgres.py --postgres "postgresql://user:pass@localhost:5432/intellirag"
"""
import sys
import argparse
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.config import DATABASE_URL
from app.database import (
    Base,
    User,
    Document,
    Attempt,
    Leaderboard,
    TopicScore,
    QuizAnswerLog,
    EvaluationReport,
    CourseNode,
)


def migrate(sqlite_path: Path, pg_url: str):
    print("=" * 60)
    print(" IntelliRAG SQLite -> PostgreSQL Data Migration")
    print("=" * 60)

    if not sqlite_path.exists():
        print(f"[!] SQLite file not found at: {sqlite_path}")
        print("Nothing to migrate. A fresh PostgreSQL schema will be initialized on app startup.")
        return

    sqlite_url = f"sqlite:///{sqlite_path}"
    print(f" Source SQLite:     {sqlite_url}")
    print(f" Target PostgreSQL: {pg_url}")
    print("-" * 60)

    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    pg_engine = create_engine(pg_url, pool_pre_ping=True)

    # Initialize tables in PostgreSQL
    print("[1/3] Ensuring PostgreSQL tables exist...")
    Base.metadata.create_all(bind=pg_engine)
    print("      Tables verified.")

    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    src = SqliteSession()
    dst = PgSession()

    tables = [
        ("Users", User),
        ("Documents", Document),
        ("Attempts", Attempt),
        ("Leaderboard", Leaderboard),
        ("TopicScores", TopicScore),
        ("QuizAnswerLogs", QuizAnswerLog),
        ("EvaluationReports", EvaluationReport),
        ("CourseNodes", CourseNode),
    ]

    print("\n[2/3] Migrating data records...")
    total_migrated = 0

    try:
        for name, model in tables:
            rows = src.query(model).all()
            count = len(rows)
            migrated_count = 0

            for r in rows:
                src.expunge(r)
                # Merge into PostgreSQL (avoids primary key collisions)
                dst.merge(r)
                migrated_count += 1

            dst.commit()
            total_migrated += migrated_count
            print(f"  - {name:<20}: {migrated_count:>5} / {count} rows synced")

        print("-" * 60)
        print(f"[3/3] Migration Complete! Total rows migrated: {total_migrated}")
        print("=" * 60)

    except Exception as e:
        dst.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate IntelliRAG from SQLite to PostgreSQL")
    parser.add_argument(
        "--postgres",
        type=str,
        default=DATABASE_URL if not DATABASE_URL.startswith("sqlite") else "postgresql://postgres:postgres@localhost:5432/intellirag",
        help="Target PostgreSQL connection URL (e.g. postgresql://user:pass@localhost:5432/dbname)",
    )
    parser.add_argument(
        "--sqlite",
        type=str,
        default=str(BASE_DIR / "learning_engine.db"),
        help="Path to source SQLite database file",
    )
    args = parser.parse_args()

    migrate(Path(args.sqlite), args.postgres)
