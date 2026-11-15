"""
GARI Auth Server 1.0 — Database Engine & Session Management
"""
import os
import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from app.config import settings


def get_engine(database_url: str = settings.database_url):
    """Creates database engine tailored for Serverless (NullPool) vs Managed environments."""
    is_serverless = os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None

    if database_url.startswith("postgresql"):
        if is_serverless:
            # Serverless microVMs: use NullPool to immediately close idle connections and protect Neon pool limits.
            # pool_pre_ping is False because NullPool generates fresh connections per request (no stale pooled sockets).
            return create_engine(
                database_url,
                poolclass=NullPool,
                pool_pre_ping=False
            )
        else:
            # Long-running servers (e.g. Render / local dev): use managed connection pool
            return create_engine(
                database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10
            )
    else:
        connect_args = {"check_same_thread": False, "timeout": 15}
        return create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True
        )


engine = get_engine()

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
