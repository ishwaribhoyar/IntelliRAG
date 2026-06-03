"""Shared schemas — Auth."""
from pydantic import BaseModel
from typing import Optional


class AuthRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    email: Optional[str] = None
