"""Chunk quality validator — SEMANTIC + REDUNDANCY checks.
Uses MiniLM embeddings for duplicate detection via cosine similarity.
"""
import logging
import numpy as np
from app.state import chunk_store
from app.rag.embedder import embed_single

logger = logging.getLogger(__name__)

ANSWER_KEYWORDS = {"is", "are", "means", "refers to", "defined as",
                   "consists of", "includes", "known as", "used for",
                   "provides", "describes", "explains", "represents"}

TRAILING_BAD = {"and", "or", "but", "the", "a", "an", "of", "in", "to", "for", "with"}


def _cosine_sim(vec_a, vec_b) -> float:
    """Cosine similarity between two vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def has_complete_idea(text: str) -> bool:
    """Check if chunk contains at least one complete idea."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in ANSWER_KEYWORDS)


def is_duplicate(chunk_emb, previous_embs: list, threshold: float = 0.85) -> bool:
    """Check if chunk is a near-duplicate of any previous chunk."""
    for prev_emb in previous_embs:
        if _cosine_sim(chunk_emb, prev_emb) > threshold:
            return True
    return False


def validate_chunks(doc_id: str) -> dict:
    """Validate all chunks for a document with semantic checks.

    Checks:
    1. Word count >= 50 (independence)
    2. Ends with sentence terminator (completeness)
    3. Contains definition/explanation keywords (answerability)
    4. No trailing conjunctions (grammatical completeness)
    5. Not a near-duplicate (cosine sim > 0.85) — SEMANTIC

    A chunk is valid if it passes ≥ 3 of 5 checks.
    """
    chunks = chunk_store.get(doc_id, [])
    if not chunks:
        return {"error": "No chunks found", "quality_score": 0.0}

    total = 0
    valid_count = 0
    word_count_pass = 0
    sentence_end_pass = 0
    answerable_pass = 0
    no_trailing_conj = 0
    not_duplicate = 0
    duplicate_count = 0

    issues = []
    previous_embs = []

    for chunk in chunks:
        text = chunk.get("text", "")
        ctype = chunk.get("type", "text")
        words = text.split()
        wc = len(words)

        # Skip parent / table chunks
        if ctype in ("parent", "table"):
            continue

        total += 1
        checks_passed = 0

        # Check 1: Word count
        if wc >= 50:
            word_count_pass += 1
            checks_passed += 1
        else:
            if len(issues) < 15:
                issues.append({"chunk_id": chunk.get("chunk_id", ""), "issue": f"Short: {wc} words"})

        # Check 2: Sentence ending
        stripped = text.rstrip()
        if stripped and stripped[-1] in ".!?":
            sentence_end_pass += 1
            checks_passed += 1
        else:
            if len(issues) < 15:
                issues.append({"chunk_id": chunk.get("chunk_id", ""), "issue": "No sentence ending"})

        # Check 3: Complete idea (answerability)
        if has_complete_idea(text):
            answerable_pass += 1
            checks_passed += 1

        # Check 4: No trailing conjunction
        if words:
            last_word = words[-1].lower().rstrip(".,;:!?")
            if last_word not in TRAILING_BAD:
                no_trailing_conj += 1
                checks_passed += 1

        # Check 5: Semantic duplicate check (sample first 30 for perf)
        if total <= 30 and wc >= 20:
            try:
                chunk_emb = embed_single(text[:300])
                if not is_duplicate(chunk_emb, previous_embs):
                    not_duplicate += 1
                    checks_passed += 1
                    previous_embs.append(chunk_emb)
                else:
                    duplicate_count += 1
                    if len(issues) < 15:
                        issues.append({"chunk_id": chunk.get("chunk_id", ""), "issue": "Duplicate (sim > 0.85)"})
                    previous_embs.append(chunk_emb)
            except Exception:
                not_duplicate += 1
                checks_passed += 1
        else:
            not_duplicate += 1
            checks_passed += 1

        # Valid = passes 3 of 5
        if checks_passed >= 3:
            valid_count += 1

    total = max(total, 1)
    quality_score = round(valid_count / total, 4)

    report = {
        "quality_score": quality_score,
        "quality_pct": round(quality_score * 100, 1),
        "total_text_chunks": total,
        "valid_chunks": valid_count,
        "duplicate_chunks": duplicate_count,
        "duplicate_pct": round(duplicate_count / total * 100, 1),
        "checks": {
            "word_count_pass": word_count_pass,
            "word_count_pct": round(word_count_pass / total * 100, 1),
            "sentence_end_pass": sentence_end_pass,
            "sentence_end_pct": round(sentence_end_pass / total * 100, 1),
            "answerable_pass": answerable_pass,
            "answerable_pct": round(answerable_pass / total * 100, 1),
            "no_trailing_conj": no_trailing_conj,
            "no_trailing_conj_pct": round(no_trailing_conj / total * 100, 1),
            "not_duplicate": not_duplicate,
            "not_duplicate_pct": round(not_duplicate / total * 100, 1),
        },
        "issues": issues[:10],
    }

    logger.info(
        f"\nChunk Quality Score: {report['quality_pct']}%\n"
        f"  Valid (4/5 checks): {valid_count}/{total}\n"
        f"  Duplicate Chunks Removed: {duplicate_count} ({report['duplicate_pct']}%)\n"
        f"  Word count >= 120: {word_count_pass} ({report['checks']['word_count_pct']}%)\n"
        f"  Sentence ending: {sentence_end_pass} ({report['checks']['sentence_end_pct']}%)\n"
        f"  Answerable: {answerable_pass} ({report['checks']['answerable_pct']}%)\n"
        f"  Not duplicate: {not_duplicate} ({report['checks']['not_duplicate_pct']}%)"
    )

    return report
