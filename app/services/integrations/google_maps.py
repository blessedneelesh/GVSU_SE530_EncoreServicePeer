from urllib.parse import quote_plus
import httpx
from fastapi import HTTPException, status

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

# OpenStreetMap requires a descriptive User-Agent header for free API usage
HEADERS = {
    "User-Agent": "EncoreConcertService/1.0 (GVSU-SE530-Project)"
}


def build_google_maps_url(query: str) -> str:
    """
    Generates an official clickable Google Maps link for a venue or address.
    Uses Google Maps Universal URLs (100% free, no API key required).
    """
    encoded_query = quote_plus(query)
    return f"https://www.google.com/maps/search/?api=1&query={encoded_query}"


async def get_venue_coordinates(address: str) -> dict:
    """
    Converts a venue name or street address into latitude/longitude coordinates
    and a Google Maps link for free without requiring an API key.
    """
    if not address or not address.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Venue address cannot be empty."
        )

    params = {
        "q": address.strip(),
        "format": "jsonv2",
        "limit": 1,
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
        try:
            response = await client.get(NOMINATIM_SEARCH_URL, params=params)
            response.raise_for_status()
            results = response.json()
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to the geocoding service."
            )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find coordinates for venue address: '{address}'"
        )

    top_match = results[0]
    lat = float(top_match["lat"])
    lon = float(top_match["lon"])

    return {
        "address": top_match.get("display_name", address),
        "latitude": lat,
        "longitude": lon,
        "google_maps_url": build_google_maps_url(f"{lat},{lon}"),
    }