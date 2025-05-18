from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app import crud, schemas, models
from app.database import get_db
from app.auth import jwt as jwt_utils # Renamed to avoid conflict
from app.core.config import settings
from app.auth.dependencies import get_current_active_user # Import the new dependency

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # In a real application, you would authenticate the user against the database.
    # Here, we simulate it for a dummy user "testuser" with password "testpass"
    # You should replace this with actual user lookup and password verification.
    
    user = crud.get_user_by_username(db, username=form_data.username)
    
    # For testing, if user doesn't exist, create a dummy one if it's "testuser"
    # THIS IS FOR DEMONSTRATION ONLY - REMOVE/REPLACE IN PRODUCTION
    if not user and form_data.username == "testuser":
        hashed_password = jwt_utils.get_password_hash("testpass")
        # For creating the testuser, we need a UserCreate schema instance
        test_user_create_data = schemas.UserCreate(username="testuser", password="testpass", email="test@example.com")
        user = crud.create_user(db, user_create=test_user_create_data, hashed_password_in=hashed_password)
    
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
async def signup_new_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user_by_username = crud.get_user_by_username(db, username=user_in.username)
    if db_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Optional: Add email existence check if your User model has a unique constraint on email
    # if user_in.email:
    #     db_user_by_email = db.query(models.User).filter(models.User.email == user_in.email).first()
    #     if db_user_by_email:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="Email already registered"
    #         )
            
    hashed_password = jwt_utils.get_password_hash(user_in.password)
    # user_in is already schemas.UserCreate, which is what crud.create_user now expects
    created_user = crud.create_user(db, user_create=user_in, hashed_password_in=hashed_password)
    return created_user

@router.post("/logout")
async def logout(current_user: models.User = Depends(get_current_active_user)):
    # For stateless JWT, logout is primarily handled by the client deleting the token.
    # This endpoint can acknowledge the request and optionally log the logout attempt.
    # If using a token blocklist, this is where you would add the token to it.
    return {"message": "Logout successful. Please clear your token."}

# Example of a protected route, can be moved to another router
@router.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    # The get_current_active_user dependency now handles fetching and validation.
    # The current_user object is the SQLAlchemy model instance.
    # We return it directly as Pydantic will convert it based on response_model=schemas.User
    return current_user 