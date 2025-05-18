from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging
from contextlib import asynccontextmanager

from app.database import create_tables #, engine, Base # For Alembic, you might not call create_tables() here
from app.routers import names, auth
from app.core.config import settings # Used implicitly by other modules

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables if they don't exist...")
    try:
        await create_tables()
        logger.info("Database tables checked/created.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    yield
    logger.info("Application shutdown.")

app = FastAPI(
    title="Nationality Prediction API",
    description="Fetches and aggregates data from Nationalize.io and REST Countries.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Global Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the validation errors for debugging
    logger.error(f"Request validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body if hasattr(exc, 'body') else None}
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    # For security, don't expose detailed SQLAlchemy errors to the client in production.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal database error occurred."}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."}
    )

# --- Include Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(names.router, prefix="/api/v1")

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

