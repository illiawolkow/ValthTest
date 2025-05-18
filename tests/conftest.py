import os
import asyncio
import pytest
from typing import AsyncGenerator, Generator

# Set environment variables for testing BEFORE other imports that might load settings
# This ensures that when Pydantic's Settings model is initialized, it finds these values.
# These are typically needed for app initialization even if parts are overridden later (like DB URL).
os.environ["DATABASE_URL"] = "sqlite:///./test_override.db" # Dummy, will be overridden by engine
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_pytest_12345678901234567890"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app # Your FastAPI application instance
from app.database import Base, get_db # Your SQLAlchemy Base and get_db dependency
from app.core.config import settings

# Use an in-memory SQLite database for testing
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db" # In-memory: "sqlite:///:memory:"
# Using a file-based SQLite for easier inspection during test development, 
# change to ":memory:" for potentially faster tests if inspection is not needed.

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """Create test database tables before tests run, and drop them after."""
    Base.metadata.create_all(bind=engine) # Create tables
    yield
    Base.metadata.drop_all(bind=engine) # Drop tables

def override_get_db() -> Generator[Session, None, None]:
    """Dependency override for get_db to use the test database."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Apply the override for get_db for all tests
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client for making requests to the FastAPI app."""
    transport = ASGITransport(app=app) 
    async with AsyncClient(transport=transport, base_url=f"http://127.0.0.1:8000{settings.API_V1_STR}") as ac:
        yield ac

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Yield a database session for direct data manipulation in tests."""
    # This provides a direct session if needed, different from the one injected into routes.
    # Ensure it's used carefully and consistently with the test database setup.
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fixture to provide a default user and their password for tests
# This can be expanded or parameterized as needed.
@pytest.fixture(scope="function")
async def test_user_data(client: AsyncClient, db_session: Session) -> dict:
    from app import crud, schemas
    from app.auth.jwt import get_password_hash

    user_in = schemas.UserCreate(
        username="testuser123", 
        email="testuser123@example.com", 
        password="testpassword123"
    )
    # Clean up existing user if any, before creating
    existing_user = crud.get_user_by_username(db_session, username=user_in.username)
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    # user_in is already schemas.UserCreate
    hashed_password = get_password_hash(user_in.password)
    crud.create_user(db_session, user_create=user_in, hashed_password_in=hashed_password)
    
    return {"username": user_in.username, "password": user_in.password, "email": user_in.email, "full_name": "Test User"}

@pytest.fixture(scope="function")
async def authenticated_client(client: AsyncClient, test_user_data: dict) -> AsyncClient:
    """Returns an AsyncClient that is authenticated with the test_user_data."""
    login_data = {
        "username": test_user_data["username"],
        "password": test_user_data["password"],
    }
    # The token endpoint expects form data, not JSON
    response = await client.post(f"/auth/token", data=login_data) 
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client 