"""Database tables.

documents: one row per archive item. Descriptive fields follow Dublin Core
           (see docs/METADATA_STANDARD.md).
chunks:    small pieces of each item's text, each with an embedding vector
           used for semantic search and the "Ask the Archive" chatbot.
"""
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Dublin Core descriptive metadata ---
    title: Mapped[str | None] = mapped_column(String(300))
    creator: Mapped[str | None] = mapped_column(String(300))
    date: Mapped[str | None] = mapped_column(String(20))        # YYYY, YYYY-MM or YYYY-MM-DD
    subject: Mapped[str | None] = mapped_column(Text)            # tags separated by "; "
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(String(30))         # Text, StillImage, Sound, MovingImage
    format: Mapped[str | None] = mapped_column(String(100))      # MIME type
    source: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str | None] = mapped_column(String(20))
    coverage: Mapped[str | None] = mapped_column(Text)           # places, "; " separated
    rights: Mapped[str | None] = mapped_column(String(300))
    people: Mapped[str | None] = mapped_column(Text)             # local extension, "; " separated

    # --- File and processing info ---
    file_name: Mapped[str] = mapped_column(String(300))
    file_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # duplicate check
    status: Mapped[str] = mapped_column(String(20), default="pending")      # pending/processing/done/failed
    error: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(settings.embed_dim))

    document: Mapped[Document] = relationship(back_populates="chunks")
