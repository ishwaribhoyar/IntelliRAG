"""OpenAI LLM provider implementation.

Set LLM_PROVIDER=openai and OPENAI_API_KEY in .env to activate.
"""
from __future__ import annotations

import os
import httpx
import logging
from typing import Any

from app.modules.llm_router.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider — production-ready implementation."""

    @property
    def provider_name(self) -> str:
        return "openai"

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
        """Call OpenAI chat completions API with caching and error handling."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if llm_variant == "gpt-5-nano":
            model = os.getenv("OPENAI_MODEL_5_NANO", "gpt-5-nano")

        if not api_key or api_key == "dummy":
            from app.rag.llm_client import _mock_llm_response
            mock_ans = _mock_llm_response(task_type, prompt, context)
            return {
                "answer": mock_ans,
                "source_chunks": [],
                "cached": False,
                "llm_model": "mock-openai",
            }

        # Check cache first
        from app.state import llm_cache
        from app.rag.llm_client import _cache_key
        key = _cache_key(doc_id, task_type, context, model)
        if use_cache and key in llm_cache:
            logger.info(f"OpenAI cache hit for {doc_id}/{task_type}")
            cached = llm_cache[key].copy()
            cached["cached"] = True
            return cached

        # Enforce rate limit/gap if needed (optional but good practice)
        from app.rag.llm_client import _rate_limit
        await _rate_limit(doc_id)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Determine max tokens
        from app.rag.llm_client import _max_tokens_for_task
        mtok = _max_tokens_for_task(task_type) if max_tokens is None else max_tokens

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
            "temperature": temperature if temperature is not None else 0.2,
            "max_tokens": mtok,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    api_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                answer = data["choices"][0]["message"]["content"].strip()

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
            logger.error(f"OpenAI call failed: {e}")
            return {
                "answer": f"OpenAI call failed: {e}",
                "source_chunks": [],
                "cached": False,
                "llm_model": model,
            }
