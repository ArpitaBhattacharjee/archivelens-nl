import math

import pytest

from app import ai
from app.search import rrf


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_fallback_embedding_is_normalized_and_sized():
    v = ai.fallback_embedding("cod fishery in Bonavista", 768)
    assert len(v) == 768
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)


def test_fallback_embedding_empty_text_is_safe():
    v = ai.fallback_embedding("", 16)
    assert math.isclose(sum(x * x for x in v), 1.0)


def test_similar_texts_are_closer():
    a = ai.fallback_embedding("seal hunt disaster sealers lost on the ice")
    b = ai.fallback_embedding("sealers lost on the ice in the seal hunt")
    c = ai.fallback_embedding("railway timetable for the Avalon peninsula")
    assert _cos(a, b) > _cos(a, c)


def test_parse_metadata_json_cleans_output():
    raw = '```json\n{"title": "Letter", "date": "around 1890", "subject": "fishery, trade", "people": ["A", ""]}\n```'
    meta = ai.parse_metadata_json(raw)
    assert meta["title"] == "Letter"
    assert meta["date"] == ""                     # invalid dates are dropped, never guessed
    assert meta["subject"] == ["fishery", "trade"]
    assert meta["people"] == ["A"]


def test_parse_metadata_json_rejects_garbage():
    with pytest.raises(ValueError):
        ai.parse_metadata_json("not json")


def test_fallback_metadata_finds_title_and_year():
    meta = ai.fallback_metadata("THE EVENING TELEGRAM\nSt. John's, March 4, 1914", "scan.png")
    assert meta["title"] == "THE EVENING TELEGRAM"
    assert meta["date"] == "1914"


def test_answer_without_passages():
    assert "couldn't find" in ai.answer("anything?", [])


def test_rrf_combines_rankings():
    assert rrf([1, 2, 3], [3, 1, 4])[0] == 1
