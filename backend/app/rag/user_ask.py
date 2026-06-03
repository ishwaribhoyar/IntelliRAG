"""User-library RAG: single entry point for AI Ask across all of a user's PDFs.

Rules: retrieve-first only; LLM sees only retrieved chunks; strict not-found handling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from app.config import PROMPT_VERSION, FEATURE_TOKEN_BUDGETS
from app.database import SessionLocal, Document
from app.generators.prompts import get_prompt
from app.llm.trust import build_source_citations, compute_confidence
from app.query.expander import sanitize_query, expand_query
from app.modules.llm_router.router import llm_router
from app.retrieval.context_filter import filter_context
from app.retrieval.hybrid import hybrid_retrieve
from app.retrieval.mmr import mmr_filter
from app.reranker.llm_reranker import rerank_chunks
from app.state import MAX_USER_ASK_CACHE, user_ask_cache, touch_doc

logger = logging.getLogger(__name__)

NOT_FOUND = "Not found in your documents"
NO_RELEVANT = "No relevant content found in your documents"
ASK_CACHE_VERSION = "v2"
MAX_FOLLOWUP_MEMORY = 500
_last_query_by_user: dict[str, str] = {}


def _put_user_ask_cache(key: str, payload: dict) -> None:
    if key in user_ask_cache:
        user_ask_cache.pop(key, None)
    user_ask_cache[key] = payload
    while len(user_ask_cache) > MAX_USER_ASK_CACHE:
        user_ask_cache.popitem(last=False)
# RRF scores are typically small (e.g. 0.01–0.15); below this, treat as no match.
MIN_TOP_RRF = 0.008
EXTRACTIVE_RRF = 0.06
MAX_CONTEXT_TOKENS = FEATURE_TOKEN_BUDGETS["ask"]["context"]
MERGE_POOL = 20
MMR_MAX = 3
TOP_RELEVANCE_GATE = 0.55
NOISE_WORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "being", "been",
    "what", "who", "when", "where", "why", "how", "please", "explain", "define",
    "of", "for", "to", "in", "on", "at", "with", "about", "from", "by",
    "this", "that", "it",
}


def _query_type(query: str) -> str:
    q = query.strip().lower()
    if q.startswith("what is") or q.startswith("define"):
        return "definition"
    if any(x in q for x in ("explain", "simplify", "describe", "rephrase")):
        return "explanation"
    return "general"


def _keywords(query: str) -> list[str]:
    q = query.lower()
    toks = re.findall(r"[a-z0-9\+\#]{2,}", q)
    return [t for t in toks if t not in NOISE_WORDS]


def normalize_query(raw: str) -> str | None:
    cleaned = sanitize_query(raw)
    if not cleaned:
        return None
    lowered = cleaned.lower().strip()
    keys = _keywords(lowered)
    # Keep intent words in surface query, append concise keyword bag.
    if keys:
        return f"{lowered} | keywords: {' '.join(keys[:8])}"
    return lowered


def is_valid_query(raw: str) -> bool:
    q = (raw or "").strip()
    if len(q) < 3:
        return False
    # Block single/random letters like "s", "aa", "xq".
    letters_only = re.sub(r"[^a-zA-Z]", "", q)
    if letters_only and len(letters_only) <= 2:
        return False
    if re.fullmatch(r"[a-zA-Z]{1,2}", q):
        return False
    return True


def _weight_for_query(query: str) -> tuple[float, float]:
    if _query_type(query) == "explanation":
        # Explanatory prompts can be broader; keep vector strong.
        return 0.6, 0.4
    word_count = len(re.findall(r"\w+", query))
    if word_count <= 5:
        return 0.3, 0.7  # vector, bm25
    return 0.6, 0.4


def _keyword_boost(chunk: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    text = f"{chunk.get('section', '')} {chunk.get('text', '')}".lower()
    boost = 0.0
    for k in keywords:
        if re.search(rf"\b{re.escape(k)}\b", text):
            boost += 0.04
    return min(boost, 0.2)


def _relevance_score(chunk: dict, keywords: list[str]) -> float:
    base = float(chunk.get("rrf_score", chunk.get("score", 0)) or 0)
    if not keywords:
        return min(base * 20.0, 1.0)
    text = f"{chunk.get('section', '')} {chunk.get('text', '')}".lower()
    hits = 0
    for k in keywords:
        if re.search(rf"\b{re.escape(k)}\b", text):
            hits += 1
    overlap = hits / max(1, len(keywords))
    phrase = " ".join(keywords[:3]).strip()
    phrase_hit = 1.0 if phrase and phrase in text else 0.0
    # Scale RRF into [0,1]-ish and blend with lexical overlap.
    base_norm = min(base * 20.0, 1.0)
    return 0.5 * overlap + 0.2 * base_norm + 0.3 * phrase_hit


def _keyword_coverage(chunk: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    text = f"{chunk.get('section', '')} {chunk.get('text', '')}".lower()
    matched = 0
    for k in keywords:
        if re.search(rf"\b{re.escape(k)}\b", text):
            matched += 1
    return matched / max(1, len(keywords))


def _relevance_gate_for_query(query: str, has_keywords: bool) -> float:
    qt = _query_type(query)
    if qt == "explanation" and not has_keywords:
        # "explain this" style prompts should be allowed when context is loosely related.
        return 0.35
    if qt == "explanation":
        return 0.45
    return TOP_RELEVANCE_GATE


def _dedupe_chunks(chunks: list[dict], similarity_threshold: float = 0.9) -> list[dict]:
    """Remove near-duplicate chunks by text similarity."""
    out: list[dict] = []
    for c in chunks:
        text = (c.get("text", "") or "").strip()
        if not text:
            continue
        is_dup = False
        for prev in out:
            prev_text = (prev.get("text", "") or "").strip()
            if not prev_text:
                continue
            sim = SequenceMatcher(None, text, prev_text).ratio()
            if sim >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            out.append(c)
    return out


def _cache_key(user_id: str, normalized_q: str) -> str:
    h = hashlib.sha256(f"{ASK_CACHE_VERSION}\n{user_id}\n{normalized_q}".encode("utf-8")).hexdigest()
    return h


def _remember_last_query(user_id: str, query: str) -> None:
    q = (query or "").strip()
    if not q:
        return
    _last_query_by_user[user_id] = q
    # Bounded in-memory store to avoid unbounded growth.
    if len(_last_query_by_user) > MAX_FOLLOWUP_MEMORY:
        first_key = next(iter(_last_query_by_user))
        _last_query_by_user.pop(first_key, None)


def _resolve_followup_query(user_id: str, raw_query: str) -> str:
    q = (raw_query or "").strip()
    if not q:
        return q
    is_explain_followup = bool(
        re.match(
            r"^(?:pls|please)?\s*(?:can you\s*)?(?:explain|simplify|describe|rephrase)"
            r"(?:\s+this|\s+it)?(?:\s+in\s+detail)?\s*$",
            q,
            flags=re.IGNORECASE,
        )
    )
    if not is_explain_followup:
        return q
    prev = (_last_query_by_user.get(user_id) or "").strip()
    if not prev:
        return q
    return f"Explain this topic from my documents in simple terms: {prev}"


def _diverse_by_doc(chunks: list[dict], max_total: int = MMR_MAX, max_per_doc: int = 3) -> list[dict]:
    """Prefer chunks from multiple documents when scores are similar."""
    if not chunks:
        return []
    out: list[dict] = []
    counts: dict[str, int] = defaultdict(int)
    for c in chunks:
        did = str(c.get("doc_id", "") or "")
        if counts[did] >= max_per_doc:
            continue
        out.append(c)
        counts[did] += 1
        if len(out) >= max_total:
            break
    if len(out) < min(3, len(chunks)):
        for c in chunks:
            if c in out:
                continue
            out.append(c)
            if len(out) >= max_total:
                break
    return out[:max_total]


async def retrieve_context(user_id: str, query: str, scope_doc_id: str | None = None) -> list[dict]:
    """Hybrid retrieval across all ready user documents; returns top chunks with doc_id set."""
    from app.shared.utils.doc_utils import _ensure_doc_assets_ready

    db = SessionLocal()
    try:
        q = db.query(Document).filter(
            Document.user_id == user_id,
            Document.status.in_(["ready", "partially_ready"]),
        )
        if scope_doc_id:
            q = q.filter(Document.doc_id == scope_doc_id)
        docs = q.order_by(Document.created_at.desc()).all()
    finally:
        db.close()

    merged: list[dict] = []
    qtype = _query_type(query)
    query_for_retrieval = query.split("| keywords:")[0].strip()
    keywords = _keywords(query_for_retrieval)
    vector_w, bm25_w = _weight_for_query(query_for_retrieval)
    # Query expansion helps short definition queries get exact topical context.
    expanded = expand_query(query_for_retrieval, "analytical" if qtype == "explanation" else "factual")
    # Deduplicate while preserving order.
    expanded_queries = []
    seen_q = set()
    for qtxt, _w in expanded[:3]:
        qk = qtxt.strip().lower()
        if qk not in seen_q:
            seen_q.add(qk)
            expanded_queries.append(qtxt)
    if query_for_retrieval not in seen_q:
        expanded_queries.insert(0, query_for_retrieval)
    for d in docs:
        try:
            await _ensure_doc_assets_ready(d.doc_id)
            touch_doc(d.doc_id)
        except Exception as e:
            logger.warning("[user_ask] skip doc %s: %s", d.doc_id, e)
            continue

        for qtxt in expanded_queries:
            try:
                part = await hybrid_retrieve(
                    doc_id=d.doc_id,
                    query=qtxt,
                    query_type="factual" if qtype == "definition" else "analytical",
                    top_k=5,
                    vector_weight=vector_w,
                    bm25_weight=bm25_w,
                    rrf_k=8 if qtype == "definition" else 10,
                )
            except Exception as e:
                logger.warning("[user_ask] retrieve failed for %s: %s", d.doc_id, e)
                continue

            for c in part:
                ch = dict(c)
                ch["doc_id"] = d.doc_id
                ch["rrf_score"] = float(ch.get("rrf_score", ch.get("score", 0)) or 0) + _keyword_boost(ch, keywords)
                merged.append(ch)

    # Remove weak matches early so the final context is tighter/relevant.
    merged = [c for c in merged if float(c.get("rrf_score", c.get("score", 0)) or 0) >= 0.006]
    # Hard relevance filter (lexical + retrieval blend). Target >= 0.5.
    filtered = []
    for c in merged:
        rel = _relevance_score(c, keywords)
        if rel >= 0.5:
            c = dict(c)
            c["relevance_score"] = round(rel, 4)
            filtered.append(c)
    merged = filtered
    # Force keyword presence for short/keyword-heavy queries.
    if qtype != "explanation" and keywords and len(keywords) <= 3:
        keyword_required = []
        for c in merged:
            text = f"{c.get('section', '')} {c.get('text', '')}".lower()
            if any(re.search(rf"\b{re.escape(k)}\b", text) for k in keywords):
                keyword_required.append(c)
        merged = keyword_required
    # For multi-keyword definition queries, require phrase match or high keyword coverage.
    if qtype == "definition" and len(keywords) >= 2:
        strict = []
        phrase = " ".join(keywords[:3]).strip()
        for c in merged:
            text = f"{c.get('section', '')} {c.get('text', '')}".lower()
            coverage = _keyword_coverage(c, keywords)
            if (phrase and phrase in text) or coverage >= 0.75:
                strict.append(c)
        merged = strict

    merged.sort(key=lambda x: float(x.get("rrf_score", x.get("score", 0)) or 0), reverse=True)
    merged = _dedupe_chunks(merged, similarity_threshold=0.9)
    merged = merged[:MERGE_POOL]
    merged = mmr_filter(merged, max_chunks=MMR_MAX, similarity_threshold=0.85)
    merged = _diverse_by_doc(merged, max_total=MMR_MAX, max_per_doc=3)
    merged = filter_context(merged, max_tokens=MAX_CONTEXT_TOKENS)
    for i, c in enumerate(merged[:5], 1):
        logger.info(
            "[user_ask] query='%s' top%d doc=%s chunk=%s section=%s page=%s score=%.5f rel=%s preview=%s",
            query_for_retrieval[:120],
            i,
            c.get("doc_id", ""),
            c.get("chunk_id", ""),
            (c.get("section", "") or "")[:60],
            c.get("page", 1),
            float(c.get("rrf_score", c.get("score", 0)) or 0),
            c.get("relevance_score", ""),
            (c.get("text", "") or "").replace("\n", " ")[:140],
        )
    return merged


def post_filter(chunks: list[dict]) -> list[dict]:
    """Trim token budget (filter_context already ran); enforce cap."""
    if not chunks:
        return []
    return filter_context(chunks, max_tokens=MAX_CONTEXT_TOKENS)


def should_call_llm(chunks: list[dict], query: str) -> bool:
    """Skip LLM for very strong match + simple definition-style queries."""
    if not chunks:
        return True
    if _query_type(query) == "explanation":
        return True
    q_raw = query.split("| keywords:")[0].strip().lower()
    q_keys = _keywords(q_raw)
    if _query_type(q_raw) == "definition" and len(q_keys) >= 2:
        # For concept definitions, synthesize from multiple chunks instead of single extractive snippet.
        return True
    top = float(chunks[0].get("rrf_score", chunks[0].get("score", 0)) or 0)
    if top < EXTRACTIVE_RRF:
        return True
    q = query.lower().strip()
    simple = bool(
        re.match(r"^(what is|what are|define|definition of|meaning of|who is)\b", q)
        or (len(q.split()) <= 6 and len(q) < 80)
    )
    return not simple


def extractive_answer(chunks: list[dict], query: str) -> dict[str, Any]:
    """Cheap answer from the best chunk text (no LLM)."""
    text = (chunks[0].get("text") or "").strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    body = " ".join(sentences[:3]).strip()
    if len(body) > 900:
        body = body[:897] + "..."
    sources = _sources_payload(chunks[:3])
    return {
        "answer": body or NOT_FOUND,
        "sources": sources,
        "confidence": "medium",
        "confidence_detail": compute_confidence(
            [float(c.get("rrf_score", c.get("score", 0)) or 0) for c in chunks[:5]],
            reranker_score=0.0,
            llm_confidence="medium",
            num_chunks=len(chunks),
        ),
        "llm_skipped": True,
    }


def _sources_payload(chunks: list[dict]) -> list[dict]:
    out = []
    for c in chunks:
        out.append({
            "chunk_id": c.get("chunk_id", ""),
            "doc_id": c.get("doc_id", ""),
            "page": c.get("page", 1),
            "section": c.get("section", "") or "",
        })
    return out


def _should_rerank(chunks: list[dict], query: str) -> bool:
    """Only rerank when scores are ambiguous; keep speed fast by default."""
    if len(chunks) < 5:
        return False
    q = query.lower().strip()
    if len(q.split()) <= 3:
        return False
    s1 = float(chunks[0].get("rrf_score", chunks[0].get("score", 0)) or 0)
    s2 = float(chunks[1].get("rrf_score", chunks[1].get("score", 0)) or 0)
    return abs(s1 - s2) <= 0.01


def _parse_llm_json(answer: str) -> dict[str, Any] | None:
    if not answer or not answer.strip():
        return None
    cleaned = answer.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        decoder = json.JSONDecoder()
        i = cleaned.find("{")
        if i < 0:
            return None
        obj, _ = decoder.raw_decode(cleaned[i:])
        if isinstance(obj, dict) and "answer" in obj:
            return obj
    except Exception:
        pass
    return None


async def generate_answer_with_llm(
    chunks: list[dict],
    query: str,
    user_id: str,
    llm_variant: str | None,
) -> dict[str, Any]:
    """Call LLM with strict JSON-shaped prompt; only context chunks as input."""
    context_parts = []
    for i, c in enumerate(chunks, 1):
        meta = f"[doc={c.get('doc_id','')}|chunk={c.get('chunk_id','')}|page={c.get('page',1)}|section={c.get('section','')}]"
        context_parts.append(f"--- Chunk {i} {meta} ---\n{c.get('text','')}")
    context = "\n\n".join(context_parts)
    prompt = get_prompt("ask_user_library")
    user_block = f"Context:\n{context}\n\nQuestion:\n{query}\n\nRespond with ONLY valid JSON as specified in the system prompt."

    doc_key = f"userlib:{user_id}"
    t0 = time.time()
    result = await llm_router.generate(
        doc_id=doc_key,
        task_type="ask_user_library",
        prompt=prompt,
        context=user_block,
        llm_variant=llm_variant,
        temperature=0.2,
        max_tokens=FEATURE_TOKEN_BUDGETS["ask"]["output"],
    )
    llm_ms = (time.time() - t0) * 1000
    raw = (result.get("answer") or "").strip()
    parsed = _parse_llm_json(raw)
    if parsed:
        ans = (parsed.get("answer") or "").strip()
        conf_s = (parsed.get("confidence") or "medium").lower()
        if conf_s not in ("high", "medium", "low"):
            conf_s = "medium"
        src = parsed.get("sources") or []
        if isinstance(src, list):
            norm_sources = []
            for s in src:
                if isinstance(s, dict):
                    norm_sources.append({
                        "chunk_id": s.get("chunk_id", ""),
                        "doc_id": s.get("doc_id", ""),
                        "page": s.get("page", 1),
                        "section": s.get("section", "") or "",
                    })
            sources_out = norm_sources or _sources_payload(chunks)
        else:
            sources_out = _sources_payload(chunks)
        if NOT_FOUND.lower() in ans.lower() or "not found in your documents" in ans.lower():
            return {
                "answer": NOT_FOUND,
                "sources": [],
                "confidence": "low",
                "confidence_detail": compute_confidence([0.01], num_chunks=0),
                "llm_ms": llm_ms,
                "cached": result.get("cached", False),
            }
        scores = [float(c.get("rrf_score", c.get("score", 0)) or 0) for c in chunks]
        detail = compute_confidence(scores, reranker_score=0.0, llm_confidence=conf_s, num_chunks=len(chunks))
        return {
            "answer": ans,
            "sources": sources_out,
            "confidence": conf_s,
            "confidence_detail": detail,
            "llm_ms": llm_ms,
            "cached": result.get("cached", False),
        }

    # Plain text fallback — treat as answer only if not empty
    if raw and NOT_FOUND not in raw:
        detail = compute_confidence(
            [float(c.get("rrf_score", c.get("score", 0)) or 0) for c in chunks],
            llm_confidence="medium",
            num_chunks=len(chunks),
        )
        return {
            "answer": raw[:4000],
            "sources": _sources_payload(chunks),
            "confidence": detail.get("level", "medium"),
            "confidence_detail": detail,
            "llm_ms": llm_ms,
            "cached": result.get("cached", False),
        }
    return {
        "answer": NOT_FOUND,
        "sources": [],
        "confidence": "low",
        "confidence_detail": compute_confidence([0.02], num_chunks=len(chunks)),
        "llm_ms": llm_ms,
        "cached": result.get("cached", False),
    }


async def ask_ai(
    query: str,
    user_id: str,
    *,
    scope_doc_id: str | None = None,
    llm_variant: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Single entry point for user-library AI Ask."""
    timings: dict[str, float] = {}
    t_start = time.time()
    raw_query = _resolve_followup_query(user_id, query)

    nq = normalize_query(raw_query)
    if not nq or not is_valid_query(raw_query):
        return {
            "answer": "Please enter a valid question",
            "sources": [],
            "confidence": "low",
            "confidence_detail": compute_confidence([], num_chunks=0),
            "timings": {"total_ms": 0},
            "cached": False,
        }

    ck = _cache_key(user_id, nq)
    if use_cache and ck in user_ask_cache:
        user_ask_cache.move_to_end(ck)
        hit = dict(user_ask_cache[ck])
        hit["cached"] = True
        hit.setdefault("timings", {})["total_ms"] = round((time.time() - t_start) * 1000, 1)
        return hit

    t0 = time.time()
    chunks = await retrieve_context(user_id, nq, scope_doc_id=scope_doc_id)
    timings["retrieval_ms"] = round((time.time() - t0) * 1000, 1)

    chunks = post_filter(chunks)
    # Top-k safety: if filtered chunks are still unrelated, return NOT_FOUND.
    if chunks:
        q_raw = nq.split("| keywords:")[0].strip()
        q_keys = _keywords(q_raw)
        rels = [_relevance_score(c, q_keys) for c in chunks[:MMR_MAX]]
        gate = _relevance_gate_for_query(q_raw, bool(q_keys))
        if rels and max(rels) < gate:
            out = {
                "answer": NO_RELEVANT if q_keys else NOT_FOUND,
                "sources": [],
                "confidence": "low",
                "confidence_detail": compute_confidence([], num_chunks=0),
                "timings": {**timings, "total_ms": round((time.time() - t_start) * 1000, 1)},
                "cached": False,
                "source_chunks": [],
            }
            if use_cache:
                _put_user_ask_cache(ck, {k: v for k, v in out.items() if k != "cached"})
            return out
    if not chunks:
        out = {
            "answer": NOT_FOUND,
            "sources": [],
            "confidence": "low",
            "confidence_detail": compute_confidence([], num_chunks=0),
            "timings": {**timings, "total_ms": round((time.time() - t_start) * 1000, 1)},
            "cached": False,
            "source_chunks": [],
        }
        if use_cache:
            _put_user_ask_cache(ck, {k: v for k, v in out.items() if k != "cached"})
        return out

    top_score = float(chunks[0].get("rrf_score", chunks[0].get("score", 0)) or 0)
    q_raw = nq.split("| keywords:")[0].strip()
    q_keys = _keywords(q_raw)
    top_rel = _relevance_score(chunks[0], q_keys)
    rel_gate = _relevance_gate_for_query(q_raw, bool(q_keys))
    # Hard relevance gate: score + relevance + BM25 presence for short queries.
    short_query = len(re.findall(r"\w+", q_raw)) <= 5
    has_bm25_signal = chunks[0].get("bm25_rank") is not None
    if top_score < MIN_TOP_RRF or top_rel < rel_gate or (short_query and q_keys and _query_type(q_raw) != "explanation" and not has_bm25_signal):
        out = {
            "answer": NO_RELEVANT if q_keys else NOT_FOUND,
            "sources": [],
            "confidence": "low",
            "confidence_detail": compute_confidence([top_score], num_chunks=len(chunks)),
            "timings": {**timings, "total_ms": round((time.time() - t_start) * 1000, 1)},
            "cached": False,
            "source_chunks": [],
        }
        if use_cache:
            _put_user_ask_cache(ck, {k: v for k, v in out.items() if k != "cached"})
        return out

    if _should_rerank(chunks, nq):
        try:
            reranked = await rerank_chunks(
                doc_id=f"userlib:{user_id}",
                query=nq,
                chunks=chunks,
                min_candidates=5,
                score_gap_threshold=0.01,
            )
            # Keep only best 5 after rerank and re-apply token cap.
            chunks = post_filter(reranked[:MMR_MAX])
        except Exception as e:
            logger.warning("[user_ask] rerank skipped due to error: %s", e)

    if not should_call_llm(chunks, nq):
        ex = extractive_answer(chunks, nq)
        lev = ex["confidence_detail"].get("level", "medium")
        out = {
            "answer": ex["answer"],
            "sources": ex["sources"],
            "confidence": lev,
            "confidence_detail": ex["confidence_detail"],
            "timings": {
                **timings,
                "llm_ms": 0.0,
                "total_ms": round((time.time() - t_start) * 1000, 1),
            },
            "cached": False,
            "llm_skipped": True,
            "source_chunks": build_source_citations(chunks),
        }
        if use_cache:
            _put_user_ask_cache(ck, {k: v for k, v in out.items() if k != "cached"})
        return out

    gen = await generate_answer_with_llm(chunks, nq, user_id, llm_variant)
    out = {
        "answer": gen["answer"],
        "sources": gen.get("sources") or _sources_payload(chunks),
        "confidence": gen.get("confidence", "medium"),
        "confidence_detail": gen.get("confidence_detail"),
        "timings": {
            **timings,
            "llm_ms": round(gen.get("llm_ms", 0), 1),
            "total_ms": round((time.time() - t_start) * 1000, 1),
        },
        "cached": gen.get("cached", False),
        "source_chunks": build_source_citations(chunks),
    }
    if use_cache:
        _put_user_ask_cache(ck, {k: v for k, v in out.items() if k != "cached"})
    # Remember only meaningful user questions, not resolved follow-up templates.
    if _query_type(query) != "explanation":
        _remember_last_query(user_id, query)
    return out
