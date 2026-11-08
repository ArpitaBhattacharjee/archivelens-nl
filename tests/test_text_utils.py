from app.text_utils import (chunk_text, clean_text, guess_kind, make_snippet, safe_filename,
                            sha256_bytes, split_list)


def test_clean_text_joins_hyphenated_words_and_spaces():
    assert clean_text("New-\nfoundland   fishery\n\n1892") == "Newfoundland fishery 1892"


def test_chunk_text_empty():
    assert chunk_text("   ") == []


def test_chunk_text_sizes_and_overlap():
    text = " ".join(f"word{i}" for i in range(600))
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)
    # neighbouring chunks share some words (overlap keeps context)
    assert set(chunks[0].split()[-3:]) & set(chunks[1].split())


def test_guess_kind():
    assert guess_kind("letter.PDF") == "pdf"
    assert guess_kind("photo.jpeg") == "image"
    assert guess_kind("interview.mp3") == "audio"
    assert guess_kind("virus.exe") is None


def test_sha256_is_stable():
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc") != sha256_bytes(b"abd")


def test_safe_filename():
    assert safe_filename("../../my letter (1).pdf") == "my_letter__1_.pdf"


def test_snippet_centres_on_query():
    text = "x " * 300 + "the Bonavista cod catch" + " y" * 300
    assert "Bonavista" in make_snippet(text, "bonavista", 80)


def test_split_list():
    assert split_list("fishery; ; St. John's ") == ["fishery", "St. John's"]
