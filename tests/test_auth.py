import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app import schemas, crud # For type hinting and direct DB interaction if needed
from app.core.config import settings

# Test Sign-up
@pytest.mark.asyncio
async def test_signup_new_user(client: AsyncClient, db_session: Session):
    """Test successful user signup."""
    unique_username = "testsignupuser"
    unique_email = "testsignupuser@example.com"
    password = "testpassword123"

    # Ensure user does not exist from previous runs (using db_session from conftest)
    existing_user = crud.get_user_by_username(db_session, username=unique_username)
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    response = await client.post(
        f"/auth/signup", 
        json={"username": unique_username, "email": unique_email, "password": password, "full_name": "Test Signup"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == unique_username
    assert data["email"] == unique_email
    assert "id" in data
    assert "hashed_password" not in data # Ensure password is not returned

    # Verify user is in the database
    user_in_db = crud.get_user_by_username(db_session, username=unique_username)
    assert user_in_db is not None
    assert user_in_db.email == unique_email

@pytest.mark.asyncio
async def test_signup_existing_username(client: AsyncClient, test_user_data: dict):
    """Test signup with an already existing username."""
    # test_user_data fixture already creates a user
    response = await client.post(
        f"/auth/signup",
        json={"username": test_user_data["username"], "email": "newemail@example.com", "password": "anotherpassword"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Username already registered"

@pytest.mark.asyncio
async def test_signup_short_password(client: AsyncClient):
    """Test signup with a password that is too short."""
    response = await client.post(
        f"/auth/signup", 
        json={"username": "shortpassuser", "email": "short@example.com", "password": "123"}
    )
    assert response.status_code == 422 # FastAPI/Pydantic validation error
    data = response.json()
    assert any(err["type"] == "string_too_short" and "password" in err["loc"] for err in data["detail"])

# Test Sign-in (Token Generation)
@pytest.mark.asyncio
async def test_login_for_access_token(client: AsyncClient, test_user_data: dict):
    """Test successful login and token generation."""
    login_data = {
        "username": test_user_data["username"],
        "password": test_user_data["password"],
    }
    response = await client.post(f"/auth/token", data=login_data)
    assert response.status_code == 200
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
    response = await client.post(f"/auth/token", data=login_data)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with a username that does not exist."""
    login_data = {
        "username": "nonexistentuser",
        "password": "anypassword",
    }
    response = await client.post(f"/auth/token", data=login_data)
    assert response.status_code == 401 # Or 404 depending on how you want to handle
    data = response.json()
    assert data["detail"] == "Incorrect username or password"

# Test Accessing Protected Endpoints
@pytest.mark.asyncio
async def test_read_users_me_authenticated(authenticated_client: AsyncClient, test_user_data: dict):
    """Test accessing /users/me with a valid token."""
    response = await authenticated_client.get(f"/auth/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user_data["username"]
    assert data["email"] == test_user_data["email"]

@pytest.mark.asyncio
async def test_read_users_me_unauthenticated(client: AsyncClient):
    """Test accessing /users/me without a token."""
    response = await client.get(f"/auth/users/me")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_read_users_me_invalid_token(client: AsyncClient):
    """Test accessing /users/me with an invalid token."""
    client.headers = {"Authorization": "Bearer invalidtoken"}
    response = await client.get(f"/auth/users/me")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Could not validate credentials"

# Test Logout
@pytest.mark.asyncio
async def test_logout_authenticated(authenticated_client: AsyncClient):
    """Test successful logout for an authenticated user."""
    response = await authenticated_client.post(f"/auth/logout")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Logout successful. Please clear your token."
    # After logout, the token should ideally not work anymore if we had a blocklist.
    # For now, we just check the message. The client is responsible for clearing the token.

@pytest.mark.asyncio
async def test_logout_unauthenticated(client: AsyncClient):
    """Test logout attempt without authentication."""
    response = await client.post(f"/auth/logout")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated" 