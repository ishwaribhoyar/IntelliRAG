"""Token and cost tracking utility for cost-aware infrastructure.

Stores user-specific usage and billing telemetry under:
- `storage/usage/<user_id>.json`
- `storage/billing/<user_id>.json`
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

STORAGE_USAGE_DIR = Path("storage/usage")
STORAGE_BILLING_DIR = Path("storage/billing")

STORAGE_USAGE_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_BILLING_DIR.mkdir(parents=True, exist_ok=True)

# Token rates in USD per 1,000,000 tokens
MODEL_RATES = {
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gemini-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 0.15, "output": 0.60},
}


def _clean_user_id(user_id: str) -> str:
    """Normalize user_id if it has userlib: prefix."""
    if not user_id:
        return "default_user"
    if user_id.startswith("userlib:"):
        return user_id.split(":", 1)[1]
    return user_id


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count from string length (1 token ~= 4 chars)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def track_user_usage(
    user_id: str,
    provider: str,
    model: str,
    prompt: str,
    response: str,
    task_type: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
):
    """Tracks prompt/response token usage and estimated cost for a given request."""
    clean_id = _clean_user_id(user_id)
    
    # 1. Calculate tokens
    in_tokens = prompt_tokens if prompt_tokens is not None else estimate_tokens(prompt)
    out_tokens = completion_tokens if completion_tokens is not None else estimate_tokens(response)
    total_tokens = in_tokens + out_tokens

    # 2. Match rates & calculate cost
    model_key = (model or "default").strip().lower()
    rates = MODEL_RATES.get(model_key)
    if not rates:
        # Check substring match
        matched = False
        for k in MODEL_RATES:
            if k in model_key:
                rates = MODEL_RATES[k]
                matched = True
                break
        if not matched:
            rates = MODEL_RATES["default"]

    cost = ((in_tokens * rates["input"]) + (out_tokens * rates["output"])) / 1_000_000.0

    # 3. Read/Write Usage Statistics
    usage_file = STORAGE_USAGE_DIR / f"{clean_id}.json"
    usage_data: dict[str, Any] = {
        "user_id": clean_id,
        "tokens_consumed": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        },
        "provider_usage": {},
        "heavy_usage_spikes": [],
        "quota_exhaustions": {}
    }

    try:
        if usage_file.exists():
            usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read usage file for user %s: %s", clean_id, e)

    # Update tokens consumed
    tc = usage_data.setdefault("tokens_consumed", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    tc["prompt_tokens"] = tc.get("prompt_tokens", 0) + in_tokens
    tc["completion_tokens"] = tc.get("completion_tokens", 0) + out_tokens
    tc["total_tokens"] = tc.get("total_tokens", 0) + total_tokens

    # Update provider usage counts
    pu = usage_data.setdefault("provider_usage", {})
    provider_key = (provider or "unknown").strip().lower()
    pu[provider_key] = pu.get(provider_key, 0) + total_tokens

    # Track heavy usage spikes (requests using > 4000 tokens)
    if total_tokens > 4000:
        spikes = usage_data.setdefault("heavy_usage_spikes", [])
        spikes.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tokens": total_tokens,
            "model": model,
            "task_type": task_type
        })
        # Keep only the last 50 spikes
        if len(spikes) > 50:
            usage_data["heavy_usage_spikes"] = spikes[-50:]

    try:
        usage_file.write_text(json.dumps(usage_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write usage file for user %s: %s", clean_id, e)

    # 4. Read/Write Billing Data
    billing_file = STORAGE_BILLING_DIR / f"{clean_id}.json"
    billing_data = {
        "user_id": clean_id,
        "estimated_cost_usd": 0.0,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    try:
        if billing_file.exists():
            billing_data = json.loads(billing_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read billing file for user %s: %s", clean_id, e)

    billing_data["estimated_cost_usd"] = billing_data.get("estimated_cost_usd", 0.0) + cost
    billing_data["last_updated"] = datetime.now(timezone.utc).isoformat()

    try:
        billing_file.write_text(json.dumps(billing_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write billing file for user %s: %s", clean_id, e)

    logger.debug("Tracked usage for user %s: %d tokens, cost $%.8f", clean_id, total_tokens, cost)


def track_quota_exhaustion(user_id: str, limit_type: str):
    """Logs a quota exhaustion event when a rate limit boundary is reached."""
    clean_id = _clean_user_id(user_id)
    usage_file = STORAGE_USAGE_DIR / f"{clean_id}.json"
    usage_data = {}

    try:
        if usage_file.exists():
            usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    qe = usage_data.setdefault("quota_exhaustions", {})
    limit_type = limit_type.strip().lower()
    qe[limit_type] = qe.get(limit_type, 0) + 1

    try:
        usage_data["user_id"] = clean_id
        usage_file.write_text(json.dumps(usage_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write quota exhaustion for user %s: %s", clean_id, e)
