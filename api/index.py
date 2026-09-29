"""
Vercel serverless entrypoint for LATTICE · IITH Operations Console.

Vercel's FastAPI adapter expects a module-level `app` object at `api/index.py`.
We re-export the unified student_app (which sub-mounts /tech and /admin internally).

NOTE: SQLite is written to `/tmp` in Vercel's ephemeral filesystem — state is
not persisted across invocations. For a production deployment, migrate to an
external database (e.g. PostgreSQL via Neon or Supabase) and set DATABASE_URL.
"""
import sys
import os

# Make the repo root importable so `from backend.xxx import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set VERCEL flag so backend/database.py routes SQLite to writable /tmp
os.environ.setdefault("VERCEL", "1")

# On Vercel cold-start, seed the ephemeral /tmp/kandifix.db if empty
try:
    from backend import database, models, seed_data
    from backend.models import Hostel
    database.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    has_hostels = db.query(Hostel).count() > 0
    db.close()
    if not has_hostels:
        print("[Vercel] Auto-seeding initial dataset into /tmp/kandifix.db...")
        seed_data.seed_database()
except Exception as e:
    print(f"[Vercel] Seed check exception: {e}")

from backend.student_app import app  # noqa: F401 — re-exported for Vercel

__all__ = ["app"]
