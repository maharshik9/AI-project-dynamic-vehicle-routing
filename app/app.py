import streamlit as st
import time
import pandas as pd
import numpy as np
import sys
import os
import importlib

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.visualizer
importlib.reload(src.visualizer)  # Force reload so code changes are picked up

from src.simulation import SimulationController
from src.traffic_api import TrafficAPI
from src.visualizer import Visualizer
from src.geocoder import search_location
from src.route_optimizer import RouteOptimizer
from streamlit_searchbox import st_searchbox

# Page Config
st.set_page_config(
    page_title="AI Dynamic Routing",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .metric-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #41444b;
    }
    .stProgress > div > div > div > div { background-color: #00ADB5; }
    .stop-item {
        background-color: #262730;
        padding: 8px 12px;
        border-radius: 8px;
        margin: 4px 0;
        border-left: 3px solid #00ADB5;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "simulation_running" not in st.session_state:
    st.session_state.simulation_running = False
if "stops" not in st.session_state:
    st.session_state.stops = []  # List of [lat, lon]
if "stop_names" not in st.session_state:
    st.session_state.stop_names = []  # Display names
if "optimized_stops" not in st.session_state:
    st.session_state.optimized_stops = None  # Result from optimizer
if "api" not in st.session_state:
    st.session_state.api = TrafficAPI()
if "optimizer" not in st.session_state:
    st.session_state.optimizer = RouteOptimizer(st.session_state.api)
st.session_state.visualizer = Visualizer()
if "speed" not in st.session_state:
    st.session_state.speed = 0.2

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.title("🎮 Control Center")

st.sidebar.markdown("### 📍 Add Stops")

# Add Stop searchbox
new_stop = st_searchbox(
    search_location,
    key="add_stop_searchbox",
    placeholder="Search location (e.g. Koramangala)...",
    label="Add a stop",
    clear_on_submit=True,
)

# When a stop is selected, add it (guard against reruns re-adding the same stop)
if new_stop and new_stop != st.session_state.get("_last_added_stop"):
    st.session_state._last_added_stop = new_stop
    st.session_state.stops.append(new_stop)
    st.session_state.stop_names.append(f"Stop {len(st.session_state.stops)}")
    st.session_state.optimized_stops = None  # Reset optimization
    st.rerun()

# Show current stops
if st.session_state.stops:
    st.sidebar.markdown(f"**{len(st.session_state.stops)} stops added:**")
    
    for i, (stop, name) in enumerate(zip(st.session_state.stops, st.session_state.stop_names)):
        col_name, col_del = st.sidebar.columns([4, 1])
        col_name.markdown(f"**{i+1}.** 📍 `{stop[0]:.4f}, {stop[1]:.4f}`")
        if col_del.button("❌", key=f"del_{i}"):
            st.session_state.stops.pop(i)
            st.session_state.stop_names.pop(i)
            st.session_state.optimized_stops = None
            st.rerun()

    # Optimize button
    if len(st.session_state.stops) >= 2:
        st.sidebar.markdown("---")
        if st.sidebar.button("🧠 Optimize Order (RL + 2-opt)", use_container_width=True):
            with st.sidebar:
                with st.spinner("🔄 Building distance matrix & optimizing..."):
                    result = st.session_state.optimizer.optimize_order(
                        st.session_state.stops,
                        st.session_state.stop_names
                    )
                    st.session_state.optimized_stops = result
                    # Update stops to optimized order
                    st.session_state.stops = result['stops']
                    st.session_state.stop_names = result['names']
                    
                    total_min = result['total_duration'] / 60.0
                    st.success(f"✅ Optimized! Est. {total_min:.0f} min total")
                    st.rerun()

        # Show optimization result
        if st.session_state.optimized_stops:
            total_min = st.session_state.optimized_stops['total_duration'] / 60.0
            st.sidebar.info(f"🧠 Optimized: {total_min:.0f} min total ({len(st.session_state.stops)} stops)")
else:
    st.sidebar.info("Add at least 2 stops to plan a route.")

# Quick demo button
st.sidebar.markdown("---")
if st.sidebar.button("🚀 Load Demo Route (4 stops)"):
    st.session_state.stops = [
        [12.9352, 77.6245],   # Koramangala
        [12.9716, 77.5946],   # MG Road
        [12.9784, 77.6408],   # Indiranagar
        [12.9698, 77.7500],   # Whitefield
    ]
    st.session_state.stop_names = [
        "Koramangala", "MG Road", "Indiranagar", "Whitefield"
    ]
    st.session_state.optimized_stops = None
    st.sidebar.success("Demo: 4 Bangalore stops loaded!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Simulation Settings")
st.session_state.speed = st.sidebar.slider("Simulation Speed (Delay)", 0.01, 1.0, 0.2, help="Lower is faster")

# Clear All
if st.sidebar.button("🗑️ Clear All Stops"):
    st.session_state.stops = []
    st.session_state.stop_names = []
    st.session_state.optimized_stops = None
    st.session_state.simulation_running = False
    st.rerun()

col_swa, col_swb = st.sidebar.columns(2)
if col_swa.button("▶ Start"):
    if len(st.session_state.stops) < 2:
        st.sidebar.error("Add at least 2 stops first!")
    else:
        st.session_state.simulation_running = True

if col_swb.button("⏹ Stop"):
    st.session_state.simulation_running = False
    st.rerun()

# ---------------------------------------------------------
# Main Interface
# ---------------------------------------------------------
st.title("🚦 AI Dynamic Routing Manager")

if st.session_state.simulation_running and len(st.session_state.stops) >= 2:
    
    stops = st.session_state.stops
    stop_names = st.session_state.stop_names
    num_legs = len(stops) - 1
    
    controller = SimulationController(st.session_state.api)
    
    # Layout
    leg_info_placeholder = st.empty()
    metrics_placeholder = st.empty()
    map_placeholder = st.empty()
    
    with st.expander("📝 Mission Logs", expanded=True):
        log_placeholder = st.empty()

    # Data Containers
    logs = []
    visited_path = []
    grand_total_distance = 0.0
    grand_total_time = 0.0
    
    # Persistent State
    if "current_route_geometry" not in st.session_state:
        st.session_state.current_route_geometry = []
    if "alternatives_geometry" not in st.session_state:
        st.session_state.alternatives_geometry = []
    if "primary_duration" not in st.session_state:
        st.session_state.primary_duration = 0
    if "alternatives_meta" not in st.session_state:
        st.session_state.alternatives_meta = []

    # Progress Bar
    progress_bar = st.progress(0, text="Mission Progress")

    try:
        # OUTER LOOP: Leg by Leg
        for leg_idx in range(num_legs):
            origin = stops[leg_idx]
            dest = stops[leg_idx + 1]
            origin_name = stop_names[leg_idx] if leg_idx < len(stop_names) else f"Stop {leg_idx+1}"
            dest_name = stop_names[leg_idx + 1] if leg_idx + 1 < len(stop_names) else f"Stop {leg_idx+2}"
            
            # Show leg header
            with leg_info_placeholder.container():
                st.markdown(f"### 📍 Leg {leg_idx + 1}/{num_legs}: **{origin_name}** → **{dest_name}**")
            
            logs.append(f"📍 Starting Leg {leg_idx+1}/{num_legs}: {origin_name} → {dest_name}")
            st.toast(f"📍 Leg {leg_idx+1}/{num_legs}: {origin_name} → {dest_name}", icon="🚗")

            # Reset route state for this leg
            st.session_state.current_route_geometry = []
            st.session_state.alternatives_geometry = []
            st.session_state.primary_duration = 0
            st.session_state.alternatives_meta = []

            # Fetch initial routes for this leg
            initial_routes = st.session_state.api.get_routes(origin, dest, alternatives=True)
            if initial_routes:
                st.session_state.current_route_geometry = initial_routes[0]['geometry']
                st.session_state.primary_duration = initial_routes[0].get('duration', 0)
                st.session_state.alternatives_geometry = [r['geometry'] for r in initial_routes[1:]]
                st.session_state.alternatives_meta = [
                    {'duration': r.get('duration', 0), 'distance': r.get('distance', 0)}
                    for r in initial_routes[1:]
                ]

            # Show map for this leg
            with map_placeholder:
                deck = st.session_state.visualizer.create_deck(
                    origin, 
                    st.session_state.current_route_geometry, 
                    visited_path,
                    st.session_state.alternatives_geometry,
                    primary_duration=st.session_state.primary_duration,
                    alternatives_meta=st.session_state.alternatives_meta
                )
                st.pydeck_chart(deck, width="stretch")

            # Run simulation for this leg
            sim_gen = controller.run_simulation(origin, dest)
            leg_distance = 0.0
            leg_time = 0.0
            leg_total_dist = 0.0

            for step in sim_gen:
                if "error" in step:
                    st.error(step["error"])
                    break
                
                # 1. Update Data State
                if step.get("status") == "started":
                    leg_total_dist = step["route"]["distance"] / 1000.0
                    st.session_state.current_route_geometry = step["route"]["geometry"]
                    st.session_state.alternatives_geometry = []
                    logs.append(f"🚀 Leg {leg_idx+1} started. {leg_total_dist:.1f} km")
                    
                # Handle Events
                if "event" in step:
                    msg = step['message']
                    logs.append(f"⚡ {msg}")
                    
                    if step["event"] == "reroute":
                        st.toast(f"🚧 {msg}", icon="⚠️")
                        
                        if "alternatives" in step:
                            st.session_state.alternatives_geometry = [alt["geometry"] for alt in step["alternatives"]]
                            st.session_state.alternatives_meta = [
                                {'duration': alt.get('duration', 0), 'distance': alt.get('distance', 0)}
                                for alt in step["alternatives"]
                            ]
                        
                        if "new_route" in step:
                            with map_placeholder:
                                deck = st.session_state.visualizer.create_deck(
                                    step.get("location", origin),
                                    st.session_state.current_route_geometry,
                                    visited_path,
                                    st.session_state.alternatives_geometry,
                                    primary_duration=st.session_state.primary_duration,
                                    alternatives_meta=st.session_state.alternatives_meta
                                )
                                st.pydeck_chart(deck, width="stretch")
                            
                            time.sleep(1.5)
                            
                            st.session_state.current_route_geometry = step["new_route"]["geometry"]
                            st.session_state.primary_duration = step["new_route"].get("duration", 0)
                            st.toast("✅ New optimal route selected!", icon="🛣️")

                # 2. Update Metrics UI
                leg_distance = step.get('distance_covered', 0.0)
                leg_time = step.get('time_elapsed', 0.0)
                
                with metrics_placeholder.container():
                    c1, c2, c3, c4, c5 = st.columns(5)
                    
                    # Overall progress: (completed legs + current leg progress) / total legs
                    current_leg_progress = 0.0
                    if leg_total_dist > 0:
                        current_leg_progress = min(leg_distance / leg_total_dist, 1.0)
                    
                    overall_progress = (leg_idx + current_leg_progress) / num_legs
                    progress_bar.progress(min(overall_progress, 1.0), 
                                         text=f"Leg {leg_idx+1}/{num_legs} — {int(overall_progress*100)}%")
                    
                    cong = step.get('congestion', 1.0)
                    c1.metric("Leg", f"{leg_idx+1}/{num_legs}")
                    c2.metric("Traffic", f"{cong:.1f}x", delta="Normal" if cong < 1.3 else "Heavy", delta_color="inverse")
                    c3.metric("Leg Dist", f"{leg_distance:.1f} km")
                    c4.metric("Leg Time", f"{leg_time:.1f} min")
                    c5.metric("Status", step.get('status', 'WAITING').upper())

                # 3. Update Map
                if "location" in step:
                    loc = step["location"]
                    visited_path.append(loc)
                    
                    with map_placeholder:
                        deck = st.session_state.visualizer.create_deck(
                            loc, 
                            st.session_state.current_route_geometry, 
                            visited_path,
                            st.session_state.alternatives_geometry
                        )
                        st.pydeck_chart(deck, width="stretch")
                
                # 4. Logs
                with log_placeholder:
                    for l in reversed(logs[-5:]):
                        st.markdown(f"- {l}")

                # Speed Control
                time.sleep(st.session_state.speed)
                
                if step.get("completed"):
                    grand_total_distance += leg_distance
                    grand_total_time += leg_time
                    logs.append(f"✅ Leg {leg_idx+1} complete! {leg_distance:.1f} km in {leg_time:.1f} min")
                    
                    if leg_idx < num_legs - 1:
                        st.toast(f"✅ Arrived at {dest_name}! Starting next leg...", icon="📍")
                        time.sleep(1.0)
                    break
            
            # Reset environment for next leg
            controller = SimulationController(st.session_state.api)

        # ALL LEGS COMPLETE
        progress_bar.progress(1.0, text="✅ Mission Complete!")
        st.balloons()
        st.success(f"🎉 All {num_legs} legs complete! Total: {grand_total_distance:.1f} km in {grand_total_time:.1f} min")
        
    except Exception as e:
        import traceback
        st.error(f"Simulation Error: {e}")
        st.text(traceback.format_exc())

else:
    # Landing Page
    st.markdown("### 🗺️ Ready to Simulate")
    
    if st.session_state.stops:
        st.info(f"📍 {len(st.session_state.stops)} stops loaded. Click **Optimize Order** then **Start**.")
    else:
        st.info("Add stops from the sidebar, optimize the order, and click Start.")
    
    deck = st.session_state.visualizer.create_deck(None, [], [], [])
    st.pydeck_chart(deck, width="stretch")
