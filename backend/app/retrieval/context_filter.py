"""Context filter — token-safe truncation and best-chunk selection."""
import logging

logger = logging.getLogger(__name__)

# Approximate tokens per word ratio
TOKENS_PER_WORD = 1.5


def estimate_tokens(text: str) -> int:
    """Conservative token estimation."""
    return int(len(text.split()) * TOKENS_PER_WORD)


def filter_context(
    chunks: list[dict],
    max_tokens: int = 1500,
    prefer_child: bool = True,
) -> list[dict]:
    """Select best chunks that fit within token budget.

    Args:
        chunks: Ranked chunks (post-MMR)
        max_tokens: Maximum context tokens
        prefer_child: If True, prefer child/text chunks over parent summaries

    Returns: Token-safe filtered chunk list.
    """
    if not chunks:
        return []

    # Optionally deprioritise parent chunks (they're summaries, not detail)
    if prefer_child:
        chunks = sorted(
            chunks,
            key=lambda c: (
                0 if c.get("type") in ("text", "table") else 1,  # text/table first
                -(c.get("rrf_score", c.get("score", 0))),  # then by score
            ),
        )

    final = []
    total_tokens = 0

    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk["text"])
        if total_tokens + chunk_tokens > max_tokens:
            # Try to fit a truncated version if we have space
            remaining = max_tokens - total_tokens
            if remaining > 100:  # worth adding a partial chunk
                words = chunk["text"].split()
                max_words = int(remaining / TOKENS_PER_WORD)
                truncated = " ".join(words[:max_words]) + "..."
                chunk_copy = chunk.copy()
                chunk_copy["text"] = truncated
                chunk_copy["truncated"] = True
                final.append(chunk_copy)
                total_tokens += estimate_tokens(truncated)
            break

        final.append(chunk)
        total_tokens += chunk_tokens

    logger.info(f"Context filter: {len(chunks)} -> {len(final)} chunks, {total_tokens}/{max_tokens} tokens")
    return final
