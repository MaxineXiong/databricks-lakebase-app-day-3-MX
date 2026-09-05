# Weather MCP Server - Demonstration Examples

This document shows example natural-language queries and how the agent should respond using the weather MCP tools.

---

## 📋 **Example Query 1: Current Weather**

**User Query:**
> "What's the weather in Chicago right now?"

**Agent Tool Calls:**
```
1. get_current_weather("Chicago")
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "Current weather in Chicago, United States: 79.7°F (feels like 85.0°F), Mainly clear. Humidity: 73%, Wind: 6.9 mph.",
  "data": {
    "location": {
      "name": "Chicago",
      "country": "United States",
      "latitude": 41.85,
      "longitude": -87.65
    },
    "weather": {
      "temperature": 79.7,
      "feels_like": 85.0,
      "humidity": 73,
      "wind_speed": 6.9,
      "precipitation": 0,
      "conditions": "Mainly clear"
    }
  }
}
```

**Expected Agent Response:**
> "It's currently 79.7°F in Chicago (feels like 85°F) with mainly clear skies. Humidity is at 73% and there's a light breeze at 6.9 mph. It's a warm day with good visibility!"

---

## 📋 **Example Query 2: Will It Rain?**

**User Query:**
> "Will it rain in Seattle this weekend?"

**Agent Tool Calls:**
```
1. get_forecast("Seattle", days=3)
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "3-day forecast for Seattle, United States",
  "data": {
    "location": {"name": "Seattle", "country": "United States", ...},
    "forecast": [
      {
        "date": "2026-09-05",
        "temp_high": 68,
        "temp_low": 52,
        "precipitation_sum": 0.35,
        "precipitation_probability": 75,
        "conditions": "Moderate rain"
      },
      {
        "date": "2026-09-06",
        "temp_high": 65,
        "temp_low": 50,
        "precipitation_sum": 0.15,
        "precipitation_probability": 45,
        "conditions": "Light drizzle"
      }
    ]
  }
}
```

**Expected Agent Response:**
> "Yes, it looks like rain is very likely in Seattle this weekend. Saturday shows a 75% chance with about 0.35 inches expected (moderate rain), and Sunday has a 45% chance with lighter drizzle (0.15 inches). Temperatures will be in the mid-60s. Definitely bring an umbrella!"

---

## 📋 **Example Query 3: Should I Bring a Jacket?**

**User Query:**
> "Should I bring a jacket to Austin tomorrow?"

**Agent Tool Calls:**
```
1. get_forecast("Austin", days=1)
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "1-day forecast for Austin, United States",
  "data": {
    "forecast": [
      {
        "date": "2026-09-05",
        "temp_high": 95,
        "temp_low": 72,
        "precipitation_sum": 0.0,
        "precipitation_probability": 5,
        "conditions": "Clear sky"
      }
    ]
  }
}
```

**Expected Agent Response:**
> "It's going to be quite warm in Austin tomorrow - highs around 95°F with clear skies. During the day you definitely won't need a jacket, but if you're out late evening when it drops to 72°F, you might want a light layer. Overall, it'll be hot and sunny, so focus on sun protection instead!"

---

## 📋 **Example Query 4: Umbrella Prediction**

**User Query:**
> "Do I need an umbrella in New York tomorrow?"

**Agent Tool Calls:**
```
1. predict_umbrella_needed("New York", "2026-09-05")
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "YES, bring an umbrella to New York on 2026-09-05. High precipitation probability (65%). Conditions: Moderate rain.",
  "data": {
    "recommendation": "YES",
    "reason": "High precipitation probability (65%)",
    "forecast_details": {
      "date": "2026-09-05",
      "precipitation_probability": 65,
      "precipitation_sum": 0.25,
      "conditions": "Moderate rain"
    },
    "thresholds_used": {
      "precipitation_probability_threshold": "> 40%",
      "precipitation_amount_threshold": "> 0.1 inches"
    }
  }
}
```

**Expected Agent Response:**
> "Yes, I'd definitely recommend bringing an umbrella tomorrow in New York. There's a 65% chance of rain with about 0.25 inches expected. The forecast shows moderate rain, so you'll likely get wet without one!"

---

## 📋 **Example Query 5: Multi-Day Forecast**

**User Query:**
> "Give me a 5-day forecast for Miami"

**Agent Tool Calls:**
```
1. get_forecast("Miami", days=5)
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "5-day forecast for Miami, United States",
  "data": {
    "forecast": [
      {"date": "2026-09-04", "temp_high": 88, "temp_low": 78, "conditions": "Partly cloudy", "precipitation_probability": 30},
      {"date": "2026-09-05", "temp_high": 89, "temp_low": 79, "conditions": "Thunderstorm", "precipitation_probability": 80},
      {"date": "2026-09-06", "temp_high": 87, "temp_low": 77, "conditions": "Slight rain", "precipitation_probability": 50},
      {"date": "2026-09-07", "temp_high": 90, "temp_low": 80, "conditions": "Clear sky", "precipitation_probability": 10},
      {"date": "2026-09-08", "temp_high": 91, "temp_low": 81, "conditions": "Mainly clear", "precipitation_probability": 15}
    ]
  }
}
```

**Expected Agent Response:**
> "Here's the 5-day forecast for Miami:
> 
> - **Friday (9/4):** Highs of 88°F, partly cloudy, 30% rain chance
> - **Saturday (9/5):** Highs of 89°F, thunderstorms likely (80% chance) - stay indoors if possible
> - **Sunday (9/6):** Highs of 87°F, slight rain possible (50% chance)
> - **Monday (9/7):** Highs of 90°F, clear and sunny (10% rain)
> - **Tuesday (9/8):** Highs of 91°F, mainly clear (15% rain)
> 
> It's going to be hot and humid all week with a stormy Saturday. Pack an umbrella for the weekend!"

---

## 📋 **Example Query 6a: Weather Alert (US - Official NWS)**

**User Query:**
> "Are there any weather warnings in Chicago?"

**Agent Tool Calls:**
```
1. get_weather_alert("Chicago")
```

**Tool Response (with active NWS alert):**
```json
{
  "status": "success",
  "message": "WEATHER ALERT for Chicago, United States: Winter Storm Warning (Severe) - ...WINTER STORM WARNING IN EFFECT FROM 6 AM FRIDAY TO 6 PM CST SATURDAY...",
  "data": {
    "location": {
      "name": "Chicago",
      "country": "United States",
      "latitude": 41.85,
      "longitude": -87.65
    },
    "alert_status": "alerts_active",
    "count": 1,
    "alerts": [
      {
        "event": "Winter Storm Warning",
        "severity": "Severe",
        "urgency": "Expected",
        "headline": "...WINTER STORM WARNING IN EFFECT FROM 6 AM FRIDAY TO 6 PM CST SATURDAY...",
        "description": "Heavy snow expected. Total snow accumulations of 8 to 12 inches with locally higher amounts possible.",
        "instruction": "If you must travel, keep an extra flashlight, food, and water in your vehicle in case of an emergency.",
        "onset": "2024-01-19T06:00:00-06:00",
        "expires": "2024-01-20T18:00:00-06:00"
      }
    ],
    "source": "National Weather Service"
  }
}
```

**Expected Agent Response:**
> "⚠️ **WINTER STORM WARNING** for Chicago (issued by the National Weather Service): A severe winter storm is expected from Friday 6 AM to Saturday 6 PM. Heavy snow with 8-12 inches of accumulation is forecast. If you must travel, keep emergency supplies in your vehicle including flashlight, food, and water. Stay safe and avoid unnecessary travel during the storm!"

---

## 📋 **Example Query 6b: Weather Alert (International - Heuristic)**

**User Query:**
> "Any extreme weather in Dubai right now?"

**Agent Tool Calls:**
```
1. get_weather_alert("Dubai")
```

**Tool Response (heuristic alert for non-US location):**
```json
{
  "status": "success",
  "message": "WEATHER ADVISORY for Dubai, United Arab Emirates: Extreme heat: currently 43.2°C",
  "data": {
    "location": {
      "name": "Dubai",
      "country": "United Arab Emirates",
      "latitude": 25.26,
      "longitude": 55.31
    },
    "alert_status": "alerts_present",
    "count": 1,
    "alerts": [
      {
        "type": "extreme_heat",
        "event": "Extreme Heat",
        "severity": "Moderate",
        "message": "Extreme heat: currently 43.2°C"
      }
    ],
    "source": "Heuristic Analysis (non-US location)",
    "current_conditions": {
      "temperature": 43.2,
      "feels_like": 45.8,
      "wind_speed": 11.4,
      "humidity": 35,
      "conditions": "Clear sky"
    }
  }
}
```

**Expected Agent Response:**
> "⚠️ **EXTREME HEAT ADVISORY** for Dubai: Current temperatures are at 43.2°C (110°F) with clear skies. This is dangerous heat! If you're outdoors, seek shade frequently, stay hydrated, and avoid strenuous activity during midday hours. Indoor air-conditioned spaces are strongly recommended."

---

## 📋 **Example Query 7: Location Not Found**

**User Query:**
> "What's the weather in Atlantis?"

**Agent Tool Calls:**
```
1. get_current_weather("Atlantis")
```

**Tool Response:**
```json
{
  "status": "error",
  "message": "Location 'Atlantis' not found. Please try a different city name or be more specific (e.g., 'Paris, France')."
}
```

**Expected Agent Response:**
> "I couldn't find a location called 'Atlantis' in the weather database. Could you double-check the city name? If it's a smaller town, try including the state or country (e.g., 'Atlantis, Florida' or 'Atlantis, South Africa')."

---

## 📋 **Example Query 8: Historical Weather Data**

**User Query:**
> "What was the weather like in Chicago on January 15, 2024?"

**Agent Tool Calls:**
```
1. get_historical_weather("Chicago", "2024-01-15", "2024-01-15")
```

**Tool Response:**
```json
{
  "status": "success",
  "message": "Historical weather for Chicago, United States from 2024-01-15 to 2024-01-15",
  "data": {
    "location": {
      "name": "Chicago",
      "country": "United States",
      "latitude": 41.85,
      "longitude": -87.65
    },
    "date_range": {
      "start": "2024-01-15",
      "end": "2024-01-15"
    },
    "daily_data": [
      {
        "date": "2024-01-15",
        "temperature_high": 32.5,
        "temperature_low": 20.3,
        "temperature_mean": 26.4,
        "precipitation_sum": 0.15,
        "wind_speed_max": 18.6
      }
    ]
  }
}
```

**Expected Agent Response:**
> "On January 15, 2024, Chicago had a high of 32.5°F and a low of 20.3°F, with an average temperature of 26.4°F. There was light precipitation (0.15 inches) and maximum wind speeds reached 18.6 mph. It was a cold, blustery winter day!"

