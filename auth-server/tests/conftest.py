"""
Pytest configuration and fixtures for GARI Auth Server
"""
import pytest
import os
import tempfile
from pathlib import Path
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configure test environment variables before importing app modules
test_dir = tempfile.mkdtemp()
test_db_path = Path(test_dir) / "test_gari_auth.db"

os.environ["AUTH_ENV"] = "testing"
os.environ["AUTH_DB_PATH"] = str(test_db_path)
os.environ["BOOTSTRAP_ADMIN_TOKEN"] = "super_secure_bootstrap_secret_token_12345"

from app.config import settings
settings.AUTH_DB_PATH = str(test_db_path)
settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS = 100
settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS = 50

from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import rate_limiter

test_engine = create_engine(
    f"sqlite:///{test_db_path.as_posix()}",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Rebuilds clean database tables and resets rate limiters before each test function."""
    rate_limiter._history.clear()
    settings.REGISTRATION_OPEN = True
    settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS = 100
    settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS = 50

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    rate_limiter._history.clear()


@pytest.fixture
def client():
    """Provides a fresh TestClient for making HTTP requests."""
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def db_session():
    """Provides a direct database session for test assertions."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
