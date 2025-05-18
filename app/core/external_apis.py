import httpx
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import re # Import re for regex operations

from app.core.config import settings
from app import schemas

NATIONALIZE_API_URL = settings.NATIONALIZE_API_BASE_URL
RESTCOUNTRIES_API_URL = settings.RESTCOUNTRIES_API_BASE_URL

# Regex to check for a scheme (http or https)
SCHEME_REGEX = re.compile(r"^(http|https)://", re.IGNORECASE)

def _ensure_https_url(url_string: Optional[str]) -> Optional[str]:
    """Prepends 'https://' to a URL string if it doesn't have a scheme."""
    if url_string is None:
        return None
    if not SCHEME_REGEX.match(url_string):
        # Check if it's a common case of just missing the scheme
        if "//" not in url_string and "." in url_string: # Simple check for domain-like structure
            return f"https://{url_string}"
        # If it's not a simple case or already has some malformed scheme attempt,
        # it might be better to return None or log a warning,
        # but for now, we'll try prepending.
        # Pydantic will validate it further.
        return f"https://{url_string.lstrip('/')}" # Remove leading slashes if any before prepending
    return url_string

async def fetch_nationalities_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Fetches nationality predictions for a given name from Nationalize.io."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{NATIONALIZE_API_URL}?name={name}")
            response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
            data = response.json()
            if not data.get("country"):
                return None # API returned success but no countries for the name
            return data
        except httpx.HTTPStatusError as e:
            # Log the error e.response.status_code, e.request.url
            # Depending on the error, you might want to raise HTTPException or return None
            if e.response.status_code == 429: # Rate limit
                 raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded with Nationalize.io API.")
            # For other client/server errors from the external API, we might treat it as data not found or an internal issue
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error fetching data from Nationalize.io: {e.response.status_code}")
        except httpx.RequestError as e:
            # Log the error e.request.url
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Request to Nationalize.io failed: {str(e)}")

async def fetch_country_details(country_code: str) -> Optional[schemas.CountryCreate]:
    """Fetches detailed country information from REST Countries API by country code (cca2)."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{RESTCOUNTRIES_API_URL}alpha/{country_code}")
            response.raise_for_status()
            data = response.json()
            if not data or not isinstance(data, list) or not data[0]:
                return None
            
            country_data = data[0]
            
            capital_name = None
            # REST Countries API returns capital as a list, e.g. ["Rome"]
            if country_data.get("capital") and isinstance(country_data["capital"], list) and len(country_data["capital"]) > 0:
                capital_name = country_data["capital"][0]
            elif country_data.get("capital") and isinstance(country_data["capital"], str):
                 # some entries might have capital as string directly (though API docs say list)
                 capital_name = country_data["capital"]

            capital_lat, capital_lon = None, None
            if country_data.get("capitalInfo") and country_data["capitalInfo"].get("latlng"):
                latlng = country_data["capitalInfo"]["latlng"]
                if isinstance(latlng, list) and len(latlng) == 2:
                    capital_lat, capital_lon = latlng[0], latlng[1]

            # Ensure common_name and country_code are present, as they are vital
            common_name = country_data.get("name", {}).get("common")
            cca2_code = country_data.get("cca2")

            if not common_name or not cca2_code:
                # Log this: missing essential data from RESTCountries
                print(f"Warning: Missing common_name or cca2 for {country_code} from RESTCountries API.")
                return None

            return schemas.CountryCreate(
                country_code=cca2_code,
                common_name=common_name,
                official_name=country_data.get("name", {}).get("official"),
                region=country_data.get("region"),
                subregion=country_data.get("subregion"),
                is_independent=country_data.get("independent"),
                google_maps_url=_ensure_https_url(country_data.get("maps", {}).get("googleMaps")),
                open_street_map_url=_ensure_https_url(country_data.get("maps", {}).get("openStreetMaps")),
                capital_name=capital_name,
                capital_latitude=capital_lat,
                capital_longitude=capital_lon,
                flag_png_url=_ensure_https_url(country_data.get("flags", {}).get("png")),
                flag_svg_url=_ensure_https_url(country_data.get("flags", {}).get("svg")),
                flag_alt_text=country_data.get("flags", {}).get("alt"),
                coat_of_arms_png_url=_ensure_https_url(country_data.get("coatOfArms", {}).get("png")),
                coat_of_arms_svg_url=_ensure_https_url(country_data.get("coatOfArms", {}).get("svg")),
                borders=country_data.get("borders")
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None # Country not found by code
            # Log error e.response.text for more details
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error fetching data from REST Countries ({e.response.status_code}): {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Request to REST Countries failed: {str(e)}")
        except (KeyError, IndexError, TypeError) as e:
            # Data parsing error from REST Countries response
            # Log this error for debugging with more context (e.g. country_code, problematic part of data)
            print(f"Error parsing country data for {country_code}: {str(e)}. Data: {country_data}") # print for server log
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error parsing country data from external API: {str(e)}") 