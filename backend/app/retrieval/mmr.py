"""Maximal Marginal Relevance (MMR) — diversity filtering for retrieved chunks."""
import logging
import numpy as np
from app.rag.embedder import embed_texts

logger = logging.getLogger(__name__)


def mmr_filter(
    chunks: list[dict],
    lambda_param: float = 0.7,
    similarity_threshold: float = 0.85,
    max_chunks: int = 10,
) -> list[dict]:
    """Apply MMR to remove near-duplicate chunks and ensure diversity.

    Args:
        chunks: Ranked chunks from hybrid retrieval
        lambda_param: Tradeoff between relevance (1.0) and diversity (0.0)
        similarity_threshold: Chunks with cosine sim > this are near-duplicates
        max_chunks: Max number of chunks to return

    Returns: Filtered list with diverse, relevant chunks.
    """
    if len(chunks) <= 1:
        return chunks

    # Embed all chunk texts
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    embeddings = np.array(embeddings, dtype="float32")

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    selected_indices = [0]  # Always keep the top-ranked chunk
    remaining = list(range(1, len(chunks)))

    while remaining and len(selected_indices) < max_chunks:
        best_idx = None
        best_mmr_score = -float("inf")

        for idx in remaining:
            # Relevance: use the retrieval score (rrf_score or score)
            relevance = chunks[idx].get("rrf_score", chunks[idx].get("score", 0))

            # Max similarity to already selected chunks
            max_sim = 0.0
            for sel_idx in selected_indices:
                sim = float(np.dot(embeddings[idx], embeddings[sel_idx]))
                max_sim = max(max_sim, sim)

            # Skip near-duplicates
            if max_sim > similarity_threshold:
                remaining.remove(idx)
                logger.debug(f"MMR: skipping chunk {chunks[idx]['chunk_id']} (sim={max_sim:.3f})")
                continue

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)
        else:
            break

    result = [chunks[i] for i in selected_indices]
    logger.info(f"MMR filter: {len(chunks)} -> {len(result)} chunks (lambda={lambda_param})")
    return result
