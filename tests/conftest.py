import os
import asyncio
import pytest
from typing import AsyncGenerator, Generator

# Use an async SQLite URL for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_pytest.db" # Use a distinct file for test DB
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_pytest_12345678901234567890"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
# For async testing setup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Important: Import app and its components AFTER environment variables are set
from app.main import app
from app.database import Base, get_db # get_db is now async
from app.core.config import settings

# Create an async engine for testing
# The DATABASE_URL from os.environ will be used by app.database.engine
# This test_engine is for direct manipulation in conftest if needed, or for overriding get_db
test_engine = create_async_engine(
    settings.DATABASE_URL, # This should now be the async sqlite URL
    echo=False # Can be True for debugging test SQL
)

# Async sessionmaker for tests
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_test_database() -> AsyncGenerator[None, None]: # Changed to async
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose() # Dispose of the test engine

async def override_get_db() -> AsyncGenerator[AsyncSession, None]: # Changed to async
    async with TestingSessionLocal() as session:
        yield session
        # No explicit close needed due to async context manager

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    # ASGITransport needs the app itself
    async with ASGITransport(app=app) as transport: # Corrected ASGITransport usage
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac: # base_url can be testserver
            yield ac

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]: # Changed to async
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture(scope="function")
async def test_user_data(db_session: AsyncSession) -> dict: # Changed to take async db_session
    # Assumes crud.get_user_by_username and crud.create_user are now async
    # and accept AsyncSession. This will require changes in app.crud
    from app import crud, schemas # crud functions need to be async
    from app.auth.jwt import get_password_hash

    user_in = schemas.UserCreate(
        username="testuser123",
        email="testuser123@example.com",
        password="testpassword123"
    )
    
    # Make sure CRUD functions are async and awaited
    existing_user = await crud.get_user_by_username(db_session, username=user_in.username)
    if existing_user:
        await db_session.delete(existing_user)
        await db_session.commit()

    hashed_password = get_password_hash(user_in.password) # This can remain sync
    # Ensure create_user is async and handles commit
    await crud.create_user(db_session, user_create=user_in, hashed_password_in=hashed_password)
    
    return {"username": user_in.username, "password": user_in.password, "email": user_in.email, "full_name": "Test User"}

@pytest.fixture(scope="function")
async def authenticated_client(client: AsyncClient, test_user_data: dict) -> AsyncClient:
    login_data = {
        "username": test_user_data["username"],
        "password": test_user_data["password"],
    }
    # The app's API_V1_STR is used if client has base_url ending before that
    # If client base_url is "http://testserver", path should be settings.API_V1_STR + "/auth/token"
    # Or, if client already includes API_V1_STR in its base_url, then just "/auth/token"
    # Current client fixture base_url="http://testserver", so we need the prefix
    # However, previous base_url for client in conftest was "http://127.0.0.1:8000{settings.API_V1_STR}"
    # Let's assume client base_url is now just "http://testserver" for simplicity with ASGITransport
    
    # Corrected URL for ASGITransport if base_url is "http://testserver"
    # The path must be absolute from the app's root.
    token_url = f"{settings.API_V1_STR}/auth/token"

    response = await client.post(token_url, data=login_data)
    
    if response.status_code != 200:
        # Provide more info on auth failure during tests
        pytest.fail(f"Authentication failed: {response.status_code} {response.text}")
        
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client 