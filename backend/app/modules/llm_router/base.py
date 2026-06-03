"""LLM Router — abstract provider protocol.

All LLM providers must implement this interface.
Features use LLMRouter.generate() instead of provider-specific calls.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for all LLM provider implementations."""

    @abstractmethod
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
        """Generate a response from the LLM.

        Returns:
            {
                "answer": str,
                "source_chunks": list,
                "cached": bool,
                "llm_model": str,
            }
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name string (e.g. 'sarvam', 'openai')."""
        ...
