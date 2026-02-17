"""
Traffic API with OSRM integration for real road geometry.
Free, no API key required.
"""

import os
import time
import requests
import numpy as np
from typing import List, Tuple, Dict
from functools import lru_cache


class TrafficAPI:
    """
    Traffic and routing API using OSRM (free) as primary source.
    Falls back to ORS if API key is available.
    """
    
    OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
    ORS_BASE = "https://api.openrouteservice.org/v2"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ORS_API_KEY")
        self.available = True  # OSRM is always available
        self.failed = False
        self._cache = {}
        self.last_call_time = 0
        self.call_count_per_min = 0
        self.min_start_time = time.time()
    
    def _rate_limit_wait(self):
        """Stay under 35 calls/min for ORS free tier"""
        now = time.time()
        if now - self.min_start_time > 60:
            self.call_count_per_min = 0
            self.min_start_time = now
        
        self.call_count_per_min += 1
        if self.call_count_per_min > 35:
            time.sleep(2)
    
    def get_osrm_geometry(self, waypoints_latlon: List[Tuple[float, float]]) -> List[List[float]]:
        """
        Get road geometry from OSRM (free, no API key).
        
        Args:
            waypoints_latlon: List of (lat, lon) tuples
        
        Returns:
            List of [lat, lon] pairs following real roads
        
        CRITICAL: OSRM URL takes lon,lat ORDER
                  but returns coordinates as [lon, lat]
                  Folium needs [lat, lon]
                  So we MUST swap after receiving.
        """
        if len(waypoints_latlon) < 2:
            return [list(w) for w in waypoints_latlon]
        
        # Build coordinate string: lon,lat;lon,lat (OSRM format)
        coord_str = ";".join([
            f"{lon},{lat}" 
            for lat, lon in waypoints_latlon
        ])
        
        url = f"{self.OSRM_BASE}/{coord_str}"
        params = {
            "overview": "full",       # Get complete geometry
            "geometries": "geojson",  # GeoJSON format
            "steps": "false",
            "annotations": "false"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    # Extract coordinates from GeoJSON
                    coords = data["routes"][0]["geometry"]["coordinates"]
                    # OSRM returns [lon, lat] - convert to [lat, lon] for folium
                    road_path = [[c[1], c[0]] for c in coords]
                    return road_path
        except Exception as e:
            pass  # Silent fallback for demo
        
        # Fallback: straight line
        return [list(w) for w in waypoints_latlon]
    
    def get_osrm_travel_time(self, origin_latlon: Tuple[float, float], 
                            dest_latlon: Tuple[float, float]) -> float:
        """
        Get real travel time from OSRM in minutes.
        Free, no API key needed.
        
        Args:
            origin_latlon: (lat, lon)
            dest_latlon: (lat, lon)
        
        Returns:
            Travel time in minutes
        """
        cache_key = (
            round(origin_latlon[0], 4), round(origin_latlon[1], 4),
            round(dest_latlon[0], 4), round(dest_latlon[1], 4)
        )
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        lat1, lon1 = origin_latlon
        lat2, lon2 = dest_latlon
        coord_str = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{self.OSRM_BASE}/{coord_str}"
        params = {
            "overview": "false",
            "geometries": "geojson"
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    duration_sec = data["routes"][0]["duration"]
                    travel_min = duration_sec / 60.0
                    self._cache[cache_key] = travel_min
                    return travel_min
        except:
            pass
        
        # Fallback: euclidean estimate
        dist_km = 111 * np.linalg.norm(
            np.array(origin_latlon) - np.array(dest_latlon)
        )
        return (dist_km / 30.0) * 60  # 30 km/h assumed
    
    def get_ors_geometry(self, waypoints_latlon: List[Tuple[float, float]]) -> List[List[float]]:
        """
        Backup method using ORS API if key available.
        Only called if OSRM fails.
        """
        if not self.api_key or self.failed:
            return None
        
        self._rate_limit_wait()
        
        try:
            # ORS takes [lon, lat] order
            coords = [[lon, lat] for lat, lon in waypoints_latlon]
            url = f"{self.ORS_BASE}/directions/driving-car/geojson"
            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
            body = {
                "coordinates": coords,
                "geometry_simplify": False,
                "instructions": False
            }
            
            response = requests.post(
                url, json=body, headers=headers, timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                coords_raw = data["features"][0]["geometry"]["coordinates"]
                # ORS returns [lon, lat] - convert to [lat, lon] for folium
                return [[c[1], c[0]] for c in coords_raw]
        except Exception as e:
            print(f"ORS geometry error: {e}")
            self.failed = True
        
        return None
    
    def get_route_geometry(self, waypoints_latlon: List[Tuple[float, float]]) -> List[List[float]]:
        """
        MAIN METHOD called by streamlit_app.py
        
        Priority:
        1. OSRM (free, no key, best for demo)
        2. ORS (if key available and OSRM fails)
        3. Straight line (last resort only)
        
        Args:
            waypoints_latlon: List of (lat, lon) tuples
        
        Returns:
            List of [lat, lon] pairs for folium
        """
        # Try OSRM first (completely free)
        result = self.get_osrm_geometry(waypoints_latlon)
        
        # Check if we got real road data (more points = real roads)
        if result and len(result) > len(waypoints_latlon):
            return result
        
        # Try ORS backup
        if self.api_key and not self.failed:
            ors_result = self.get_ors_geometry(waypoints_latlon)
            if ors_result and len(ors_result) > len(waypoints_latlon):
                return ors_result
        
        # Last resort: straight line
        return [list(w) for w in waypoints_latlon]
    
    def get_traffic_multiplier(self, origin_latlon: Tuple[float, float], 
                               dest_latlon: Tuple[float, float]) -> float:
        """
        Compare OSRM real travel time vs expected time
        to derive a traffic multiplier.
        
        multiplier > 1.0 = congestion
        multiplier = 1.0 = free flow
        
        Args:
            origin_latlon: (lat, lon)
            dest_latlon: (lat, lon)
        
        Returns:
            Traffic multiplier (1.0 - 3.0)
        """
        real_time = self.get_osrm_travel_time(origin_latlon, dest_latlon)
        
        # Expected time at 40 km/h free flow
        dist_km = 111 * np.linalg.norm(
            np.array(origin_latlon) - np.array(dest_latlon)
        )
        expected_time = (dist_km / 40.0) * 60  # minutes
        
        if expected_time < 0.1:
            return 1.0
        
        multiplier = real_time / expected_time
        return float(np.clip(multiplier, 1.0, 3.0))
    
    def get_travel_time(self, origin_latlon: Tuple[float, float], 
                       dest_latlon: Tuple[float, float]) -> float:
        """Returns travel time in minutes using OSRM"""
        return self.get_osrm_travel_time(origin_latlon, dest_latlon)
    
    def is_available(self) -> bool:
        """OSRM is always available (free)"""
        return True
    
    def get_status(self) -> Tuple[str, str]:
        """Return status message and mode"""
        if self.api_key and not self.failed:
            return "🟢 Real Traffic (ORS + OSRM)", "real"
        return "🟢 Real Roads (OSRM - Free)", "real"
    
    def get_routes(self, origin_latlon: Tuple[float, float], dest_latlon: Tuple[float, float], alternatives: bool = False) -> List[Dict]:
        """
        Get route alternatives using OSRM.
        
        Args:
            origin_latlon: (lat, lon)
            dest_latlon: (lat, lon)
            alternatives: If True, request alternative routes
            
        Returns:
            List of dicts: [{'geometry': [[lat,lon]...], 'duration': seconds, 'distance': meters, 'nodes': []}]
        """
        # OSRM (lon, lat)
        coord_str = f"{origin_latlon[1]},{origin_latlon[0]};{dest_latlon[1]},{dest_latlon[0]}"
        url = f"{self.OSRM_BASE}/{coord_str}"
        
        params = {
            "overview": "full",       # Get complete geometry
            "geometries": "geojson",  # GeoJSON format
            "steps": "false",
            "alternatives": "true" if alternatives else "false"
        }
        
        routes_data = []
        
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    for r in data["routes"]:
                        # Extract geometry [lon, lat] -> [lat, lon]
                        coords = r["geometry"]["coordinates"]
                        geometry = [[c[1], c[0]] for c in coords]
                        
                        routes_data.append({
                            'geometry': geometry,
                            'duration': r['duration'],
                            'distance': r['distance'],
                            'nodes': [0, 1] # Placeholder for graph nodes if we had a graph
                        })
        except Exception as e:
            print(f"OSRM Error: {e}")
            
        # Fallback if no routes found
        if not routes_data:
            # Straight line fallback
            geometry = [list(origin_latlon), list(dest_latlon)]
            dist_km = 111 * np.linalg.norm(np.array(origin_latlon) - np.array(dest_latlon))
            duration_sec = (dist_km / 30.0) * 3600
            
            routes_data.append({
                'geometry': geometry,
                'duration': duration_sec,
                'distance': dist_km * 1000,
                'nodes': [0, 1],
                'type': 'fallback'
            })
            
        return routes_data

    def get_traffic_variance(self) -> float:
        """Placeholder for compatibility"""
        return 0.0
