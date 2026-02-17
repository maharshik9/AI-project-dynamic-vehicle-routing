import json
import time
import requests
from typing import List, Dict, Any, Tuple, Optional

def load_orders_from_json(file_content: bytes) -> List[Dict[str, str]]:
    """
    Parses the JSON content and extracts the list of orders.
    Expected format: {"orders": [{"order_no": "...", "address": "..."}, ...]}
    """
    try:
        data = json.loads(file_content)
        return data.get("orders", [])
    except json.JSONDecodeError:
        return []

def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Geocodes an address string to (lat, lon) using Nominatim.
    Returns None if geocoding fails.
    Respects API limits with a 1-second delay.
    """
    if not address:
        return None

    try:
        # Respect Nominatim usage policy
        time.sleep(1.0) 
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 0
        }
        headers = {
            "User-Agent": "ai_dynamic_vehicle_routing_bot/1.0" 
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            results = response.json()
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                return lat, lon
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
        
    return None

def process_orders(file_content: bytes) -> Dict[str, Any]:
    """
    Orchestrates the loading and geocoding of orders.
    Returns a dictionary with:
    - 'valid_stops': List of [lat, lon]
    - 'valid_stop_names': List of "Order No - Address"
    - 'failed_orders': List of order objects that failed geocoding
    - 'total_processed': count
    """
    orders = load_orders_from_json(file_content)
    
    valid_stops = []
    valid_stop_names = []
    failed_orders = []
    
    for order in orders:
        order_no = order.get("order_no", "Unknown")
        address = order.get("address", "")
        
        coords = geocode_address(address)
        
        if coords:
            valid_stops.append(list(coords))
            valid_stop_names.append(f"{order_no} - {address}")
        else:
            failed_orders.append(order)
            
    return {
        "valid_stops": valid_stops,
        "valid_stop_names": valid_stop_names,
        "failed_orders": failed_orders,
        "total_processed": len(orders)
    }
