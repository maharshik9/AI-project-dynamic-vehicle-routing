"""
Route Optimizer for Multi-Stop Delivery

Builds a duration matrix via OSRM Table API, then optimizes
the visit order using:
  1. Nearest-Neighbor heuristic (fast baseline)
  2. 2-opt local search improvement
"""

import requests
import numpy as np
from typing import List, Tuple, Dict


class RouteOptimizer:
    """Optimizes the order of multiple stops to minimize total travel time."""

    OSRM_TABLE_URL = "http://router.project-osrm.org/table/v1/driving"

    def __init__(self, api=None):
        self.api = api
        self.duration_matrix = None
        self.distance_matrix = None

    def build_duration_matrix(self, stops: List[List[float]]) -> np.ndarray:
        """
        Query OSRM Table API to get an NxN duration matrix between all stops.
        stops: list of [lat, lon]
        Returns: NxN numpy array of durations in seconds.
        """
        n = len(stops)
        if n < 2:
            return np.zeros((n, n))

        # OSRM expects lon,lat
        coords = ";".join([f"{s[1]},{s[0]}" for s in stops])
        url = f"{self.OSRM_TABLE_URL}/{coords}"

        try:
            resp = requests.get(url, params={
                "annotations": "duration,distance"
            }, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok":
                    self.duration_matrix = np.array(data["durations"])
                    self.distance_matrix = np.array(data["distances"])
                    return self.duration_matrix
        except Exception as e:
            print(f"OSRM Table API error: {e}")

        # Fallback: estimate from haversine
        self.duration_matrix = self._estimate_matrix(stops)
        return self.duration_matrix

    def _estimate_matrix(self, stops: List[List[float]]) -> np.ndarray:
        """Fallback: estimate duration matrix from straight-line distance."""
        n = len(stops)
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist_km = 111 * np.linalg.norm(
                        np.array(stops[i]) - np.array(stops[j])
                    )
                    # Assume 25 km/h average
                    matrix[i][j] = (dist_km / 25.0) * 3600
        return matrix

    def optimize_order(self, stops: List[List[float]], 
                       stop_names: List[str] = None) -> Dict:
        """
        Optimize visit order using nearest-neighbor + 2-opt.
        
        Args:
            stops: List of [lat, lon] coordinates
            stop_names: Optional list of display names
            
        Returns:
            Dict with:
                'order': optimized indices
                'stops': reordered [lat, lon] list
                'names': reordered names
                'total_duration': estimated total seconds
                'legs': list of {from_idx, to_idx, duration}
        """
        n = len(stops)
        if n <= 2:
            return {
                'order': list(range(n)),
                'stops': stops,
                'names': stop_names or [f"Stop {i+1}" for i in range(n)],
                'total_duration': 0,
                'legs': []
            }

        # Build matrix if not done
        if self.duration_matrix is None or self.duration_matrix.shape[0] != n:
            self.build_duration_matrix(stops)

        # Step 1: Nearest-Neighbor starting from index 0
        order = self._nearest_neighbor(n, start=0)

        # Step 2: 2-opt improvement
        order = self._two_opt(order)

        # Calculate total duration
        total_dur = sum(
            self.duration_matrix[order[i]][order[i+1]] 
            for i in range(len(order) - 1)
        )

        # Build legs info
        legs = []
        for i in range(len(order) - 1):
            legs.append({
                'from_idx': order[i],
                'to_idx': order[i+1],
                'duration': self.duration_matrix[order[i]][order[i+1]]
            })

        names = stop_names or [f"Stop {i+1}" for i in range(n)]
        
        return {
            'order': order,
            'stops': [stops[i] for i in order],
            'names': [names[i] for i in order],
            'total_duration': total_dur,
            'legs': legs
        }

    def _nearest_neighbor(self, n: int, start: int = 0) -> List[int]:
        """Nearest-neighbor heuristic for TSP."""
        visited = {start}
        order = [start]
        current = start

        while len(visited) < n:
            # Find nearest unvisited
            best_next = None
            best_dur = float('inf')
            for j in range(n):
                if j not in visited and self.duration_matrix[current][j] < best_dur:
                    best_dur = self.duration_matrix[current][j]
                    best_next = j
            
            if best_next is not None:
                visited.add(best_next)
                order.append(best_next)
                current = best_next

        return order

    def _two_opt(self, order: List[int]) -> List[int]:
        """2-opt local search improvement."""
        improved = True
        best_order = order[:]
        
        while improved:
            improved = False
            for i in range(1, len(best_order) - 1):
                for j in range(i + 1, len(best_order)):
                    # Try reversing segment [i, j]
                    new_order = best_order[:i] + best_order[i:j+1][::-1] + best_order[j+1:]
                    
                    new_cost = sum(
                        self.duration_matrix[new_order[k]][new_order[k+1]]
                        for k in range(len(new_order) - 1)
                    )
                    old_cost = sum(
                        self.duration_matrix[best_order[k]][best_order[k+1]]
                        for k in range(len(best_order) - 1)
                    )
                    
                    if new_cost < old_cost:
                        best_order = new_order
                        improved = True
            
        return best_order
