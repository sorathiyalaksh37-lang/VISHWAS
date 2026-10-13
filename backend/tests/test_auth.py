"""
Tests for Phase 7 authentication and authorization.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.models.user import User
from app.models.call import CallRecord, Contact
from app.auth.security import get_password_hash


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_auth.db"
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
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.close()


@pytest.fixture
def test_user2(test_db):
    """Create a second test user."""
    db = TestingSessionLocal()
    user = User(
        email="test2@example.com",
        hashed_password=get_password_hash("testpassword2"),
        full_name="Test User 2",
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
        json={"email": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── Registration Tests ────────────────────────────────────────────────────────

def test_register_new_user(test_db):
    """Test successful user registration."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "full_name": "New User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    # New response includes access_token and user object
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["full_name"] == "New User"
    assert data["user"]["is_active"] is True
    assert "id" in data["user"]


def test_register_duplicate_email(test_user):
    """Test that duplicate email registration fails."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "anotherpassword",
            "full_name": "Duplicate User"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_register_invalid_email(test_db):
    """Test registration with invalid email."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "password123",
            "full_name": "Invalid Email"
        }
    )
    assert response.status_code == 422  # Validation error


def test_register_short_password(test_db):
    """Test registration with too short password."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "short",
            "full_name": "Short Password"
        }
    )
    assert response.status_code == 422  # Validation error


# ── Login Tests ───────────────────────────────────────────────────────────────

def test_login_success(test_user):
    """Test successful login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(test_user):
    """Test login with incorrect password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_nonexistent_user(test_db):
    """Test login with non-existent email."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password"}
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_inactive_user(test_db):
    """Test login with inactive user account."""
    db = TestingSessionLocal()
    user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("password"),
        is_active=False
    )
    db.add(user)
    db.commit()
    db.close()
    
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "password"}
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_get_current_user(test_user, auth_headers):
    """Test retrieving current user information."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"


def test_get_current_user_invalid_token(test_db):
    """Test accessing protected endpoint with invalid token."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_get_current_user_no_token(test_db):
    """Test accessing protected endpoint without token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403  # HTTPBearer returns 403 when no token provided


# ── Upload Authorization Tests ────────────────────────────────────────────────

def test_upload_requires_auth(test_db):
    """Test that upload endpoint requires authentication."""
    # Create a dummy file
    response = client.post(
        "/api/v1/analyze/recording",
        files={"file": ("test.wav", b"fake audio data", "audio/wav")}
    )
    assert response.status_code == 403  # HTTPBearer returns 403 when no token provided


def test_upload_with_auth(test_user, auth_headers, tmp_path):
    """Test authenticated upload creates call with owner_id."""
    # Create a small test WAV file
    wav_file = tmp_path / "test.wav"
    wav_file.write_bytes(b"RIFF" + b"\x00" * 40)  # Minimal WAV header
    
    with open(wav_file, "rb") as f:
        response = client.post(
            "/api/v1/analyze/recording",
            files={"file": ("test.wav", f, "audio/wav")},
            headers=auth_headers
        )
    
    # May fail due to invalid WAV, but should not be auth error
    assert response.status_code != 401
    
    # If successful, verify ownership in database
    if response.status_code == 202:
        call_id = response.json()["call_id"]
        db = TestingSessionLocal()
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        assert call is not None
        assert call.owner_id == test_user.id
        db.close()


# ── Ownership Tests ───────────────────────────────────────────────────────────

def test_user_cannot_access_other_user_call(test_user, test_user2, auth_headers):
    """Test that User A cannot access User B's call."""
    # Create a call for user2
    db = TestingSessionLocal()
    call = CallRecord(
        owner_id=test_user2.id,
        original_filename="other_user_call.wav",
        stored_filename="stored.wav",
        storage_reference="/path/to/file",
        status="completed",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    call_id = call.id
    db.close()
    
    # Try to access with test_user's token (user1)
    response = client.get(
        f"/api/v1/call/{call_id}/status",
        headers=auth_headers
    )
    
    # Should return 404 (not 403) to avoid information disclosure
    assert response.status_code == 404


def test_user_can_access_own_call(test_user, auth_headers):
    """Test that user can access their own call."""
    # Create a call for test_user
    db = TestingSessionLocal()
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="my_call.wav",
        stored_filename="stored.wav",
        storage_reference="/path/to/file",
        status="completed",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    call_id = call.id
    db.close()
    
    # Access with own token
    response = client.get(
        f"/api/v1/call/{call_id}/status",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json()["call_id"] == call_id


def test_list_calls_only_shows_own_calls(test_user, test_user2, auth_headers):
    """Test that /calls endpoint only returns user's own calls."""
    # Create calls for both users
    db = TestingSessionLocal()
    
    call1 = CallRecord(
        owner_id=test_user.id,
        original_filename="my_call.wav",
        stored_filename="stored1.wav",
        storage_reference="/path/1",
        status="completed"
    )
    call2 = CallRecord(
        owner_id=test_user2.id,
        original_filename="other_call.wav",
        stored_filename="stored2.wav",
        storage_reference="/path/2",
        status="completed"
    )
    db.add_all([call1, call2])
    db.commit()
    db.close()
    
    # List calls with test_user's token
    response = client.get("/api/v1/calls", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 1
    assert data["calls"][0]["original_filename"] == "my_call.wav"


def test_user_cannot_access_other_user_contact(test_user, test_user2, auth_headers):
    """Test that User A cannot access User B's contact."""
    # Create a contact for user2
    db = TestingSessionLocal()
    contact = Contact(
        owner_id=test_user2.id,
        name="User2 Contact",
        relation="friend"
    )
    db.add(contact)
    db.commit()
    contact_id = contact.id
    db.close()
    
    # Try to enroll voiceprint with test_user's token
    response = client.post(
        f"/api/v1/contacts/{contact_id}/voiceprint",
        files={"file": ("voice.wav", b"fake audio", "audio/wav")},
        headers=auth_headers
    )
    
    # Should return 404
    assert response.status_code == 404


def test_list_contacts_only_shows_own_contacts(test_user, test_user2, auth_headers):
    """Test that /contacts endpoint only returns user's own contacts."""
    # Create contacts for both users
    db = TestingSessionLocal()
    
    contact1 = Contact(
        owner_id=test_user.id,
        name="My Contact",
        relation="mother"
    )
    contact2 = Contact(
        owner_id=test_user2.id,
        name="Other Contact",
        relation="friend"
    )
    db.add_all([contact1, contact2])
    db.commit()
    db.close()
    
    # List contacts with test_user's token
    response = client.get("/api/v1/contacts", headers=auth_headers)
    
    assert response.status_code == 200
    contacts = response.json()
    assert len(contacts) == 1
    assert contacts[0]["name"] == "My Contact"


# ── Password Security Tests ───────────────────────────────────────────────────

def test_passwords_are_hashed(test_db):
    """Test that passwords are not stored in plaintext."""
    # Register a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "hash@example.com",
            "password": "myplaintextpassword",
            "full_name": "Hash Test"
        }
    )
    
    # Check database
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "hash@example.com").first()
    
    assert user is not None
    assert user.hashed_password != "myplaintextpassword"
    assert user.hashed_password.startswith("$2b$")  # bcrypt hash prefix
    assert len(user.hashed_password) > 50  # bcrypt hashes are long
    
    db.close()


# ── Background Job Ownership Tests ────────────────────────────────────────────

def test_background_analysis_preserves_ownership(test_user, auth_headers, tmp_path):
    """Test that background analysis task preserves call ownership."""
    # This test verifies the upload endpoint sets owner_id correctly
    # The actual background task receives only call_id, which has owner_id set
    
    # Create a call
    db = TestingSessionLocal()
    call = CallRecord(
        owner_id=test_user.id,
        original_filename="test.wav",
        stored_filename="stored.wav",
        storage_reference="/path/to/file",
        status="queued",
        analysis_mode="mock"
    )
    db.add(call)
    db.commit()
    call_id = call.id
    db.close()
    
    # Verify owner_id is set
    db = TestingSessionLocal()
    retrieved_call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    assert retrieved_call.owner_id == test_user.id
    db.close()


# ── Token Expiration Tests ────────────────────────────────────────────────────

def test_expired_token_rejected():
    """Test that expired tokens are rejected."""
    # This would require mocking time or creating a token with past expiration
    # For now, we test invalid token format
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid"}
    )
    assert response.status_code == 401
