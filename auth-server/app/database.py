"""
GARI Auth Server 1.0 — Database Engine & Session Management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
import sqlite3
from typing import Generator
from app.config import settings

# Engine configuration: PostgreSQL (Neon Serverless) vs SQLite
if settings.database_url.startswith("postgresql"):
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10
    )
else:
    connect_args = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True
    )

# Enforce SQLite foreign keys and WAL journal mode when using SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a thread-safe database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes database schema and tables."""
    from app.models.user import User  # noqa: F401
    from app.models.session import SessionModel  # noqa: F401
    from app.models.security_event import SecurityEvent  # noqa: F401
    Base.metadata.create_all(bind=engine)
