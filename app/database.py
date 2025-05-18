from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# Use create_async_engine for an asynchronous engine
engine = create_async_engine(settings.DATABASE_URL, echo=False) # echo=True for debugging SQL

# Configure SessionLocal for AsyncSession
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession, # Use AsyncSession
    expire_on_commit=False, # Common practice for async sessions
    autocommit=False, # Explicit commit/rollback is better
    autoflush=False,  # Explicit flush is better
)

Base = declarative_base()

async def get_db() -> AsyncSession: # Changed to async def
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() # Ensure session is closed

async def create_tables(): # Changed to async def
    async with engine.begin() as conn:
        # For creating tables with an async engine
        await conn.run_sync(Base.metadata.create_all) 