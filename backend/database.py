"""
Database Engine & Session Management for LATTICE · IITH Operations Console
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Vercel (or AWS Lambda / serverless container), the deployment bundle is read-only at /var/task.
# SQLite must be placed in writable /tmp directory.
def _resolve_db_path():
    env_db = os.getenv("DATABASE_URL")
    if env_db:
        return env_db, False

    default_path = os.path.join(BASE_DIR, "kandifix.db")
    # Check if running on Vercel or if BASE_DIR is read-only
    is_serverless = os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
    if is_serverless or not os.access(BASE_DIR, os.W_OK):
        tmp_path = "/tmp/kandifix.db"
        return f"sqlite:///{tmp_path}", True
    return f"sqlite:///{default_path}", False

DATABASE_URL, IS_SERVERLESS_TMP = _resolve_db_path()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)

from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        # WAL mode requires write access to the directory to create -wal and -shm files.
        # In serverless /tmp or normal disk this works; if WAL fails, fallback to default.
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
    except Exception:
        pass
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
