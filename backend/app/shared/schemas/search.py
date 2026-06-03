"""Shared schemas — Search."""
from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    doc_id: str
    query: str
    mode: str = "auto"  # keyword | hybrid | ai | auto
    user_id: str = "default_user"
    llm_variant: Optional[str] = "30b"


class UserSearchRequest(BaseModel):
    user_id: str
    query: str
    mode: str = "hybrid"
    limit: int = 20
