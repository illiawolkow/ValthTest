from sqlalchemy import (Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, create_engine)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.core.config import settings # To check the dialect
from app.db_types import JsonEncodedList # Import the custom type

# Determine if we are using SQLite based on the DATABASE_URL
# This is a simple check; more robust dialect checking might be needed for other DBs
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

class Country(Base):
    __tablename__ = "countries"

    country_code = Column(String(2), primary_key=True, index=True)
    common_name = Column(Text, nullable=False)
    official_name = Column(Text)
    region = Column(Text)
    subregion = Column(Text)
    is_independent = Column(Boolean)
    google_maps_url = Column(Text)
    open_street_map_url = Column(Text)
    capital_name = Column(Text)
    capital_latitude = Column(Float)
    capital_longitude = Column(Float)
    flag_png_url = Column(Text)
    flag_svg_url = Column(Text)
    flag_alt_text = Column(Text)
    coat_of_arms_png_url = Column(Text)
    coat_of_arms_svg_url = Column(Text)
    
    if IS_SQLITE:
        borders = Column(JsonEncodedList)
    else:
        borders = Column(ARRAY(String))
        
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship (back-populates)
    name_probabilities = relationship("NameCountryProbability", back_populates="country_details")

class QueriedName(Base):
    __tablename__ = "queried_names"

    id = Column(Integer, primary_key=True, index=True)
    name_text = Column(Text, nullable=False, unique=True, index=True)
    last_nationalize_fetch_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship (back-populates)
    country_probabilities = relationship("NameCountryProbability", back_populates="queried_name_details")

class NameCountryProbability(Base):
    __tablename__ = "name_country_probabilities"

    id = Column(Integer, primary_key=True, index=True)
    queried_name_id = Column(Integer, ForeignKey("queried_names.id", ondelete="CASCADE"), nullable=False)
    country_code = Column(String(2), ForeignKey("countries.country_code", ondelete="RESTRICT"), nullable=False)
    probability = Column(Float, nullable=False)
    access_count = Column(Integer, nullable=False, default=1)
    last_accessed_details_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    queried_name_details = relationship("QueriedName", back_populates="country_probabilities")
    country_details = relationship("Country", back_populates="name_probabilities")

    __table_args__ = (UniqueConstraint('queried_name_id', 'country_code', name='_name_country_uc'),)

# Basic User Model for JWT Authentication context
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True) # Optional email
    full_name = Column(String, index=True, nullable=True) # Optional full name
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now()) 