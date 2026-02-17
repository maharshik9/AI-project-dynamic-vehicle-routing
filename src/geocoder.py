"""
Geocoder module using Nominatim (OpenStreetMap) for location autocomplete.
Uses requests directly (no geopy dependency needed).
"""
import requests
from typing import List, Any


def search_location(query: str) -> List[Any]:
    """
    Search for locations matching the query string.
    Returns a list of (display_name, [lat, lon]) tuples for streamlit-searchbox.
    Biased toward Bangalore, India for relevance.
    """
    if not query or len(query) < 2:
        return []

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 5,
                "viewbox": "77.3,13.2,77.9,12.7",  # Bangalore bbox
                "bounded": 0,
                "addressdetails": 1,
            },
            headers={"User-Agent": "ai_dynamic_routing_app_v1"},
            timeout=5,
        )
        
        if response.status_code != 200:
            return []
        
        results = response.json()
        return [
            (r["display_name"], [float(r["lat"]), float(r["lon"])])
            for r in results
        ]
    except Exception as e:
        print(f"Geocoding error: {e}")
        return []
