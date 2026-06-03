"""Auto-classify documents into subjects using LLM analysis of content."""
import json
import logging
import re
from pathlib import Path
from app.modules.llm_router.router import llm_router
from app.state import chunk_store
from app.config import CHUNKS_DIR

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """You are a document classifier. Given text excerpts from a document, determine the PRIMARY academic subject this document belongs to.

Rules:
- Return ONLY a JSON object: {"subject": "Subject Name", "confidence": 0.0-1.0}
- Subject should be a clean academic category, 1-3 words max
- Examples: "Machine Learning", "Data Structures", "Operating Systems", "Python Programming", "Database Systems", "Computer Networks", "Web Development", "Mathematics", "Physics", "Chemistry", "Biology", "English Literature", "History", "Economics", "Digital Electronics"
- If truly unclear, use "General Studies"
- Do NOT include file extensions, doc IDs, or generic filler words
- Do NOT return numbers like "1" or "Unit 1"
"""

_GENERIC_SUBJECTS = {
    "general",
    "general studies",
    "document",
    "notes",
    "study material",
    "miscellaneous",
}

_SUBJECT_KEYWORDS: dict[str, list[str]] = {
    "Machine Learning": ["machine learning", "supervised", "unsupervised", "regression", "classification", "overfitting", "neural network"],
    "Python": ["python", "pip", "numpy", "pandas", "def ", "list comprehension", "tuple", "dictionary", "django", "flask"],
    "Computer Programming": ["programming", "algorithm", "java", "c++", "javascript", "function", "variable", "loop", "compiler"],
    "Data Structures": ["array", "linked list", "stack", "queue", "tree", "graph", "sorting", "hash table"],
    "Operating Systems": ["process", "thread", "scheduler", "kernel", "paging", "deadlock", "semaphore", "ipc"],
    "Database Systems": ["sql", "database", "query", "normalization", "transaction", "indexing", "join", "acid"],
    "Artificial Intelligence": [
        "artificial intelligence",
        "intelligent agent",
        "knowledge representation",
        "expert system",
        "search",
        "planning",
        "inference",
        "heuristic",
        "logic programming",
    ],
    "Aerospace Engineering": ["aerospace", "propulsion", "thrust", "turbine", "compressor", "rocket", "nozzle", "jet engine"],
    "Computer Networks": ["tcp", "udp", "ip", "routing", "network", "protocol", "osi", "dns", "http"],
}


def _load_chunks(doc_id: str) -> list[dict]:
    """Load chunks from memory first, then disk as fallback."""
    # Try in-memory store first
    chunks = chunk_store.get(doc_id, [])
    if chunks:
        return chunks

    # Fallback: read from disk
    chunks_path = Path(CHUNKS_DIR) / f"{doc_id}.json"
    if chunks_path.exists():
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            logger.info(f"[{doc_id}] Loaded {len(chunks)} chunks from disk for classification")
            return chunks
        except Exception as e:
            logger.error(f"[{doc_id}] Failed to load chunks from disk: {e}")

    return []


def _load_chunks_from_sibling(doc_id: str) -> list[dict]:
    """Fallback: reuse chunks from another ready doc with same file hash."""
    try:
        from app.database import SessionLocal, Document
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc or not doc.file_hash:
                return []
            siblings = db.query(Document).filter(
                Document.file_hash == doc.file_hash,
                Document.doc_id != doc_id,
                Document.status == "ready",
            ).all()
            for sib in siblings:
                sib_chunks = _load_chunks(sib.doc_id)
                if sib_chunks:
                    logger.info(f"[{doc_id}] Using sibling chunks from {sib.doc_id} for classification")
                    return sib_chunks
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[{doc_id}] Sibling chunk fallback failed: {e}")
    return []


async def classify_document(doc_id: str) -> str:
    """Classify a document's subject from its first few chunks.

    Args:
        doc_id: The document ID to classify

    Returns:
        Subject string like "Machine Learning" or "Python Programming"
    """
    chunks = _load_chunks(doc_id)
    if not chunks:
        chunks = _load_chunks_from_sibling(doc_id)
    if not chunks:
        logger.warning(f"No chunks found for {doc_id}, defaulting to General Studies")
        return "General Studies"

    # Sample chunks across beginning/middle/end so classification reflects full document content.
    if len(chunks) <= 8:
        sample_chunks = chunks
    else:
        mid = len(chunks) // 2
        sample_chunks = chunks[:3] + chunks[max(0, mid - 1):mid + 2] + chunks[-3:]
    sample_text = "\n\n".join(
        f"[Section: {c.get('section', 'Unknown')}]\n{c.get('text', '')[:500]}"
        for c in sample_chunks
    )
    extracted_headings = [str(c.get("section", "Unknown")).strip() for c in sample_chunks if str(c.get("section", "")).strip()]
    logger.info(f"[{doc_id}] extracted headings for classification: {extracted_headings[:8]}")

    # Limit total context size for LLM classification.
    if len(sample_text) > 3500:
        sample_text = sample_text[:3500]

    # Step 1: deterministic keyword scoring on content
    keyword_subject, keyword_conf, keyword_scores = _keyword_score_subject(sample_text)
    logger.info(f"[{doc_id}] classification keyword scores: {keyword_scores}")
    if keyword_conf >= 2:
        logger.info(f"[{doc_id}] keyword classification winner='{keyword_subject}' conf={keyword_conf}")
        return keyword_subject

    try:
        # Step 2: LLM fallback only when keyword confidence is low
        result = await llm_router.generate(
            doc_id=doc_id,
            task_type="classify",
            prompt=CLASSIFY_PROMPT,
            context=f"Document excerpts:\n\n{sample_text}\n\nClassify this document's subject.",
        )

        answer = result.get("answer", "")

        data = _extract_json_obj(answer)
        if isinstance(data, dict):
            subject = _sanitize_subject(data.get("subject", "General"))
            confidence = data.get("confidence", 0.5)
            if subject == "General":
                logger.info(f"[{doc_id}] LLM returned generic subject -> keyword fallback used")
                subject = _keyword_fallback_subject(sample_text)
            logger.info(f"[{doc_id}] Classified as '{subject}' (confidence: {confidence})")
            return subject

        # Plain-text fallback
        subject = _sanitize_subject(answer.strip().strip('"').strip("'"))
        if subject == "General":
            logger.info(f"[{doc_id}] plain text classification generic -> keyword fallback used")
            subject = _keyword_fallback_subject(sample_text)
        logger.info(f"[{doc_id}] Classified as '{subject}' (plain text fallback)")
        return subject

    except Exception as e:
        logger.error(f"[{doc_id}] Classification failed: {e}")
        subject = _keyword_fallback_subject(sample_text)
        logger.info(f"[{doc_id}] fallback subject after exception: '{subject}'")
        return subject


def _sanitize_subject(subject: str) -> str:
    """Normalize noisy model output into a clean subject label."""
    if not isinstance(subject, str):
        return "General"

    s = subject.strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\.pdf$|\.xlsx$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bdoc_[a-z0-9]+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^A-Za-z0-9 &/\-]", "", s).strip()

    if not s or len(s) < 2 or len(s) > 40:
        return "General"

    lowered = s.lower()
    canonical = {
        "ai": "AI",
        "artificial intelligence": "AI",
        "artificial-intelligence": "AI",
        "ml": "Machine Learning",
        "machine learning": "Machine Learning",
        "python": "Python",
        "python programming": "Python",
        "computer programming": "Computer Programming",
    }
    if lowered in canonical:
        return canonical[lowered]

    if lowered in _GENERIC_SUBJECTS:
        return "General"

    if len(s.split()) > 4:
        return "General"

    normalized = s.title()
    if normalized == "Artificial Intelligence":
        return "AI"
    if normalized == "Python Programming":
        return "Python"
    return normalized


def _keyword_fallback_subject(text: str) -> str:
    """Heuristic subject fallback when LLM classification is weak/unavailable."""
    if not text:
        return "General"

    t = text.lower()
    subject, score, _ = _keyword_score_subject(t)
    return subject if score > 0 else "General Studies"

def _extract_json_obj(text: str):
    """Robustly extract the first JSON object from a model response."""
    if not isinstance(text, str) or "{" not in text:
        return None
    cleaned = text.strip()
    # Strip fenced code blocks if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    decoder = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned[i:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _keyword_score_subject(text: str) -> tuple[str, int, dict[str, int]]:
    """Compute subject score from content keywords."""
    t = (text or "").lower()
    scores: dict[str, int] = {}
    best_subject = "General Studies"
    best_score = 0
    for subject, keywords in _SUBJECT_KEYWORDS.items():
        s = 0
        for kw in keywords:
            if " " in kw:
                s += t.count(kw) * 2
            else:
                s += len(re.findall(rf"\b{re.escape(kw)}\b", t))
        # Strong disambiguation for common AI-vs-ML confusion.
        if subject == "Artificial Intelligence":
            if re.search(r"\bartificial intelligence\b", t):
                s += 6
            if re.search(r"\bai\b", t):
                s += 4
            if re.search(r"\bintelligent agents?\b", t):
                s += 3
            if re.search(r"\bmachine learning\b", t):
                s -= 1
        elif subject == "Machine Learning":
            if re.search(r"\bmachine learning\b", t):
                s += 4
            if re.search(r"\bml\b", t):
                s += 2
            if re.search(r"\bartificial intelligence\b", t):
                s -= 1
        elif subject == "Python":
            if re.search(r"\bpython\b", t):
                s += 6
            if re.search(r"\bpython programming\b", t):
                s += 6
            if re.search(r"\bdef\s+[a-zA-Z_]\w*\s*\(", t):
                s += 2
        elif subject == "Computer Programming":
            if re.search(r"\bcomputer programming\b", t):
                s += 5
            if re.search(r"\bpython\b", t):
                s -= 2
        scores[subject] = s
        if s > best_score:
            best_subject = subject
            best_score = s
    return best_subject, best_score, scores
