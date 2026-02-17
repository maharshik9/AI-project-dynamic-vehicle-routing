import requests
import json
import numpy as np

# Coordinates (Lat, Lon)
origin = [12.9352, 77.6245]
dest = [12.9716, 77.5946]

print(f"Origin: {origin}")
print(f"Dest: {dest}")

# Construc OSRM URL (Lon, Lat)
coord_str = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}"

params = {
    "overview": "full",
    "geometries": "geojson",
    "steps": "false",
    "alternatives": "true"
}

print(f"\nRequesting: {url}")
try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("routes"):
            print(f"Found {len(data['routes'])} routes.")
            for i, route in enumerate(data["routes"]):
                geometry = route["geometry"]["coordinates"]
                print(f"\nRoute {i+1}:")
                print(f"  Distance: {route['distance']} m")
                print(f"  Duration: {route['duration']} s")
                print(f"  Geometry Points: {len(geometry)}")
                
                # Check resolution
                if len(geometry) > 1:
                    dist_check = np.linalg.norm(np.array(geometry[0]) - np.array(geometry[1]))
                    print(f"  Dist between first two points: {dist_check:.6f}")
                else:
                    print("  Single point geometry.")
        else:
            print("No routes in response.")

    else:
        print("Error response.")
except Exception as e:
    print(f"Exception: {e}")
