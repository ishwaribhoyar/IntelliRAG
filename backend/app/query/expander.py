"""Query expander — multi-query generation for better retrieval coverage."""
import logging
from app.rag.embedder import embed_single

logger = logging.getLogger(__name__)


def expand_query(query: str, query_type: str = "factual") -> list[tuple[str, float]]:
    """Generate weighted query variants for multi-query retrieval.

    Returns list of (query_text, weight) tuples.
    """
    variants = [(query, 0.5)]  # Original always has highest weight

    # Add type-specific expansions
    if query_type == "comparison":
        variants.append((f"Compare and contrast: {query}", 0.3))
        variants.append((f"Similarities and differences of {query}", 0.2))
    elif query_type == "procedural":
        variants.append((f"Steps and process for {query}", 0.3))
        variants.append((f"How to implement {query}", 0.2))
    elif query_type == "analytical":
        variants.append((f"Explain in detail: {query}", 0.3))
        variants.append((f"Why and how: {query}", 0.2))
    else:  # factual
        variants.append((f"Define and explain {query}", 0.3))
        variants.append((f"Key facts about {query}", 0.2))

    logger.debug(f"Expanded query into {len(variants)} variants")
    return variants


def sanitize_query(query: str) -> str | None:
    """Sanitize user query. Returns None if invalid."""
    if not query:
        return None
    query = query.strip()
    if len(query) > 500:
        query = query[:500]
    if not query:
        return None
    # Remove repetitive tokens
    words = query.split()
    seen = []
    for w in words:
        if w.lower() not in [s.lower() for s in seen[-3:]] if seen else True:
            seen.append(w)
    return " ".join(seen)
