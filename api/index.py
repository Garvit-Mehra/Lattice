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

from backend.student_app import app  # noqa: F401 — re-exported for Vercel

__all__ = ["app"]
