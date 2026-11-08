"""Search: hybrid keyword + semantic, combined with Reciprocal Rank Fusion (RRF)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai
from .models import Chunk, Document


def _apply_filters(stmt, doc_type=None, subject=None, year_from=None, year_to=None):
    stmt = stmt.where(Document.status == "done")
    if doc_type:
        stmt = stmt.where(Document.type == doc_type)
    if subject:
        stmt = stmt.where(Document.subject.ilike(f"%{subject}%"))
    year = func.substr(Document.date, 1, 4)
    if year_from:
        stmt = stmt.where(year >= str(year_from))
    if year_to:
        stmt = stmt.where(year <= str(year_to))
    return stmt


def keyword_ids(db: Session, q: str, limit: int, **filters) -> list[int]:
    """PostgreSQL full-text search over title, tags and text."""
    doc_text = func.concat_ws(" ", Document.title, Document.subject, Document.description, Document.full_text)
    tsv = func.to_tsvector("english", doc_text)
    tsq = func.websearch_to_tsquery("english", q)
    stmt = select(Document.id).where(tsv.op("@@")(tsq)).order_by(func.ts_rank(tsv, tsq).desc()).limit(limit)
    return list(db.scalars(_apply_filters(stmt, **filters)))


def vector_ids(db: Session, q: str, limit: int, **filters) -> list[int]:
    """Semantic search: closest chunk embeddings by cosine distance (pgvector)."""
    qvec = ai.embed([q], task="RETRIEVAL_QUERY")[0]
    distance = func.min(Chunk.embedding.cosine_distance(qvec)).label("distance")
    stmt = (select(Chunk.document_id, distance)
            .join(Document, Document.id == Chunk.document_id)
            .group_by(Chunk.document_id).order_by(distance).limit(limit))
    return [row[0] for row in db.execute(_apply_filters(stmt, **filters))]


def rrf(*ranked_lists: list[int], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion: items ranked high in either list rise to the top."""
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


def search(db: Session, q: str = "", limit: int = 20, **filters) -> list[Document]:
    q = (q or "").strip()
    if not q:  # browse mode
        stmt = _apply_filters(select(Document), **filters).order_by(Document.date.asc().nulls_last(), Document.id)
        return list(db.scalars(stmt.limit(50)))
    ids = rrf(keyword_ids(db, q, limit, **filters), vector_ids(db, q, limit, **filters))[:limit]
    if not ids:
        return []
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_(ids)))}
    return [docs[i] for i in ids if i in docs]


def retrieve_passages(db: Session, question: str, k: int = 6) -> list[dict]:
    """Top-k chunks for the chatbot, numbered so the answer can cite them."""
    qvec = ai.embed([question], task="RETRIEVAL_QUERY")[0]
    stmt = (select(Chunk, Document.title)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == "done")
            .order_by(Chunk.embedding.cosine_distance(qvec)).limit(k))
    return [
        {"n": i + 1, "document_id": chunk.document_id, "title": title or "Untitled", "text": chunk.text}
        for i, (chunk, title) in enumerate(db.execute(stmt))
    ]


def ask(db: Session, question: str) -> dict:
    passages = retrieve_passages(db, question)
    return {"question": question, "answer": ai.answer(question, passages), "sources": passages}
