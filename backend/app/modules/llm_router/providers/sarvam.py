"""Sarvam LLM provider — wraps existing rag/llm_client.py logic.

This is the REAL provider implementation. All other providers are stubs
until their API keys and endpoints are configured.
"""
from __future__ import annotations

from typing import Any

from app.modules.llm_router.base import LLMProvider


class SarvamProvider(LLMProvider):
    """Sarvam-M (105B / 30B) provider — production-ready implementation."""

    @property
    def provider_name(self) -> str:
        return "sarvam"

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
        # Import here to avoid circular imports at module load time.
        from app.rag.llm_client import call_sarvam_direct as _sarvam_call
        return await _sarvam_call(
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
