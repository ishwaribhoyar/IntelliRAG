"""Analytics / Health module — routes."""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check():
    """System health check — db, model, queue status."""
    from app.rag.embedder import get_model
    from app.tasks.pipeline_queue import queue_stats

    model_loaded = get_model() is not None
    db_ok = True
    try:
        from sqlalchemy import text
        from app.shared.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_ok = False

    q = queue_stats()
    return {
        "status": "ok" if (model_loaded and db_ok) else "degraded",
        "model_loaded": model_loaded,
        "db_connected": db_ok,
        "database": "connected" if db_ok else "error",
        "faiss_ready": True,
        "queue": q,
    }
