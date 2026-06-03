"""Rapid Fire game — timed quick questions."""
from app.generators.content import generate_content


async def generate_rapid_fire(doc_id: str) -> dict:
    return await generate_content(doc_id, "rapid_fire")
