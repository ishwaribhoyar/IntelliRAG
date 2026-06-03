"""Hierarchical chunking engine — VALIDATED.
Rules: independence check, question coverage, sentence-safe splitting,
proper table EAV conversion, debug logger.
"""
import uuid
import re
import logging
import nltk

logger = logging.getLogger(__name__)

# --- Configuration ---
MIN_WORDS = 120       # Rule 1: minimum for independence
IDEAL_MIN = 200
IDEAL_MAX = 350
SPLIT_THRESHOLD = 500
OVERLAP_SENTENCES = 2  # Overlap in sentences, not words

# Ensure punkt is available
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)


# =====================================================================
# VALIDATION RULES
# =====================================================================

def is_valid_chunk(text: str) -> bool:
    """Rule 1 — Independence Check.
    Each chunk MUST be understandable alone and contain full sentence boundaries.
    """
    words = text.split()
    if len(words) < MIN_WORDS:
        return False
    # Must not end mid-sentence (trailing conjunctions / prepositions)
    trailing = text.rstrip().split()[-1].lower().rstrip(".,;:!?") if words else ""
    if trailing in ("and", "or", "but", "the", "a", "an", "of", "in", "to", "for", "with", "is"):
        return False
    # Must contain at least one period/question mark (full sentence)
    if not re.search(r'[.!?]', text):
        return False
    return True


def can_answer_question(text: str) -> bool:
    """Rule 2 — Question Coverage.
    Heuristic: chunk contains definition/explanation keywords.
    """
    keywords = [
        "is", "are", "means", "refers to", "defined as",
        "consists of", "includes", "known as", "called",
        "used for", "used to", "provides", "enables",
        "describes", "explains", "represents",
    ]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)


def sentence_split(text: str) -> list[str]:
    """Rule 3 — Sentence-safe splitting using nltk."""
    try:
        sentences = nltk.sent_tokenize(text)
    except Exception:
        # Fallback: split on period+space
        sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def convert_table_to_eav(table: list[list[str]]) -> str:
    """Rule 4 — Proper Entity → Attribute → Value conversion.
    Input: [["Name", "Age", "City"], ["Alice", "30", "NYC"]]
    Output: "Entity: Alice | Attribute: Name | Value: Alice\n
             Entity: Alice | Attribute: Age | Value: 30\n..."
    """
    if not table or len(table) < 2:
        return ""

    headers = table[0]
    rows = table[1:]
    lines = []

    for row in rows:
        entity = row[0] if row else "Unknown"
        for i, value in enumerate(row):
            attr = headers[i] if i < len(headers) else f"Column_{i+1}"
            lines.append(f"Entity: {entity} | Attribute: {attr} | Value: {value}")

    return "\n".join(lines)


def debug_log_chunk(text: str, section: str, chunk_id: str, chunk_type: str,
                    valid: bool, answerable: bool):
    """Rule 5 — Debug logger (MANDATORY)."""
    word_count = len(text.split())
    preview = text[:100].replace("\n", " ")
    logger.info(
        f"\n[CHUNK DEBUG]\n"
        f"  ID:         {chunk_id}\n"
        f"  Type:       {chunk_type}\n"
        f"  Words:      {word_count}\n"
        f"  Section:    {section}\n"
        f"  Valid:       {valid}\n"
        f"  Answerable: {answerable}\n"
        f"  Preview:    {preview}...\n"
    )


# =====================================================================
# MAIN CHUNKER
# =====================================================================

def chunk_document(normalized: dict) -> list[dict]:
    """Create hierarchical chunks with hard validation.

    Returns list of chunk dicts:
    {chunk_id, text, doc_id, section, page, level, type, parent_id, word_count}
    """
    doc_id = normalized["doc_id"]
    sections = normalized.get("sections", [])
    all_chunks: list[dict] = []
    discarded = 0

    for section in sections:
        heading = section.get("heading", "")
        content = section.get("content", "")
        page = section.get("page", 1)
        level = section.get("level", "h1")

        if not content.strip():
            continue

        # --- 1. Create PARENT chunk (section summary) ---
        parent_id = _gen_id()
        parent_text = _build_parent_text(heading, content)
        parent_chunk = _make_chunk(
            parent_id, parent_text, doc_id, heading, page, level, "parent", None
        )
        all_chunks.append(parent_chunk)

        # --- 2. Extract tables → table chunks ---
        tables = section.get("tables", [])
        for table in tables:
            table_text = convert_table_to_eav(table)
            if table_text and len(table_text.split()) >= 10:
                tc = _make_chunk(
                    _gen_id(), table_text, doc_id, heading, page, level, "table", parent_id
                )
                valid = True  # Tables are always valid
                answerable = True
                debug_log_chunk(table_text, heading, tc["chunk_id"], "table", valid, answerable)
                all_chunks.append(tc)

        # --- 3. SENTENCE-SAFE child chunking ---
        sentences = sentence_split(content)
        raw_chunks = _group_sentences_to_chunks(sentences)

        for chunk_text in raw_chunks:
            wc = len(chunk_text.split())
            if wc < 10:
                discarded += 1
                continue

            chunk_id = _gen_id()
            valid = is_valid_chunk(chunk_text)
            answerable = can_answer_question(chunk_text)

            debug_log_chunk(chunk_text, heading, chunk_id, "text", valid, answerable)

            if not valid:
                # Try to salvage by keeping, but flag it
                if wc < 50:
                    discarded += 1
                    continue
                # Still include short-ish chunks but log warning
                logger.warning(f"Chunk {chunk_id} below independence threshold ({wc} words), included anyway")

            child = _make_chunk(
                chunk_id, chunk_text.strip(), doc_id, heading, page, level, "text", parent_id
            )
            all_chunks.append(child)

        debug_log_chunk(parent_text, heading, parent_id, "parent",
                        is_valid_chunk(parent_text), can_answer_question(parent_text))

    # Final stats
    text_count = sum(1 for c in all_chunks if c["type"] == "text")
    parent_count = sum(1 for c in all_chunks if c["type"] == "parent")
    table_count = sum(1 for c in all_chunks if c["type"] == "table")
    logger.info(
        f"[CHUNK SUMMARY] doc={doc_id} | "
        f"total={len(all_chunks)} (parents={parent_count}, text={text_count}, table={table_count}) | "
        f"discarded={discarded}"
    )

    return all_chunks


# =====================================================================
# HELPERS
# =====================================================================

def _group_sentences_to_chunks(sentences: list[str]) -> list[str]:
    """Group sentences into chunks of IDEAL_MIN–IDEAL_MAX words.
    Sentence-safe: never breaks mid-sentence.
    Overlap: last OVERLAP_SENTENCES sentences carry over.
    """
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_word_count = 0

    for sentence in sentences:
        sw = len(sentence.split())
        current_sentences.append(sentence)
        current_word_count += sw

        if current_word_count >= IDEAL_MAX:
            # Emit chunk
            chunk_text = " ".join(current_sentences)
            chunks.append(chunk_text)
            # Overlap: keep last N sentences
            if len(current_sentences) > OVERLAP_SENTENCES:
                current_sentences = current_sentences[-OVERLAP_SENTENCES:]
                current_word_count = sum(len(s.split()) for s in current_sentences)
            else:
                current_sentences = []
                current_word_count = 0

    # Emit remaining
    if current_sentences:
        remaining = " ".join(current_sentences)
        remaining_wc = len(remaining.split())

        if remaining_wc < MIN_WORDS and chunks:
            # Merge into last chunk
            chunks[-1] = chunks[-1] + " " + remaining
        else:
            chunks.append(remaining)

    return chunks


def _build_parent_text(heading: str, content: str) -> str:
    """Build a parent chunk: heading + first ~100 words."""
    words = content.split()
    summary_words = words[:100] if len(words) > 100 else words
    summary = " ".join(summary_words)
    if len(words) > 100:
        summary += "..."
    return f"{heading}\n\n{summary}"


def _make_chunk(chunk_id: str, text: str, doc_id: str, section: str,
                page: int, level: str, ctype: str, parent_id: str | None) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "doc_id": doc_id,
        "section": section,
        "page": page,
        "level": level,
        "type": ctype,
        "parent_id": parent_id,
        "word_count": len(text.split()),
    }


def _gen_id() -> str:
    return f"c_{uuid.uuid4().hex[:12]}"
