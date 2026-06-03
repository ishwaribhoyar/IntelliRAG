"""Shared schemas — Content Library."""
from pydantic import BaseModel


class LibraryAddRequest(BaseModel):
    doc_id: str
    subject: str
    title: str = ""


class LibraryRemoveRequest(BaseModel):
    doc_id: str
    subject: str = ""
