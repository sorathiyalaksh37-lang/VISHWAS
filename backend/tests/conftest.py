"""
Pytest configuration and fixtures.

Uses file-based temporary SQLite database for test isolation.
All tests share the same DB setup pattern for consistency.
"""
import pytest
import tempfile
import shutil
import os
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.config import settings

# Create a shared temp database file for the test session
_tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db_file.close()
TEST_DATABASE_URL = f"sqlite:///{_tmp_db_file.name}"
TEST_UPLOAD_DIR = None

# Override database URL before any imports that use it
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Create test engine and session factory
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Create fresh database tables for each test.
    Ensures test isolation without recreating the database file.
    """
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    yield
    
    # Drop all tables after test
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create a database session for each test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_upload_dir():
    """Create a temporary upload directory for tests."""
    global TEST_UPLOAD_DIR
    TEST_UPLOAD_DIR = tempfile.mkdtemp()
    original_upload_dir = settings.upload_dir
    settings.upload_dir = TEST_UPLOAD_DIR
    
    yield TEST_UPLOAD_DIR
    
    # Cleanup
    if Path(TEST_UPLOAD_DIR).exists():
        shutil.rmtree(TEST_UPLOAD_DIR)
    settings.upload_dir = original_upload_dir


@pytest.fixture(scope="function")
def client(test_db, test_upload_dir):
    """Create a test client with test database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_audio_file():
    """Create a sample audio file for testing."""
    content = b"RIFF" + b"\x00" * 40  # Minimal WAV-like header
    return ("test_recording.wav", content, "audio/wav")


def pytest_sessionfinish(session, exitstatus):
    """Cleanup: Remove temporary database file after all tests complete."""
    try:
        db_path = Path(_tmp_db_file.name)
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass  # Ignore cleanup errors
