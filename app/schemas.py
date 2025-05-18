from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Union
from datetime import datetime

# --- Country Schemas ---
class CountryBase(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2 country code")
    common_name: str
    official_name: Optional[str] = None
    region: Optional[str] = None
    subregion: Optional[str] = None
    is_independent: Optional[bool] = None
    google_maps_url: Optional[HttpUrl] = None
    open_street_map_url: Optional[HttpUrl] = None
    capital_name: Optional[str] = None
    capital_latitude: Optional[float] = None
    capital_longitude: Optional[float] = None
    flag_png_url: Optional[HttpUrl] = None
    flag_svg_url: Optional[HttpUrl] = None
    flag_alt_text: Optional[str] = None
    coat_of_arms_png_url: Optional[HttpUrl] = None
    coat_of_arms_svg_url: Optional[HttpUrl] = None
    borders: Optional[List[str]] = None

class CountryCreate(CountryBase):
    pass

class CountryInDBBase(CountryBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Changed from orm_mode for Pydantic v2

class Country(CountryInDBBase):
    pass

# --- QueriedName Schemas ---
class QueriedNameBase(BaseModel):
    name_text: str = Field(..., description="The name being queried")

class QueriedNameCreate(QueriedNameBase):
    last_nationalize_fetch_at: Optional[datetime] = None

class QueriedNameInDBBase(QueriedNameBase):
    id: int
    last_nationalize_fetch_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QueriedName(QueriedNameInDBBase):
    pass

# --- NameCountryProbability Schemas ---
class NameCountryProbabilityBase(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    probability: float = Field(..., ge=0, le=1)

class NameCountryProbabilityCreate(NameCountryProbabilityBase):
    queried_name_id: int
    access_count: int = 1
    last_accessed_details_at: Optional[datetime] = None

class NameCountryProbabilityUpdate(BaseModel):
    probability: Optional[float] = Field(None, ge=0, le=1)
    access_count: Optional[int] = Field(None, gt=0)
    last_accessed_details_at: Optional[datetime] = None

class NameCountryProbabilityInDBBase(NameCountryProbabilityBase):
    id: int
    queried_name_id: int
    access_count: int
    last_accessed_details_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NameCountryProbability(NameCountryProbabilityInDBBase):
    pass # Full representation, potentially with relationships

class NameCountryProbabilityWithCountry(NameCountryProbability):
    country_details: Country

# --- API Endpoint Specific Schemas ---
class NamePredictionResponseItem(BaseModel):
    country_code: str
    common_name: str
    probability: float

class NamePredictionResponse(BaseModel):
    name: str
    countries: List[NamePredictionResponseItem]

class PopularNameItem(BaseModel):
    name_text: str
    frequency: int

class PopularNamesResponse(BaseModel):
    country_code: str
    popular_names: List[PopularNameItem]

# --- Token Schemas for JWT ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    id: int
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str

# Schema for creating a new user (input for signup)
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100) # Add email validation if needed
    full_name: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8) 