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
                   alternatives_meta: Optional[List[dict]] = None,
                   stops: Optional[List[List[float]]] = None,
                   stop_names: Optional[List[str]] = None) -> pdk.Deck:
        """
        Construct the PyDeck object with all layers.
        primary_duration: duration in seconds for the primary route
        alternatives_meta: list of {'duration': seconds, 'distance': meters} for each alternative
        stops: list of [lat, lon] to display as markers
        stop_names: list of names/order numbers corresponding to stops
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
                    [{"path": self._swap_coords(alt_route), "color": color, "tooltip": "Alternative Route"}],
                    get_path="path",
                    get_color="color",
                    width_scale=1,
                    width_min_pixels=1,
                    get_width=width,
                    pickable=True
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
                [{"path": self._swap_coords(visited_path), "color": self.COLOR_VISITED, "tooltip": "Visited Path"}],
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
            route_width = 4 if is_fallback else 15
            
            # Glow Effect (Wider, transparent layer below)
            if not is_fallback:
                layers.append(pdk.Layer(
                    "PathLayer",
                    [{"path": self._swap_coords(current_route), "color": self.COLOR_PRIMARY_ROUTE[:3] + [50]}], # Low opacity
                    get_path="path",
                    get_color="color",
                    width_scale=1,
                    width_min_pixels=4,
                    get_width=30, # Double width for glow
                    pickable=False,
                ))

            layers.append(pdk.Layer(
                "PathLayer",
                [{"path": self._swap_coords(current_route), "color": route_color, "tooltip": "Active Route"}],
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
                    "text": f"{pri_min:.0f} min",
                    "col": self.COLOR_PRIMARY_ROUTE[:3]
                })
            
            # Start/End Markers
            start = current_route[0]
            end = current_route[-1]
            text_data = [
                {"pos": [start[1], start[0]], "text": "Start", "col": [0, 255, 0]},
                {"pos": [end[1], end[0]], "text": "End", "col": [255, 200, 50]}
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
            vehicle_data = [{"pos": [vehicle_loc[1], vehicle_loc[0]], "tooltip": f"Vehicle Location\nLat: {vehicle_loc[0]}\nLon: {vehicle_loc[1]}"}]
            
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

        # 6. Stops Layer (For uploaded orders)
        if stops:
            formatted_stops = []
            stop_labels = []
            
            for i, s in enumerate(stops):
                name = stop_names[i] if stop_names and i < len(stop_names) else f"Stop {i+1}"
                formatted_stops.append({
                    "pos": [s[1], s[0]], 
                    "name": name,
                    "lat": s[0],
                    "lon": s[1],
                    "tooltip": f"{name}\nLat: {s[0]:.4f}\nLon: {s[1]:.4f}"
                })
                # Add number label
                stop_labels.append({
                    "pos": [s[1], s[0]],
                    "text": str(i + 1),
                    "col": [255, 255, 255]
                })

            layers.append(pdk.Layer(
                "ScatterplotLayer",
                formatted_stops,
                get_position="pos",
                get_fill_color=[0, 173, 181], # Teal color
                get_line_color=[0, 0, 0],
                get_radius=60,
                radius_min_pixels=8,
                radius_max_pixels=20,
                filled=True,
                stroked=True,
                line_width_min_pixels=1,
                pickable=True
            ))
            
            # Numbered Labels
            layers.append(pdk.Layer(
                "TextLayer",
                stop_labels,
                get_position="pos",
                get_text="text",
                get_color="col",
                get_size=12,
                get_alignment_baseline="'center'",
                get_text_anchor="'middle'",
                font_weight="'bold'"
            ))

        # View State Logic
        lat, lon = 12.9716, 77.5946 # Default Bangalore
        zoom = 11

        if vehicle_loc:
            lat, lon = vehicle_loc[0], vehicle_loc[1]
            zoom = 14
        elif stops:
            # Center at first stop as requested
            if len(stops) > 0:
                lat = stops[0][0]
                lon = stops[0][1]
                zoom = 12
        elif current_route:
             # If no vehicle but has route (shouldn't happen often), center on start
             lat, lon = current_route[0][0], current_route[0][1]

        view_state = pdk.ViewState(
            latitude=lat,
            longitude=lon,
            zoom=zoom,
            pitch=50,
            bearing=0
        )
        
        return pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            map_style=self.map_style,
            tooltip={"text": "{tooltip}"}
        )
