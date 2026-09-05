"""
Weather data broker using Open-Meteo API.

This module handles all HTTP calls to the Open-Meteo API and returns
clean, normalized dictionaries. The MCP server tools stay thin - all
API interaction, geocoding, parsing, and error handling happens here.

Open-Meteo is a free, open-source weather API that requires NO API key:
- 10,000 requests/day (non-commercial)
- Current conditions, forecasts, historical data
- Global coverage
- Documentation: https://open-meteo.com/

API endpoint structure:
- Forecast API: https://api.open-meteo.com/v1/forecast
- Geocoding API: https://geocoding-api.open-meteo.com/v1/search

All functions return dicts with a consistent structure:
- Success: {"status": "success", "data": {...}, "message": "..."}
- Error: {"status": "error", "message": "...", "details": "..."}
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger("weather-broker")

# Open-Meteo API endpoints (no authentication required)
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"

# Request timeout in seconds
TIMEOUT = 10


def geocode_location(location: str) -> dict:
    """
    Convert a location string (city name, address, etc.) to latitude/longitude
    coordinates using Open-Meteo's geocoding API.
    
    Args:
        location: Location string (e.g., "Chicago", "Austin, TX", "Paris, France")
    
    Returns:
        dict with status and either coordinates or error message:
        - Success: {"status": "success", "data": {"latitude": float, "longitude": float, "name": str, "country": str}}
        - Error: {"status": "error", "message": str}
    """
    try:
        response = requests.get(
            GEOCODING_API,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("results"):
            return {
                "status": "error",
                "message": f"Location '{location}' not found. Please try a different city name or be more specific (e.g., 'Paris, France').",
            }
        
        result = data["results"][0]
        return {
            "status": "success",
            "data": {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "name": result["name"],
                "country": result.get("country", "Unknown"),
                "admin1": result.get("admin1", ""),  # State/province
            },
        }
    
    except requests.Timeout:
        return {
            "status": "error",
            "message": "Geocoding request timed out. Please try again.",
        }
    except requests.RequestException as e:
        logger.exception("Geocoding API request failed")
        return {
            "status": "error",
            "message": f"Failed to geocode location: {str(e)}",
        }
    except Exception as e:
        logger.exception("Unexpected error in geocoding")
        return {
            "status": "error",
            "message": f"Unexpected error during geocoding: {str(e)}",
        }


def get_current_weather(latitude: float, longitude: float) -> dict:
    """
    Fetch current weather conditions for given coordinates from Open-Meteo API.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        dict with status and weather data:
        - Success: {"status": "success", "data": {"temperature": float, "conditions": str, ...}}
        - Error: {"status": "error", "message": str}
    """
    try:
        response = requests.get(
            FORECAST_API,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        
        data = response.json()
        current = data.get("current", {})
        
        # Map WMO weather codes to human-readable conditions
        weather_code = current.get("weather_code", 0)
        conditions = _weather_code_to_description(weather_code)
        
        return {
            "status": "success",
            "data": {
                "current": {
                    "temperature": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "precipitation": current.get("precipitation", 0),
                    "conditions": conditions,
                    "weather_code": weather_code,
                    "timestamp": current.get("time"),
                },
                "timezone": data.get("timezone", "UTC"),
            },
        }
    
    except requests.Timeout:
        return {
            "status": "error",
            "message": "Weather API request timed out. Please try again.",
        }
    except requests.RequestException as e:
        logger.exception("Weather API request failed")
        return {
            "status": "error",
            "message": f"Failed to fetch current weather: {str(e)}",
        }
    except Exception as e:
        logger.exception("Unexpected error fetching current weather")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }


def get_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    """
    Fetch weather forecast for given coordinates from Open-Meteo API.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        days: Number of forecast days (1-16, default 7)
    
    Returns:
        dict with status and forecast data:
        - Success: {"status": "success", "data": {"daily": [...]}}
        - Error: {"status": "error", "message": str}
    """
    # Clamp days to valid range
    days = max(1, min(16, days))
    
    try:
        response = requests.get(
            FORECAST_API,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
                "forecast_days": days,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        
        data = response.json()
        daily = data.get("daily", {})
        
        # Parse daily forecast into structured records
        forecast_days = []
        times = daily.get("time", [])
        
        for i, date_str in enumerate(times):
            weather_code = daily.get("weather_code", [])[i]
            forecast_days.append({
                "date": date_str,
                "temp_high": daily.get("temperature_2m_max", [])[i],
                "temp_low": daily.get("temperature_2m_min", [])[i],
                "precipitation_sum": daily.get("precipitation_sum", [])[i],
                "precipitation_probability": daily.get("precipitation_probability_max", [])[i],
                "wind_speed_max": daily.get("wind_speed_10m_max", [])[i],
                "conditions": _weather_code_to_description(weather_code),
                "weather_code": weather_code,
            })
        
        return {
            "status": "success",
            "data": {
                "daily": forecast_days,
                "timezone": data.get("timezone", "UTC"),
            },
        }
    
    except requests.Timeout:
        return {
            "status": "error",
            "message": "Forecast API request timed out. Please try again.",
        }
    except requests.RequestException as e:
        logger.exception("Forecast API request failed")
        return {
            "status": "error",
            "message": f"Failed to fetch forecast: {str(e)}",
        }
    except Exception as e:
        logger.exception("Unexpected error fetching forecast")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }


def _weather_code_to_description(code: int) -> str:
    """
    Convert WMO weather code to human-readable description.
    
    WMO codes: https://open-meteo.com/en/docs
    """
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return weather_codes.get(code, "Unknown")


def get_nws_alerts(latitude: float, longitude: float) -> dict:
    """
    Fetch active weather alerts from the National Weather Service API.
    
    The NWS API provides official weather warnings, watches, and advisories
    for locations within the United States and its territories.
    
    NOTE: NWS API only covers the United States. For international locations,
    this will return a graceful message indicating no alerts are available.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        dict with status and alert data:
        - Success: {"status": "success", "data": {"alerts": [...], "count": int}}
        - Error: {"status": "error", "message": str}
        - No alerts: {"status": "success", "data": {"alerts": [], "count": 0}}
    """
    try:
        # NWS API endpoint for alerts by geographic point
        url = "https://api.weather.gov/alerts/active"
        params = {
            "point": f"{latitude},{longitude}",
            "status": "actual",  # Exclude test alerts
        }
        
        # NWS requires a User-Agent header
        headers = {
            "User-Agent": "WeatherMCPServer/1.0 (Databricks Weather Assistant)"
        }
        
        logger.info(f"Fetching NWS alerts for point: {latitude},{longitude}")
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        
        # NWS API returns 400 or 404 for locations outside US jurisdiction
        if response.status_code in [400, 404]:
            return {
                "status": "success",
                "data": {
                    "alerts": [],
                    "count": 0,
                    "coverage": "outside_us",
                    "message": "Location is outside NWS coverage area (US only)",
                },
            }
        
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant alert information
        features = data.get("features", [])
        alerts = []
        
        for feature in features:
            props = feature.get("properties", {})
            
            # Skip if alert has ended
            if props.get("status") == "Actual" and props.get("messageType") != "Cancel":
                alert = {
                    "event": props.get("event", "Unknown"),
                    "severity": props.get("severity", "Unknown"),
                    "urgency": props.get("urgency", "Unknown"),
                    "certainty": props.get("certainty", "Unknown"),
                    "headline": props.get("headline", ""),
                    "description": props.get("description", ""),
                    "instruction": props.get("instruction", ""),
                    "onset": props.get("onset", ""),
                    "expires": props.get("expires", ""),
                    "areas": props.get("areaDesc", ""),
                }
                alerts.append(alert)
        
        return {
            "status": "success",
            "data": {
                "alerts": alerts,
                "count": len(alerts),
                "coverage": "us",
                "source": "National Weather Service",
            },
        }
    
    except requests.exceptions.Timeout:
        logger.error("NWS API request timed out")
        return {
            "status": "error",
            "message": "Weather alert service request timed out. Please try again.",
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"NWS API request failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to fetch weather alerts: {str(e)}",
        }


def get_historical_weather(lat: float, lon: float, start_date: str, end_date: Optional[str] = None) -> dict:
    """
    Fetch historical weather data for a location between two dates.
    
    Uses Open-Meteo's Archive API to retrieve past weather observations including
    temperature, precipitation, humidity, wind speed, and conditions.
    
    Args:
        lat: Latitude of the location
        lon: Longitude of the location
        start_date: Start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format (defaults to start_date for single day)
    
    Returns:
        dict with status and historical data:
        - Success: {"status": "success", "data": {"daily": [...], "timezone": str}}
        - Error: {"status": "error", "message": str}
    
    Note:
        - Historical data is available from 1940 to approximately 5 days ago
        - Date range cannot exceed 366 days
        - All times are in the location's local timezone
    """
    logger.info(f"Fetching historical weather for ({lat}, {lon}) from {start_date} to {end_date or start_date}")
    
    # Validate dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else start_dt
    except ValueError as e:
        return {
            "status": "error",
            "message": f"Invalid date format. Use YYYY-MM-DD: {str(e)}",
        }
    
    # Check date range
    if end_dt < start_dt:
        return {
            "status": "error",
            "message": "End date cannot be before start date.",
        }
    
    days_diff = (end_dt - start_dt).days
    if days_diff > 366:
        return {
            "status": "error",
            "message": "Date range cannot exceed 366 days.",
        }
    
    # Check that dates are not too recent (Archive API typically has ~5 day delay)
    today = datetime.now().date()
    if start_dt.date() > today - timedelta(days=5):
        return {
            "status": "error",
            "message": "Historical data is only available for dates at least 5 days in the past. For recent data, use get_current_weather or get_forecast.",
        }
    
    # Prepare API request
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date or start_date,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,snowfall_sum,precipitation_hours,weathercode,windspeed_10m_max,windgusts_10m_max",
        "timezone": "auto",
    }
    
    try:
        response = requests.get(ARCHIVE_API, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Parse daily data
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        
        if not dates:
            return {
                "status": "error",
                "message": "No historical data available for the specified dates.",
            }
        
        # Build structured daily data
        daily_data = []
        for i, date in enumerate(dates):
            weathercode = daily["weathercode"][i]
            daily_data.append({
                "date": date,
                "temp_high": daily["temperature_2m_max"][i],
                "temp_low": daily["temperature_2m_min"][i],
                "temp_mean": daily["temperature_2m_mean"][i],
                "precipitation_sum": daily["precipitation_sum"][i],
                "rain_sum": daily["rain_sum"][i],
                "snowfall_sum": daily["snowfall_sum"][i],
                "precipitation_hours": daily["precipitation_hours"][i],
                "wind_speed_max": daily["windspeed_10m_max"][i],
                "wind_gusts_max": daily["windgusts_10m_max"][i],
                "weathercode": weathercode,
                "conditions": _weather_code_to_description(weathercode),
            })
        
        return {
            "status": "success",
            "data": {
                "daily": daily_data,
                "timezone": data.get("timezone", "UTC"),
            },
        }
    
    except requests.exceptions.Timeout:
        logger.error("Archive API request timed out")
        return {
            "status": "error",
            "message": "Historical weather request timed out. Please try again.",
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Archive API request failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to fetch historical weather data: {str(e)}",
        }
