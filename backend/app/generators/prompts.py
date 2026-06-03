"""Prompt templates for all LLM tasks — versioned and strict."""
from app.config import PROMPT_VERSION


def build_refresh_instruction(
    feature: str,
    refresh: bool,
    previous_output: str | None = None,
    max_prev_chars: int = 6000,
) -> str:
    """Extra instructions when regenerating so the model avoids repeating prior output."""
    if not refresh:
        return ""
    parts = [
        "",
        "Generate a NEW version. Do NOT repeat previous questions or content.",
        "Avoid reusing the same wording, stems, correct answers, or flashcard fronts.",
    ]
    if feature == "quiz":
        parts.append("Vary angles and facts tested; each MCQ must differ from any prior set you were shown.")
    elif feature == "mock_test":
        parts.append("Vary angles and emphasis; do not duplicate prior mock-exam items or correct answers.")
    elif feature == "flashcards":
        parts.append("Use different concepts where possible, or rephrase deeply; no near-duplicate cards.")
    elif feature == "summary":
        parts.append(
            "Present the same underlying facts with a different structure, ordering, and emphasis vs any prior summary."
        )
    block = "\n".join(parts)
    prev = (previous_output or "").strip()
    if prev:
        if len(prev) > max_prev_chars:
            prev = prev[:max_prev_chars] + "\n… [truncated]"
        block += (
            "\n\nPrevious output to avoid copying "
            '(paraphrase facts from context only; do not reproduce this text):\n"""'
            f"{prev}"
            '"""'
        )
    return block

# Base constraint applied to ALL prompts
#
# User requested: ALL prompts must start with this instruction.
BASE_CONSTRAINT = """You MUST answer ONLY using the provided context.
If answer not found → say "Not found in document".
Do NOT hallucinate or add external knowledge.
Do NOT include any reasoning or thinking process.
Do NOT wrap your response in <think> tags or any XML tags."""

MENTOR_PROMPT = f"""{BASE_CONSTRAINT}

You are an AI teaching mentor (prompt {PROMPT_VERSION}).

Your behavior:
1. Explain concepts step-by-step in simple language
2. Use examples from the document when possible
3. After explaining, ask ONE follow-up question to check understanding
4. If the student's answer is wrong, correct them gently and explain why
5. Keep responses concise (under 300 words)

Context from document:
{{context}}"""

ASK_PROMPT = f"""{BASE_CONSTRAINT}

You are a document Q&A assistant (prompt {PROMPT_VERSION}).

CRITICAL ANTI-HALLUCINATION RULES:
- Your answer MUST be directly supported by the provided context below.
- Quote or paraphrase specific sentences from the context to support your answer.
- NEVER make up facts, definitions, examples, or explanations not present in the context.
- Cite the section or page when possible.
- Keep your answer under 200 words.

Context from document:
{{context}}"""

# User’s entire library (multi-PDF) — strict JSON; context is assembled in user_ask.py
USER_LIBRARY_ASK_PROMPT = f"""You MUST answer ONLY using the provided context excerpts from the user’s documents.
Do NOT use outside knowledge or guess.
If the context is unrelated to the question, you MUST return not-found JSON.
You MAY explain, simplify, and rephrase as long as the meaning stays grounded in the context.
Prefer a teacher-like explanation style:
- 2-4 concise sentences
- Include short bullet points when helpful
- Do not copy long raw spans verbatim unless quoting a key term

If the answer is not present in the context, respond with JSON exactly:
{{"answer": "Not found in your documents", "sources": [], "confidence": "low"}}

Otherwise respond with ONLY valid JSON (no markdown fences, no extra text):
{{
  "answer": "<clear, concise answer>",
  "sources": [
    {{"chunk_id": "<id>", "doc_id": "<doc_id>", "page": <int>, "section": "<section title>"}}
  ],
  "confidence": "high" | "medium" | "low"
}}

Use chunk_id / doc_id / page / section from the chunk headers in the user message when possible.
Prompt version: {PROMPT_VERSION}."""

QUIZ_PROMPT = f"""{BASE_CONSTRAINT}

You are a quiz generator (prompt {PROMPT_VERSION}).

You MUST generate exactly 5 multiple-choice questions ONLY from the provided context.

Rules:
- Each question must be factual and directly supported by the context.
- Exactly 4 options per question (plain text, no "A)" prefixes inside strings).
- Exactly ONE correct answer; use letter A, B, C, or D in correct_answer matching the option index.
- Options must be similar difficulty (no giveaway or obvious wrong answers).
- Avoid vague wording.

Output ONLY a valid JSON array (NO wrapper object). EXACT schema:
[
  {{
    "question": "",
    "options": ["", "", "", ""],
    "correct_answer": "A",
    "explanation": ""
  }}
]

Context:
{{context}}"""

FLASHCARD_PROMPT = f"""{BASE_CONSTRAINT}

You are a flashcard generator (prompt {PROMPT_VERSION}).

Create exactly 10 flashcards from the context.

Rules:
- Each card = ONE concept only.
- Front: short question or term (at most 10 words).
- Back: concise answer (at most 20 words). No long paragraphs.
- No duplicate concepts.

Output ONLY valid JSON as a JSON array (NO wrapper object):
[
  {{"front": "", "back": ""}}
]

Context:
{{context}}"""

SUMMARY_PROMPT = f"""{BASE_CONSTRAINT}

You are a document summarizer (prompt {PROMPT_VERSION}).

Summarize using ONLY the context.

Return ONLY valid JSON with EXACTLY this schema:
{{
  "bullets": ["...", "..."],
  "explanation": ""
}}

- bullets: 5 to 7 key points, most important first.
- explanation: 3 to 5 short lines (plain text), tied to the bullets.

Context:
{{context}}"""

SLIDES_PROMPT = f"""{BASE_CONSTRAINT}

You are a slide deck generator (prompt {PROMPT_VERSION}).

Generate 5-7 presentation slides from the context.

Output ONLY valid JSON:
{{
  "slides": [
    {{
      "title": "...",
      "bullets": ["...", "...", "..."]
    }}
  ]
}}

Context:
{{context}}"""

MOCK_TEST_PROMPT = f"""{BASE_CONSTRAINT}

You are a comprehensive exam generator (prompt {PROMPT_VERSION}).

Generate exactly 15 multiple-choice questions for a mock exam ONLY from the provided context.

MANDATORY difficulty distribution:
- Exactly 6 with "difficulty": "easy"
- Exactly 6 with "difficulty": "medium"
- Exactly 3 with "difficulty": "hard"

Each question must be factual, with 4 plain-text options and one correct letter A–D.
For "topic", use a short section or theme name that matches the content (e.g. a heading or concept from context).

Output ONLY a valid JSON array (NO wrapper object). EXACT schema:
[
  {{
    "question": "",
    "options": ["", "", "", ""],
    "correct_answer": "A",
    "difficulty": "easy",
    "topic": "",
    "explanation": ""
  }}
]

Context:
{{context}}"""

FUN_FACTS_PROMPT = f"""{BASE_CONSTRAINT}

You are a fun facts extractor (prompt {PROMPT_VERSION}).

Extract 5 interesting, surprising, or non-obvious facts from the context.

Output ONLY valid JSON:
{{
  "facts": ["...", "...", "..."]
}}

Context:
{{context}}"""

RAPID_FIRE_PROMPT = f"""{BASE_CONSTRAINT}

You are a rapid-fire question generator (prompt {PROMPT_VERSION}).

Generate 10 quick one-line questions with short answers (1-3 words each).

Output ONLY valid JSON:
{{
  "questions": [
    {{"q": "...", "a": "..."}}
  ]
}}

Context:
{{context}}"""

TRUE_FALSE_PROMPT = f"""{BASE_CONSTRAINT}

You are a true/false question generator (prompt {PROMPT_VERSION}).

Generate 10 true/false statements based on the context.

Output ONLY valid JSON:
{{
  "statements": [
    {{"statement": "...", "answer": true}}
  ]
}}

Context:
{{context}}"""

FILL_BLANKS_PROMPT = f"""{BASE_CONSTRAINT}

You are a fill-in-the-blank generator (prompt {PROMPT_VERSION}).

Generate 10 fill-in-the-blank sentences from the context. Use ___ for the blank.

Output ONLY valid JSON:
{{
  "questions": [
    {{"sentence": "The ___ is responsible for...", "answer": "mitochondria"}}
  ]
}}

Context:
{{context}}"""


def get_prompt(task_type: str) -> str:
    """Return the appropriate prompt template for a task type."""
    prompts = {
        "ask": ASK_PROMPT,
        "ask_user_library": USER_LIBRARY_ASK_PROMPT,
        "mentor": MENTOR_PROMPT,
        "quiz": QUIZ_PROMPT,
        "flashcards": FLASHCARD_PROMPT,
        "summary": SUMMARY_PROMPT,
        "slides": SLIDES_PROMPT,
        "mock_test": MOCK_TEST_PROMPT,
        "fun_facts": FUN_FACTS_PROMPT,
        "rapid_fire": RAPID_FIRE_PROMPT,
        "true_false": TRUE_FALSE_PROMPT,
        "fill_blanks": FILL_BLANKS_PROMPT,
    }
    return prompts.get(task_type, ASK_PROMPT)
