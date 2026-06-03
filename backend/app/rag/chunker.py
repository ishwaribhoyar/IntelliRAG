"""Smart chunking engine — 300-400 word chunks with 50 overlap and metadata."""
import uuid
import logging

logger = logging.getLogger(__name__)


def chunk_document(normalized: dict) -> list[dict]:
    """Chunk normalized document into 300-400 word segments with 50 word overlap.

    Returns list of chunk dicts: {chunk_id, text, section, doc_id}
    """
    doc_id = normalized["doc_id"]
    chunks = []

    for section in normalized.get("sections", []):
        heading = section.get("heading", "")
        content = section.get("content", "")

        if not content.strip():
            continue

        words = content.split()
        if len(words) <= 400:
            # Small enough to be a single chunk
            chunks.append({
                "chunk_id": _gen_chunk_id(),
                "text": content.strip(),
                "section": heading,
                "doc_id": doc_id,
            })
            continue

        # Sliding window chunking
        start = 0
        while start < len(words):
            end = min(start + 375, len(words))  # Target ~375 words per chunk
            chunk_text = " ".join(words[start:end])

            chunks.append({
                "chunk_id": _gen_chunk_id(),
                "text": chunk_text,
                "section": heading,
                "doc_id": doc_id,
            })

            # Move forward by (chunk_size - overlap)
            start += 375 - 50  # 325 word steps

    logger.info(f"Created {len(chunks)} chunks for doc {doc_id}")
    return chunks


def _gen_chunk_id() -> str:
    return f"c_{uuid.uuid4().hex[:12]}"
