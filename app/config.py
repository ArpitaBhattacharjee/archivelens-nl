"""App settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://archive:archive@localhost:5432/archive")
    # Hosts like Supabase/Render give "postgres://" or "postgresql://"; SQLAlchemy needs the driver name.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    def __init__(self) -> None:
        self.database_url = _database_url()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.chat_model = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
        self.embed_model = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
        self.embed_dim = 768
        self.admin_password = os.getenv("ADMIN_PASSWORD", "change-me")
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
        self.watch_dir = Path(os.getenv("WATCH_DIR", "data/watch"))
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        self.watch_interval = int(os.getenv("WATCH_INTERVAL_SECONDS", "5"))


settings = Settings()
