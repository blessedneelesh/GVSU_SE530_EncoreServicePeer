import httpx
from fastapi import HTTPException, status
from app.services.integrations.google_maps import get_venue_coordinates

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Maps standard WMO weather codes returned by Open-Meteo to readable descriptions
WMO_WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


async def get_concert_weather(latitude: float, longitude: float) -> dict:
    """
    Fetches current weather for a concert venue's coordinates using Open-Meteo.
    Requires no API key.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Weather service is currently unavailable."
            )

    current = data.get("current_weather")
    if not current:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from weather provider."
        )

    temp_c = current.get("temperature")
    temp_f = round((temp_c * 9 / 5) + 32, 1) if temp_c is not None else None
    code = current.get("weathercode")

    return {
        "temperature_celsius": temp_c,
        "temperature_fahrenheit": temp_f,
        "windspeed_kmh": current.get("windspeed"),
        "weathercode": code,
        "condition": WMO_WEATHER_DESCRIPTIONS.get(code, "Unknown"),
    }


async def get_weather_for_venue(address: str) -> dict:
    """
    Convenience helper: takes a venue address, geocodes it for free via
    google_maps.py, and returns both location details and current weather.
    """
    location = await get_venue_coordinates(address)
    weather = await get_concert_weather(
        latitude=location["latitude"],
        longitude=location["longitude"],
    )
    return {
        "location": location,
        "weather": weather,
    }