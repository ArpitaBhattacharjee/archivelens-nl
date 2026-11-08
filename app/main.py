"""FastAPI app: web pages (HTMX) + JSON API."""
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, HTTPException,
                     Request, UploadFile)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import ai
from .config import settings
from .db import get_db, init_db
from .models import Document
from .pipeline import process_document, register_file
from .search import ask, search
from .text_utils import make_snippet, split_list

BASE_DIR = Path(__file__).resolve().parent
DC_TYPES = ["Text", "StillImage", "Sound", "MovingImage"]
EDITABLE = ["title", "creator", "date", "subject", "description", "coverage", "people", "source", "rights", "language"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="ArchiveLens NL", description="AI-ready digital archive for Newfoundland and Labrador history",
              lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(snippet=make_snippet, split_list=split_list, ai_enabled=ai.enabled)


# ---------- Auth ----------

def is_admin(request: Request) -> bool:
    if request.session.get("admin") is True:
        return True
    token = request.headers.get("X-Admin-Token", "")
    return bool(token) and secrets.compare_digest(token, settings.admin_password)


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


def render(request: Request, name: str, status_code: int = 200, **context):
    context.setdefault("is_admin", is_admin(request))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def filters_from(doc_type: str = "", subject: str = "", year_from: str = "", year_to: str = "") -> dict:
    return {"doc_type": doc_type or None, "subject": subject.strip() or None,
            "year_from": year_from.strip() or None, "year_to": year_to.strip() or None}


# ---------- Public pages ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = "", doc_type: str = "", subject: str = "", year_from: str = "",
         year_to: str = "", db: Session = Depends(get_db)):
    results = search(db, q, **filters_from(doc_type, subject, year_from, year_to))
    total = db.query(Document).filter(Document.status == "done").count()
    return render(request, "index.html", results=results, q=q, doc_type=doc_type, subject=subject,
                  year_from=year_from, year_to=year_to, types=DC_TYPES, total=total)


@app.get("/search", response_class=HTMLResponse)
def search_partial(request: Request, q: str = "", doc_type: str = "", subject: str = "", year_from: str = "",
                   year_to: str = "", db: Session = Depends(get_db)):
    results = search(db, q, **filters_from(doc_type, subject, year_from, year_to))
    return render(request, "_results.html", results=results, q=q)


@app.get("/item/{doc_id}", response_class=HTMLResponse)
def item(request: Request, doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None or (doc.status != "done" and not is_admin(request)):
        raise HTTPException(404, "Item not found")
    return render(request, "item.html", doc=doc, fields=EDITABLE)


@app.get("/files/{doc_id}")
def original_file(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None or not Path(doc.file_path).exists():
        raise HTTPException(404, "Original file not available")
    return FileResponse(doc.file_path, media_type=doc.format, filename=doc.file_name)


@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    return render(request, "ask.html")


@app.post("/ask", response_class=HTMLResponse)
def ask_partial(request: Request, question: str = Form(...), db: Session = Depends(get_db)):
    return render(request, "_answer.html", result=ask(db, question.strip()[:500]))


# ---------- Admin ----------

@app.get("/admin/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", error=None)


@app.post("/admin/login", response_class=HTMLResponse)
def login(request: Request, password: str = Form(...)):
    if secrets.compare_digest(password, settings.admin_password):
        request.session["admin"] = True
        return RedirectResponse("/admin", status_code=303)
    return render(request, "login.html", status_code=401, error="Wrong password")


@app.post("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    require_admin(request)
    messages = request.session.pop("flash", [])
    return render(request, "admin.html", messages=messages)


@app.get("/admin/status", response_class=HTMLResponse)
def admin_status(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    docs = db.scalars(select(Document).order_by(Document.id.desc()).limit(100)).all()
    return render(request, "_status.html", docs=docs)


@app.post("/admin/upload")
async def upload(request: Request, background: BackgroundTasks, files: list[UploadFile] = File(...),
                 source: str = Form(""), rights: str = Form(""), db: Session = Depends(get_db)):
    require_admin(request)
    messages = []
    for f in files:
        name = f.filename or "file"
        try:
            doc, created = register_file(db, name, await f.read(), source=source.strip(), rights=rights.strip())
        except ValueError as exc:
            messages.append(f"{name}: skipped ({exc})")
            continue
        if created:
            background.add_task(process_document, doc.id)
            messages.append(f"{name}: queued for processing")
        else:
            messages.append(f"{name}: already in the archive (item #{doc.id})")
    request.session["flash"] = messages
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/item/{doc_id}")
def edit_item(request: Request, doc_id: int, db: Session = Depends(get_db),
              title: str = Form(""), creator: str = Form(""), date: str = Form(""), subject: str = Form(""),
              description: str = Form(""), coverage: str = Form(""), people: str = Form(""),
              source: str = Form(""), rights: str = Form(""), language: str = Form("")):
    """Human-in-the-loop: an archivist reviews and corrects AI-generated metadata."""
    require_admin(request)
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Item not found")
    values = dict(title=title, creator=creator, date=date, subject=subject, description=description,
                  coverage=coverage, people=people, source=source, rights=rights, language=language)
    for field, value in values.items():
        setattr(doc, field, value.strip() or None)
    db.commit()
    return RedirectResponse(f"/item/{doc_id}", status_code=303)


@app.post("/admin/item/{doc_id}/reprocess")
def reprocess(request: Request, doc_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    require_admin(request)
    if db.get(Document, doc_id) is None:
        raise HTTPException(404, "Item not found")
    background.add_task(process_document, doc_id)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/item/{doc_id}/delete")
def delete_item(request: Request, doc_id: int, db: Session = Depends(get_db)):
    require_admin(request)
    doc = db.get(Document, doc_id)
    if doc is not None:
        Path(doc.file_path).unlink(missing_ok=True)
        db.delete(doc)
        db.commit()
    return RedirectResponse("/admin", status_code=303)


# ---------- JSON API ----------

class AskIn(BaseModel):
    question: str


def doc_json(doc: Document, full: bool = False) -> dict:
    data = {
        "id": doc.id, "title": doc.title, "creator": doc.creator, "date": doc.date,
        "subject": split_list(doc.subject), "description": doc.description, "type": doc.type,
        "format": doc.format, "source": doc.source, "language": doc.language,
        "coverage": split_list(doc.coverage), "people": split_list(doc.people), "rights": doc.rights,
        "status": doc.status, "error": doc.error, "file_name": doc.file_name,
    }
    if full:
        data["full_text"] = doc.full_text
    return data


@app.get("/health")
def health():
    return {"status": "ok", "ai_enabled": ai.enabled()}


@app.get("/api/documents")
def api_documents(status: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    stmt = select(Document).order_by(Document.id.desc()).limit(min(limit, 200))
    if status:
        stmt = stmt.where(Document.status == status)
    return [doc_json(d) for d in db.scalars(stmt)]


@app.get("/api/documents/{doc_id}")
def api_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Item not found")
    return doc_json(doc, full=True)


@app.get("/api/search")
def api_search(q: str = "", doc_type: str = "", subject: str = "", year_from: str = "", year_to: str = "",
               db: Session = Depends(get_db)):
    results = search(db, q, **filters_from(doc_type, subject, year_from, year_to))
    return {"query": q, "count": len(results), "results": [doc_json(d) for d in results]}


@app.post("/api/ask")
def api_ask(body: AskIn, db: Session = Depends(get_db)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")
    return ask(db, question[:500])
