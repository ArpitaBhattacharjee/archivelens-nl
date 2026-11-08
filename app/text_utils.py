"""Small helpers with no outside dependencies (easy to unit test)."""
import hashlib
import re
from pathlib import Path

KIND_BY_EXT = {
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".tif": "image", ".tiff": "image", ".webp": "image",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio", ".flac": "audio",
    ".mp4": "video", ".mov": "video", ".webm": "video",
    ".txt": "text", ".md": "text",
}

MIME_BY_EXT = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".tif": "image/tiff", ".tiff": "image/tiff", ".webp": "image/webp",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".flac": "audio/flac",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".txt": "text/plain", ".md": "text/markdown",
}

# Dublin Core "Type" vocabulary
DC_TYPE = {"pdf": "Text", "text": "Text", "image": "StillImage", "audio": "Sound", "video": "MovingImage"}


def guess_kind(filename: str) -> str | None:
    return KIND_BY_EXT.get(Path(filename).suffix.lower())


def guess_mime(filename: str) -> str:
    return MIME_BY_EXT.get(Path(filename).suffix.lower(), "application/octet-stream")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str) -> str:
    name = Path(name).name or "file"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[-100:]


def clean_text(text: str) -> str:
    """Tidy OCR output: join words split across lines, drop odd characters, collapse spaces."""
    if not text:
        return ""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Split text into overlapping pieces (~size characters), cutting at spaces."""
    text = clean_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            cut = text.rfind(" ", start + size // 2, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def make_snippet(text: str | None, query: str | None = None, length: int = 220) -> str:
    """Short preview of text, centred on the first query word found."""
    if not text:
        return ""
    pos = 0
    if query:
        lower = text.lower()
        for word in re.findall(r"\w{3,}", query.lower()):
            found = lower.find(word)
            if found != -1:
                pos = max(found - length // 3, 0)
                break
    snippet = text[pos:pos + length].strip()
    return ("…" if pos > 0 else "") + snippet + ("…" if pos + length < len(text) else "")


def split_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(";") if v.strip()]
