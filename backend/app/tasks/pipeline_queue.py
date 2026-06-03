"""Adaptive async queue + worker pool for document ingestion."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.tasks.background import process_document_pipeline

import os

from app.config import (
    MAX_INGEST_QUEUE_SIZE,
    PIPELINE_MIN_WORKERS,
    PIPELINE_DEFAULT_WORKERS,
    PIPELINE_MAX_WORKERS,
)

logger = logging.getLogger(__name__)

MIN_WORKERS = max(1, PIPELINE_MIN_WORKERS)
DEFAULT_WORKERS = max(MIN_WORKERS, PIPELINE_DEFAULT_WORKERS)
MAX_WORKERS = max(DEFAULT_WORKERS, PIPELINE_MAX_WORKERS)

# PriorityQueue item: (priority, seq, doc_id)
# Lower `priority` gets processed first.
_queue: asyncio.PriorityQueue[tuple[float, int, str]] = asyncio.PriorityQueue()
_workers: dict[int, asyncio.Task] = {}
_scaler_task: asyncio.Task | None = None
_running = False
_busy_workers: set[int] = set()

# Pending entries tracked for queue position/wait-time calculation.
_pending: dict[str, dict[str, Any]] = {}
_pending_lock = asyncio.Lock()
_seq_counter = 0


def _target_workers() -> int:
    """Scale workers with queue depth without collapsing to MIN when backlog is empty.

    Previously: idle queue (q=0) mapped to MIN_WORKERS only, so the scaler cancelled
    extra workers right after startup. Keep DEFAULT_WORKERS as the idle baseline.
    """
    q = len(_pending)
    base = max(MIN_WORKERS, DEFAULT_WORKERS)
    scaled = base + (q // 2)
    return max(MIN_WORKERS, min(MAX_WORKERS, scaled))


async def _worker_loop(worker_id: int):
    logger.info("[queue] worker-%s started", worker_id)
    try:
        while _running:
            # Check if we should scale down gracefully before waiting for next job
            target = _target_workers()
            if len(_workers) > target:
                logger.info("[queue] worker-%s retiring gracefully (workers count %s > target %s)", worker_id, len(_workers), target)
                _workers.pop(worker_id, None)
                break

            priority, seq, doc_id = await _queue.get()
            _busy_workers.add(worker_id)
            try:
                async with _pending_lock:
                    entry = _pending.pop(doc_id, None)
                if not entry:
                    continue
                file_path = entry["file_path"]
                await process_document_pipeline(doc_id, file_path)
            except Exception as e:
                logger.error("[queue] worker-%s failed item: %s", worker_id, e, exc_info=True)
            finally:
                _busy_workers.discard(worker_id)
                _queue.task_done()
    except asyncio.CancelledError:
        pass
    finally:
        _busy_workers.discard(worker_id)
        logger.info("[queue] worker-%s stopped", worker_id)


async def _ensure_worker_count(desired: int):
    desired = max(MIN_WORKERS, min(MAX_WORKERS, desired))
    # Scale up
    while len(_workers) < desired:
        wid = 1
        while wid in _workers:
            wid += 1
        _workers[wid] = asyncio.create_task(_worker_loop(wid))
    # Scale down (only cancel idle workers)
    while len(_workers) > desired:
        idle_wids = [wid for wid in _workers if wid not in _busy_workers]
        if not idle_wids:
            break
        wid = idle_wids[-1]
        task = _workers.pop(wid)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _scaler_loop():
    while _running:
        try:
            await _ensure_worker_count(_target_workers())
        except Exception as e:
            logger.error("[queue] scaler error: %s", e, exc_info=True)
        await asyncio.sleep(2.0)


async def start_pipeline_pool(default_workers: int = DEFAULT_WORKERS):
    global _running, _scaler_task
    if _running:
        return
    _running = True
    try:
        await _ensure_worker_count(default_workers)
        _scaler_task = asyncio.create_task(_scaler_loop())
        logger.info("[queue] started with workers=%s", len(_workers))
    except Exception:
        _running = False
        raise


async def stop_pipeline_pool():
    global _running, _scaler_task
    if not _running:
        return
    _running = False
    if _scaler_task:
        _scaler_task.cancel()
        try:
            await _scaler_task
        except asyncio.CancelledError:
            pass
        _scaler_task = None
    for wid in list(_workers.keys()):
        task = _workers.pop(wid)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("[queue] stopped")


def _file_size_mb(file_path: str) -> float:
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 999999.0


async def enqueue_pipeline_job(doc_id: str, file_path: str, file_size_mb: float | None = None):
    # Backpressure (soft guard): actual rejection is handled in API layer,
    # but we also protect the queue internals.
    async with _pending_lock:
        if len(_pending) >= MAX_INGEST_QUEUE_SIZE:
            raise asyncio.QueueFull(f"Ingestion queue full (max={MAX_INGEST_QUEUE_SIZE}).")

        global _seq_counter
        _seq_counter += 1
        if file_size_mb is None:
            file_size_mb = _file_size_mb(file_path)

        # Priority rule: smaller docs first (lower priority value).
        priority = float(file_size_mb)
        _pending[doc_id] = {
            "doc_id": doc_id,
            "file_path": file_path,
            "priority": priority,
            "seq": _seq_counter,
            "enqueued_at": time.time(),
            "size_mb": file_size_mb,
        }

        await _queue.put((priority, _seq_counter, doc_id))


async def get_doc_queue_info(doc_id: str) -> dict[str, Any] | None:
    """Return queue position + estimated wait for a doc if still queued."""
    async with _pending_lock:
        if doc_id not in _pending:
            return None

        entries = sorted(_pending.values(), key=lambda e: (e["priority"], e["seq"]))
        pos = next((i for i, e in enumerate(entries) if e["doc_id"] == doc_id), None)
        queue_length = len(entries)
        active_workers = max(len(_workers), 1)
        estimated_wait = queue_length / active_workers

        return {
            "doc_id": doc_id,
            "queue_length": queue_length,
            "doc_position_in_queue": int(pos) + 1 if pos is not None else None,
            "estimated_wait": estimated_wait,
            "active_workers": active_workers,
        }


def queue_stats() -> dict[str, int]:
    return {
        "queued": len(_pending),
        "workers": len(_workers),
        "min_workers": MIN_WORKERS,
        "max_workers": MAX_WORKERS,
    }
