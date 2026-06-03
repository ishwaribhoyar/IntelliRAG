"""Centralized exception handlers for FastAPI.

Register these in main.py using app.add_exception_handler().
Provides consistent JSON error responses for all exception types.
"""
from __future__ import annotations

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle FastAPI/Starlette HTTP exceptions → consistent JSON shape."""
    logger.warning(
        "HTTP %s at %s — %s",
        exc.status_code, request.url.path, exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors → user-friendly messages."""
    errors = []
    for e in exc.errors():
        loc = " -> ".join(str(x) for x in e.get("loc", []) if x != "body")
        errors.append(f"{loc}: {e['msg']}" if loc else e["msg"])

    logger.warning("Validation error at %s: %s", request.url.path, errors)
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "status_code": 422,
            "detail": "Invalid request",
            "errors": errors,
            "path": str(request.url.path),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — never expose a traceback to clients."""
    logger.exception("Unhandled error at %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "An unexpected error occurred. Please try again.",
            "path": str(request.url.path),
        },
    )


def register_exception_handlers(app) -> None:
    """Register all exception handlers on a FastAPI app instance.

    Usage (in main.py):
        from app.core.exceptions.handlers import register_exception_handlers
        register_exception_handlers(app)
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
