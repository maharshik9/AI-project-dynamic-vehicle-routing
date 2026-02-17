import sys
import os
import json
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.order_processing import process_orders
from src.route_optimizer import RouteOptimizer
from src.traffic_api import TrafficAPI

def test_auto_route():
    print("Testing auto-route generation...")
    
    # 1. Mock Data
    orders_json = json.dumps({
        "orders": [
            { "order_no": "O1", "address": "MG Road, Bangalore" },
            { "order_no": "O2", "address": "Koramangala, Bangalore" },
            { "order_no": "O3", "address": "Indiranagar, Bangalore" }
        ]
    }).encode('utf-8')
    
    # 2. Process Orders
    print("Processing orders...")
    results = process_orders(orders_json)
    stops = results["valid_stops"]
    stop_names = results["valid_stop_names"]
    
    if len(stops) != 3:
        print(f"FAIL: Expected 3 stops, got {len(stops)}")
        return
        
    print(f"Got {len(stops)} valid stops.")
    
    # 3. Optimize
    print("Optimizing...")
    api = TrafficAPI()
    optimizer = RouteOptimizer(api)
    
    opt_result = optimizer.optimize_order(stops, stop_names)
    optimized_stops = opt_result['stops']
    
    print(f"Optimization complete. Total duration: {opt_result['total_duration']}s")
    
    # 4. Fetch Full Route Geometry
    print("Fetching route geometry...")
    full_route = []
    
    for i in range(len(optimized_stops) - 1):
        origin = optimized_stops[i]
        dest = optimized_stops[i+1]
        
        routes = api.get_routes(origin, dest)
        if routes:
            geometry = routes[0]['geometry']
            full_route.extend(geometry)
            print(f"  Leg {i}: Got {len(geometry)} points")
        else:
            print(f"  Leg {i}: No route found")
            
    print(f"Full route has {len(full_route)} points.")
    
    if len(full_route) > 0:
        print("PASS: Route geometry generated successfully.")
    else:
        print("FAIL: No route geometry generated.")

if __name__ == "__main__":
    test_auto_route()
