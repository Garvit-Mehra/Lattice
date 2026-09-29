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
    # On Vercel / AWS Lambda, the root is located in /var/task which is read-only
    is_serverless = (
        os.getenv("VERCEL") == "1"
        or "VERCEL" in os.environ
        or "VERCEL_ENV" in os.environ
        or "AWS_LAMBDA_FUNCTION_NAME" in os.environ
        or "/var/task" in BASE_DIR
        or not os.access(BASE_DIR, os.W_OK)
    )
    if is_serverless:
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
    # In serverless environments, WAL journal mode can fail if disk locks are restricted;
    # use default or DELETE journal mode in serverless /tmp
    if not IS_SERVERLESS_TMP:
        try:
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
