"""Embedding engine — singleton MiniLM model with warmup.

Step 1 (Feature 2): adds optional micro-batching for ingestion-time embeddings.
Chunking/retrieval callers can keep using `embed_texts()` unchanged.
"""
from __future__ import annotations

import logging
import asyncio
import time
import numpy as np
from typing import TYPE_CHECKING

from app.config import EMBEDDING_MODEL_NAME, EMBED_BATCH_WINDOW_S

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load MiniLM lazily so importing this module does not pull torch (fast uvicorn bind on PaaS)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer as ST

        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        _model = ST(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    return _model


def warmup():
    """Warm up the model on startup to avoid cold-start latency."""
    model = get_model()
    model.encode(["warmup"])
    logger.info("Embedding model warmed up")


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts, returns numpy array of embeddings."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings


def embed_single(text: str) -> np.ndarray:
    """Embed a single text."""
    return embed_texts([text])[0]


class EmbeddingBatcher:
    """Micro-batch embedding requests across multiple documents.

    - Batches requests arriving within a small time window.
    - Uses a single model encode lock so only one encode call runs at a time.
    - Falls back to per-request `embed_texts()` if batching fails.
    """

    def __init__(self, batch_window_s: float = EMBED_BATCH_WINDOW_S, max_batch_texts: int = 2048):
        self.batch_window_s = batch_window_s
        self.max_batch_texts = max_batch_texts

        # Queue items: (texts, future) where future resolves to np.ndarray
        self._queue: asyncio.Queue[tuple[list[str], asyncio.Future]] = asyncio.Queue()
        self._runner_task: asyncio.Task | None = None
        self._model_encode_lock = asyncio.Lock()

    def _ensure_runner(self):
        if self._runner_task is None or self._runner_task.done():
            self._runner_task = asyncio.create_task(self._runner_loop())

    async def embed_texts_async(self, texts: list[str]) -> np.ndarray:
        if not texts:
            # Return empty array; callers can handle no embeddings.
            return np.zeros((0, 0), dtype="float32")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        await self._queue.put((texts, fut))
        self._ensure_runner()
        return await fut

    async def _runner_loop(self):
        while True:
            first_texts, first_fut = await self._queue.get()

            start_wait = time.perf_counter()
            batch_texts: list[str] = list(first_texts)
            batch_slices: list[tuple[int, asyncio.Future]] = [(len(first_texts), first_fut)]

            # Collect more requests for a short window
            while True:
                elapsed = time.perf_counter() - start_wait
                remaining = self.batch_window_s - elapsed
                if remaining <= 0:
                    break

                try:
                    more_texts, more_fut = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                if len(batch_texts) + len(more_texts) > self.max_batch_texts:
                    # Too large: push back this request for the next batch.
                    await self._queue.put((more_texts, more_fut))
                    break

                batch_slices.append((len(more_texts), more_fut))
                batch_texts.extend(more_texts)

            wait_time_ms = int((time.perf_counter() - start_wait) * 1000)
            num_requests = len(batch_slices)
            batch_size = len(batch_texts)

            try:
                # Single model lock: only one encode call at a time.
                async with self._model_encode_lock:
                    embeddings = await asyncio.to_thread(
                        embed_texts,
                        batch_texts,
                    )
            except Exception as e:
                logger.exception(
                    "[EmbeddingBatcher] batch failed (batch_size=%s, num_requests=%s, wait_time_ms=%s). %s",
                    batch_size,
                    num_requests,
                    wait_time_ms,
                    e,
                )

                # Fallback: embed each request separately
                offset = 0
                for count, fut in batch_slices:
                    part_texts = batch_texts[offset : offset + count]
                    try:
                        part = await asyncio.to_thread(embed_texts, part_texts)
                        fut.set_result(part)
                    except Exception as e2:
                        fut.set_exception(e2)
                    offset += count
                continue

            # Split embeddings back into individual request results
            offset = 0
            for count, fut in batch_slices:
                part = embeddings[offset : offset + count]
                fut.set_result(part)
                offset += count

            # Mandatory logging
            logger.info(
                "[EmbeddingBatcher] batch_size=%s num_requests=%s wait_time_ms=%s",
                batch_size,
                num_requests,
                wait_time_ms,
            )


_batcher: EmbeddingBatcher | None = None


def _get_batcher() -> EmbeddingBatcher:
    global _batcher
    if _batcher is None:
        _batcher = EmbeddingBatcher()
    return _batcher


async def embed_texts_async(texts: list[str]) -> np.ndarray:
    """Async micro-batched embedding API.

    Fallback: if batching fails, uses the old `embed_texts()` path.
    """
    batcher = _get_batcher()
    try:
        return await batcher.embed_texts_async(texts)
    except Exception:
        logger.exception("[embed_texts_async] batcher failed; using embed_texts fallback.")
        return await asyncio.to_thread(embed_texts, texts)
