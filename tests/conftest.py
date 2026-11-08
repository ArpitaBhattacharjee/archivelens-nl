import os
import tempfile

# Settings must be set before the app is imported.
os.environ["GEMINI_API_KEY"] = ""  # tests always use the offline fallbacks
os.environ.setdefault("ADMIN_PASSWORD", "test-pass")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="archivelens-uploads-")
os.environ["WATCH_DIR"] = tempfile.mkdtemp(prefix="archivelens-watch-")

import pytest  # noqa: E402


def _database_available() -> bool:
    try:
        from sqlalchemy import text

        from app.db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database():
    if not _database_available():
        pytest.skip("PostgreSQL is not running (start it with: docker compose up -d db)")
    from sqlalchemy import text

    from app.db import engine, init_db

    init_db()
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE documents RESTART IDENTITY CASCADE"))


@pytest.fixture()
def client(database):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.main import app

    with database.begin() as conn:
        conn.execute(text("TRUNCATE documents RESTART IDENTITY CASCADE"))
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_client(client):
    r = client.post("/admin/login", data={"password": os.environ["ADMIN_PASSWORD"]}, follow_redirects=False)
    assert r.status_code == 303
    return client
