import pydeck as pdk
from typing import List, Tuple, Optional

class Visualizer:
    """
    Handles PyDeck map rendering for the vehicle routing simulation.
    Separates visualization logic from the main application.
    """
    
    def __init__(self):
        # CartoDB Dark Matter style (no token needed, high contrast)
        self.map_style = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        
        # Colors (R, G, B, [A])
        self.COLOR_PRIMARY_ROUTE = [0, 255, 200] # Bright Cyan
        self.COLOR_ALTERNATIVE = [255, 215, 0, 180] # Gold/Amber (High contrast on dark map)
        self.COLOR_VISITED = [150, 150, 150, 200] # Solid Gray
        self.COLOR_VEHICLE = [255, 50, 50] # Bright Red
        
    def _swap_coords(self, coords: List[List[float]]) -> List[List[float]]:
        """
        Convert [lat, lon] (used in app) to [lon, lat] (used in PyDeck).
        """
        return [[c[1], c[0]] for c in coords]

    def create_deck(self, 
                   vehicle_loc: List[float], 
                   current_route: List[List[float]], 
                   visited_path: List[List[float]], 
                   alternatives: Optional[List[List[List[float]]]] = None,
                   primary_duration: float = 0,
                   alternatives_meta: Optional[List[dict]] = None) -> pdk.Deck:
        """
        Construct the PyDeck object with all layers.
        primary_duration: duration in seconds for the primary route
        alternatives_meta: list of {'duration': seconds, 'distance': meters} for each alternative
        """
        layers = []
        route_labels = []  # Collect labels for all routes
        
        # 1. Alternative Routes Layer (Bottom)
        if alternatives:
            for i, alt_route in enumerate(alternatives):
                is_fallback = len(alt_route) <= 2
                color = [255, 0, 0, 200] if is_fallback else self.COLOR_ALTERNATIVE
                width = 2 if is_fallback else 4
                
                layers.append(pdk.Layer(
                    "PathLayer",
                    [{"path": self._swap_coords(alt_route), "color": color}],
                    get_path="path",
                    get_color="color",
                    width_scale=1,
                    width_min_pixels=1,
                    get_width=width,
                    pickable=False
                ))
                
                # Add duration label at midpoint of alternative route
                if alternatives_meta and i < len(alternatives_meta) and len(alt_route) > 1:
                    mid_idx = len(alt_route) // 2
                    mid_pt = alt_route[mid_idx]
                    alt_dur = alternatives_meta[i].get('duration', 0)
                    alt_min = alt_dur / 60
                    
                    if primary_duration > 0:
                        diff_min = (alt_dur - primary_duration) / 60
                        if diff_min > 0:
                            label = f"{alt_min:.0f} min (+{diff_min:.0f} min)"
                        else:
                            label = f"{alt_min:.0f} min"
                    else:
                        label = f"{alt_min:.0f} min"
                    
                    route_labels.append({
                        "pos": [mid_pt[1], mid_pt[0]],
                        "text": label,
                        "col": list(color[:3])
                    })
        
        # 2. Visited Path Layer
        if visited_path:
            layers.append(pdk.Layer(
                "PathLayer",
                [{"path": self._swap_coords(visited_path), "color": self.COLOR_VISITED}],
                get_path="path",
                get_color="color",
                width_scale=1,
                width_min_pixels=2,
                get_width=8,
                pickable=True
            ))
            
        # 3. Primary Active Route Layer
        if current_route:
            is_fallback = len(current_route) <= 2
            
            route_color = [255, 0, 0, 200] if is_fallback else self.COLOR_PRIMARY_ROUTE
            route_width = 4 if is_fallback else 12
            
            layers.append(pdk.Layer(
                "PathLayer",
                [{"path": self._swap_coords(current_route), "color": route_color}],
                get_path="path",
                get_color="color",
                width_scale=1,
                width_min_pixels=4,
                get_width=route_width,
                pickable=True,
                auto_highlight=True,
            ))
            
            # Primary route label at midpoint
            if primary_duration > 0 and len(current_route) > 1:
                mid_idx = len(current_route) // 2
                mid_pt = current_route[mid_idx]
                pri_min = primary_duration / 60
                route_labels.append({
                    "pos": [mid_pt[1], mid_pt[0]],
                    "text": f"{pri_min:.0f} min ✓ Optimal",
                    "col": self.COLOR_PRIMARY_ROUTE[:3]
                })
            
            # Start/End Markers
            start = current_route[0]
            end = current_route[-1]
            text_data = [
                {"pos": [start[1], start[0]], "text": "Origin", "col": [0, 255, 0]},
                {"pos": [end[1], end[0]], "text": "Dest", "col": [255, 200, 50]}
            ]
            
            layers.append(pdk.Layer(
                "TextLayer",
                text_data,
                get_position="pos",
                get_text="text",
                get_color="col",
                get_size=15,
                get_alignment_baseline="'bottom'",
                get_background_color=[0, 0, 0, 200],
            ))
        
        # 5. Route Duration Labels Layer
        if route_labels:
            layers.append(pdk.Layer(
                "TextLayer",
                route_labels,
                get_position="pos",
                get_text="text",
                get_color="col",
                get_size=14,
                get_alignment_baseline="'bottom'",
                get_background_color=[0, 0, 0, 220],
                font_weight="'bold'",
            ))

        # 4. Vehicle Layer (Top)
        if vehicle_loc:
            vehicle_data = [{"pos": [vehicle_loc[1], vehicle_loc[0]]}]
            
            # Pulsing effect or just a distinct marker
            layers.append(pdk.Layer(
                "ScatterplotLayer",
                vehicle_data,
                get_position="pos",
                get_fill_color=self.COLOR_VEHICLE,
                get_line_color=[255, 255, 255],
                get_radius=80,
                radius_min_pixels=6,
                radius_max_pixels=15,
                filled=True,
                stroked=True,
                line_width_min_pixels=2,
                pickable=True
            ))

        # View State
        view_state = pdk.ViewState(
            latitude=vehicle_loc[0] if vehicle_loc else 12.9716,
            longitude=vehicle_loc[1] if vehicle_loc else 77.5946,
            zoom=14,
            pitch=50,
            bearing=0
        )
        
        return pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            map_style=self.map_style,
            tooltip={"text": "Route Segment"}
        )
