"""The ingestion pipeline: file -> text -> metadata -> chunks -> embeddings -> database.

Every upload (web form, API or watch folder) goes through the same steps,
so the process is repeatable. Status moves pending -> processing -> done/failed.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from . import ai, ocr
from .config import settings
from .db import SessionLocal
from .models import Chunk, Document
from .text_utils import (DC_TYPE, chunk_text, clean_text, guess_kind, guess_mime,
                         safe_filename, sha256_bytes)


def register_file(db: Session, filename: str, data: bytes, source: str | None = None,
                  rights: str | None = None) -> tuple[Document, bool]:
    """Save a new file and create its row. Returns (document, created). Skips exact duplicates."""
    kind = guess_kind(filename)
    if kind is None:
        raise ValueError("unsupported file type")
    if not data:
        raise ValueError("file is empty")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"file is larger than {settings.max_upload_mb} MB")

    digest = sha256_bytes(data)
    existing = db.query(Document).filter_by(sha256=digest).first()
    if existing:
        return existing, False

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{digest[:12]}_{safe_filename(filename)}"
    path.write_bytes(data)

    doc = Document(
        file_name=Path(filename).name, file_path=str(path), sha256=digest,
        type=DC_TYPE[kind], format=guess_mime(filename),
        source=source or None, rights=rights or None, status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc, True


def extract_text(path: Path, filename: str, mime: str | None) -> str:
    kind = guess_kind(filename)
    data = path.read_bytes()
    if kind == "pdf":
        return ocr.pdf_text(data)
    if kind == "image":
        return ocr.ocr_image_bytes(data)
    if kind in ("audio", "video"):
        return ai.transcribe(data, mime or guess_mime(filename))
    if kind == "text":
        return data.decode("utf-8", errors="ignore")
    raise ValueError("unsupported file type")


def apply_metadata(doc: Document, meta: dict) -> None:
    """Fill only empty fields, so an archivist's manual edits are never overwritten."""
    values = {
        "title": meta.get("title"),
        "creator": meta.get("creator"),
        "date": meta.get("date"),
        "subject": "; ".join(meta.get("subject") or []),
        "description": meta.get("description"),
        "people": "; ".join(meta.get("people") or []),
        "coverage": "; ".join(meta.get("places") or []),
        "language": meta.get("language"),
    }
    for field, value in values.items():
        if value and not getattr(doc, field):
            setattr(doc, field, value)
    if not doc.title:
        doc.title = doc.file_name


def process_document(doc_id: int) -> None:
    """Run the full pipeline for one document. Safe to re-run (reprocess)."""
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.status, doc.error = "processing", None
        db.commit()

        text = clean_text(extract_text(Path(doc.file_path), doc.file_name, doc.format))
        if not text:
            raise ValueError("no text could be extracted")

        apply_metadata(doc, ai.extract_metadata(text, doc.file_name))
        doc.full_text = text

        pieces = chunk_text(text)
        vectors = ai.embed([f"{doc.title}\n{p}" for p in pieces])
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.add_all(
            Chunk(document_id=doc.id, position=i, text=p, embedding=v)
            for i, (p, v) in enumerate(zip(pieces, vectors))
        )
        doc.status = "done"
        db.commit()
    except Exception as exc:  # record the error so it shows on the admin page
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status, doc.error = "failed", str(exc)[:500]
            db.commit()
    finally:
        db.close()
