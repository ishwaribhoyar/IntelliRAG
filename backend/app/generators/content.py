"""General content generators — flashcards, summary, slides, fun facts, mentor.
Upgraded: uses hybrid retrieval pipeline.
"""
import json
import re
import logging
from app.config import AI_RETRIEVAL_MAX_CHUNKS, LLM_REFRESH_TEMPERATURE, FEATURE_TOKEN_BUDGETS
from app.retrieval.hybrid import retrieve_for_task, get_chunks_by_ordered_ids
from app.modules.llm_router.router import llm_router
from app.generators.prompts import get_prompt, build_refresh_instruction
from app.generators.cache import get_cached, set_cached
from app.retrieval.mmr import mmr_filter
from app.retrieval.context_filter import filter_context

logger = logging.getLogger(__name__)


def _dedupe_chunks_by_id(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for c in chunks:
        cid = c.get("chunk_id") or ""
        if cid in seen:
            continue
        seen.add(cid)
        out.append(c)
    return out


def _word_count(s: str) -> int:
    return len(re.split(r"\s+", (s or "").strip())) if (s or "").strip() else 0


async def generate_content(
    doc_id: str,
    content_type: str,
    query: str = "",
    llm_variant: str | None = None,
    refresh: bool = False,
    previous_output: str | None = None,
    source_chunk_ids: list[str] | None = None,
) -> dict:
    """Generic generator for flashcards, summary, slides, fun_facts, mock_test."""
    apply_refresh = refresh and content_type in ("flashcards", "summary")
    # Strict features: always fresh generation (no stale cached JSON).
    skip_cache = content_type in ("flashcards", "summary")
    if not skip_cache:
        cached = await get_cached(doc_id, content_type)
        if cached:
            cached["cached"] = True
            return cached

    if content_type == "summary":
        query_text = "Summarize the entire document covering introduction, main topics, and conclusion"
    elif content_type == "slides":
        query_text = "Key points and main themes for a presentation"
    else:
        query_text = query or f"Generate {content_type} about the main topics"

    chunks: list[dict] = []
    if apply_refresh and source_chunk_ids:
        chunks = get_chunks_by_ordered_ids(doc_id, source_chunk_ids)
        chunks = chunks[:AI_RETRIEVAL_MAX_CHUNKS]
        if chunks:
            logger.info(
                "[CONTENT CHUNKS] refresh=fixed doc=%s type=%s ids=%s",
                doc_id,
                content_type,
                [c.get("chunk_id", "") for c in chunks],
            )

    if not chunks:
        chunks = await retrieve_for_task(doc_id, query_text, task_type=content_type)

        if not chunks:
            return {"error": "No content found in document"}

        chunks = _dedupe_chunks_by_id(chunks)

        try:
            chunks = mmr_filter(chunks, max_chunks=AI_RETRIEVAL_MAX_CHUNKS, lambda_param=0.7)
        except Exception:
            logger.exception("MMR filter failed in generate_content; continuing without it.")

        try:
            max_context_tokens = 1200
            if content_type == "summary":
                max_context_tokens = FEATURE_TOKEN_BUDGETS["summary"]["context"]
            elif content_type in ("flashcards", "flashcard"):
                max_context_tokens = FEATURE_TOKEN_BUDGETS["flashcard"]["context"]
            chunks = filter_context(chunks, max_tokens=max_context_tokens, prefer_child=True)
        except Exception:
            logger.exception("filter_context failed in generate_content; continuing without it.")

        chunks = chunks[:AI_RETRIEVAL_MAX_CHUNKS]

    logger.info(
        "[CONTENT RETRIEVAL] doc=%s type=%s query='%s' chunk_ids=%s",
        doc_id,
        content_type,
        query_text[:80],
        [c.get("chunk_id", "") for c in chunks],
    )

    context = "\n\n".join(c["text"] for c in chunks)
    if not context.strip():
        return {"error": "No usable text in document chunks"}

    logger.info(
        "[CONTENT CONTEXT] doc=%s type=%s preview=%s",
        doc_id,
        content_type,
        (context[:1200] + "…") if len(context) > 1200 else context,
    )

    base_prompt = get_prompt(content_type)
    if apply_refresh:
        base_prompt += build_refresh_instruction(content_type, True, previous_output)

    _final_suffix = "\n\nFINAL ATTEMPT: JSON only; match the schema exactly."
    if content_type == "flashcards":
        _final_suffix += " Ten cards; front ≤10 words, back ≤20 words."
    elif content_type == "summary":
        _final_suffix += " 5–7 bullets with a short 3–5 line explanation."
    strict_suffixes = [
        "",
        "\n\nSTRICT: Return ONLY valid JSON matching the schema; no markdown fences.",
        _final_suffix,
    ]

    last_answer = ""
    validated = None

    def validate_parsed(p: dict) -> dict | None:
        if not isinstance(p, dict):
            return None
        if content_type == "flashcards":
            cards = p.get("flashcards")
            if not isinstance(cards, list) or len(cards) != 10:
                return None
            for c in cards:
                if not isinstance(c, dict):
                    return None
                if not isinstance(c.get("front"), str) or not c.get("front").strip():
                    return None
                if not isinstance(c.get("back"), str) or not c.get("back").strip():
                    return None
                if _word_count(c["front"]) > 12 or _word_count(c["back"]) > 24:
                    return None
            return p
        if content_type == "summary":
            bullets = p.get("bullets")
            explanation = p.get("explanation")
            if not isinstance(bullets, list) or not (5 <= len(bullets) <= 7):
                return None
            if not isinstance(explanation, str) or not explanation.strip():
                return None
            return p
        return p

    llm_temp = LLM_REFRESH_TEMPERATURE if apply_refresh else None
    max_attempts = 4 if apply_refresh else 3
    for attempt in range(max_attempts):
        prompt = base_prompt + strict_suffixes[min(attempt, len(strict_suffixes) - 1)]
        logger.info("[CONTENT PROMPT] doc=%s type=%s attempt=%s len=%s", doc_id, content_type, attempt + 1, len(prompt))
        llm_max_tokens = None
        if content_type == "summary":
            llm_max_tokens = FEATURE_TOKEN_BUDGETS["summary"]["output"]
        elif content_type in ("flashcards", "flashcard"):
            llm_max_tokens = FEATURE_TOKEN_BUDGETS["flashcard"]["output"]

        result = await llm_router.generate(
            doc_id=doc_id,
            task_type=content_type,
            prompt=prompt,
            context=context,
            use_cache=False,
            llm_variant=llm_variant,
            temperature=llm_temp,
            max_tokens=llm_max_tokens,
        )
        last_answer = result.get("answer", "") or ""
        logger.info(
            "[CONTENT LLM] doc=%s type=%s attempt=%s len=%s",
            doc_id,
            content_type,
            attempt + 1,
            len(last_answer),
        )

        parsed = _parse_json_response(last_answer)
        validated = validate_parsed(parsed) if parsed else None
        logger.info("[CONTENT PARSED] doc=%s type=%s attempt=%s ok=%s", doc_id, content_type, attempt + 1, bool(validated))
        if validated:
            break

    if validated:
        validated["source_chunks"] = [
            {"chunk_id": c["chunk_id"], "section": c.get("section", "")}
            for c in chunks
        ]
        validated["cached"] = False
        if not skip_cache:
            await set_cached(doc_id, content_type, validated)
        return validated

    return {"error": "Could not produce valid structured output for this document.", "raw": last_answer, "cached": False}


async def ask_mentor(
    doc_id: str, question: str, conversation_history: list = None, llm_variant: str | None = None,
) -> dict:
    """AI Mentor — context-aware Q&A with follow-up questions."""
    chunks = await retrieve_for_task(doc_id, question, task_type="mentor")

    if not chunks:
        return {"answer": "Not in document.", "source_chunks": [], "follow_up": None}

    context = "\n\n".join(c["text"] for c in chunks)

    full_context = context
    if conversation_history:
        history_text = "\n".join(
            f"{'Student' if m['role']=='user' else 'Mentor'}: {m['content']}"
            for m in conversation_history[-4:]
        )
        full_context = f"Previous conversation:\n{history_text}\n\nDocument context:\n{context}"

    prompt = get_prompt("mentor")
    result = await llm_router.generate(
        doc_id=doc_id,
        task_type="mentor",
        prompt=prompt,
        context=f"{full_context}\n\nStudent's question: {question}",
        llm_variant=llm_variant,
    )

    return {
        "answer": result["answer"],
        "source_chunks": [
            {"chunk_id": c["chunk_id"], "section": c.get("section", ""), "text": c["text"][:200]}
            for c in chunks
        ],
        "cached": result.get("cached", False),
    }


def _parse_json_response(text: str) -> dict | None:
    """Robust JSON extraction — handles <think> tags, markdown fences, and reasoning preamble."""
    if not text or not isinstance(text, str):
        return None

    # 1) Strip <think>...</think> blocks
    clean = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE).strip()

    # 2) Try direct JSON parse
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            # Flashcards strict schema: [{front, back}, ...]
            if parsed and all(isinstance(item, dict) and "front" in item and "back" in item for item in parsed):
                return {"flashcards": parsed}
            # Quiz schema (if misrouted) could show up as list
            if parsed and all(isinstance(item, dict) and "question" in item and "options" in item for item in parsed):
                return {"questions": parsed}
            return {"items": parsed}
    except json.JSONDecodeError:
        pass

    # 3) Extract from markdown code fences ```json ... ```
    fence_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', clean)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 4) Find the last { ... } block (LLM often puts reasoning before JSON)
    brace_positions = [i for i, c in enumerate(clean) if c == '{']
    for start_pos in reversed(brace_positions):
        depth = 0
        end_pos = start_pos
        for i in range(start_pos, len(clean)):
            if clean[i] == '{':
                depth += 1
            elif clean[i] == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break
        if end_pos > start_pos:
            candidate = clean[start_pos:end_pos]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    # 5) Try finding a JSON array [ ... ]
    arr_match = re.search(r'\[[\s\S]*\]', clean)
    if arr_match:
        try:
            arr = json.loads(arr_match.group())
            if isinstance(arr, list) and arr:
                # Guess the wrapper key from content
                if all('front' in item and 'back' in item for item in arr if isinstance(item, dict)):
                    return {"flashcards": arr}
                if all('q' in item and 'a' in item for item in arr if isinstance(item, dict)):
                    return {"flashcards": arr}
                if all('question' in item and 'options' in item for item in arr if isinstance(item, dict)):
                    return {"questions": arr}
                return {"items": arr}
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse JSON from LLM response ({len(text)} chars)")
    return None

