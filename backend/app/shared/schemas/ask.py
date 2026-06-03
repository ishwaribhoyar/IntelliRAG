"""Shared schemas — Ask AI / Mentor."""
from pydantic import BaseModel, Field
from typing import Optional


class AskRequest(BaseModel):
    """AI Ask over the user's entire PDF library (retrieval-first RAG)."""
    user_id: str = "default_user"
    query: str = ""
    question: str = ""  # alias for query (backward compatible)
    doc_id: Optional[str] = None  # optional: restrict search to one doc
    stream: bool = False
    llm_variant: Optional[str] = "30b"  # default 30b, switchable to 105b


class MentorRequest(BaseModel):
    doc_id: str
    question: str
    user_id: str = "default_user"
    history: list = Field(default_factory=list)
    llm_variant: Optional[str] = "30b"
