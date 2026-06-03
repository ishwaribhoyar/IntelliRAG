"""Ollama provider — stub. Set LLM_PROVIDER=ollama + OLLAMA_BASE_URL."""
from app.modules.llm_router.base import LLMProvider
from typing import Any

class OllamaProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "ollama"

    async def generate(self, doc_id, task_type, prompt, context, stream=False,
                       use_cache=True, temperature=None, max_tokens=None, llm_variant=None) -> dict[str, Any]:
        """TODO: Implement Ollama local API. Env: OLLAMA_BASE_URL, OLLAMA_MODEL."""
        raise NotImplementedError("Ollama provider not yet implemented.")
