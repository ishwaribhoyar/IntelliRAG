"""FastAPI main application — IntelliRAG Advanced RAG System entry point.

Router registration order:
  1. Module routers (new, clean, per-feature)  ← preferred for new development
  2. Legacy monolithic router (api/routes.py)   ← kept for 100% backward compat
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
from app.api.routes import router as legacy_router          # backward compat
from app.rag.embedder import warmup
from app.gamification.leaderboard import load_leaderboard_cache
from app.tasks.background import flush_pending_updates
from app.tasks.pipeline_queue import start_pipeline_pool, stop_pipeline_pool
from app.config import LLM_PROVIDER
from app.core.logging import setup_logging
from app.core.exceptions import register_exception_handlers

# --- Module routers ---
from app.modules.auth.routes import router as auth_router
from app.modules.upload_pipeline.routes import router as upload_router
from app.modules.ask_ai.routes import router as ask_router
from app.modules.quizzes.routes import router as quiz_router
from app.modules.flashcards.routes import router as flashcards_router
from app.modules.search_engine.routes import router as search_router
from app.modules.evaluation.routes import router as eval_router
from app.modules.weaknesses.routes import router as weakness_router
from app.modules.content_library.routes import router as library_router
from app.modules.courses.routes import router as courses_router
from app.modules.gamification.routes import router as gamification_router
from app.modules.analytics.routes import router as analytics_router
from app.modules.payments.routes import router as payments_router

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
IS_PRODUCTION = (
    os.getenv("APP_ENV", "").strip().lower() == "production"
    or bool(os.getenv("RENDER"))
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("Starting IntelliRAG — Advanced RAG System...")

    # 1. Initialize database tables
    init_db()
    logger.info("[OK] Database initialized")

    # 2. Warm up embedding model in background
    asyncio.create_task(asyncio.to_thread(warmup))
    logger.info("[OK] Embedding warmup started in background")

    # 3. Load leaderboard cache from DB
    try:
        load_leaderboard_cache()
        logger.info("[OK] Leaderboard cache loaded")
    except Exception:
        logger.exception("Leaderboard cache load failed; continuing with empty cache")

    # 4. Load content library catalog
    try:
        from app.core.library import _load_catalog
        _load_catalog()
        logger.info("[OK] Content library catalog loaded")
    except Exception as e:
        logger.warning("Library catalog load skipped: %s", e)

    # 5. Start background flush task
    flush_task = asyncio.create_task(flush_pending_updates())
    logger.info("[OK] Background flush task started")

    # 6. Start ingestion queue worker pool
    try:
        await start_pipeline_pool()
        logger.info("[OK] Ingestion worker pool started")
    except Exception:
        logger.exception("Ingestion worker pool failed to start; continuing without background workers")

    logger.info("=" * 60)
    logger.info("System READY - Advanced RAG pipeline operational")
    logger.info("  Retrieval: Hybrid (FAISS + BM25 + RRF)")
    logger.info("  Features:  Search Engine | Personalization | Content Library")
    logger.info("  LLM Provider: %s", LLM_PROVIDER)
    logger.info("=" * 60)

    yield

    # --- SHUTDOWN ---
    flush_task.cancel()
    await stop_pipeline_pool()
    logger.info("System shutting down")


app = FastAPI(
    title="IntelliRAG — Advanced RAG System",
    description="Production-ready AI Document Retrieval + Learning System with hybrid search, personalization, and content library.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Centralized exception handlers (consistent JSON errors for all exceptions)
register_exception_handlers(app)

# No-cache middleware (dev mode only)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.endswith(('.js', '.css', '.html')) or request.url.path == '/':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response


if not IS_PRODUCTION:
    app.add_middleware(NoCacheMiddleware)

# ── Module Routers (new modular architecture) ──────────────────────────────
# Each module owns its own routes, service, and schemas.
# These are the preferred entry points for all features.
app.include_router(auth_router,         prefix="/api")
app.include_router(upload_router,       prefix="/api")
app.include_router(ask_router,          prefix="/api")
app.include_router(quiz_router,         prefix="/api")
app.include_router(flashcards_router,   prefix="/api")
app.include_router(search_router,       prefix="/api")
app.include_router(eval_router,         prefix="/api")
app.include_router(weakness_router,     prefix="/api")
app.include_router(library_router,      prefix="/api")
app.include_router(courses_router,      prefix="/api")
app.include_router(gamification_router, prefix="/api")
app.include_router(analytics_router,    prefix="/api")
app.include_router(payments_router,     prefix="/api")

# ── Legacy Router (backward compatibility) ─────────────────────────────────
# The original monolithic router is still included so that any integration
# that was calling /api/* continues to work unchanged.
# Once all callers are migrated to module routers, this line can be removed.
app.include_router(legacy_router, prefix="/api")

# Serve frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="root")
else:
    @app.get("/")
    async def root():
        return {"message": "IntelliRAG — Advanced RAG System", "docs": "/docs"}
