from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta

from . import models, schemas

# --- QueriedName CRUD --- #
def get_queried_name(db: Session, name_text: str) -> Optional[models.QueriedName]:
    return db.query(models.QueriedName).filter(models.QueriedName.name_text == name_text).first()

def create_queried_name(db: Session, name_create: schemas.QueriedNameCreate) -> models.QueriedName:
    db_name = models.QueriedName(
        name_text=name_create.name_text,
        last_nationalize_fetch_at=name_create.last_nationalize_fetch_at
    )
    db.add(db_name)
    db.commit()
    db.refresh(db_name)
    return db_name

def update_queried_name_fetch_time(db: Session, name_text: str, fetch_time: datetime) -> Optional[models.QueriedName]:
    db_name = get_queried_name(db, name_text=name_text)
    if db_name:
        db_name.last_nationalize_fetch_at = fetch_time
        db_name.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_name)
    return db_name

# --- Country CRUD --- #
def get_country(db: Session, country_code: str) -> Optional[models.Country]:
    return db.query(models.Country).filter(models.Country.country_code == country_code).first()

def create_country(db: Session, country_create: schemas.CountryCreate) -> models.Country:
    country_data = country_create.model_dump()
    
    url_fields = [
        "google_maps_url",
        "open_street_map_url",
        "flag_png_url",
        "flag_svg_url",
        "coat_of_arms_png_url",
        "coat_of_arms_svg_url",
    ]
    
    for field in url_fields:
        if field in country_data and country_data[field] is not None:
            country_data[field] = str(country_data[field])
            
    db_country = models.Country(**country_data)
    db.add(db_country)
    db.commit()
    db.refresh(db_country)
    return db_country

# --- NameCountryProbability CRUD --- #
def get_name_country_probabilities(db: Session, queried_name_id: int) -> List[models.NameCountryProbability]:
    return (
        db.query(models.NameCountryProbability)
        .filter(models.NameCountryProbability.queried_name_id == queried_name_id)
        .options(joinedload(models.NameCountryProbability.country_details))
        .order_by(desc(models.NameCountryProbability.probability))
        .all()
    )

def get_name_country_probability(db: Session, queried_name_id: int, country_code: str) -> Optional[models.NameCountryProbability]:
    return (
        db.query(models.NameCountryProbability)
        .filter(
            models.NameCountryProbability.queried_name_id == queried_name_id,
            models.NameCountryProbability.country_code == country_code
        )
        .first()
    )

def create_name_country_probability(db: Session, probability_create: schemas.NameCountryProbabilityCreate) -> models.NameCountryProbability:
    db_prob = models.NameCountryProbability(**probability_create.model_dump())
    db.add(db_prob)
    db.commit()
    db.refresh(db_prob)
    return db_prob

def update_name_country_probability(
    db: Session, 
    queried_name_id: int, 
    country_code: str, 
    probability_update: schemas.NameCountryProbabilityUpdate
) -> Optional[models.NameCountryProbability]:
    db_prob = get_name_country_probability(db, queried_name_id, country_code)
    if db_prob:
        update_data = probability_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_prob, key, value)
        db_prob.updated_at = datetime.utcnow()
        if 'access_count' in update_data and update_data['access_count'] is not None:
            # If access_count is explicitly provided, use it. 
            # Otherwise, if only probability or last_accessed is updated, don't reset it.
            # The router logic should handle incrementing access_count properly.
            pass 
        elif probability_update.access_count is None and 'access_count' not in update_data: # ensure access_count is not reset to None if not provided
            pass # do nothing to access_count if not in update
        
        db.commit()
        db.refresh(db_prob)
    return db_prob

def increment_name_country_access(db: Session, queried_name_id: int, country_code: str) -> Optional[models.NameCountryProbability]:
    db_prob = get_name_country_probability(db, queried_name_id, country_code)
    if db_prob:
        db_prob.access_count = (db_prob.access_count or 0) + 1
        db_prob.last_accessed_details_at = datetime.utcnow()
        db_prob.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_prob)
    return db_prob


def get_popular_names_for_country(db: Session, country_code: str, limit: int = 5) -> List[schemas.PopularNameItem]:
    results = (
        db.query(
            models.QueriedName.name_text,
            func.sum(models.NameCountryProbability.access_count).label("total_frequency")
        )
        .join(models.NameCountryProbability, models.QueriedName.id == models.NameCountryProbability.queried_name_id)
        .filter(models.NameCountryProbability.country_code == country_code)
        .group_by(models.QueriedName.name_text)
        .order_by(desc("total_frequency"))
        .limit(limit)
        .all()
    )
    return [schemas.PopularNameItem(name_text=name, frequency=freq) for name, freq in results]

# --- User CRUD (Placeholder for auth) --- #
def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Placeholder: Fetches a user by username. Implement properly for actual user auth."""
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user_create: schemas.UserCreate, hashed_password_in: str) -> models.User:
    """Creates a new user in the database."""
    db_user = models.User(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        hashed_password=hashed_password_in,
        disabled=False # New users are active by default, can be overridden if needed
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user 