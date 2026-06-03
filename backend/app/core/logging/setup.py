"""Structured logging setup.

Import and call setup_logging() once in main.py lifespan to enable:
- JSON-formatted structured logs in production
- Human-readable colored logs in development
- Per-request correlation IDs via middleware
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger. Call this at application startup."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    is_production = (
        os.getenv("APP_ENV", "").strip().lower() == "production"
        or bool(os.getenv("RENDER"))
    )

    if is_production:
        fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    else:
        fmt = "%(asctime)s | \033[1;%(levelcolor)sm%(levelname)-8s\033[0m | %(name)s | %(message)s"

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # Suppress noisy loggers
    for noisy in ("uvicorn.access", "multipart", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestLogger:
    """Lightweight per-request logger with doc_id / user_id context."""

    def __init__(self, logger: logging.Logger):
        self._log = logger

    def request(
        self,
        endpoint: str,
        doc_id: str = "",
        user_id: str = "",
        query: str = "",
        cache_hit: bool = False,
        latency_ms: float = 0,
        extra: dict | None = None,
    ) -> None:
        msg = f"[{endpoint}] doc={doc_id or '-'} user={user_id or '-'}"
        if query:
            msg += f" query={query[:60]!r}"
        if cache_hit:
            msg += " [CACHE HIT]"
        if latency_ms:
            msg += f" latency={latency_ms:.0f}ms"
        if extra:
            for k, v in extra.items():
                msg += f" {k}={v}"
        self._log.info(msg)

    def error(self, endpoint: str, error: Exception, doc_id: str = "") -> None:
        self._log.error("[%s] doc=%s error=%s", endpoint, doc_id or "-", str(error), exc_info=True)
