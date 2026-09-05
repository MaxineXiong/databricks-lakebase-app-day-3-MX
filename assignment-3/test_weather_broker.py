#!/usr/bin/env python
"""
Quick test script to validate weather_broker.py functions.

Run this to check that the Open-Meteo API integration is working correctly
before deploying the full MCP server.

Usage:
    python test_weather_broker.py
"""

import sys
sys.path.insert(0, './mcp_server')

import weather_broker

def test_geocode():
    """Test location geocoding."""
    print("\n🌍 Testing geocode_location...")
    
    test_locations = ["Chicago", "Austin, TX", "Paris, France", "InvalidCity123"]
    
    for location in test_locations:
        print(f"\n  Location: {location}")
        result = weather_broker.geocode_location(location)
        
        if result["status"] == "success":
            data = result["data"]
            print(f"  ✅ Found: {data['name']}, {data['country']} ({data['latitude']}, {data['longitude']})")
        else:
            print(f"  ❌ Error: {result['message']}")

def test_current_weather():
    """Test current weather fetching."""
    print("\n\n🌤️  Testing get_current_weather...")
    
    # Chicago coordinates
    lat, lon = 41.8781, -87.6298
    
    result = weather_broker.get_current_weather(lat, lon)
    
    if result["status"] == "success":
        data = result["data"]["current"]
        print(f"  ✅ Current weather:")
        print(f"     Temperature: {data['temperature']}°C (feels like {data['feels_like']}°C)")
        print(f"     Conditions: {data['conditions']}")
        print(f"     Humidity: {data['humidity']}%")
        print(f"     Wind: {data['wind_speed']} km/h")
    else:
        print(f"  ❌ Error: {result['message']}")

def test_forecast():
    """Test forecast fetching."""
    print("\n\n📅 Testing get_forecast...")
    
    # Austin coordinates
    lat, lon = 30.2672, -97.7431
    days = 3
    
    result = weather_broker.get_forecast(lat, lon, days)
    
    if result["status"] == "success":
        data = result["data"]
        print(f"  ✅ {days}-day forecast:")
        
        for day in data["daily"]:
            print(f"     {day['date']}: {day['temp_low']}°F - {day['temp_high']}°F, {day['conditions']}")
            print(f"       Precipitation: {day['precipitation_probability']}% chance, {day['precipitation_sum']} inches")
    else:
        print(f"  ❌ Error: {result['message']}")

def test_nws_alerts():
    """Test NWS weather alerts fetching."""
    print("\n\n⚠️  Testing get_nws_alerts...")
    
    # Test US location
    print("\n  US Location (Chicago):")
    result = weather_broker.get_nws_alerts(41.8781, -87.6298)
    
    if result["status"] == "success":
        data = result["data"]
        print(f"  ✅ Alert count: {data['count']}")
        if data['count'] > 0:
            print(f"     Active alerts:")
            for alert in data['alerts'][:2]:
                print(f"       - {alert['event']} ({alert['severity']})")
        else:
            print(f"     No active alerts (all clear)")
    else:
        print(f"  ❌ Error: {result['message']}")
    
    # Test non-US location
    print("\n  Non-US Location (London):")
    result = weather_broker.get_nws_alerts(51.5074, -0.1278)
    
    if result["status"] == "success":
        data = result["data"]
        if data.get('coverage') == 'outside_us':
            print(f"  ✅ Correctly identified as outside US coverage")
        else:
            print(f"  Alert count: {data['count']}")
    else:
        print(f"  ❌ Error: {result['message']}")

def main():
    print("="*60)
    print("Weather Broker Test Suite")
    print("="*60)
    
    try:
        test_geocode()
        test_current_weather()
        test_forecast()
        test_nws_alerts()
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
