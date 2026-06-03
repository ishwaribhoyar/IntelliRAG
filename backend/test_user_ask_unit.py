"""Unit tests for user-library Ask (no server)."""
import pytest

from app.rag import user_ask as ua


def test_cache_key_stable():
    a = ua._cache_key("user_1", "hello world")
    b = ua._cache_key("user_1", "hello world")
    c = ua._cache_key("user_2", "hello world")
    assert a == b
    assert a != c


def test_parse_llm_json():
    raw = '{"answer": "ok", "sources": [{"chunk_id": "c1", "page": 1, "section": "S"}], "confidence": "high"}'
    parsed = ua._parse_llm_json(raw)
    assert parsed["answer"] == "ok"
    assert parsed["confidence"] == "high"


def test_not_found_constant():
    assert "not found" in ua.NOT_FOUND.lower()


def test_keyword_boost_prefers_exact_term():
    keys = ua._keywords("what is python")
    py_chunk = {"section": "Python Basics", "text": "Python is a programming language.", "rrf_score": 0.02}
    ai_chunk = {"section": "AI Intro", "text": "Artificial intelligence overview.", "rrf_score": 0.02}
    assert ua._keyword_boost(py_chunk, keys) > ua._keyword_boost(ai_chunk, keys)


def test_relevance_score_definition_topic_alignment():
    keys = ua._keywords("what is supervised learning")
    ml_chunk = {"section": "Supervised Learning", "text": "Supervised learning uses labeled data.", "rrf_score": 0.03}
    unrelated = {"section": "AI History", "text": "AI history started decades ago.", "rrf_score": 0.03}
    assert ua._relevance_score(ml_chunk, keys) > ua._relevance_score(unrelated, keys)


def test_query_validation_blocks_garbage():
    assert ua.is_valid_query("what is python")
    assert not ua.is_valid_query("s")
    assert not ua.is_valid_query("  ")


def test_phrase_match_beats_partial_match():
    keys = ua._keywords("what is machine learning")
    ml_chunk = {"section": "Machine Learning", "text": "Machine learning is a subset of AI.", "rrf_score": 0.02}
    machine_code_chunk = {"section": "Python Execution", "text": "Python compiles to bytecode before machine code execution.", "rrf_score": 0.02}
    assert ua._relevance_score(ml_chunk, keys) > ua._relevance_score(machine_code_chunk, keys)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
