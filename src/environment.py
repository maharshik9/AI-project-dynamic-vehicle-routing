"""
Dynamic Delivery Environment (Phase 2 Redesign)

This environment supports:
- Fine-grained simulation loop (vehicle movement along polyline)
- Time-dependent traffic states
- Sequential decision making (Keep vs Reroute)
- Numeric state vector for DQN
"""

import numpy as np
from typing import Tuple, Dict, List
import math

class TrafficEnvironment:
    """
    State-managed environment for dynamic vehicle routing.
    Manages vehicle physics, traffic state, and reward calculation.
    """
    
    def __init__(self, traffic_api, num_nodes=5, pickup_node=0, deadlines=None):
        self.traffic_api = traffic_api
        self.num_nodes = num_nodes
        self.pickup_node = pickup_node
        
        # Physics State
        self.current_location = None  # [lat, lon]
        self.active_route_nodes = []  # List of node IDs
        self.active_route_geometry = []  # List of [lat, lon] points
        self.current_polyline_index = 0 # Index in geometry
        self.destination_node = None
        
        # Simulation State
        self.time_elapsed = 0.0
        self.reroute_count = 0
        self.decision_interval = 5.0 # Minutes between decisions
        self.last_decision_time = 0.0
        
        # Traffic State
        self.congestion_level = 1.0
        self.congestion_variance = 0.0
        
        # Metrics
        self.total_distance_covered = 0.0
        self.arrival_status = False
        
        # Initialize
        self.reset()

    def reset(self):
        """Reset environment to initial state."""
        # Randomize locations (for demo) or reset to fixed
        # For now, we assume locations are managed externally or fixed
        self.current_location = None
        self.active_route_nodes = []
        self.active_route_geometry = []
        self.current_polyline_index = 0
        self.time_elapsed = 0.0
        self.reroute_count = 0
        self.last_decision_time = 0.0
        self.total_distance_covered = 0.0
        self.arrival_status = False
        
        return self.get_state_vector()

    def set_route(self, route_nodes: List[int], geometry: List[List[float]]):
        """
        Update the active route.
        Called at initialization and upon rerouting.
        """
        self.active_route_nodes = route_nodes
        self.active_route_geometry = geometry
        self.current_polyline_index = 0
        self.destination_node = route_nodes[-1]
        
        # If first assignment, set current location
        if self.current_location is None and len(geometry) > 0:
            self.current_location = geometry[0]

    def update_physics(self, dt_minutes: float):
        """
        Move vehicle along the active geometry for dt_minutes.
        Returns distance covered in this step (km).
        """
        if not self.active_route_geometry or self.arrival_status:
            return 0.0
            
        # 1. Update Traffic Factor (Simulate volatility)
        # In a real system, this would come from API updates
        # Here we drift it randomly for simulation
        drift = np.random.normal(0, 0.05)
        self.congestion_level = float(np.clip(self.congestion_level + drift, 1.0, 3.0))
        
        # Effective Speed (km/min)
        # Base speed 30km/h = 0.5 km/min
        speed_km_min = (30.0 / 60.0) / self.congestion_level
        
        distance_to_travel = speed_km_min * dt_minutes
        distance_traveled = 0.0
        
        # Move along polyline segments
        while distance_to_travel > 0 and self.current_polyline_index < len(self.active_route_geometry) - 1:
            p1 = self.active_route_geometry[self.current_polyline_index]
            p2 = self.active_route_geometry[self.current_polyline_index + 1]
            
            # Dist between p1 and p2
            seg_dist = self._haversine_km(p1, p2)
            
            if seg_dist == 0:
                self.current_polyline_index += 1
                continue
                
            if distance_to_travel >= seg_dist:
                # Consume full segment
                distance_traveled += seg_dist
                distance_to_travel -= seg_dist
                self.current_polyline_index += 1
                self.current_location = p2
            else:
                # Move partial segment
                ratio = distance_to_travel / seg_dist
                new_lat = p1[0] + (p2[0] - p1[0]) * ratio
                new_lon = p1[1] + (p2[1] - p1[1]) * ratio
                self.current_location = [new_lat, new_lon]
                distance_traveled += distance_to_travel
                distance_to_travel = 0
        
        self.total_distance_covered += distance_traveled
        self.time_elapsed += dt_minutes
        
        # Check arrival
        if self.current_polyline_index >= len(self.active_route_geometry) - 1:
            self.arrival_status = True
            
        return distance_traveled

    def get_state_vector(self, alternatives_meta: List[Dict] = None) -> np.ndarray:
        """
        Construct numeric state vector for DQN.
        
        State: [
            dist_rem (km), 
            eta_rem (min), 
            congestion_level (1.0-3.0), 
            congestion_var, 
            time_elapsed (min), 
            reroute_count, 
            eta_diff (best_alt - curr)
        ]
        """
        # Estimate remaining
        dist_rem = 0.0
        if self.active_route_geometry and self.current_polyline_index < len(self.active_route_geometry):
             # Sum remaining segments
             for i in range(self.current_polyline_index, len(self.active_route_geometry)-1):
                 dist_rem += self._haversine_km(self.active_route_geometry[i], self.active_route_geometry[i+1])
        
        # Current ETA based on current congestion
        eta_rem = (dist_rem / (30.0 / self.congestion_level)) * 60.0
        
        # ETA Difference (if alternatives provided)
        eta_diff = 0.0
        if alternatives_meta:
            # traffic_api returns 'duration' in seconds
            best_alt_sec = min([alt['duration'] for alt in alternatives_meta])
            best_alt_min = best_alt_sec / 60.0
            eta_diff = best_alt_min - eta_rem # Negative means alternative is faster
            
        state = np.array([
            dist_rem,
            eta_rem,
            self.congestion_level,
            self.congestion_variance,
            self.time_elapsed,
            float(self.reroute_count),
            eta_diff
        ], dtype=np.float32)
        
        return state

    def calculate_reward(self, step_dist: float, step_time: float, did_reroute: bool):
        """
        Calculate reward for the simulation step.
        R_t = - alpha * time - beta * congestion - gamma * reroute + bonus
        """
        alpha = 1.0  # Time penalty
        beta = 0.5   # Congestion penalty
        gamma = 2.0  # Reroute penalty (cost of switching)
        
        reward = - (alpha * step_time)
        reward -= (beta * (self.congestion_level - 1.0) * step_time)
        
        if did_reroute:
            reward -= gamma
            
        if self.arrival_status:
            reward += 50.0 # Arrival bonus
            
        return reward

    def _haversine_km(self, p1, p2):
        """Calculate distance in km between two [lat, lon] points."""
        R = 6371  # Earth radius in km
        lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
        lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
