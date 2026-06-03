"""Quiz generator — CONNECTED to personalization.
Prioritizes weak topics when generating quiz questions.
Includes failure handling for edge cases.
"""
import json
import re
import logging
import random
import time
from app.config import AI_RETRIEVAL_MAX_CHUNKS, LLM_REFRESH_TEMPERATURE, FEATURE_TOKEN_BUDGETS
from app.retrieval.hybrid import retrieve_for_task, get_chunks_by_ordered_ids
from app.modules.llm_router.router import llm_router
from app.generators.prompts import get_prompt, build_refresh_instruction
from app.personalization.tracker import get_weak_topics_for_quiz
from app.retrieval.mmr import mmr_filter

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


def _options_distinct(opts: list) -> bool:
    if not isinstance(opts, list) or len(opts) != 4:
        return False
    norm = [str(o).strip().lower() for o in opts]
    return len(set(norm)) == 4


def _mock_difficulty_ok(questions: list[dict]) -> bool:
    diffs = [str(q.get("difficulty", "")).strip().lower() for q in questions]
    return diffs.count("easy") == 6 and diffs.count("medium") == 6 and diffs.count("hard") == 3


def _fill_mock_metadata(chunks: list[dict], questions: list[dict]) -> list[dict]:
    default_sec = ""
    if chunks:
        default_sec = (chunks[0].get("section") or "").strip()
    if not default_sec:
        default_sec = "General"
    for q in questions:
        t = (q.get("topic") or "").strip()
        if not t or t.lower() in {"general", "misc", "n/a"}:
            q["topic"] = default_sec[:120]
        else:
            q["topic"] = t[:120]
    return questions


def _randomize_questions(questions: list[dict]) -> list[dict]:
    """Shuffle question order + option order while preserving correctness."""
    if not questions:
        return questions
    rng = random.Random(time.time_ns())
    out = []
    for q in questions:
        item = dict(q)
        opts = list(item.get("options") or [])
        ca = str(item.get("correct_answer") or "").strip().upper()
        if len(opts) == 4 and ca in ("A", "B", "C", "D"):
            correct_idx = ord(ca) - ord("A")
            correct_opt = opts[correct_idx]
            pairs = list(enumerate(opts))
            rng.shuffle(pairs)
            new_opts = [p[1] for p in pairs]
            new_correct_idx = next((i for i, o in enumerate(new_opts) if o == correct_opt), 0)
            item["options"] = new_opts
            item["correct_answer"] = chr(ord("A") + new_correct_idx)
        out.append(item)
    rng.shuffle(out)
    return out


def _is_valid_quiz_question(q: dict, expects_difficulty: bool = False) -> bool:
    if not isinstance(q, dict):
        return False
    if not isinstance(q.get("question"), str) or not q.get("question").strip():
        return False
    opts = q.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        return False
    if not _options_distinct(opts):
        return False
    if expects_difficulty:
        d = str(q.get("difficulty", "")).strip().lower()
        if d not in ("easy", "medium", "hard"):
            return False
        top = q.get("topic")
        if not isinstance(top, str) or not top.strip():
            return False
    ca = q.get("correct_answer")
    if not isinstance(ca, str) or ca.strip().upper() not in ("A", "B", "C", "D"):
        return False
    letter = ca.strip().upper()
    idx = ord(letter) - ord("A")
    correct_text = str(opts[idx]).strip()
    if not correct_text:
        return False
    exp = q.get("explanation")
    if not isinstance(exp, str) or not exp.strip():
        return False
    return True


def _normalize_quiz_questions(
    parsed: object, quiz_type: str, chunks: list[dict] | None = None,
) -> list[dict]:
    expects_difficulty = quiz_type == "mock_test"
    # Accept either:
    # - a list of question objects (strict prompt)
    # - {"questions": [...]}
    if isinstance(parsed, list):
        questions = parsed
    elif isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        questions = parsed["questions"]
    else:
        return []

    # If model returned options as ["A) ...", ...] we still accept;
    # frontend strips labels by rendering as A/B/C/D.
    normalized = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        # Support legacy keys in case model returns mixed format.
        if "question" not in q and "q" in q:
            q = {**q, "question": q.get("q")}
        if "correct_answer" not in q and "answer" in q:
            q = {**q, "correct_answer": q.get("answer")}
        if "options" not in q and "opts" in q:
            q = {**q, "options": q.get("opts")}
        normalized.append(q)

    # Validate strict schema.
    expected_count = 15 if quiz_type == "mock_test" else 5
    if len(normalized) != expected_count:
        return []
    if expects_difficulty:
        normalized = _fill_mock_metadata(chunks or [], normalized)
    if not all(_is_valid_quiz_question(q, expects_difficulty=expects_difficulty) for q in normalized):
        return []

    if expects_difficulty:
        if not _mock_difficulty_ok(normalized):
            return []
        for q in normalized:
            q["difficulty"] = str(q.get("difficulty", "")).strip().lower()

    return normalized


async def generate_quiz(
    doc_id: str,
    quiz_type: str = "quiz",
    user_id: str = "default_user",
    llm_variant: str | None = None,
    refresh: bool = False,
    previous_output: str | None = None,
    source_chunk_ids: list[str] | None = None,
) -> dict:
    """Generate quiz questions — prioritizes weak topics for adaptive learning."""
    # Intentionally do NOT reuse cached quiz/mock_test payloads:
    # users expect fresh randomized questions/options each attempt.

    # Get weak topics for this user
    weak_topics = get_weak_topics_for_quiz(user_id)

    if quiz_type == "mock_test":
        query = "Generate comprehensive exam questions covering all sections and advanced topics"
    elif weak_topics:
        # Prioritize weak topics in quiz
        topics_str = ", ".join(weak_topics)
        query = f"Generate quiz questions focusing on these weak areas: {topics_str}. Also include general topics."
        logger.info(f"[ADAPTIVE QUIZ] Prioritizing weak topics for {user_id}: {weak_topics}")
    else:
        query = "Generate quiz questions about the main topics and key definitions"

    chunks: list[dict] = []
    if refresh and source_chunk_ids:
        chunks = get_chunks_by_ordered_ids(doc_id, source_chunk_ids)
        chunks = chunks[:AI_RETRIEVAL_MAX_CHUNKS]
        if chunks:
            logger.info(
                "[QUIZ CHUNKS] refresh=fixed doc=%s type=%s ids=%s",
                doc_id,
                quiz_type,
                [c.get("chunk_id", "") for c in chunks],
            )

    if not chunks:
        try:
            chunks = await retrieve_for_task(doc_id, query, task_type=quiz_type)
        except Exception as e:
            logger.error(f"Retrieval failed during quiz generation: {e}")
            return {"questions": [], "error": "Retrieval failed. Please try again."}

        if not chunks:
            return {"questions": [], "error": "No content found in document"}

        chunks = _dedupe_chunks_by_id(chunks)

        try:
            chunks = mmr_filter(chunks, max_chunks=AI_RETRIEVAL_MAX_CHUNKS, lambda_param=0.7)
        except Exception:
            logger.exception("MMR filter failed during quiz generation; continuing without it.")

        chunks = chunks[:AI_RETRIEVAL_MAX_CHUNKS]

    context = "\n\n".join(c["text"] for c in chunks)
    if not context.strip():
        return {"questions": [], "error": "No usable text in document chunks"}

    # Log what we retrieved (chunk ids + brief preview) to debug context mapping.
    logger.info(
        "[QUIZ RETRIEVAL] doc=%s type=%s query='%s' chunk_ids=%s",
        doc_id,
        quiz_type,
        query[:80],
        [c.get("chunk_id", "") for c in chunks],
    )
    logger.info(
        "[QUIZ CONTEXT] doc=%s preview=%s",
        doc_id,
        (context[:1200] + "…") if len(context) > 1200 else context,
    )

    feat = "mock_test" if quiz_type == "mock_test" else "quiz"
    base_prompt = (
        get_prompt(quiz_type)
        + "\n\nGenerate a fresh variant from context and avoid repeated options."
        + build_refresh_instruction(feat, refresh, previous_output)
    )

    strict_suffixes = [
        "",
        "\n\nSTRICT: Output ONLY valid JSON array matching the schema exactly; no markdown fences; no extra keys.",
        "\n\nFINAL ATTEMPT: JSON array only; 4 distinct options per question; correct_answer must be A/B/C/D only.",
    ]

    llm_temp = LLM_REFRESH_TEMPERATURE if refresh else None
    max_attempts = 4 if refresh else 3
    last_answer = ""
    for attempt in range(max_attempts):
        prompt = base_prompt + strict_suffixes[min(attempt, len(strict_suffixes) - 1)]
        logger.info("[QUIZ PROMPT] doc=%s attempt=%s len=%s", doc_id, attempt + 1, len(prompt))
        try:
            result = await llm_router.generate(
                doc_id=doc_id,
                task_type=quiz_type,
                prompt=prompt,
                context=context,
                use_cache=False,
                llm_variant=llm_variant,
                temperature=llm_temp,
                max_tokens=FEATURE_TOKEN_BUDGETS["quiz"]["output"] if quiz_type in ("quiz", "mock_test") else None,
            )
        except Exception as e:
            logger.error(f"LLM call failed during quiz generation: {e}")
            return {"questions": [], "error": "AI service temporarily unavailable. Please try again."}

        last_answer = result.get("answer", "") or ""
        logger.info(
            "[QUIZ LLM RESPONSE] doc=%s attempt=%s len=%s preview=%s",
            doc_id,
            attempt + 1,
            len(last_answer),
            (last_answer[:2000] + "…") if len(last_answer) > 2000 else last_answer,
        )

        parsed_raw = _parse_json_response(last_answer)
        questions = _normalize_quiz_questions(parsed_raw, quiz_type, chunks=chunks)
        logger.info("[QUIZ PARSED] doc=%s attempt=%s valid=%s", doc_id, attempt + 1, bool(questions))
        if questions:
            response = {"questions": _randomize_questions(questions)}
            response["source_chunks"] = [{"chunk_id": c["chunk_id"], "section": c.get("section", "")} for c in chunks]
            if weak_topics:
                response["weak_topics_targeted"] = weak_topics
            return response

    fallback_questions = _build_fallback_quiz(
        chunks,
        count=15 if quiz_type == "mock_test" else 5,
        quiz_type=quiz_type,
    )
    if fallback_questions:
        response = {
            "questions": _randomize_questions(fallback_questions),
            "source_chunks": [{"chunk_id": c["chunk_id"], "section": c.get("section", "")} for c in chunks],
            "fallback_generated": True,
        }
        if weak_topics:
            response["weak_topics_targeted"] = weak_topics
        return response

    return {"questions": [], "raw": last_answer, "source_chunks": []}


def _option_label_text(opts: list, letter: str) -> str:
    if letter not in ("A", "B", "C", "D"):
        return ""
    idx = ord(letter) - ord("A")
    if not isinstance(opts, list) or not (0 <= idx < len(opts)):
        return ""
    return str(opts[idx]).strip()


def evaluate_quiz(questions: list, user_answers: list) -> dict:
    """Evaluate user's quiz answers with robust matching."""
    correct = 0
    total = len(questions)
    details = []

    for i, (q, ua) in enumerate(zip(questions, user_answers)):
        opts = q.get("options") or []
        correct_answer = (q.get("correct_answer", "") or "").strip().upper()
        user_answer = (ua or "").strip().upper()

        is_correct = bool(correct_answer) and (user_answer == correct_answer)

        if is_correct:
            correct += 1
        details.append({
            "question_id": f"q{i}",
            "question": q.get("question", "") or q.get("q", ""),
            "user_answer": ua,
            "user_answer_letter": user_answer,
            "user_answer_text": _option_label_text(opts, user_answer),
            "correct_answer": correct_answer,
            "correct_answer_text": _option_label_text(opts, correct_answer),
            "is_correct": is_correct,
            "topic": (q.get("topic") or "").strip() or "General",
            "explanation": q.get("explanation", ""),
        })

    return {
        "score": correct,
        "correct": correct,
        "total": total,
        "accuracy": round(correct / max(total, 1), 2),
        "details": details,
    }


def _parse_json_response(text: str) -> dict | None:
    """Robust JSON extraction — handles <think> tags, markdown fences, and reasoning preamble."""
    if not text or not isinstance(text, str):
        return None

    # Strip <think>...</think> blocks
    clean = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE).strip()

    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code fences
    fence_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', clean)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find balanced { ... } blocks (last one first — LLM puts reasoning before JSON)
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

    # Try finding a JSON array
    arr_match = re.search(r'\[[\s\S]*\]', clean)
    if arr_match:
        try:
            arr = json.loads(arr_match.group())
            if isinstance(arr, list) and arr:
                return {"questions": arr}
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse quiz JSON from LLM response ({len(text)} chars)")
    return None


def _parse_mcq_text(text: str) -> list[dict]:
    """Parse plain-text MCQs when model doesn't return strict JSON."""
    if not text:
        return []

    blocks = re.split(r"\n\s*\n", text)
    questions = []
    for block in blocks:
        q_match = re.search(r"(?:^|\n)(?:Q\d*[\):.\s-]*|Question[\s:.-]*)(.+)", block, flags=re.IGNORECASE)
        if not q_match:
            continue
        q_text = q_match.group(1).strip()

        options = []
        for letter in ("A", "B", "C", "D"):
            opt_match = re.search(rf"(?:^|\n){letter}[\)\].:\-]\s*(.+)", block, flags=re.IGNORECASE)
            if opt_match:
                options.append(f"{letter}) {opt_match.group(1).strip()}")

        ans_match = re.search(r"(?:^|\n)(?:Answer|Correct(?:\s*Answer)?)\s*[:\-]\s*([A-D])", block, flags=re.IGNORECASE)
        answer = ans_match.group(1).upper() if ans_match else "A"

        if q_text and len(options) >= 2:
            while len(options) < 4:
                options.append(f"{chr(ord('A') + len(options))}) None of the above")
            questions.append({
                "q": q_text,
                "options": options[:4],
                "answer": answer,
                "difficulty": "medium",
                "topic": "General",
            })

    return questions


def _build_fallback_quiz(chunks: list[dict], count: int = 5, quiz_type: str = "quiz") -> list[dict]:
    """Deterministic fallback MCQ builder from retrieved chunks."""
    if not chunks:
        return []

    facts = []
    for c in chunks:
        section = c.get("section", "General")
        text = re.sub(r"\s+", " ", c.get("text", "")).strip()
        if not text:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            s = s.strip()
            if len(s) >= 40 and len(s) <= 180:
                facts.append((section, s))
            if len(facts) >= count * 3:
                break
        if len(facts) >= count * 3:
            break

    if not facts:
        return []

    questions = []

    # Mock test needs specific difficulty distribution.
    if quiz_type == "mock_test":
        difficulty_by_index = []
        difficulty_by_index += ["easy"] * 6
        difficulty_by_index += ["medium"] * 6
        difficulty_by_index += ["hard"] * 3
    else:
        difficulty_by_index = []
    for i in range(count):
        correct_idx = i % len(facts)
        section, correct_sentence = facts[correct_idx]
        distractors = []
        for j in range(len(facts)):
            if j == correct_idx:
                continue
            cand = facts[j][1]
            if cand != correct_sentence and len(distractors) < 3:
                distractors.append(cand)
        while len(distractors) < 3:
            distractors.append("Not stated in the document.")

        options = [correct_sentence] + distractors[:3]
        # Keep deterministic order but rotate by index for answer variety.
        rot = i % 4
        options = options[rot:] + options[:rot]
        answer_idx = options.index(correct_sentence)
        answer_letter = chr(ord("A") + answer_idx)

        # Output schema required by strict JSON prompt:
        # { question, options:[A,B,C,D], correct_answer:"A|B|C|D", explanation }
        option_texts = [str(opt) for opt in options[:4]]
        exp = correct_sentence if isinstance(correct_sentence, str) and correct_sentence.strip() else "Not found in the document."

        q_obj = {
            "question": f"Which statement is correct about {section}?",
            "options": option_texts,
            "correct_answer": answer_letter,
            "explanation": exp,
            "topic": str(section)[:120],
        }
        if quiz_type == "mock_test":
            q_obj["difficulty"] = difficulty_by_index[i] if i < len(difficulty_by_index) else "medium"

        questions.append(q_obj)

    return questions

