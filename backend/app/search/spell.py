"""Search spelling + suggestions from indexed PDF content only."""
import re
import json
import logging
from pathlib import Path
from difflib import get_close_matches
from app.state import chunk_store
from app.config import CHUNKS_DIR
from app.database import SessionLocal, Document

logger = logging.getLogger(__name__)

# Cache vocabularies/suggestions per doc
_vocab_cache: dict[str, set[str]] = {}
_term_score_cache: dict[str, dict[str, int]] = {}
_suggest_cache: dict[tuple[str, str, int], list[str]] = {}
_suggest_user_cache: dict[tuple[str, str, int], list[str]] = {}


def _load_chunks(doc_id: str) -> list[dict]:
    """Load chunks from memory first, then disk as fallback."""
    chunks = chunk_store.get(doc_id, [])
    if chunks:
        return chunks

    # Fallback: read from disk
    chunks_path = Path(CHUNKS_DIR) / f"{doc_id}.json"
    if chunks_path.exists():
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            logger.info(f"[spell] Loaded {len(chunks)} chunks from disk for {doc_id}")
            return chunks
        except Exception as e:
            logger.error(f"[spell] Failed to load chunks from disk for {doc_id}: {e}")

    return []


def build_vocabulary(doc_id: str) -> set[str]:
    """Build word vocabulary from document chunks."""
    if doc_id in _vocab_cache and _vocab_cache[doc_id]:
        return _vocab_cache[doc_id]

    chunks = _load_chunks(doc_id)
    vocab = set()
    for chunk in chunks:
        text = chunk.get("text", "")
        # Extract words, lowercase, filter short/numeric
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        vocab.update(words)

    # Add common academic terms that might not be in the doc
    common_terms = {
        "machine", "learning", "artificial", "intelligence", "neural", "network",
        "algorithm", "data", "structure", "database", "programming", "python",
        "computer", "science", "mathematics", "physics", "chemistry", "biology",
        "operating", "system", "software", "engineering", "analysis", "design",
        "function", "variable", "array", "string", "class", "object", "method",
        "model", "training", "testing", "validation", "accuracy", "performance",
        "search", "query", "index", "vector", "embedding", "retrieval"
    }
    vocab.update(common_terms)

    _vocab_cache[doc_id] = vocab
    logger.info(f"Built vocabulary for {doc_id}: {len(vocab)} words")
    return vocab


def build_search_terms(doc_id: str) -> dict[str, int]:
    """Build weighted term index from chunk text + headings."""
    if doc_id in _term_score_cache and _term_score_cache[doc_id]:
        return _term_score_cache[doc_id]

    chunks = _load_chunks(doc_id)
    term_scores: dict[str, int] = {}
    heading_bonus = 3

    for c in chunks:
        heading = (c.get("section") or "").strip().lower()
        text = (c.get("text") or "").strip().lower()
        if heading:
            term_scores[heading] = term_scores.get(heading, 0) + heading_bonus

        # Candidate phrases (2-3 grams)
        words = re.findall(r"[a-zA-Z]{3,}", text)
        for n in (1, 2, 3):
            for i in range(0, max(0, len(words) - n + 1)):
                term = " ".join(words[i:i + n]).strip()
                if len(term) < 3:
                    continue
                # ignore noisy phrases
                if n > 1 and term in {"of the", "in the", "for the"}:
                    continue
                term_scores[term] = term_scores.get(term, 0) + 1

    # Repetition boost and pruning
    pruned = {
        t: (s + 2 if s >= 3 else s)
        for t, s in term_scores.items()
        if s >= 2 and len(t) <= 64
    }
    _term_score_cache[doc_id] = pruned
    return pruned


def suggest_query(query: str, doc_id: str) -> dict:
    """Check query for typos and suggest corrections.

    Returns:
        {
            "original": "machien lerning",
            "corrected": "machine learning",
            "did_you_mean": True/False,
            "corrections": {"machien": "machine", "lerning": "learning"}
        }
    """
    vocab = build_vocabulary(doc_id)
    if not vocab:
        return {"original": query, "corrected": query, "did_you_mean": False, "corrections": {}}

    words = query.split()
    corrected_words = []
    corrections = {}

    for word in words:
        word_lower = word.lower()
        # Skip if word exists in vocabulary or is very short
        if word_lower in vocab or len(word_lower) < 3:
            corrected_words.append(word)
            continue

        # Find close matches with a slightly relaxed cutoff for better suggestions
        matches = get_close_matches(word_lower, list(vocab), n=3, cutoff=0.72)
        if matches and matches[0] != word_lower:
            corrections[word] = matches[0]
            corrected_words.append(matches[0])
            logger.debug(f"Typo correction: '{word}' → '{matches[0]}'")
        else:
            corrected_words.append(word)

    corrected = " ".join(corrected_words)
    did_you_mean = corrected.lower() != query.lower()

    return {
        "original": query,
        "corrected": corrected,
        "did_you_mean": did_you_mean,
        "corrections": corrections,
    }


def suggest_autocomplete(prefix: str, doc_id: str, limit: int = 8) -> list[str]:
    """Return ranked suggestions from PDF terms only."""
    p = (prefix or "").strip().lower()
    if len(p) < 2:
        return []
    key = (doc_id, p, limit)
    if key in _suggest_cache:
        return _suggest_cache[key]

    term_scores = build_search_terms(doc_id)
    if not term_scores:
        return []

    terms = list(term_scores.keys())
    # Prefix-first ranking
    prefix_hits = [t for t in terms if t.startswith(p)]
    prefix_hits.sort(key=lambda t: (-term_scores.get(t, 0), len(t)))

    # Fuzzy continuation
    fuzzy = get_close_matches(p, terms, n=limit * 5, cutoff=0.65)
    fuzzy.sort(key=lambda t: (-term_scores.get(t, 0), len(t)))

    out: list[str] = []
    seen = set()
    for t in prefix_hits + fuzzy:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break

    _suggest_cache[key] = out
    return out


def suggest_autocomplete_user(prefix: str, user_id: str, limit: int = 5) -> list[str]:
    """Return user-scoped suggestions merged across all available docs."""
    p = (prefix or "").strip().lower()
    if len(p) < 2:
        return []
    key = (user_id, p, limit)
    if key in _suggest_user_cache:
        return _suggest_user_cache[key]

    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.user_id == user_id,
            Document.status.in_(["ready", "partially_ready"]),
        ).all()
    finally:
        db.close()

    merged_scores: dict[str, int] = {}
    for d in docs:
        term_scores = build_search_terms(d.doc_id)
        for term, score in term_scores.items():
            merged_scores[term] = merged_scores.get(term, 0) + score

    if not merged_scores:
        return []

    terms = list(merged_scores.keys())
    prefix_hits = [t for t in terms if t.startswith(p)]
    prefix_hits.sort(key=lambda t: (-merged_scores.get(t, 0), len(t)))
    fuzzy = get_close_matches(p, terms, n=limit * 5, cutoff=0.65)
    fuzzy.sort(key=lambda t: (-merged_scores.get(t, 0), len(t)))

    out: list[str] = []
    seen = set()
    for t in prefix_hits + fuzzy:
        if t in seen:
            continue
        seen.add(t)
        if len(t) > 64:
            continue
        out.append(t)
        if len(out) >= limit:
            break
    _suggest_user_cache[key] = out
    return out
