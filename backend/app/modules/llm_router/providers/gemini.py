"""Gemini LLM provider implementation.

Set LLM_PROVIDER=gemini and GEMINI_API_KEY in .env to activate.
"""
from __future__ import annotations

import os
import httpx
import logging
from typing import Any

from app.modules.llm_router.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider — production-ready implementation."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate(
        self,
        doc_id: str,
        task_type: str,
        prompt: str,
        context: str,
        stream: bool = False,
        use_cache: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        llm_variant: str | None = None,
    ) -> dict[str, Any]:
        """Call Gemini REST API with caching and error handling."""
        api_key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        if llm_variant == "gemini-flash-lite":
            model = os.getenv("GEMINI_MODEL_FLASH_LITE", "gemini-2.5-flash-lite")
        elif llm_variant == "gemini-3.1-flash-lite":
            model = os.getenv("GEMINI_MODEL_3_1_FLASH_LITE", "gemini-3.1-flash-lite")

        api_url = os.getenv(
            "GEMINI_API_URL",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

        if not api_key or api_key == "dummy":
            from app.rag.llm_client import _mock_llm_response
            mock_ans = _mock_llm_response(task_type, prompt, context)
            return {
                "answer": mock_ans,
                "source_chunks": [],
                "cached": False,
                "llm_model": "mock-gemini",
            }

        # Check cache first
        from app.state import llm_cache
        from app.rag.llm_client import _cache_key
        key = _cache_key(doc_id, task_type, context, model)
        if use_cache and key in llm_cache:
            logger.info(f"Gemini cache hit for {doc_id}/{task_type}")
            cached = llm_cache[key].copy()
            cached["cached"] = True
            return cached

        # Enforce rate limit/gap
        from app.rag.llm_client import _rate_limit
        await _rate_limit(doc_id)

        # Determine max tokens
        from app.rag.llm_client import _max_tokens_for_task
        mtok = _max_tokens_for_task(task_type) if max_tokens is None else max_tokens

        url_with_key = f"{api_url}?key={api_key}"
        headers = {"Content-Type": "application/json"}

        payload = {
            "systemInstruction": {
                "parts": [{"text": prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": context}]
                }
            ],
            "generationConfig": {
                "temperature": temperature if temperature is not None else 0.2,
                "maxOutputTokens": mtok,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url_with_key,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Extract generated text from Gemini structure
                answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                result = {
                    "answer": answer,
                    "source_chunks": [],
                    "cached": False,
                    "llm_model": model,
                }

                if use_cache:
                    llm_cache[key] = {"answer": answer, "source_chunks": [], "llm_model": model}

                return result

        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            return {
                "answer": f"Gemini call failed: {e}",
                "source_chunks": [],
                "cached": False,
                "llm_model": model,
            }
