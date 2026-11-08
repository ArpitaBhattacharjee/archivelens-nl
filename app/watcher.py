"""Watch folder: drop files into WATCH_DIR and they are ingested automatically.

This copies the idea behind IBM Content Aware Storage: storage that notices
new content and prepares it for AI search without anyone pressing a button.

Run:  python -m app.watcher          (keeps watching)
      python -m app.watcher --once   (process what's there, then stop)
"""
import argparse
import logging
import shutil
import time

from .config import settings
from .db import SessionLocal, init_db
from .pipeline import process_document, register_file
from .text_utils import guess_kind

log = logging.getLogger("watcher")


def scan_once() -> int:
    settings.watch_dir.mkdir(parents=True, exist_ok=True)
    done_dir = settings.watch_dir / "processed"
    done_dir.mkdir(exist_ok=True)
    count = 0
    for path in sorted(settings.watch_dir.iterdir()):
        if not path.is_file() or path.name.startswith(".") or guess_kind(path.name) is None:
            continue
        db = SessionLocal()
        try:
            doc, created = register_file(db, path.name, path.read_bytes(), source="Watch folder")
        except ValueError as exc:
            log.warning("Skipped %s: %s", path.name, exc)
            continue
        finally:
            db.close()
        if created:
            log.info("Ingesting %s (item #%s)", path.name, doc.id)
            process_document(doc.id)
            count += 1
        else:
            log.info("Duplicate %s (already item #%s)", path.name, doc.id)
        shutil.move(str(path), done_dir / path.name)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="ArchiveLens watch folder")
    parser.add_argument("--once", action="store_true", help="scan one time and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    log.info("Watching %s", settings.watch_dir.resolve())
    while True:
        scan_once()
        if args.once:
            break
        time.sleep(settings.watch_interval)


if __name__ == "__main__":
    main()
