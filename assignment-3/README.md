# Weather MCP Server

A **Model Context Protocol (MCP) server** that exposes weather data tools for Databricks Agent Bricks agents. Built with **FastMCP** and powered by the free **Open-Meteo API** (no API key required).

---

## 🌦️ **What This Project Does**

This project is my submission for **Day 3 Homework: Build Weather MCP Server** under the [DataExpert.io](https://www.dataexpert.io) program [The Rise of the AI Data Engineer](https://learn.dataexpert.io/program/the-one-week-beginners-databricks-boot-camp-7129).

The weather MCP server enables a Databricks Agent Bricks agent to answer natural-language weather questions like:
- *"What's the weather in Chicago right now?"*
- *"Will it rain in Austin this weekend?"*
- *"Should I bring a jacket to Seattle tomorrow?"*
- *"Give me a 5-day forecast for New York"*

The agent automatically decides which tools to call and in what order, then synthesizes the results into a helpful answer.

---

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│  User Query: "Will it rain in Chicago tomorrow?"            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         Databricks Agent Bricks Agent                        │
│  (Interprets intent, decides tool calls, synthesizes answer) │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼ MCP Tool Calls
┌─────────────────────────────────────────────────────────────┐
│            Weather MCP Server (FastMCP)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tools (weather_mcp_server.py):                      │   │
│  │  • get_current_weather(location)                     │   │
│  │  • get_forecast(location, days)                      │   │
│  │  • predict_umbrella_needed(location, date)           │   │
│  │  • get_weather_alert(location)                       │   │
│  │  • get_historical_weather(location, start, end)      │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                         │
│                     ▼ Calls                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Broker (weather_broker.py):                         │   │
│  │  • geocode_location(location)                        │   │
│  │  • get_current_weather(lat, lon)                     │   │
│  │  • get_forecast(lat, lon, days)                      │   │
│  │  • get_nws_alerts(lat, lon)                          │   │
│  │  • get_historical_weather(lat, lon, start, end)      │   │
│  └──────────────────┬───────────────────────────────────┘   │
└────────────────────┼────────────────────────────────────────┘
                     │ HTTP Requests
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                     External Weather APIs                     │
│                                                               │
│  Open-Meteo API (Global):                                    │
│    • https://api.open-meteo.com/v1/forecast                  │
│    • https://archive-api.open-meteo.com/v1/archive           │
│    • https://geocoding-api.open-meteo.com/v1/search          │
│                                                               │
│  National Weather Service API (US only):                      │
│    • https://api.weather.gov/alerts/active                   │
└──────────────────────────────────────────────────────────────┘
```

### **Key Design Principles**

1. **Thin MCP tools** - Tools in `weather_mcp_server.py` focus on orchestration and formatting. All HTTP calls and parsing happen in `weather_broker.py`.
2. **Separation of concerns** - The broker module is testable independently and can be swapped for a different weather API without touching the MCP layer.
3. **No secrets required** - Open-Meteo is completely free and needs no API key, so there's zero secrets management overhead.
4. **Consistent error handling** - All functions return `{"status": "success"/"error", "message": "...", "data": {...}}` for predictable agent behavior.

---

## 🛠️ **MCP Tools Exposed**

### **1. get_current_weather(location)**
Fetches real-time weather conditions for a given location.

**Args:**
- `location` (str): City name or location (e.g., `"Chicago"`, `"Austin, TX"`, `"Paris, France"`)

**Returns:**
```json
{
  "status": "success",
  "message": "Current weather in Chicago, United States: 72.5°C (feels like 70.3°C), Partly cloudy. Humidity: 65%, Wind: 8.5 km/h.",
  "data": {
    "location": {"name": "Chicago", "country": "United States", "latitude": 41.85, "longitude": -87.65},
    "weather": {
      "temperature": 72.5,
      "feels_like": 70.3,
      "humidity": 65,
      "wind_speed": 8.5,
      "precipitation": 0,
      "conditions": "Partly cloudy"
    },
    "timezone": "America/Chicago"
  }
}
```

---

### **2. get_forecast(location, days=7)**
Fetches a multi-day weather forecast.

**Args:**
- `location` (str): City name or location
- `days` (int): Number of forecast days (1-16, default 7)

**Returns:**
```json
{
  "status": "success",
  "message": "7-day forecast for Austin, United States",
  "data": {
    "location": {"name": "Austin", "country": "United States", ...},
    "forecast": [
      {
        "date": "2024-01-15",
        "temp_high": 75,
        "temp_low": 55,
        "precipitation_sum": 0.1,
        "precipitation_probability": 30,
        "wind_speed_max": 12,
        "conditions": "Partly cloudy"
      },
      ...
    ],
    "timezone": "America/Chicago"
  }
}
```

---

### **3. predict_umbrella_needed(location, date=None)**
**DERIVED JUDGMENT TOOL** - Recommends whether to bring an umbrella based on forecast logic.

**Logic:**
- Recommend umbrella if **precipitation probability > 40%** OR **precipitation amount > 0.1 inches**.
- This is where we show reasoning beyond raw API data.

**Args:**
- `location` (str): City name
- `date` (str, optional): Target date in YYYY-MM-DD format (defaults to tomorrow)

**Returns:**
```json
{
  "status": "success",
  "message": "YES, bring an umbrella to Seattle on 2024-01-20. High precipitation probability (65%). Conditions: Moderate rain.",
  "data": {
    "location": {"name": "Seattle", "country": "United States", ...},
    "date": "2024-01-20",
    "recommendation": "YES",
    "reason": "High precipitation probability (65%)",
    "forecast_details": {...},
    "thresholds_used": {
      "precipitation_probability_threshold": "> 40%",
      "precipitation_amount_threshold": "> 2.5 mm"
    }
  }
}
```

---

### **4. get_weather_alert(location)** *(Bonus Tool - Hybrid System)*
Provides weather alerts for **any location worldwide** using a hybrid approach:

#### **For US Locations:**
Fetches **official alerts** from the **National Weather Service (NWS)** API:
- Tornado Warnings & Watches
- Winter Storm Warnings
- Flood Advisories
- Heat Advisories
- And all other NOAA-issued alerts

#### **For International Locations:**
Performs **heuristic analysis** on current conditions and 3-day forecast:
- **Extreme Heat** (>35°C / 95°F)
- **Extreme Cold** (<-7°C / 20°F)
- **High Winds** (>40 km/h / 25 mph)
- **Heavy Rain Expected** (>12.7 mm / 0.5 inches)
- **High Precipitation Probability** (>70%)

**Args:**
- `location` (str): City name (works globally)

**Returns (US location with NWS alerts):**
```json
{
  "status": "success",
  "message": "2 active weather alerts for Chicago, United States: Winter Storm Warning, Wind Chill Advisory",
  "data": {
    "location": {"name": "Chicago", "country": "United States", ...},
    "alert_status": "alerts_active",
    "count": 2,
    "alerts": [
      {
        "event": "Winter Storm Warning",
        "severity": "Severe",
        "urgency": "Expected",
        "headline": "...WINTER STORM WARNING IN EFFECT FROM 6 AM FRIDAY TO 6 PM CST SATURDAY...",
        "description": "Heavy snow expected. Total snow accumulations of 8 to 12 inches...",
        "instruction": "If you must travel, keep an extra flashlight, food, and water...",
        "onset": "2024-01-19T06:00:00-06:00",
        "expires": "2024-01-20T18:00:00-06:00"
      }
    ],
    "source": "National Weather Service"
  }
}
```

**Returns (International location with heuristic alerts):**
```json
{
  "status": "success",
  "message": "WEATHER ADVISORY for Dubai, United Arab Emirates: Extreme heat: currently 43.2°C",
  "data": {
    "location": {"name": "Dubai", "country": "United Arab Emirates", ...},
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
    "current_conditions": {"temperature": 43.2, "wind_speed": 11.4, ...}
  }
}
```

---

### **5. get_historical_weather(location, start_date, end_date)** *(Historical Data Tool)*
Retrieves historical weather data for a specific location and date range using the Open-Meteo Archive API.

**Coverage:**
- Data available from **1940 to ~5 days ago**
- Cannot query recent days (data needs time to be finalized)

**Validation:**
- Date format: YYYY-MM-DD (ISO 8601)
- Start date must be at least 5 days ago
- Date range cannot exceed 366 days

**Args:**
- `location` (str): City name or location
- `start_date` (str): Start date in YYYY-MM-DD format
- `end_date` (str): End date in YYYY-MM-DD format

**Returns:**
```json
{
  "status": "success",
  "message": "Historical weather for Chicago, United States from 2024-01-15 to 2024-01-17",
  "data": {
    "location": {"name": "Chicago", "country": "United States", ...},
    "date_range": {
      "start": "2024-01-15",
      "end": "2024-01-17"
    },
    "historical": [
      {
        "date": "2024-01-15",
        "temperature_high": 32.5,
        "temperature_low": 20.3,
        "temperature_mean": 26.4,
        "precipitation_sum": 0.15,
        "wind_speed_max": 18.6
      },
      {
        "date": "2024-01-16",
        "temperature_high": 28.8,
        "temperature_low": 18.1,
        "temperature_mean": 23.5,
        "precipitation_sum": 0.0,
        "wind_speed_max": 12.4
      },
      ...
    ],
    "timezone": "America/Chicago"
  }
}
```

**Error Example (date too recent):**
```json
{
  "status": "error",
  "message": "Start date must be at least 5 days ago. Historical data is not yet available for recent dates."
}
```

---

## 🔌 **Weather APIs Used**

### **1. Open-Meteo API** (Primary - Current, Forecast & Historical)
- **URL:** https://open-meteo.com/
- **Authentication:** None required (completely free)
- **Rate limits:** 10,000 requests/day (non-commercial use)
- **Coverage:** Global
- **Data:**
  - Current conditions & forecasts (Forecast API)
  - Historical weather from 1940 to ~5 days ago (Archive API)
- **Used by:** `get_current_weather`, `get_forecast`, `predict_umbrella_needed`, `get_historical_weather`

#### **Why Open-Meteo?**
1. **Zero setup friction** - No signup, no API key, no credit card.
2. **Perfect for learning** - You can build and test the entire pipeline immediately.
3. **Production-ready** - If you need more calls later, they offer paid tiers, but the free tier is generous.

---

### **2. National Weather Service API** (US Alerts)
- **URL:** https://api.weather.gov/
- **Authentication:** None required (free, official US government API)
- **Rate limits:** Reasonable for non-commercial use (no hard limit published)
- **Coverage:** United States and territories only
- **Data:** Official weather warnings, watches, and advisories from NOAA
- **Used by:** `get_weather_alert` (for US locations)

#### **Why NWS?**
1. **Official alerts** - Direct from NOAA, the authoritative source for US weather warnings.
2. **No signup** - Just like Open-Meteo, zero authentication required.
3. **Comprehensive** - Includes tornado warnings, winter storm watches, flood advisories, heat alerts, and more.
4. **Trusted data** - Government-issued alerts that emergency services rely on.

---

### **3. Heuristic Alert System** (International Alerts)
- **Coverage:** Global (automatic fallback for non-US locations)
- **Data sources:** Open-Meteo current weather + 3-day forecast
- **Used by:** `get_weather_alert` (for international locations)

#### **Why Heuristic System?**
1. **Global coverage** - Works anywhere in the world, not just the US.
2. **Real-time analysis** - Checks actual current conditions and upcoming forecast.
3. **Configurable thresholds** - Detects extreme heat, cold, winds, and heavy rain.
4. **Automatic fallback** - Seamlessly activates when NWS doesn't cover the location.

---

## 📁 **Project Structure**

```
assignment-3/
├── mcp_server/
│   ├── weather_mcp_server.py   # FastMCP server with 5 tools
│   ├── weather_broker.py        # HTTP adapter for Open-Meteo & NWS APIs
│   ├── requirements.txt         # Python dependencies
│   └── app.yaml                 # Databricks App config
├── test_weather_broker.py       # Unit tests for broker functions
├── setup_secrets.py             # (Not needed for Open-Meteo, kept for reference)
├── README.md                    # This file (comprehensive documentation)
├── DEMONSTRATION.md             # Live test results and example outputs
└── AGENT_SYSTEM_PROMPT.md       # Recommended agent system prompt template
```

---

## 🚀 **Setup & Deployment**

### **Prerequisites**
- Databricks workspace
- Agent Bricks enabled (for agent deployment)

### **Step 1: Deploy the MCP Server as a Databricks App**

```bash
cd assignment-3/mcp_server
databricks apps create weather-mcp-server
databricks apps deploy weather-mcp-server --source-code-path .
```

The app will be accessible at a URL like:
```
https://<workspace>.cloud.databricks.com/apps/weather-mcp-server
```

### **Step 2: Register the MCP Server as an External MCP**

Follow [Connect agents to external MCPs and tools](https://docs.databricks.com/en/agents/) documentation:

1. In your workspace, go to **AI Gateway** > **MCPs** > **Add MCP** (or **Register external MCP**).
2. Paste the `weather-mcp-server` app's URL from Step 1 as the server endpoint (streamable HTTP):
   ```
   https://<workspace>.cloud.databricks.com/apps/weather-mcp-server
   ```
3. Give it a name (e.g., `weather-assistant`) and save. Databricks will introspect the server and list the 5 tools:
   - `get_current_weather`
   - `get_forecast`
   - `predict_umbrella_needed`
   - `get_weather_alert`
   - `get_historical_weather`
4. Grant your Agent Bricks agent (created in Step 3) access to this MCP server via Unity Catalog permissions, if prompted.

---

### **Step 3: Build the Agent Bricks Agent**

1. In your workspace sidebar, go to **Agents** > **Agent Bricks** > **Create agent**.
2. Choose the **Custom LLM** (or **Multi-agent supervisor**, if you want to combine this with other agents) agent type.
3. Under **Tools**, add:
   - The `weather-assistant` MCP server you registered in Step 2 (you can select all 5 tools, or a curated subset).
   - Optionally, additional **Unity Catalog function tools** or **Genie spaces** if you have location preferences, travel data, or other context to enhance weather recommendations.
4. Give the agent a system prompt (see **Agent System Prompt** section below for a recommended template).
5. **Evaluate and iterate**: Agent Bricks auto-evaluates the agent against sample prompts (e.g., "What's the weather in Chicago?", "Will I need an umbrella in Seattle tomorrow?"). Use this to tune the system prompt and tool selection.
6. **Deploy the agent** and chat with it! Example queries:
   - *"What's the weather in Austin right now?"*
   - *"Give me a 5-day forecast for New York"*
   - *"Should I bring an umbrella to Seattle tomorrow?"*
   - *"Are there any weather alerts for Miami?"*
   - *"What was the weather like in Paris on January 15, 2024?"*

---

## 🤖 **Agent System Prompt**

The agent system prompt is included in [AGENT_SYSTEM_PROMPT.md](./AGENT_SYSTEM_PROMPT.md). This prompt includes:

* Tool usage guidelines for all 5 MCP tools
* Best practices for handling user queries
* Example response patterns
* Instructions for US vs. international weather alerts
* Historical weather query guidelines

Refer to the file for the complete prompt in use when configuring the weather agent.

---

## ✅ **Demonstration (Example Queries)**

Demonstration examples with actual tool calls and agent responses are provided in [DEMONSTRATION.md](./DEMONSTRATION.md). This includes:

* Example queries for all 5 MCP tools
* Tool call sequences and parameters
* Sample agent responses

Refer to the file for demo example queries and responses.

---

## 🎯 **Key Agent Behaviors**

1. **No hallucination** - The agent ALWAYS calls a tool rather than guessing weather data.

2. **Error handling** - When a tool fails, the agent explains the error and suggests how to fix it (e.g., "try a different location").

3. **Conversational summaries** - The agent doesn't dump raw JSON; it summarizes key points in natural language.

4. **Context-aware** - The agent understands implied timeframes ("tomorrow", "this weekend") and calls the right tool.

5. **Helpful advice** - The agent goes beyond raw data to give actionable recommendations (e.g., "bring an umbrella", "stay hydrated").

---

## 🧪 **Testing Locally (Optional)**

To test the MCP server locally before deploying:

```bash
cd assignment-3/mcp_server
pip install -r requirements.txt
python weather_mcp_server.py
```

The server will start on `http://localhost:8000` (or the default FastMCP port).

You can test tool calls with `curl`:

```bash
curl -X POST http://localhost:8000/tools/get_current_weather \
  -H "Content-Type: application/json" \
  -d '{"location": "Chicago"}'
```

---

## 🔒 **Security & Secrets Management**

**This implementation requires NO secrets** because Open-Meteo is completely free and unauthenticated.

If you were using a different weather API that requires an API key (e.g., WeatherAPI.com), you would:

1. **Store the key as a Databricks secret:**
   ```python
   from databricks.sdk import WorkspaceClient
   w = WorkspaceClient()
   
   # Create scope if it doesn't exist
   if not any(scope.name == 'weather' for scope in w.secrets.list_scopes()):
       w.secrets.create_scope(scope='weather')
   
   # Store API key
   w.secrets.put_secret(scope='weather', key='api-key')
   ```

2. **Fetch it in `weather_broker.py`:**
   ```python
   from databricks.sdk import WorkspaceClient
   import os
   
   _w = WorkspaceClient()
   _SECRET_SCOPE = os.environ.get("WEATHER_SECRET_SCOPE", "weather")
   
   def _get_api_key():
       secret = _w.secrets.get_secret(scope=_SECRET_SCOPE, key="api-key")
       return secret.value
   ```

3. **Never commit the key to git.**

---

## 📊 **Error Handling**

All broker functions return a consistent structure:

**Success:**
```json
{
  "status": "success",
  "message": "Human-readable summary",
  "data": {...}
}
```

**Error:**
```json
{
  "status": "error",
  "message": "What went wrong and how to fix it"
}
```

The MCP tools check `status` and either:
- Return the data to the agent (success case)
- Return a user-friendly error message (error case)

This prevents the agent from hallucinating or guessing when a tool call fails.

---

## 📚 **References**

- **Open-Meteo API Docs:** https://open-meteo.com/en/docs
- **FastMCP Documentation:** https://github.com/jlowin/fastmcp
- **Databricks Agent Bricks:** https://docs.databricks.com/en/agents/
- **MCP Protocol Spec:** https://modelcontextprotocol.io/


