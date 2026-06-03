"""Test Sarvam chat API — same model and token budget style as app (105B + reasoning headroom)."""
import httpx
import json
from app.config import (
    SARVAM_API_KEY,
    SARVAM_API_URL,
    SARVAM_MODEL,
    LLM_MAX_TOKENS_DEFAULT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)

headers = {
    "Authorization": f"Bearer {SARVAM_API_KEY}",
    "Content-Type": "application/json",
}
payload = {
    "model": SARVAM_MODEL,
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "max_tokens": LLM_MAX_TOKENS_DEFAULT,
    "temperature": LLM_TEMPERATURE,
}
r = httpx.post(
    SARVAM_API_URL,
    json=payload,
    headers=headers,
    timeout=max(LLM_TIMEOUT_SECONDS, 60) + 15,
)
print(f"STATUS: {r.status_code}")
data = r.json()
print(f"MODEL (response): {data.get('model', '?')}")
print(f"KEYS: {list(data.keys())}")
if "usage" in data:
    print(f"USAGE: {data['usage']}")
if "choices" in data and data["choices"]:
    c0 = data["choices"][0]
    msg = c0.get("message") or {}
    print(f"finish_reason: {c0.get('finish_reason')}")
    content = msg.get("content")
    rc = msg.get("reasoning_content")
    print(f"content: {repr(content)[:500]}")
    if rc:
        print(f"reasoning_content (len={len(rc)}): {repr(rc)[:200]}…")
    if content:
        print(f"\nANSWER: {content}")
    elif rc and not content:
        print(
            "\nNOTE: content is empty but reasoning_content exists — increase max_tokens "
            f"(current payload max_tokens={payload['max_tokens']})."
        )
else:
    print(f"FULL: {json.dumps(data, indent=2)[:800]}")
