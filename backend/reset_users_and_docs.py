"""One-off maintenance script to wipe users and documents data.

Usage (local):
    cd backend
    python reset_users_and_docs.py

Usage on Render (one-off shell):
    cd backend
    python reset_users_and_docs.py

This only deletes application data (users / documents and their derived records),
not the database file or schema.
"""

from app.database import (
    SessionLocal,
    User,
    Document,
    Attempt,
    Leaderboard,
    TopicScore,
    QuizAnswerLog,
    EvaluationReport,
    CourseNode,
)


def main() -> None:
    db = SessionLocal()
    try:
        # Delete dependent / derived records first, then core entities.
        db.query(QuizAnswerLog).delete()
        db.query(TopicScore).delete()
        db.query(Attempt).delete()
        db.query(EvaluationReport).delete()
        db.query(CourseNode).delete()
        db.query(Leaderboard).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.commit()
        print("[OK] Deleted all users, documents, and related quiz/leaderboard records.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

