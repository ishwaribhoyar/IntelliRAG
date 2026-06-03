"""Sarvam-M LLM client — with caching, timeout, retry, streaming, and rate limiting."""
import asyncio
import hashlib
import json
import re
import time
import logging
import httpx
from app.config import (
    SARVAM_API_KEY, SARVAM_API_URL, SARVAM_MODEL, LLM_TEMPERATURE,
    LLM_MAX_TOKENS_DEFAULT, LLM_MAX_TOKENS_BY_TASK,
    LLM_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES, LLM_RETRY_DELAY, RATE_LIMIT_GAP_SECONDS,
    PROMPT_VERSION,
    sarvam_model_id_for_variant,
)
from app.state import llm_cache, last_request_time, doc_locks

logger = logging.getLogger(__name__)

TIMEOUT_FALLBACK = "Response taking too long. Please retry."


def _cache_key(doc_id: str, task_type: str, context: str, model_id: str) -> tuple:
    context_hash = hashlib.md5(context.encode()).hexdigest()
    return (doc_id, task_type, context_hash, PROMPT_VERSION, model_id)


async def _rate_limit(doc_id: str):
    """Enforce minimum gap between LLM calls for a document."""
    last = last_request_time.get(doc_id, 0)
    elapsed = time.time() - last
    if elapsed < RATE_LIMIT_GAP_SECONDS:
        await asyncio.sleep(RATE_LIMIT_GAP_SECONDS - elapsed)
    last_request_time[doc_id] = time.time()


def _max_tokens_for_task(task_type: str) -> int:
    return LLM_MAX_TOKENS_BY_TASK.get(task_type, LLM_MAX_TOKENS_DEFAULT)


def _mock_llm_response(task_type: str, prompt: str, context: str) -> str:
    import re
    # Clean up and get sentences
    sentences = [s.strip() for s in re.split(r'[.!?]+', context) if len(s.strip()) > 15]
    if not sentences:
        sentences = ["This is a fallback placeholder sentence for testing purposes only."]
    
    # 1. flashcards
    if task_type == "flashcards":
        cards = []
        while len(sentences) < 10:
            sentences.extend(sentences)
        for i, s in enumerate(sentences[:10]):
            words = s.split()
            front = " ".join(words[:6]) + "?"
            back = " ".join(words[:12])
            cards.append({"front": front[:45], "back": back[:75]})
        return json.dumps(cards)
        
    # 2. summary
    elif task_type == "summary":
        while len(sentences) < 5:
            sentences.extend(sentences)
        bullets = [s[:90] + ("..." if len(s) > 90 else "") for s in sentences[:5]]
        explanation = "This summary highlights key definitions, practical steps, and architectural goals discussed in the document."
        return json.dumps({
            "bullets": bullets,
            "explanation": explanation
        })
        
    # 3. slides
    elif task_type == "slides":
        slides = []
        chunks_count = min(len(sentences), 5)
        for i in range(chunks_count):
            title = f"Topic {i+1}: Study Guide"
            bullets = [sentences[(i + j) % len(sentences)][:100] for j in range(3)]
            slides.append({
                "title": title,
                "bullets": bullets
            })
        return json.dumps({"slides": slides})
        
    # 4. quiz
    elif task_type == "quiz":
        questions = []
        for i in range(5):
            correct_sent = sentences[i % len(sentences)]
            distractors = [
                f"Distractor choice A for sentence {i}",
                f"Distractor choice B for sentence {i}",
                f"Distractor choice C for sentence {i}"
            ]
            options = [correct_sent] + distractors
            rot = i % 4
            options = options[rot:] + options[:rot]
            correct_answer = chr(ord("A") + options.index(correct_sent))
            questions.append({
                "question": f"Which statement is true regarding topic {i+1}?",
                "options": [opt[:100] for opt in options],
                "correct_answer": correct_answer,
                "explanation": f"Correct answer is derived from: {correct_sent}"
            })
        return json.dumps(questions)
        
    # 5. mock_test
    elif task_type == "mock_test":
        questions = []
        diffs = ["easy"] * 6 + ["medium"] * 6 + ["hard"] * 3
        for i in range(15):
            correct_sent = sentences[i % len(sentences)]
            distractors = [
                f"Incorrect alternative Option X {i}",
                f"Incorrect alternative Option Y {i}",
                f"Incorrect alternative Option Z {i}"
            ]
            options = [correct_sent] + distractors
            rot = i % 4
            options = options[rot:] + options[:rot]
            correct_answer = chr(ord("A") + options.index(correct_sent))
            questions.append({
                "question": f"Question {i+1}: What is verified in section {i}?",
                "options": [opt[:100] for opt in options],
                "correct_answer": correct_answer,
                "difficulty": diffs[i],
                "topic": f"Section {i//3 + 1}",
                "explanation": f"Correct because: {correct_sent}"
            })
        return json.dumps(questions)
        
    # 6. fun_facts
    elif task_type == "fun_facts":
        facts = [s[:120] for s in sentences[:5]]
        return json.dumps({"facts": facts})
        
    # 7. rapid_fire
    elif task_type == "rapid_fire":
        qas = []
        for i in range(10):
            sent = sentences[i % len(sentences)]
            words = sent.split()
            q = f"What is key about {' '.join(words[:4])}?"
            a = words[-1] if words else "Yes"
            qas.append({"q": q[:100], "a": a[:20]})
        return json.dumps({"questions": qas})
        
    # 8. true_false
    elif task_type == "true_false":
        statements = []
        for i in range(10):
            sent = sentences[i % len(sentences)]
            ans = (i % 2 == 0)
            stmt = sent if ans else f"It is false that {sent}"
            statements.append({"statement": stmt[:150], "answer": ans})
        return json.dumps({"statements": statements})
        
    # 9. fill_blanks
    elif task_type == "fill_blanks":
        fill_blanks = []
        for i in range(10):
            sent = sentences[i % len(sentences)]
            words = sent.split()
            if len(words) > 4:
                answer = words[len(words)//2]
                words[len(words)//2] = "___"
                sentence = " ".join(words)
            else:
                sentence = "The primary RAG component is ___."
                answer = "LLM"
            fill_blanks.append({"sentence": sentence[:150], "answer": answer[:30]})
        return json.dumps({"questions": fill_blanks})
        
    # 10. general Q&A
    else:
        if "ask_user_library" in task_type or "eval_" in task_type:
            if '{"answer":' in prompt or 'valid JSON' in prompt:
                return json.dumps({
                    "answer": f"Based on the documents, the concept refers to: {sentences[0][:150]}",
                    "sources": [
                        {"chunk_id": "chunk_0", "doc_id": "doc_0", "page": 1, "section": "Introduction"}
                    ],
                    "confidence": "high"
                })
        reply = f"Here is the mentor explanation: {sentences[0]}\n\nLet's break it down further. Does this align with what you read in the first section?"
        return reply


async def call_sarvam_direct(
    doc_id: str,
    task_type: str,
    prompt: str,
    context: str,
    stream: bool = False,
    use_cache: bool = True,
    temperature: float | None = None,
    max_tokens: int | None = None,
    llm_variant: str | None = None,
) -> dict:
    """Call Sarvam chat completions directly with caching, timeout, retry, and rate limiting."""
    model_id = sarvam_model_id_for_variant(llm_variant)
    
    if SARVAM_API_KEY == "dummy" or not SARVAM_API_KEY:
        mock_ans = _mock_llm_response(task_type, prompt, context)
        return {
            "answer": mock_ans,
            "source_chunks": [],
            "cached": False,
            "llm_model": "mock-sarvam",
        }

    key = _cache_key(doc_id, task_type, context, model_id)

    # Check cache first → instant return
    if use_cache and key in llm_cache:
        logger.info(f"Sarvam cache hit for {doc_id}/{task_type}")
        cached = llm_cache[key].copy()
        cached["cached"] = True
        cached.setdefault("llm_model", model_id)
        return cached

    # Rate limit
    await _rate_limit(doc_id)

    # Build messages
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": context},
    ]

    temp = LLM_TEMPERATURE if temperature is None else temperature
    mtok = _max_tokens_for_task(task_type) if max_tokens is None else max_tokens

    # Retry loop with backoff (network/API failures)
    last_error = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                _make_api_call(messages, temperature=temp, max_tokens=mtok, model=model_id),
                timeout=LLM_TIMEOUT_SECONDS,
            )

            result = {
                "answer": response,
                "source_chunks": [],
                "cached": False,
                "llm_model": model_id,
            }

            # Cache the final response
            if use_cache:
                llm_cache[key] = {"answer": response, "source_chunks": [], "llm_model": model_id}

            return result

        except asyncio.TimeoutError:
            logger.warning(f"Sarvam timeout (attempt {attempt+1}/{LLM_MAX_RETRIES})")
            last_error = "timeout"
        except Exception as e:
            logger.error(f"Sarvam error (attempt {attempt+1}): {e}")
            last_error = str(e)

        if attempt < LLM_MAX_RETRIES - 1:
            await asyncio.sleep(LLM_RETRY_DELAY)

    return {
        "answer": TIMEOUT_FALLBACK if last_error == "timeout" else f"Error: {last_error}",
        "source_chunks": [],
        "cached": False,
        "llm_model": model_id,
    }


async def call_llm(
    doc_id: str,
    task_type: str,
    prompt: str,
    context: str,
    stream: bool = False,
    use_cache: bool = True,
    temperature: float | None = None,
    max_tokens: int | None = None,
    llm_variant: str | None = None,
) -> dict:
    """Backward compatibility wrapper — redirects to the unified llm_router."""
    from app.modules.llm_router.router import llm_router
    return await llm_router.generate(
        doc_id=doc_id,
        task_type=task_type,
        prompt=prompt,
        context=context,
        stream=stream,
        use_cache=use_cache,
        temperature=temperature,
        max_tokens=max_tokens,
        llm_variant=llm_variant,
    )


def _clean_response(text: str) -> str:
    """Strip <think>...</think> CoT reasoning blocks and clean up LLM output."""
    if not isinstance(text, str):
        return ""
    # Remove <think>...</think> blocks (chain-of-thought reasoning)
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
    # Remove any leftover standalone <think> or </think> tags
    cleaned = re.sub(r'</?think>', '', cleaned).strip()
    return cleaned if cleaned else text


def _extract_assistant_text(data: dict) -> str:
    """Read `message.content`; Sarvam 105B may use reasoning tokens first, leaving content null."""
    if "choices" in data and data["choices"]:
        choice0 = data["choices"][0]
        msg = choice0.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return _clean_response(content)
        rc = msg.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            logger.warning(
                "LLM returned empty content but reasoning_content is non-empty "
                "(finish_reason=%s, reasoning_chars=%s). Raise max_tokens if outputs are missing.",
                choice0.get("finish_reason"),
                len(rc),
            )
        return ""
    if "result" in data:
        r = data["result"]
        return _clean_response(r) if isinstance(r, str) else json.dumps(r)
    return json.dumps(data)


async def _make_api_call(
    messages: list[dict],
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS_DEFAULT,
    model: str | None = None,
) -> str:
    """Make the actual HTTP call to Sarvam chat completions API."""
    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model or SARVAM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS + 5) as client:
        response = await client.post(
            SARVAM_API_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        raw = _extract_assistant_text(data)
        usage = data.get("usage")
        if usage:
            logger.debug("LLM usage: %s", usage)
        return raw
