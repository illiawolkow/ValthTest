from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    NATIONALIZE_API_BASE_URL: str = "https://api.nationalize.io/"
    RESTCOUNTRIES_API_BASE_URL: str = "https://restcountries.com/v3.1/"
    API_V1_STR: str = "/api/v1"

    model_config = {
        "env_file": ".env.example",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 