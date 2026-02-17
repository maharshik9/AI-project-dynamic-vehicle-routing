"""
Simulation Controller

Manages the sequential decision-making loop:
1. Initializes route
2. Moves vehicle
3. Triggers RL agent decisions
4. Handles rerouting
"""

import time
import numpy as np
from src.environment import TrafficEnvironment

class SimulationController:
    def __init__(self, api, agent=None):
        self.api = api
        self.agent = agent  # HybridController or DQNAgent
        self.env = TrafficEnvironment(api)
        self.logs = []
        
        # Configuration
        self.decision_interval = 5.0 # minutes
        self.step_size = 2.0 # minutes (coarser physics for speed)
        
    def run_simulation(self, origin, destination):
        """
        Generator that yields simulation state at each step.
        """
        # 1. Initial Route Selection
        # Get alternatives
        routes = self.api.get_routes(origin, destination, alternatives=True)
        if not routes:
            yield {"error": "No routes found"}
            return
            
        # Select initial route (Phase A)
        # For now, pick best ETA (heuristic) or let agent pick if implemented
        # Simulating agent choice:
        initial_route_idx = 0 
        active_route = routes[initial_route_idx]
        
        # Initialize Environment
        self.env.set_route(active_route['nodes'], active_route['geometry'])
        
        yield {
            "status": "started",
            "route": active_route,
            "location": self.env.current_location,
            "eta": active_route['duration'] / 60.0
        }
        
        # 2. Simulation Loop
        time_since_decision = 0.0
        
        while not self.env.arrival_status:
            # Physics Update
            dist_covered = self.env.update_physics(self.step_size)
            time_since_decision += self.step_size
            
            # Check Triggers
            decision_needed = (time_since_decision >= self.decision_interval)
            
            if decision_needed:
                # Get Alternatives for State Context
                alternatives = self.api.get_routes(
                    self.env.current_location,
                    destination,
                    alternatives=True
                )
                
                # Get State
                state = self.env.get_state_vector(alternatives)
                
                # Phase B: Action (Keep vs Reroute)
                # Action 0: Keep, 1: Reroute
                action = 0 
                if self.agent:
                    # action = self.agent.select_action(state)
                    pass
                
                # Heuristic Fallback / Logic
                # If significant ETA improvement identified in state[6] (eta_diff)
                # state[6] is eta_diff (best_alt - current)
                # If eta_diff < -5.0 (save 5 mins), reroute
                eta_diff = state[6]
                if eta_diff < -2.0 or self.env.congestion_level > 2.0:
                     # Check if we should actually reroute
                     if alternatives:
                         action = 1
                
                if action == 1 and alternatives:
                    # Perform Reroute
                    # Pick best by duration
                    best_new = min(alternatives, key=lambda x: x['duration'])
                    
                    # Only switch if it's actually better than current legacy assessment
                    # (Here we just switch for demo dynamics)
                    self.env.set_route(best_new['nodes'], best_new['geometry'])
                    self.env.reroute_count += 1
                    time_since_decision = 0.0
                    
                    yield {
                        "event": "reroute",
                        "message": f"Rerouted! Traffic Level {self.env.congestion_level:.1f}. Saving time.",
                        "new_route": best_new,
                        "alternatives": alternatives
                    }
                else:
                    time_since_decision = 0.0
            
            # Yield Step Update
            yield {
                "status": "running",
                "location": self.env.current_location,
                "time_elapsed": self.env.time_elapsed,
                "distance_covered": self.env.total_distance_covered,
                "congestion": self.env.congestion_level,
                "completed": False
            }
            
            # Artificial sleep for demo pacing
            time.sleep(0.1)
            
        # Arrival
        yield {
            "status": "finished",
            "completed": True,
            "final_time": self.env.time_elapsed,
            "total_distance": self.env.total_distance_covered
        }
