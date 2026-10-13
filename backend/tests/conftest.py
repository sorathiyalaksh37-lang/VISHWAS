"""
Pytest configuration and fixtures.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.config import settings

TEST_DATABASE_URL = "sqlite:///:memory:"
TEST_UPLOAD_DIR = None


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory database for each test."""
    # StaticPool keeps one shared connection, so the tables stay visible
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_upload_dir():
    """Create a temporary upload directory for tests."""
    global TEST_UPLOAD_DIR
    TEST_UPLOAD_DIR = tempfile.mkdtemp()
    original_upload_dir = settings.upload_dir
    settings.upload_dir = TEST_UPLOAD_DIR
    yield TEST_UPLOAD_DIR
    if Path(TEST_UPLOAD_DIR).exists():
        shutil.rmtree(TEST_UPLOAD_DIR)
    settings.upload_dir = original_upload_dir


@pytest.fixture(scope="function")
def client(test_db, test_upload_dir):
    """Create a test client with the test database."""
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
    content = b"RIFF" + b"\x00" * 40
    return ("test_recording.wav", content, "audio/wav")