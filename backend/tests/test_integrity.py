"""
Tests for Phase 8: SHA-256 file integrity tracking and verification.
"""
import hashlib
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.models.user import User
from app.models.call import CallRecord
from app.models.integrity import FileIntegrityRecord
from app.services.integrity_service import integrity_service
from app.auth.security import get_password_hash


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_integrity.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def test_db():
    """Create fresh test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    db = TestingSessionLocal()
    user = User(
        email="integrity@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Integrity Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.close()


@pytest.fixture
def auth_token(test_user):
    """Get authentication token for test user."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "integrity@example.com", "password": "testpass"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def temp_test_file():
    """Create a temporary test file with known content."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        test_content = b"This is test audio data for integrity verification"
        f.write(test_content)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


# ── Test 01: SHA-256 Calculation Against Known Vectors ────────────────────────

def test_sha256_known_vectors(test_db, temp_test_file):
    """Test SHA-256 calculation against known test vectors."""
    # Known SHA-256 of "This is test audio data for integrity verification"
    expected_hash = hashlib.sha256(b"This is test audio data for integrity verification").hexdigest()
    expected_size = 50  # Actual byte count of the string above
    
    calculated_hash, calculated_size = integrity_service.calculate_sha256(temp_test_file)
    
    assert calculated_hash == expected_hash
    assert calculated_size == expected_size
    assert len(calculated_hash) == 64  # SHA-256 produces 64 hex characters


def test_sha256_empty_file(test_db):
    """Test SHA-256 of empty file."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        temp_path = Path(f.name)
    
    try:
        # Empty file SHA-256
        expected_empty_hash = hashlib.sha256(b"").hexdigest()
        calculated_hash, calculated_size = integrity_service.calculate_sha256(temp_path)
        
        assert calculated_hash == expected_empty_hash
        assert calculated_size == 0
    finally:
        temp_path.unlink()


def test_sha256_large_file_streaming(test_db):
    """Test streaming hash calculation for large files (memory-bounded)."""
    # Create a 1MB file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        chunk = b"A" * 8192  # 8KB chunks
        for _ in range(128):  # 128 chunks = 1MB
            f.write(chunk)
        temp_path = Path(f.name)
    
    try:
        # Calculate hash (should not load entire file into memory at once)
        calculated_hash, calculated_size = integrity_service.calculate_sha256(temp_path)
        
        assert len(calculated_hash) == 64
        assert calculated_size == 1048576  # 1MB
        
        # Verify it matches full calculation
        expected_hash = hashlib.sha256(b"A" * 1048576).hexdigest()
        assert calculated_hash == expected_hash
    finally:
        temp_path.unlink()


def test_sha256_nonexistent_file(test_db):
    """Test error handling for nonexistent file."""
    fake_path = Path("/nonexistent/fake/file.txt")
    
    with pytest.raises(FileNotFoundError):
        integrity_service.calculate_sha256(fake_path)


# ── Test 02-03: Hash Persistence and Retrieval ────────────────────────────────

def test_hash_persistence(test_db, test_user, temp_test_file):
    """Test recording file hash in database."""
    db = TestingSessionLocal()
    
    # Create a test call record
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="test_stored.wav",
        storage_reference=str(temp_test_file),
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Calculate and record hash
    record = integrity_service.calculate_and_record(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    db.commit()
    
    assert record is not None
    assert record.call_id == call.id
    assert record.artifact_type == "original_upload"
    assert record.sha256_hash is not None
    assert len(record.sha256_hash) == 64
    assert record.file_size_bytes == 50
    assert record.hash_algorithm == "sha256"
    
    db.close()


def test_hash_retrieval(test_db, test_user, temp_test_file):
    """Test retrieving stored hash from database."""
    db = TestingSessionLocal()
    
    # Create call and record hash
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="test_stored.wav",
        storage_reference=str(temp_test_file),
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Record hash
    integrity_service.calculate_and_record(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    db.commit()
    
    # Retrieve hash
    stored_record = integrity_service.get_stored_hash(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
    )
    
    assert stored_record is not None
    assert stored_record.call_id == call.id
    assert stored_record.artifact_type == "original_upload"
    
    db.close()


# ── Test 05-06: Hash Stability and Modification Detection ─────────────────────

def test_hash_stability_unchanged_bytes(test_db, test_user):
    """Test hash remains stable for unchanged file bytes."""
    db = TestingSessionLocal()
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        f.write(b"Stable content for hash testing")
        temp_path = Path(f.name)
    
    try:
        # Calculate hash twice
        hash1, size1 = integrity_service.calculate_sha256(temp_path)
        hash2, size2 = integrity_service.calculate_sha256(temp_path)
        
        assert hash1 == hash2
        assert size1 == size2
    finally:
        temp_path.unlink()
    
    db.close()


def test_modified_file_detection(test_db, test_user, temp_test_file):
    """Test detection of modified file bytes."""
    db = TestingSessionLocal()
    
    # Create call and record original hash
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="test_stored.wav",
        storage_reference=str(temp_test_file),
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Record original hash
    integrity_service.calculate_and_record(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    db.commit()
    
    # Modify file
    with open(temp_test_file, 'ab') as f:
        f.write(b" MODIFIED")
    
    # Verify - should detect mismatch
    status, message = integrity_service.verify_file_integrity(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    
    assert status == "mismatch"
    assert "mismatch" in message.lower()
    
    db.close()


# ── Test 07-08: Missing File and Missing Hash Handling ────────────────────────

def test_missing_file_handling(test_db, test_user):
    """Test handling when file is missing."""
    db = TestingSessionLocal()
    
    # Create call with hash but no actual file
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="nonexistent.wav",
        storage_reference="/fake/path/nonexistent.wav",
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Record a fake hash entry
    integrity_service.record_file_hash(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path="nonexistent.wav",
        sha256_hash="a" * 64,
        file_size_bytes=1000,
    )
    db.commit()
    
    # Try to verify - should return unavailable
    fake_path = Path("/fake/path/nonexistent.wav")
    status, message = integrity_service.verify_file_integrity(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=fake_path,
    )
    
    assert status == "unavailable"
    assert "not found" in message.lower()
    
    db.close()


def test_missing_hash_handling(test_db, test_user, temp_test_file):
    """Test handling when hash record is missing (legacy uploads)."""
    db = TestingSessionLocal()
    
    # Create call without hash record (simulates legacy upload)
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="legacy.wav",
        stored_filename="legacy_stored.wav",
        storage_reference=str(temp_test_file),
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # NO hash record created
    
    # Try to verify - should return unavailable
    status, message = integrity_service.verify_file_integrity(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    
    assert status == "unavailable"
    assert "no integrity record" in message.lower()
    
    db.close()


# ── Test 09: Separate Hashes for Original and Converted ───────────────────────

def test_separate_artifact_hashes(test_db, test_user):
    """Test storing separate hashes for original and processed artifacts."""
    db = TestingSessionLocal()
    
    # Create two different files
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.mp3') as f:
        f.write(b"Original MP3 content")
        original_path = Path(f.name)
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.wav') as f:
        f.write(b"Converted WAV content")
        converted_path = Path(f.name)
    
    try:
        # Create call
        call = CallRecord(
            owner_id=test_user.id,
            original_filename="test.mp3",
            stored_filename="test_stored.mp3",
            storage_reference=str(original_path),
            status="processing",
            analysis_mode="real"
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Record hash for original
        original_record = integrity_service.calculate_and_record(
            db=db,
            call_id=call.id,
            artifact_type="original_upload",
            file_path=original_path,
        )
        
        # Record hash for converted
        converted_record = integrity_service.calculate_and_record(
            db=db,
            call_id=call.id,
            artifact_type="processed_wav",
            file_path=converted_path,
        )
        db.commit()
        
        # Verify both exist and are different
        assert original_record.artifact_type == "original_upload"
        assert converted_record.artifact_type == "processed_wav"
        assert original_record.sha256_hash != converted_record.sha256_hash
        
        # Get all hashes for call
        all_records = integrity_service.get_all_hashes_for_call(db, call.id)
        assert len(all_records) == 2
        
    finally:
        original_path.unlink()
        converted_path.unlink()
    
    db.close()


# ── Test 10: Verification API Endpoint Authorization ───────────────────────────

def test_integrity_api_requires_auth(test_db, test_user, temp_test_file):
    """Test that integrity verification endpoint requires authentication."""
    db = TestingSessionLocal()
    
    # Create call
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="test_stored.wav",
        storage_reference=str(temp_test_file),
        status="completed",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Try to access without authentication
    response = client.get(f"/api/v1/calls/{call.id}/integrity")
    assert response.status_code == 403  # HTTPBearer returns 403 when no token
    
    db.close()


def test_integrity_api_with_auth(test_db, test_user, auth_headers, temp_test_file):
    """Test integrity verification API with authentication."""
    db = TestingSessionLocal()
    
    # Create call with hash
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="test_stored.wav",
        storage_reference=str(temp_test_file),
        status="completed",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    # Record hash
    integrity_service.calculate_and_record(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=temp_test_file,
    )
    db.commit()
    
    # Access with authentication
    response = client.get(
        f"/api/v1/calls/{call.id}/integrity",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["call_id"] == call.id
    assert data["status"] == "verified"
    assert "stored_hash" in data
    
    db.close()


def test_integrity_api_cross_user_denial(test_db, test_user, auth_headers):
    """Test that users cannot verify integrity of other users' files."""
    db = TestingSessionLocal()
    
    # Create another user
    other_user = User(
        email="other@example.com",
        hashed_password=get_password_hash("otherpass"),
        full_name="Other User",
        is_active=True
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    
    # Create file owned by other user
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        f.write(b"Other user's file")
        temp_path = Path(f.name)
    
    try:
        call = CallRecord(
            owner_id=other_user.id,  # Different owner
            original_filename="other.wav",
            stored_filename="other_stored.wav",
            storage_reference=str(temp_path),
            status="completed",
            analysis_mode="mock"
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Try to verify with test_user's token
        response = client.get(
            f"/api/v1/calls/{call.id}/integrity",
            headers=auth_headers  # test_user's token
        )
        
        # Should be denied (404 to avoid information disclosure)
        assert response.status_code == 404
        
    finally:
        temp_path.unlink()
    
    db.close()


# ── Test 11: Failure During Upload Without False Verified Status ──────────────

def test_no_false_verified_on_upload_failure(test_db):
    """Test that failed uploads don't create false 'verified' status."""
    db = TestingSessionLocal()
    
    # Simulate a call that failed during upload
    # (In reality, the transaction would rollback, but let's check the logic)
    
    fake_call_id = "failed-upload-123"
    fake_path = Path("/nonexistent/failed.wav")
    
    # Try to verify non-existent file
    status, message = integrity_service.verify_file_integrity(
        db=db,
        call_id=fake_call_id,
        artifact_type="original_upload",
        file_path=fake_path,
    )
    
    # Should NOT report as verified
    assert status != "verified"
    assert status == "unavailable"
    
    db.close()
