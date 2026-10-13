"""
Pytest configuration and fixtures.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.config import settings
# Import all models so Base.metadata knows about them
from app.models.call import CallRecord, AnalysisReport, Contact

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
TEST_UPLOAD_DIR = None


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test."""
    # For in-memory SQLite, use StaticPool to share the same connection
    # Otherwise each connection gets a fresh empty database
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool  # Share connection for in-memory database
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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
    # Disable lifespan events for tests (init_db uses production engine)
    app_no_lifespan = FastAPI(
        title="VISHWAS API Test",
        version="test"
    )
    
    # Copy routes from original app
    from app.api.routes import health, calls, analyze
    app_no_lifespan.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app_no_lifespan.include_router(analyze.router, prefix="/api/v1", tags=["Analysis"])
    app_no_lifespan.include_router(calls.router, prefix="/api/v1", tags=["Calls (legacy)"])
    
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app_no_lifespan.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app_no_lifespan) as test_client:
        yield test_client
    
    app_no_lifespan.dependency_overrides.clear()


@pytest.fixture
def sample_audio_file():
    """Create a sample audio file for testing."""
    content = b"RIFF" + b"\x00" * 40  # Minimal WAV-like header
    return ("test_recording.wav", content, "audio/wav")
