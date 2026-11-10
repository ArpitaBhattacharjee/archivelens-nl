"""All AI calls (Google Gemini) live here.

If GEMINI_API_KEY is not set, the app still works with simple offline
fallbacks, so tests and local demos never need a key.
"""
import hashlib
import json
import logging
import math
import re

from .config import settings

_client = None
log = logging.getLogger("archivelens.ai")


def enabled() -> bool:
    return bool(settings.gemini_api_key)


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        # 90-second timeout so a slow or busy model can't leave an item stuck
        _client = genai.Client(api_key=settings.gemini_api_key,
                               http_options=types.HttpOptions(timeout=90_000))
    return _client


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec = [0.0] * len(vec)
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


def _with_retry(call, attempts: int = 4):
    """Retry when Gemini is busy (503) or rate-limited (429), waiting longer each time."""
    import time

    for i in range(attempts):
        try:
            return call()
        except Exception as exc:
            busy = any(code in str(exc) for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
            if not busy or i == attempts - 1:
                raise
            wait = 5 * (2 ** i)
            log.warning("Gemini busy, retrying in %s seconds: %s", wait, exc)
            time.sleep(wait)


# ---------- Embeddings ----------

def fallback_embedding(text: str, dim: int | None = None) -> list[float]:
    """Offline stand-in: hashes words into a vector (keyword-like, not truly semantic)."""
    dim = dim or settings.embed_dim
    vec = [0.0] * dim
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < 3:
            continue
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    return _normalize(vec)


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Turn texts into vectors. task is RETRIEVAL_DOCUMENT (storing) or RETRIEVAL_QUERY (searching)."""
    if not texts:
        return []
    if not enabled():
        return [fallback_embedding(t) for t in texts]

    from google.genai import types

    vectors: list[list[float]] = []
    for i in range(0, len(texts), 50):
        result = _with_retry(lambda: _get_client().models.embed_content(
            model=settings.embed_model,
            contents=texts[i:i + 50],
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=settings.embed_dim),
        ))
        # Reduced-size Gemini embeddings must be normalized before cosine search.
        vectors.extend(_normalize(list(e.values)) for e in result.embeddings)
    return vectors


# ---------- Metadata ----------

METADATA_PROMPT = """You are an archivist cataloguing a historical item from Newfoundland and Labrador.
Read the text below (from OCR or a transcript) and return ONLY a JSON object with these keys:
- "title": short descriptive title (max 12 words)
- "creator": author, photographer or organization, or "" if unknown
- "date": "YYYY", "YYYY-MM" or "YYYY-MM-DD" if stated in the text, else ""
- "subject": list of 3-6 short topic tags
- "description": 1-2 plain sentences about the item
- "people": list of people's names mentioned
- "places": list of places mentioned
- "language": ISO 639-1 code such as "en" or "fr"
Use only information found in the text. Never invent dates or names.

File name: {filename}

Text:
{text}
"""

_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[;,]", value)
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def parse_metadata_json(raw: str) -> dict:
    """Parse the model's reply safely and normalize every field."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Metadata is not a JSON object")
    date = str(data.get("date") or "").strip()
    return {
        "title": str(data.get("title") or "").strip()[:300],
        "creator": str(data.get("creator") or "").strip()[:300],
        "date": date if _DATE_RE.match(date) else "",
        "subject": _as_list(data.get("subject"))[:8],
        "description": str(data.get("description") or "").strip(),
        "people": _as_list(data.get("people"))[:20],
        "places": _as_list(data.get("places"))[:20],
        "language": str(data.get("language") or "").strip()[:20],
    }


def fallback_metadata(text: str, filename: str) -> dict:
    first_line = next((l.strip() for l in text.splitlines() if len(l.strip()) > 3), "")
    title = first_line[:80] if first_line else filename.rsplit(".", 1)[0].replace("_", " ")
    year = re.search(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", text)
    return {
        "title": title, "creator": "", "date": year.group(1) if year else "",
        "subject": [], "description": "", "people": [], "places": [], "language": "en",
    }


def extract_metadata(text: str, filename: str) -> dict:
    if not enabled() or not text.strip():
        return fallback_metadata(text, filename)
    from google.genai import types

    try:
        response = _with_retry(lambda: _get_client().models.generate_content(
            model=settings.chat_model,
            contents=METADATA_PROMPT.format(filename=filename, text=text[:12000]),
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        ))
        return parse_metadata_json(response.text)
    except Exception as exc:
        log.warning("Gemini metadata failed, using fallback: %s", exc)
        return fallback_metadata(text, filename)


# ---------- Transcription ----------

def transcribe(data: bytes, mime: str) -> str:
    """Audio/video to text with Gemini (files up to ~20 MB sent inline)."""
    if not enabled():
        raise RuntimeError("Audio/video transcription needs GEMINI_API_KEY")
    from google.genai import types

    response = _with_retry(lambda: _get_client().models.generate_content(
        model=settings.chat_model,
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime),
            "Transcribe this recording word for word. Return plain text only.",
        ],
    ))
    return response.text or ""


# ---------- Ask the Archive (RAG) ----------

ANSWER_PROMPT = """You answer questions about a digital archive of Newfoundland and Labrador history.
Use ONLY the numbered sources below. Cite sources inline like [1] or [2].
If the sources do not contain the answer, say you could not find it in the archive.
Keep the answer under 150 words. Write plain text with no Markdown (no ** or #); use "- " for lists.

Sources:
{sources}

Question: {question}
"""


def answer(question: str, passages: list[dict]) -> str:
    if not passages:
        return "I couldn't find anything about that in the archive yet."
    if not enabled():
        return "AI answers are off (no GEMINI_API_KEY set). Here are the most relevant passages from the archive."
    sources = "\n\n".join(f"[{p['n']}] {p['title']}: {p['text']}" for p in passages)
    response = _with_retry(lambda: _get_client().models.generate_content(
        model=settings.chat_model,
        contents=ANSWER_PROMPT.format(sources=sources, question=question),
    ))
    # Plain text for the web page: drop Markdown bold/italic markers
    return re.sub(r"\*\*|__", "", (response.text or "")).strip()
