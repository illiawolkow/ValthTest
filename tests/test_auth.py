import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app import schemas, crud # For type hinting and direct DB interaction if needed
from app.core.config import settings
from app.models import User # For type hinting if needed for user_in_db

# Test Sign-up
@pytest.mark.asyncio
async def test_signup_new_user(client: AsyncClient, db_session: AsyncSession):
    """Test successful user signup."""
    unique_username = "testsignupuser"
    unique_email = "testsignupuser@example.com"
    password = "testpassword123"
    full_name = "Test Signup User"

    # Ensure user does not exist from previous runs (using db_session from conftest)
    existing_user_stmt = select(User).filter(User.username == unique_username)
    existing_user_result = await db_session.execute(existing_user_stmt)
    existing_user = existing_user_result.scalars().first()
    
    if existing_user:
        await db_session.delete(existing_user)
        await db_session.commit()

    response = await client.post(
        f"{settings.API_V1_STR}/auth/signup",
        json={"username": unique_username, "email": unique_email, "password": password, "full_name": full_name}
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["username"] == unique_username
    assert data["email"] == unique_email
    assert "id" in data
    assert "hashed_password" not in data # Ensure password is not returned

    # Verify user is in the database
    user_in_db = await crud.get_user_by_username(db_session, username=unique_username)
    assert user_in_db is not None
    assert user_in_db.email == unique_email
    assert user_in_db.full_name == full_name

@pytest.mark.asyncio
async def test_signup_existing_username(client: AsyncClient, test_user_data: dict):
    """Test signup with an already existing username."""
    # test_user_data fixture already creates a user
    response = await client.post(
        f"{settings.API_V1_STR}/auth/signup",
        json={"username": test_user_data["username"], "email": "newemail@example.com", "password": "anotherpassword", "full_name": "Another User"}
    )
    assert response.status_code == 400, response.text
    data = response.json()
    assert data["detail"] == "Username already registered"

@pytest.mark.asyncio
async def test_signup_short_password(client: AsyncClient):
    """Test signup with a password that is too short."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/signup",
        json={"username": "shortpassuser", "email": "short@example.com", "password": "123", "full_name": "Short Pass"}
    )
    assert response.status_code == 422, response.text
    data = response.json()
    # Check for a Pydantic validation error related to password length
    # The exact error message/type might depend on your UserCreate schema validation
    password_error_found = False
    for error in data.get("detail", []):
        if isinstance(error, dict) and "password" in error.get("loc", []):
            if "string_too_short" in error.get("type", "") or "too_short" in error.get("msg", "").lower():
                password_error_found = True
                break
    assert password_error_found, "Password length validation error not found."

# Test Sign-in (Token Generation)
@pytest.mark.asyncio
async def test_login_for_access_token(client: AsyncClient, test_user_data: dict):
    """Test successful login and token generation."""
    login_data = {
        "username": test_user_data["username"],
        "password": test_user_data["password"],
    }
    response = await client.post(f"{settings.API_V1_STR}/auth/token", data=login_data)
    assert response.status_code == 200, response.text
    token = response.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_incorrect_password(client: AsyncClient, test_user_data: dict):
    """Test login with incorrect password."""
    login_data = {
        "username": test_user_data["username"],
        "password": "wrongpassword",
    }
    response = await client.post(f"{settings.API_V1_STR}/auth/token", data=login_data)
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with a username that does not exist."""
    login_data = {
        "username": "nonexistentuser",
        "password": "anypassword",
    }
    response = await client.post(f"{settings.API_V1_STR}/auth/token", data=login_data)
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Incorrect username or password"

# Test Accessing Protected Endpoints
@pytest.mark.asyncio
async def test_read_users_me_authenticated(authenticated_client: AsyncClient, test_user_data: dict):
    """Test accessing /users/me with a valid token."""
    response = await authenticated_client.get(f"{settings.API_V1_STR}/auth/users/me")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == test_user_data["username"]
    assert data["email"] == test_user_data["email"]

@pytest.mark.asyncio
async def test_read_users_me_unauthenticated(client: AsyncClient):
    """Test accessing /users/me without a token."""
    response = await client.get(f"{settings.API_V1_STR}/auth/users/me")
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_read_users_me_invalid_token(client: AsyncClient):
    """Test accessing /users/me with an invalid token."""
    client.headers = {"Authorization": "Bearer invalidtoken"}
    response = await client.get(f"{settings.API_V1_STR}/auth/users/me")
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Could not validate credentials"

# Test Logout
@pytest.mark.asyncio
async def test_logout_authenticated(authenticated_client: AsyncClient):
    """Test successful logout for an authenticated user."""
    response = await authenticated_client.post(f"{settings.API_V1_STR}/auth/logout")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["message"] == "Logout successful. Please clear your token."
    # After logout, the token should ideally not work anymore if we had a blocklist.
    # For now, we just check the message. The client is responsible for clearing the token.

@pytest.mark.asyncio
async def test_logout_unauthenticated(client: AsyncClient):
    """Test logout attempt without authentication."""
    response = await client.post(f"{settings.API_V1_STR}/auth/logout")
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Not authenticated" 