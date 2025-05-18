import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session # For type hinting if using db_session directly
from unittest.mock import patch # For older style mocking if needed, but pytest-mock's mocker is preferred

from app import schemas, crud, models # For type hinting expected response schemas and crud
from app.core.config import settings

# Mock data for external APIs
# ===========================
MOCK_NATIONALIZE_JOHN_SUCCESS = {
    "name": "John",
    "country": [
        {"country_id": "US", "probability": 0.082},
        {"country_id": "GB", "probability": 0.056},
        {"country_id": "AU", "probability": 0.049},
    ]
}

MOCK_RESTCOUNTRIES_US_SUCCESS = [{
    "cca2": "US",
    "name": {"common": "United States", "official": "United States of America"},
    "region": "Americas",
    "subregion": "Northern America",
    "independent": True,
    "maps": {"googleMaps": "https://goo.gl/maps/e8M246zY4BSjkjAv6", "openStreetMaps": "https://www.openstreetmap.org/relation/148838"},
    "capital": ["Washington, D.C."],
    "capitalInfo": {"latlng": [38.89, -77.04]},
    "flags": {"png": "https://flagcdn.com/w320/us.png", "svg": "https://flagcdn.com/us.svg", "alt": "The flag of the United States of America..."},
    "coatOfArms": {"png": "https://mainfacts.com/media/images/coats_of_arms/us.png", "svg": "https://mainfacts.com/media/images/coats_of_arms/us.svg"},
    "borders": ["CAN", "MEX"]
}]

MOCK_RESTCOUNTRIES_GB_SUCCESS = [{
    "cca2": "GB",
    "name": {"common": "United Kingdom", "official": "United Kingdom of Great Britain and Northern Ireland"},
    "region": "Europe",
}]
MOCK_RESTCOUNTRIES_AU_SUCCESS = [{
    "cca2": "AU",
    "name": {"common": "Australia", "official": "Commonwealth of Australia"},
    "region": "Oceania",
}]

MOCK_NATIONALIZE_NONAME_EMPTY = {
    "name": "NonExistentNameAbc",
    "country": []
}

# Tests for /names/ endpoint
# ==========================
@pytest.mark.asyncio
async def test_get_name_nationalities_success(authenticated_client: AsyncClient, mocker, db_session: Session):
    """Test successful retrieval of name nationalities."""
    test_name = "John"
    
    # Clean up any existing cache for this name to ensure mock is hit
    existing_queried_name = crud.get_queried_name(db_session, name_text=test_name)
    if existing_queried_name:
        db_session.query(models.NameCountryProbability).filter_by(queried_name_id=existing_queried_name.id).delete()
        # It's generally better to delete dependent objects first, or rely on DB cascade if configured.
        # However, for this test, we mainly want to ensure the external API mock is hit.
        db_session.delete(existing_queried_name)
        db_session.commit()

    mocker.patch("app.routers.names.fetch_nationalities_by_name", return_value=MOCK_NATIONALIZE_JOHN_SUCCESS)
    mock_fetch_country_details = mocker.patch("app.routers.names.fetch_country_details")

    def side_effect_fetch_country_details(country_code_param):
        # This side effect should return what the actual fetch_country_details returns: a schemas.CountryCreate instance or None
        # The actual fetch_country_details in external_apis.py does the transformation from raw API to CountryCreate.
        # So, this mock should either replicate that transformation or the mock data should already be in CountryCreate shape.
        
        raw_data = None
        if country_code_param == "US":
            raw_data = MOCK_RESTCOUNTRIES_US_SUCCESS[0]
        elif country_code_param == "GB":
            raw_data = MOCK_RESTCOUNTRIES_GB_SUCCESS[0]
        elif country_code_param == "AU":
            raw_data = MOCK_RESTCOUNTRIES_AU_SUCCESS[0]
        
        if raw_data:
            # Perform the transformation similar to what fetch_country_details does
            return schemas.CountryCreate(
                country_code=raw_data.get("cca2"),
                common_name=raw_data.get("name", {}).get("common"),
                official_name=raw_data.get("name", {}).get("official"),
                region=raw_data.get("region"),
                subregion=raw_data.get("subregion"),
                is_independent=raw_data.get("independent"),
                google_maps_url=raw_data.get("maps", {}).get("googleMaps"),
                open_street_map_url=raw_data.get("maps", {}).get("openStreetMaps"),
                capital_name=raw_data.get("capital", [None])[0] if raw_data.get("capital") else None,
                capital_latitude=raw_data.get("capitalInfo", {}).get("latlng", [None, None])[0],
                capital_longitude=raw_data.get("capitalInfo", {}).get("latlng", [None, None])[1],
                flag_png_url=raw_data.get("flags", {}).get("png"),
                flag_svg_url=raw_data.get("flags", {}).get("svg"),
                flag_alt_text=raw_data.get("flags", {}).get("alt"),
                coat_of_arms_png_url=raw_data.get("coatOfArms", {}).get("png"),
                coat_of_arms_svg_url=raw_data.get("coatOfArms", {}).get("svg"),
                borders=raw_data.get("borders")
            )
        return None
        
    mock_fetch_country_details.side_effect = side_effect_fetch_country_details

    response = await authenticated_client.get("/names/", params={"name": test_name})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_name
    assert len(data["countries"]) == 3
    assert data["countries"][0]["country_code"] == "US"
    assert data["countries"][0]["common_name"] == "United States"
    assert data["countries"][0]["probability"] == 0.082

@pytest.mark.asyncio
async def test_get_name_nationalities_name_not_found(authenticated_client: AsyncClient, mocker):
    """Test retrieval when Nationalize.io returns no countries for the name."""
    mocker.patch("app.core.external_apis.fetch_nationalities_by_name", return_value=MOCK_NATIONALIZE_NONAME_EMPTY)
    
    response = await authenticated_client.get("/names/", params={"name": "NonExistentNameAbc"})
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "No country data found for name: NonExistentNameAbc"

@pytest.mark.asyncio
async def test_get_name_nationalities_missing_name_param(authenticated_client: AsyncClient):
    """Test request with missing name parameter."""
    response = await authenticated_client.get("/names/")
    assert response.status_code == 422 # FastAPI Query validation
    data = response.json()
    assert any(err["type"] == "missing" and err["loc"] == ["query", "name"] for err in data["detail"])

@pytest.mark.asyncio
async def test_get_name_nationalities_unauthenticated(client: AsyncClient): # Uses unauthenticated client
    """Test accessing /names/ without authentication."""
    response = await client.get("/names/", params={"name": "Test"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated"

# Tests for /popular-names/ endpoint
# =================================
@pytest.mark.asyncio
async def test_get_popular_names_success(authenticated_client: AsyncClient, mocker, db_session: Session):
    """Test successful retrieval of popular names for a country.
    This test relies on data being populated by a call to /names/ first.
    """
    test_name_for_popular = "JohnPopulate"
     # Clean up any existing cache for this name to ensure mock is hit
    existing_queried_name = crud.get_queried_name(db_session, name_text=test_name_for_popular)
    if existing_queried_name:
        db_session.query(models.NameCountryProbability).filter_by(queried_name_id=existing_queried_name.id).delete()
        db_session.delete(existing_queried_name)
        db_session.commit()
    
    # Step 1: Populate data using the /names/ endpoint (with mocks for external calls)
    # Use a unique name for this test to avoid interference if other tests run in parallel or affect "John"
    mock_nationalize_data = {
        "name": test_name_for_popular,
        "country": MOCK_NATIONALIZE_JOHN_SUCCESS["country"]
    }
    mocker.patch("app.routers.names.fetch_nationalities_by_name", return_value=mock_nationalize_data)
    mock_fetch_country = mocker.patch("app.routers.names.fetch_country_details")

    def side_effect_populate_country_details(country_code_param):
        raw_data = None
        if country_code_param == "US":
            raw_data = MOCK_RESTCOUNTRIES_US_SUCCESS[0]
        elif country_code_param == "GB":
            raw_data = MOCK_RESTCOUNTRIES_GB_SUCCESS[0]
        elif country_code_param == "AU":
            raw_data = MOCK_RESTCOUNTRIES_AU_SUCCESS[0]
        
        if raw_data:
            # Perform the transformation
            # Ensure all required fields for CountryCreate are present or have defaults
            gb_data_template = {"maps": {}, "capitalInfo": {"latlng": [None,None]}, "flags": {}, "coatOfArms": {}, "capital": [None]}
            
            mapped_data = {
                "country_code": raw_data.get("cca2"),
                "common_name": raw_data.get("name", {}).get("common"),
                "official_name": raw_data.get("name", {}).get("official"),
                "region": raw_data.get("region"),
                "subregion": raw_data.get("subregion"),
                "is_independent": raw_data.get("independent"),
                "google_maps_url": raw_data.get("maps", gb_data_template["maps"]).get("googleMaps"),
                "open_street_map_url": raw_data.get("maps", gb_data_template["maps"]).get("openStreetMaps"),
                "capital_name": (raw_data.get("capital") or gb_data_template["capital"])[0],
                "capital_latitude": (raw_data.get("capitalInfo", gb_data_template["capitalInfo"]).get("latlng") or [None,None])[0],
                "capital_longitude": (raw_data.get("capitalInfo", gb_data_template["capitalInfo"]).get("latlng") or [None,None])[1],
                "flag_png_url": raw_data.get("flags", gb_data_template["flags"]).get("png"),
                "flag_svg_url": raw_data.get("flags", gb_data_template["flags"]).get("svg"),
                "flag_alt_text": raw_data.get("flags", gb_data_template["flags"]).get("alt"),
                "coat_of_arms_png_url": raw_data.get("coatOfArms", gb_data_template["coatOfArms"]).get("png"),
                "coat_of_arms_svg_url": raw_data.get("coatOfArms", gb_data_template["coatOfArms"]).get("svg"),
                "borders": raw_data.get("borders")
            }
            # Filter out None values for optional fields if CountryCreate doesn't handle them well (it should)
            # mapped_data_filtered = {k: v for k, v in mapped_data.items() if v is not None}
            return schemas.CountryCreate(**mapped_data)
        return None
        
    mock_fetch_country.side_effect = side_effect_populate_country_details

    # Call /names/ to populate probabilities and access counts
    for _ in range(3): # Call 3 times to ensure access count for US with JohnPopulate is 3
        await authenticated_client.get("/names/", params={"name": test_name_for_popular})

    # Step 2: Query for popular names in US
    response = await authenticated_client.get("/popular-names/", params={"country": "US"})
    assert response.status_code == 200
    data = response.json()
    assert data["country_code"] == "US"
    # The popular names might include others if the DB is not perfectly clean for each test function
    # For more robust test, ensure JohnPopulate is the only name or check its specific frequency
    john_entry = next((item for item in data["popular_names"] if item["name_text"] == test_name_for_popular), None)
    assert john_entry is not None
    assert john_entry["frequency"] >= 3

@pytest.mark.asyncio
async def test_get_popular_names_no_data(authenticated_client: AsyncClient, mocker):
    """Test popular names when no data exists for the country."""
    # This mocks the direct CRUD function call that the endpoint uses.
    mocker.patch("app.routers.names.crud.get_popular_names_for_country", return_value=[])
    
    response = await authenticated_client.get("/popular-names/", params={"country": "ZZ"})
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "No data available for country code: ZZ"

@pytest.mark.asyncio
async def test_get_popular_names_invalid_country_code(authenticated_client: AsyncClient):
    """Test popular names with an invalid country code format."""
    response = await authenticated_client.get("/popular-names/", params={"country": "USA"})
    assert response.status_code == 422 # FastAPI Query validation
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
    
    # Check for the specific error related to the 'country' parameter pattern
    found_error = False
    for err in data["detail"]:
        # Pydantic v2 error structure might be slightly different for pattern mismatches
        # Common types include 'string_pattern_mismatch', 'value_error.str.regex'
        # Check if the location is correct and if a relevant error message or type is present
        if err.get("loc") == ["query", "country"]:
            if err.get("type") == "string_pattern_mismatch" or "pattern" in err.get("msg", "").lower():
                found_error = True
                break
    assert found_error, f"Specific pattern mismatch error for country query parameter not found in {data['detail']}"

@pytest.mark.asyncio
async def test_get_popular_names_unauthenticated(client: AsyncClient):
    """Test accessing /popular-names/ without authentication."""
    response = await client.get("/popular-names/", params={"country": "US"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated"

# Placeholder for /popular-names/ tests (to be added next)
# @pytest.mark.asyncio
# async def test_get_popular_names_success(authenticated_client: AsyncClient, mocker, db_session: Session):
#     pass