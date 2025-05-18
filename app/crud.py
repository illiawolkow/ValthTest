from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from sqlalchemy.orm import joinedload # joinedload works with select() in async
from typing import List, Optional
from datetime import datetime, timedelta

from . import models, schemas

# --- QueriedName CRUD --- #
async def get_queried_name(db: AsyncSession, name_text: str) -> Optional[models.QueriedName]:
    result = await db.execute(
        select(models.QueriedName).filter(models.QueriedName.name_text == name_text)
    )
    return result.scalars().first()

async def create_queried_name(db: AsyncSession, name_create: schemas.QueriedNameCreate) -> models.QueriedName:
    db_name = models.QueriedName(
        name_text=name_create.name_text,
        last_nationalize_fetch_at=name_create.last_nationalize_fetch_at
    )
    db.add(db_name)
    await db.commit()
    await db.refresh(db_name)
    return db_name

async def update_queried_name_fetch_time(db: AsyncSession, name_text: str, fetch_time: datetime) -> Optional[models.QueriedName]:
    # Efficient update without separate select first
    stmt = (
        update(models.QueriedName)
        .where(models.QueriedName.name_text == name_text)
        .values(last_nationalize_fetch_at=fetch_time, updated_at=datetime.utcnow())
        .returning(models.QueriedName) # To get the updated row back
    )
    result = await db.execute(stmt)
    await db.commit() # Commit after execute
    updated_name = result.scalars().first()
    return updated_name

# --- Country CRUD --- #
async def get_country(db: AsyncSession, country_code: str) -> Optional[models.Country]:
    result = await db.execute(
        select(models.Country).filter(models.Country.country_code == country_code)
    )
    return result.scalars().first()

async def create_country(db: AsyncSession, country_create: schemas.CountryCreate) -> models.Country:
    country_data = country_create.model_dump()
    
    url_fields = [
        "google_maps_url", "open_street_map_url", "flag_png_url",
        "flag_svg_url", "coat_of_arms_png_url", "coat_of_arms_svg_url",
    ]
    
    for field in url_fields:
        if field in country_data and country_data[field] is not None:
            # Pydantic HttpUrl fields are already stringified by model_dump if they were HttpUrl objects
            # If they were already strings, this does nothing.
            country_data[field] = str(country_data[field])
            
    db_country = models.Country(**country_data)
    db.add(db_country)
    await db.commit()
    await db.refresh(db_country)
    return db_country

# --- NameCountryProbability CRUD --- #
async def get_name_country_probabilities(db: AsyncSession, queried_name_id: int) -> List[models.NameCountryProbability]:
    stmt = (
        select(models.NameCountryProbability)
        .filter(models.NameCountryProbability.queried_name_id == queried_name_id)
        .options(joinedload(models.NameCountryProbability.country_details)) # joinedload used with select
        .order_by(desc(models.NameCountryProbability.probability))
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_name_country_probability(db: AsyncSession, queried_name_id: int, country_code: str) -> Optional[models.NameCountryProbability]:
    stmt = (
        select(models.NameCountryProbability)
        .filter(
            models.NameCountryProbability.queried_name_id == queried_name_id,
            models.NameCountryProbability.country_code == country_code
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def create_name_country_probability(db: AsyncSession, probability_create: schemas.NameCountryProbabilityCreate) -> models.NameCountryProbability:
    db_prob = models.NameCountryProbability(**probability_create.model_dump())
    db.add(db_prob)
    await db.commit()
    await db.refresh(db_prob)
    return db_prob

async def update_name_country_probability(
    db: AsyncSession, 
    queried_name_id: int, 
    country_code: str, 
    probability_update: schemas.NameCountryProbabilityUpdate
) -> Optional[models.NameCountryProbability]:
    # First, fetch the existing record
    db_prob = await get_name_country_probability(db, queried_name_id, country_code)
    if db_prob:
        update_data = probability_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_prob, key, value)
        db_prob.updated_at = datetime.utcnow()
        
        # Logic for access_count can remain similar, as setattr handles it.
        # If access_count is explicitly provided in update_data, it will be set.
        # If not, it won't be touched by this loop.

        await db.commit()
        await db.refresh(db_prob)
    return db_prob
    
async def increment_name_country_access(db: AsyncSession, queried_name_id: int, country_code: str) -> Optional[models.NameCountryProbability]:
    db_prob = await get_name_country_probability(db, queried_name_id, country_code)
    if db_prob:
        db_prob.access_count = (db_prob.access_count or 0) + 1
        db_prob.last_accessed_details_at = datetime.utcnow()
        db_prob.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(db_prob)
    return db_prob

async def get_popular_names_for_country(db: AsyncSession, country_code: str, limit: int = 5) -> List[schemas.PopularNameItem]:
    stmt = (
        select(
            models.QueriedName.name_text,
            func.sum(models.NameCountryProbability.access_count).label("total_frequency")
        )
        .join(models.NameCountryProbability, models.QueriedName.id == models.NameCountryProbability.queried_name_id)
        .filter(models.NameCountryProbability.country_code == country_code)
        .group_by(models.QueriedName.name_text)
        .order_by(desc("total_frequency")) # For sum, might need func.sum(...) or the label
        .limit(limit)
    )
    result = await db.execute(stmt)
    # Results from a query with explicit columns are tuples (or Row objects)
    return [schemas.PopularNameItem(name_text=name, frequency=freq) for name, freq in result.all()]

# --- User CRUD --- #
async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(
        select(models.User).filter(models.User.username == username)
    )
    return result.scalars().first()

async def create_user(db: AsyncSession, user_create: schemas.UserCreate, hashed_password_in: str) -> models.User:
    db_user = models.User(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        hashed_password=hashed_password_in,
        disabled=False 
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user 