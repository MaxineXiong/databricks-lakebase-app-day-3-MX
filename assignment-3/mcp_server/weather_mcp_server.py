"""
Weather MCP Server.

Exposes weather tools over MCP (Model Context Protocol) so a Databricks
Agent Bricks agent can answer natural-language weather questions:
    - get_current_weather(location)  # Current conditions for a location
    - get_forecast(location, days)   # Multi-day forecast
    - predict_umbrella_needed(location, date)  # Smart recommendation
    - get_weather_alert(location)    # Weather advisory (US NWS + international heuristics)
    - get_historical_weather(location, start_date, end_date)  # Historical weather data

These tools are backed by Open-Meteo's free weather API (see weather_broker.py),
which requires NO API key and provides global coverage with 10,000 calls/day.

Deploy this as a Databricks App (see app.yaml) so an Agent Bricks agent can
register its URL as an external MCP server.

Run locally:
    python weather_mcp_server.py
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from fastmcp import FastMCP

import weather_broker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp-server")

mcp = FastMCP("weather-assistant")

# Context variable to store request headers for accessing end-user identity
_request_context: ContextVar[dict] = ContextVar('request_context', default={})

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture HTTP headers containing end-user identity."""
    async def dispatch(self, request: Request, call_next):
        # Capture headers that Databricks injects with user identity
        headers = {
            'x-forwarded-user': request.headers.get('x-forwarded-user'),
            'x-forwarded-email': request.headers.get('x-forwarded-email'),
        }
        _request_context.set(headers)
        response = await call_next(request)
        return response


@mcp.tool
def get_current_weather(location: str) -> dict:
    """
    Get current weather conditions for a given location.
    
    This tool fetches real-time weather data including temperature, humidity,
    wind speed, and precipitation. Perfect for answering "What's the weather
    like in [location] right now?"
    
    Args:
        location: City name or location (e.g., "Chicago", "Austin, TX", "Paris, France")
    
    Returns:
        A dict with status and weather data:
        - status: "success" or "error"
        - message: Human-readable summary
        - data: Weather details (temperature, humidity, wind, conditions, etc.)
        
    Example:
        >>> get_current_weather("Chicago")
        {
            "status": "success",
            "message": "Current weather in Chicago, United States: ...",
            "data": {
                "location": {"name": "Chicago", "country": "United States", ...},
                "weather": {"temperature": 72.5, "feels_like": 70.3, ...}
            }
        }
    """
    logger.info(f"get_current_weather called for location: {location}")
    
    # Step 1: Geocode the location
    geo_result = weather_broker.geocode_location(location)
    
    if geo_result["status"] == "error":
        return {
            "status": "error",
            "message": geo_result["message"],
        }
    
    location_data = geo_result["data"]
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Step 2: Fetch current weather
    weather_result = weather_broker.get_current_weather(lat, lon)
    
    if weather_result["status"] == "error":
        return {
            "status": "error",
            "message": f"Failed to fetch weather for {location_data['name']}: {weather_result['message']}",
        }
    
    weather_data = weather_result["data"]["current"]
    
    # Step 3: Format response
    location_str = f"{location_data['name']}, {location_data['country']}"
    temp = weather_data['temperature']
    feels_like = weather_data['feels_like']
    conditions = weather_data['conditions']
    humidity = weather_data['humidity']
    wind_speed = weather_data['wind_speed']
    
    message = (
        f"Current weather in {location_str}: {temp}°C (feels like {feels_like}°C), "
        f"{conditions}. Humidity: {humidity}%, "
        f"Wind: {wind_speed} km/h."
    )
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "location": location_data,
            "weather": weather_data,
            "timezone": weather_result["data"]["timezone"],
        },
    }


@mcp.tool
def get_forecast(location: str, days: int = 7) -> dict:
    """
    Get multi-day weather forecast for a given location.
    
    Returns daily high/low temperatures, precipitation probability, and
    conditions for the next N days. Perfect for planning trips or outdoor
    activities.
    
    Args:
        location: City name or location (e.g., "Chicago", "Austin, TX")
        days: Number of forecast days (1-16, default 7)
    
    Returns:
        A dict with status and forecast data:
        - status: "success" or "error"
        - message: Human-readable summary
        - data: Daily forecast array with temp, precipitation, conditions
        
    Example:
        >>> get_forecast("Austin", days=3)
        {
            "status": "success",
            "message": "3-day forecast for Austin, United States",
            "data": {
                "location": {"name": "Austin", ...},
                "forecast": [
                    {"date": "2024-01-15", "temp_high": 75, "temp_low": 55, ...},
                    ...
                ]
            }
        }
    """
    logger.info(f"get_forecast called for location: {location}, days: {days}")
    
    # Validate days parameter
    if days < 1 or days > 16:
        return {
            "status": "error",
            "message": "Days must be between 1 and 16.",
        }
    
    # Step 1: Geocode the location
    geo_result = weather_broker.geocode_location(location)
    
    if geo_result["status"] == "error":
        return {
            "status": "error",
            "message": geo_result["message"],
        }
    
    location_data = geo_result["data"]
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Step 2: Fetch forecast
    forecast_result = weather_broker.get_forecast(lat, lon, days)
    
    if forecast_result["status"] == "error":
        return {
            "status": "error",
            "message": f"Failed to fetch forecast for {location_data['name']}: {forecast_result['message']}",
        }
    
    forecast_data = forecast_result["data"]
    
    # Step 3: Format response
    location_str = f"{location_data['name']}, {location_data['country']}"
    message = f"{days}-day forecast for {location_str}"
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "location": location_data,
            "forecast": forecast_data["daily"],
            "timezone": forecast_data["timezone"],
        },
    }


@mcp.tool
def predict_umbrella_needed(location: str, date: Optional[str] = None) -> dict:
    """
    Predict whether you'll need an umbrella for a given location and date.
    
    This is a DERIVED JUDGMENT tool - it applies reasoning on top of raw forecast
    data. Logic: recommend an umbrella if precipitation probability > 40% OR
    if precipitation amount > 0.1 inches is expected.
    
    Args:
        location: City name or location (e.g., "Chicago", "Seattle")
        date: Optional date string in YYYY-MM-DD format (defaults to tomorrow)
    
    Returns:
        A dict with status and umbrella recommendation:
        - status: "success" or "error"
        - message: Human-readable recommendation
        - data: Reasoning details (precipitation probability, amount, etc.)
        
    Example:
        >>> predict_umbrella_needed("Seattle", "2024-01-20")
        {
            "status": "success",
            "message": "YES, bring an umbrella to Seattle on 2024-01-20...",
            "data": {
                "recommendation": "YES",
                "reason": "High precipitation probability (65%)",
                ...
            }
        }
    """
    logger.info(f"predict_umbrella_needed called for location: {location}, date: {date}")
    
    # Default to tomorrow if no date provided
    if date is None:
        target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        try:
            # Validate date format
            datetime.strptime(date, "%Y-%m-%d")
            target_date = date
        except ValueError:
            return {
                "status": "error",
                "message": "Date must be in YYYY-MM-DD format (e.g., '2024-01-20').",
            }
    
    # Step 1: Geocode the location
    geo_result = weather_broker.geocode_location(location)
    
    if geo_result["status"] == "error":
        return {
            "status": "error",
            "message": geo_result["message"],
        }
    
    location_data = geo_result["data"]
    
    # Step 2: Calculate how many days ahead the target date is
    today = datetime.now().date()
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    days_ahead = (target_date_obj - today).days
    
    # Validate date is within forecast range (0-16 days from now)
    if days_ahead < 0:
        return {
            "status": "error",
            "message": f"Cannot predict for past dates. Please choose today or a future date.",
        }
    
    if days_ahead > 16:
        return {
            "status": "error",
            "message": f"Forecast only available for the next 16 days. {target_date} is {days_ahead} days away.",
        }
    
    # Fetch forecast for exactly the number of days needed (minimum 1, maximum 16)
    forecast_result = weather_broker.get_forecast(
        location_data["latitude"],
        location_data["longitude"],
        days=min(16, max(1, days_ahead + 1))  # Cap at 16 days max
    )
    
    if forecast_result["status"] == "error":
        return {
            "status": "error",
            "message": f"Failed to fetch forecast: {forecast_result['message']}",
        }
    
    # Step 3: Find the target date in forecast
    daily_forecast = forecast_result["data"]["daily"]
    target_day_forecast = None
    
    for day_forecast in daily_forecast:
        if day_forecast["date"] == target_date:
            target_day_forecast = day_forecast
            break
    
    if target_day_forecast is None:
        return {
            "status": "error",
            "message": f"No forecast available for {target_date}. Please choose a date within the next 16 days.",
        }
    
    # Step 4: Apply umbrella logic
    precip_prob = target_day_forecast["precipitation_probability"]
    precip_sum = target_day_forecast["precipitation_sum"]
    conditions = target_day_forecast["conditions"]
    
    # Decision thresholds
    PROB_THRESHOLD = 40  # > 40% precipitation probability
    AMOUNT_THRESHOLD = 2.5  # > 2.5 mm expected (~0.1 inches)
    
    needs_umbrella = precip_prob > PROB_THRESHOLD or precip_sum > AMOUNT_THRESHOLD
    
    if needs_umbrella:
        if precip_prob > PROB_THRESHOLD:
            reason = f"High precipitation probability ({precip_prob}%)"
        else:
            reason = f"Significant precipitation expected ({precip_sum} mm)"
        
        recommendation = "YES"
        message = (
            f"YES, bring an umbrella to {location_data['name']} on {target_date}. "
            f"{reason}. Conditions: {conditions}."
        )
    else:
        recommendation = "NO"
        reason = f"Low precipitation risk ({precip_prob}% probability, {precip_sum} mm expected)"
        message = (
            f"NO, you probably don't need an umbrella in {location_data['name']} on {target_date}. "
            f"{reason}. Conditions: {conditions}."
        )
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "location": location_data,
            "date": target_date,
            "recommendation": recommendation,
            "reason": reason,
            "forecast_details": target_day_forecast,
            "thresholds_used": {
                "precipitation_probability_threshold": f"> {PROB_THRESHOLD}%",
                "precipitation_amount_threshold": f"> {AMOUNT_THRESHOLD} mm",
            },
        },
    }


@mcp.tool
def get_weather_alert(location: str) -> dict:
    """
    Get weather alerts for any location worldwide.
    
    For US locations: Fetches official warnings, watches, and advisories from the
    National Weather Service (NWS) including tornado warnings, winter storm watches,
    flood advisories, and more.
    
    For international locations: Analyzes current conditions and forecast to identify
    extreme weather (heat, cold, high winds, heavy rain) and provides advisory alerts.
    
    Args:
        location: City name or location (e.g., "Chicago", "Miami, FL")
    
    Returns:
        A dict with status and alert data:
        - status: "success" or "error"
        - message: Human-readable summary
        - data: Official NWS alert details including severity, urgency, descriptions
        
    Example:
        >>> get_weather_alert("Chicago")
        {
            "status": "success",
            "message": "2 active weather alerts for Chicago, United States",
            "data": {
                "alerts": [
                    {
                        "event": "Winter Storm Warning",
                        "severity": "Severe",
                        "headline": "...WINTER STORM WARNING IN EFFECT...",
                        "description": "..."
                    }
                ],
                "count": 2
            }
        }
    """
    logger.info(f"get_weather_alert called for location: {location}")
    
    # Step 1: Geocode the location
    geo_result = weather_broker.geocode_location(location)
    
    if geo_result["status"] == "error":
        return {
            "status": "error",
            "message": geo_result["message"],
        }
    
    location_data = geo_result["data"]
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Step 2: Try to fetch NWS alerts (US only)
    alerts_result = weather_broker.get_nws_alerts(lat, lon)
    
    if alerts_result["status"] == "error":
        return {
            "status": "error",
            "message": f"Failed to fetch weather alerts: {alerts_result['message']}",
        }
    
    location_str = f"{location_data['name']}, {location_data['country']}"
    alert_data = alerts_result["data"]
    
    # Step 3: Handle locations outside US coverage - use heuristic alerts
    if alert_data.get("coverage") == "outside_us":
        logger.info(f"Location outside US - using heuristic alerts for {location}")
        
        # Fetch current weather and 3-day forecast for heuristic analysis
        current_result = weather_broker.get_current_weather(lat, lon)
        forecast_result = weather_broker.get_forecast(lat, lon, days=3)
        
        if current_result["status"] == "error" or forecast_result["status"] == "error":
            return {
                "status": "error",
                "message": "Failed to fetch weather data for alert analysis.",
            }
        
        current = current_result["data"]["current"]
        forecast = forecast_result["data"]["daily"]
        
        # Check for notable conditions
        heuristic_alerts = []
        
        # Extreme heat (>35°C / 95°F)
        if current["temperature"] > 35:
            heuristic_alerts.append({
                "type": "extreme_heat",
                "event": "Extreme Heat",
                "severity": "Moderate",
                "message": f"Extreme heat: currently {current['temperature']}°C",
            })
        
        # Extreme cold (<-7°C / 20°F)
        if current["temperature"] < -7:
            heuristic_alerts.append({
                "type": "extreme_cold",
                "event": "Extreme Cold",
                "severity": "Moderate",
                "message": f"Extreme cold: currently {current['temperature']}°C",
            })
        
        # High winds (>40 km/h / 25 mph)
        if current["wind_speed"] > 40:
            heuristic_alerts.append({
                "type": "high_winds",
                "event": "High Winds",
                "severity": "Moderate",
                "message": f"High winds: {current['wind_speed']} km/h",
            })
        
        # Heavy rain expected in next 3 days (>12.7 mm / 0.5 inches)
        for day in forecast:
            if day["precipitation_sum"] > 12.7:
                heuristic_alerts.append({
                    "type": "heavy_rain",
                    "event": "Heavy Rain Expected",
                    "severity": "Moderate",
                    "message": f"Heavy rain expected on {day['date']}: {day['precipitation_sum']} mm",
                })
                break  # Only report once
        
        # High precipitation probability in next 3 days (>70%)
        for day in forecast:
            if day["precipitation_probability"] > 70:
                heuristic_alerts.append({
                    "type": "rain_likely",
                    "event": "Rain Very Likely",
                    "severity": "Minor",
                    "message": f"Rain very likely on {day['date']}: {day['precipitation_probability']}% chance",
                })
                break
        
        # Format heuristic alert response
        count = len(heuristic_alerts)
        if count == 0:
            message = f"No significant weather alerts for {location_str}. Conditions are normal."
            alert_status = "all_clear"
        elif count == 1:
            alert = heuristic_alerts[0]
            message = f"WEATHER ADVISORY for {location_str}: {alert['message']}"
            alert_status = "alerts_present"
        else:
            alert_messages = " | ".join([a["message"] for a in heuristic_alerts])
            message = f"WEATHER ADVISORY for {location_str}: {alert_messages}"
            alert_status = "alerts_present"
        
        return {
            "status": "success",
            "message": message,
            "data": {
                "location": location_data,
                "alert_status": alert_status,
                "alerts": heuristic_alerts,
                "count": count,
                "source": "Heuristic Analysis (non-US location)",
                "current_conditions": current,
            },
        }
    
    # Step 4: Format NWS alert response (US locations)
    alerts = alert_data["alerts"]
    count = alert_data["count"]
    
    # Format message based on alert count
    if count == 0:
        message = f"No active weather alerts for {location_str}. Conditions are normal."
        alert_status = "all_clear"
    elif count == 1:
        alert = alerts[0]
        message = f"WEATHER ALERT for {location_str}: {alert['event']} ({alert['severity']}) - {alert['headline']}"
        alert_status = "alerts_active"
    else:
        # Multiple alerts
        event_list = ", ".join([a["event"] for a in alerts[:3]])  # Show first 3
        if count > 3:
            event_list += f" and {count - 3} more"
        message = f"{count} active weather alerts for {location_str}: {event_list}"
        alert_status = "alerts_active"
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "location": location_data,
            "alert_status": alert_status,
            "alerts": alerts,
            "count": count,
            "source": "National Weather Service",
        },
    }


@mcp.tool
def get_historical_weather(location: str, start_date: str, end_date: Optional[str] = None) -> dict:
    """
    Get historical weather data for a location.
    
    Fetches past weather observations including temperature highs/lows, precipitation,
    wind speed, and conditions. Perfect for comparing past weather patterns, analyzing
    trends, or answering "What was the weather like on [date]?" questions.
    
    Args:
        location: City name or location (e.g., "Chicago", "Paris, France")
        start_date: Start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format (defaults to start_date for single day)
    
    Returns:
        A dict with status and historical data:
        - status: "success" or "error"
        - message: Human-readable summary
        - data: Daily historical weather data (temps, precipitation, wind, conditions)
        
    Example:
        >>> get_historical_weather("Chicago", "2024-01-15", "2024-01-17")
        {
            "status": "success",
            "message": "Historical weather for Chicago, United States from 2024-01-15 to 2024-01-17",
            "data": {
                "location": {"name": "Chicago", ...},
                "historical": [
                    {"date": "2024-01-15", "temp_high": 32, "temp_low": 20, ...},
                    ...
                ]
            }
        }
    
    Note:
        - Historical data available from 1940 to approximately 5 days ago
        - Date range cannot exceed 366 days
        - For recent data, use get_current_weather or get_forecast instead
    """
    logger.info(f"get_historical_weather called for location: {location}, dates: {start_date} to {end_date or start_date}")
    
    # Step 1: Geocode the location
    geo_result = weather_broker.geocode_location(location)
    
    if geo_result["status"] == "error":
        return {
            "status": "error",
            "message": geo_result["message"],
        }
    
    location_data = geo_result["data"]
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Step 2: Fetch historical weather
    historical_result = weather_broker.get_historical_weather(lat, lon, start_date, end_date)
    
    if historical_result["status"] == "error":
        return {
            "status": "error",
            "message": f"Failed to fetch historical weather for {location_data['name']}: {historical_result['message']}",
        }
    
    historical_data = historical_result["data"]
    
    # Step 3: Format response
    location_str = f"{location_data['name']}, {location_data['country']}"
    if end_date and end_date != start_date:
        date_range = f"from {start_date} to {end_date}"
    else:
        date_range = f"on {start_date}"
    
    message = f"Historical weather for {location_str} {date_range}"
    
    return {
        "status": "success",
        "message": message,
        "data": {
            "location": location_data,
            "date_range": {
                "start": start_date,
                "end": end_date or start_date,
            },
            "historical": historical_data["daily"],
            "timezone": historical_data["timezone"],
        },
    }


if __name__ == "__main__":
    # Add middleware to capture request headers for end-user identity
    if hasattr(mcp, 'app') and mcp.app is not None:
        mcp.app.add_middleware(RequestContextMiddleware)
    
    # Databricks Apps route external HTTP traffic to this port via app.yaml;
    # streamable-http is the transport Databricks' MCP client/gateway expects
    # (see the "Host your own MCP" doc linked in the module docstring above).
    port = int(os.getenv("DATABRICKS_APP_PORT", os.getenv("PORT", 8000)))
    mcp.run(transport="http", host="0.0.0.0", port=port)
