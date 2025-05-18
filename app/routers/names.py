from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app import crud, schemas, models
from app.database import get_db
from app.core.external_apis import fetch_nationalities_by_name, fetch_country_details
from app.auth.dependencies import get_current_active_user

router = APIRouter(
    tags=["names_and_countries"],
    # dependencies=[Depends(get_current_active_user)], # Uncomment to protect all routes
)

@router.get("/names/", response_model=schemas.NamePredictionResponse)
async def get_name_nationalities(
    name: str = Query(..., min_length=1, description="Name to predict nationality for"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name parameter is missing or empty.")

    db_queried_name = await crud.get_queried_name(db, name_text=name)
    current_time = datetime.now(timezone.utc)

    if db_queried_name and db_queried_name.last_nationalize_fetch_at:
        last_fetch_at = db_queried_name.last_nationalize_fetch_at
        if last_fetch_at.tzinfo is None or last_fetch_at.tzinfo.utcoffset(last_fetch_at) is None:
            last_fetch_at = last_fetch_at.replace(tzinfo=timezone.utc)
        
        if (current_time - last_fetch_at) <= timedelta(days=1):
            probabilities = await crud.get_name_country_probabilities(db, queried_name_id=db_queried_name.id)
            if probabilities:
                response_items = []
                for prob in probabilities:
                    await crud.increment_name_country_access(db, queried_name_id=db_queried_name.id, country_code=prob.country_code)
                    response_items.append(schemas.NamePredictionResponseItem(
                        country_code=prob.country_details.country_code,
                        common_name=prob.country_details.common_name,
                        probability=prob.probability
                    ))
                return schemas.NamePredictionResponse(name=name, countries=response_items)

    nationalize_data = await fetch_nationalities_by_name(name)
    if not nationalize_data or not nationalize_data.get("country"):
        if db_queried_name:
            await crud.update_queried_name_fetch_time(db, name_text=name, fetch_time=current_time)
        else:
            await crud.create_queried_name(db, schemas.QueriedNameCreate(name_text=name, last_nationalize_fetch_at=current_time))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No country data found for name: {name}")

    if not db_queried_name:
        db_queried_name = await crud.create_queried_name(db, schemas.QueriedNameCreate(name_text=name, last_nationalize_fetch_at=current_time))
    else:
        db_queried_name = await crud.update_queried_name_fetch_time(db, name_text=name, fetch_time=current_time)
        if not db_queried_name:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update or create queried name record.")

    response_countries = []
    for country_pred in nationalize_data["country"]:
        country_code = country_pred.get("country_id")
        probability = country_pred.get("probability")

        if not country_code or probability is None:
            print(f"Skipping malformed country prediction for name {name}: {country_pred}")
            continue

        db_country = await crud.get_country(db, country_code=country_code)
        if not db_country:
            country_details_ext = await fetch_country_details(country_code)
            if country_details_ext:
                db_country = await crud.create_country(db, country_create=country_details_ext)
            else:
                print(f"Warning: Could not fetch details for country_code {country_code} from RESTCountries API for name {name}.")
                continue
        
        existing_prob = await crud.get_name_country_probability(db, queried_name_id=db_queried_name.id, country_code=country_code)
        if existing_prob:
            await crud.update_name_country_probability(
                db, 
                queried_name_id=db_queried_name.id, 
                country_code=country_code, 
                probability_update=schemas.NameCountryProbabilityUpdate(probability=probability, access_count=(existing_prob.access_count or 0)+1, last_accessed_details_at=current_time)
            )
        else:
            await crud.create_name_country_probability(db, schemas.NameCountryProbabilityCreate(
                queried_name_id=db_queried_name.id,
                country_code=country_code,
                probability=probability,
                access_count=1,
                last_accessed_details_at=current_time
            ))

        response_countries.append(schemas.NamePredictionResponseItem(
            country_code=db_country.country_code,
            common_name=db_country.common_name,
            probability=probability
        ))
    
    if not response_countries:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No valid country data could be processed for name: {name} after fetching.")

    return schemas.NamePredictionResponse(name=name, countries=response_countries)

@router.get("/popular-names/", response_model=schemas.PopularNamesResponse)
async def get_popular_names(
    country: str = Query(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2 country code (e.g., US, UA)"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if not country:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Country parameter is missing or empty.")

    popular_names_data = await crud.get_popular_names_for_country(db, country_code=country, limit=5)

    if not popular_names_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No data available for country code: {country}")

    return schemas.PopularNamesResponse(country_code=country, popular_names=popular_names_data) 