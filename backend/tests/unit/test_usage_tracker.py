"""Unit tests — Usage and Billing Tracker."""
import os
import json
import pytest
from pathlib import Path
from app.shared.utils.usage_tracker import (
    track_user_usage,
    track_quota_exhaustion,
    estimate_tokens,
    STORAGE_USAGE_DIR,
    STORAGE_BILLING_DIR,
)

TEST_USER_ID = "test_tracker_user"


@pytest.fixture(autouse=True)
def cleanup_telemetry_files():
    """Clean up JSON telemetry files before and after each test."""
    usage_file = STORAGE_USAGE_DIR / f"{TEST_USER_ID}.json"
    billing_file = STORAGE_BILLING_DIR / f"{TEST_USER_ID}.json"
    
    for f in (usage_file, billing_file):
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
                
    yield
    
    for f in (usage_file, billing_file):
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass


def test_estimate_tokens():
    """estimate_tokens estimates 1 token for ~4 characters."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens("a") == 1  # max(1, len/4) for non-empty


def test_track_user_usage_writes_files():
    """track_user_usage creates and updates usage/billing files with correct structure."""
    prompt = "Hello AI"
    response = "Hi there human! How can I help you today?"
    
    # Run tracking
    track_user_usage(
        user_id=TEST_USER_ID,
        provider="openai",
        model="gpt-5-nano",
        prompt=prompt,
        response=response,
        task_type="ask"
    )
    
    usage_file = STORAGE_USAGE_DIR / f"{TEST_USER_ID}.json"
    billing_file = STORAGE_BILLING_DIR / f"{TEST_USER_ID}.json"
    
    assert usage_file.exists()
    assert billing_file.exists()
    
    # Verify usage JSON content
    usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    assert usage_data["user_id"] == TEST_USER_ID
    assert "tokens_consumed" in usage_data
    assert usage_data["tokens_consumed"]["prompt_tokens"] == estimate_tokens(prompt)
    assert usage_data["tokens_consumed"]["completion_tokens"] == estimate_tokens(response)
    assert usage_data["tokens_consumed"]["total_tokens"] == estimate_tokens(prompt) + estimate_tokens(response)
    assert usage_data["provider_usage"]["openai"] == usage_data["tokens_consumed"]["total_tokens"]
    
    # Verify billing JSON content
    billing_data = json.loads(billing_file.read_text(encoding="utf-8"))
    assert billing_data["user_id"] == TEST_USER_ID
    assert billing_data["estimated_cost_usd"] > 0.0


def test_track_user_usage_prefixed_user_id():
    """track_user_usage strips 'userlib:' prefix from user_id."""
    prefixed_id = f"userlib:{TEST_USER_ID}"
    track_user_usage(
        user_id=prefixed_id,
        provider="gemini",
        model="gemini-flash-lite",
        prompt="Test prompt",
        response="Test response"
    )
    
    usage_file = STORAGE_USAGE_DIR / f"{TEST_USER_ID}.json"
    billing_file = STORAGE_BILLING_DIR / f"{TEST_USER_ID}.json"
    
    assert usage_file.exists()
    assert billing_file.exists()
    
    usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    assert usage_data["user_id"] == TEST_USER_ID


def test_track_heavy_usage_spikes():
    """track_user_usage logs usage spikes when total tokens exceed 4000."""
    # A prompt/response that creates > 4000 tokens (1 token ~ 4 characters)
    # So length > 16000 characters
    long_prompt = "x" * 15000
    long_response = "y" * 3000
    
    track_user_usage(
        user_id=TEST_USER_ID,
        provider="gemini",
        model="gemini-3.1-flash-lite",
        prompt=long_prompt,
        response=long_response,
        task_type="summary"
    )
    
    usage_file = STORAGE_USAGE_DIR / f"{TEST_USER_ID}.json"
    usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    
    assert len(usage_data["heavy_usage_spikes"]) == 1
    spike = usage_data["heavy_usage_spikes"][0]
    assert spike["tokens"] == estimate_tokens(long_prompt) + estimate_tokens(long_response)
    assert spike["model"] == "gemini-3.1-flash-lite"
    assert spike["task_type"] == "summary"


def test_track_quota_exhaustion():
    """track_quota_exhaustion updates the usage JSON with quota exhaustion events."""
    track_quota_exhaustion(TEST_USER_ID, "rag")
    track_quota_exhaustion(TEST_USER_ID, "rag")
    track_quota_exhaustion(TEST_USER_ID, "quiz")
    
    usage_file = STORAGE_USAGE_DIR / f"{TEST_USER_ID}.json"
    assert usage_file.exists()
    
    usage_data = json.loads(usage_file.read_text(encoding="utf-8"))
    assert usage_data["user_id"] == TEST_USER_ID
    assert usage_data["quota_exhaustions"]["rag"] == 2
    assert usage_data["quota_exhaustions"]["quiz"] == 1
