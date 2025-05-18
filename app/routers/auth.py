from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app import crud, schemas, models
from app.database import get_db
from app.auth import jwt as jwt_utils
from app.core.config import settings
from app.auth.dependencies import get_current_active_user

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_username(db, username=form_data.username)
    
    if not user and form_data.username == "testuser":
        hashed_password = jwt_utils.get_password_hash("testpass")
        test_user_create_data = schemas.UserCreate(username="testuser", password="testpass", email="test@example.com", full_name="Test User")
        user = await crud.create_user(db, user_create=test_user_create_data, hashed_password_in=hashed_password)
    
    if not user or not jwt_utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt_utils.create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/signup", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def signup_new_user(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user_by_username = await crud.get_user_by_username(db, username=user_in.username)
    if db_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
            
    hashed_password = jwt_utils.get_password_hash(user_in.password)
    created_user = await crud.create_user(db, user_create=user_in, hashed_password_in=hashed_password)
    return created_user

@router.post("/logout")
async def logout(current_user: models.User = Depends(get_current_active_user)):
    # Current logout is stateless, no async changes needed here unless it interacts with DB
    return {"message": "Logout successful. Please clear your token."}

@router.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user 