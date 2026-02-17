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
from src.order_processing import process_orders
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
    
    /* Log styling */
    .log-entry {
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 4px;
        background-color: #1e1e1e;
        border-left: 4px solid #555;
        font-family: monospace;
        font-size: 0.9em;
    }
    .log-success { border-left-color: #00ADB5; }
    .log-warning { border-left-color: #FFA500; }
    .log-error { border-left-color: #FF4B4B; }
    
    /* Metrics bolding */
    div[data-testid="stMetricValue"] {
        font-weight: bold;
    }
    
    /* Stop item in sidebar */
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
st.sidebar.title("Control Center")

# 1. Delivery Orders
st.sidebar.markdown("### Delivery Orders")
if st.session_state.stops:
    st.sidebar.markdown(f"**Total Orders: {len(st.session_state.stops)}**")
    for i, (stop, name) in enumerate(zip(st.session_state.stops, st.session_state.stop_names)):
        st.sidebar.text(f"{i+1}. {name}")
    
    if st.sidebar.button("Clear All Orders"):
        st.session_state.stops = []
        st.session_state.stop_names = []
        st.session_state.optimized_stops = None
        st.session_state.simulation_running = False
        st.rerun()
else:
    st.sidebar.info("No orders added.")

st.sidebar.markdown("---")

# Stop Search
new_stop = st_searchbox(
    search_location,
    key="add_stop_searchbox",
    placeholder="Search location...",
    label="Add Manual Order",
    clear_on_submit=True,
)
if new_stop and new_stop != st.session_state.get("_last_added_stop"):
    st.session_state._last_added_stop = new_stop
    st.session_state.stops.append(new_stop)
    st.session_state.stop_names.append(f"Order {len(st.session_state.stops)}")
    st.session_state.optimized_stops = None
    st.rerun()

st.sidebar.markdown("---")

# 2. Import Orders
st.sidebar.markdown("### Import Orders")
uploaded_file = st.sidebar.file_uploader("Upload JSON", type=["json"])

if uploaded_file is not None:
    if st.sidebar.button("Load Orders"):
        with st.spinner("Processing..."):
            try:
                content = uploaded_file.getvalue()
                results = process_orders(content)
                
                valid_count = len(results["valid_stops"])
                
                if valid_count > 0:
                    st.session_state.stops = results["valid_stops"]
                    st.session_state.stop_names = results["valid_stop_names"]
                    st.session_state.optimized_stops = None
                    
                    # Auto optimize
                    result = st.session_state.optimizer.optimize_order(
                        st.session_state.stops,
                        st.session_state.stop_names
                    )
                    st.session_state.optimized_stops = result
                    st.session_state.stops = result['stops']
                    st.session_state.stop_names = result['names']
                    
                    # Auto fetch geometry
                    full_route = []
                    stops = st.session_state.stops
                    for i in range(len(stops) - 1):
                        origin = stops[i]
                        dest = stops[i+1]
                        try:
                            # Try to get existing geometry or fetch
                            # Simplified for brevity as per existing logic
                            routes = st.session_state.api.get_routes(origin, dest)
                            if routes:
                                full_route.extend(routes[0]['geometry'])
                            else:
                                full_route.extend([origin, dest])
                        except:
                            full_route.extend([origin, dest])
                    st.session_state.full_route_geometry = full_route
                    
                    st.sidebar.success(f"Imported {valid_count} orders successfully")
                    st.toast(f"✅ Imported {valid_count} orders!", icon="📂")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.sidebar.error("No valid addresses found")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("---")

# 3. Optimization
st.sidebar.markdown("### Optimization")
if len(st.session_state.stops) >= 2:
    if st.sidebar.button("Generate Optimized Route", use_container_width=True):
        with st.sidebar:
            with st.spinner("Calculating best route..."):
                start_time = time.time()
                result = st.session_state.optimizer.optimize_order(
                    st.session_state.stops,
                    st.session_state.stop_names
                )
                st.session_state.optimized_stops = result
                st.session_state.stops = result['stops']
                st.session_state.stop_names = result['names']
                
                # Fetch geometry
                full_route = []
                stops = st.session_state.stops
                for i in range(len(stops) - 1):
                    origin = stops[i]
                    dest = stops[i+1]
                    try:
                        routes = st.session_state.api.get_routes(origin, dest)
                        if routes:
                            full_route.extend(routes[0]['geometry'])
                        else:
                            full_route.extend([origin, dest])
                    except:
                        full_route.extend([origin, dest])
                st.session_state.full_route_geometry = full_route
                
                duration = (time.time() - start_time) * 1000
                st.success(f"Optimized in {duration:.0f} ms")
                st.rerun()

    if st.session_state.optimized_stops:
        total_min = st.session_state.optimized_stops['total_duration'] / 60.0
        st.sidebar.info(f"Route Ready: {total_min:.0f} min est.")
else:
    st.sidebar.warning("Add 2+ orders to optimize.")

st.sidebar.markdown("---")

# 4. Simulation Settings
st.sidebar.markdown("### Simulation Settings")
st.session_state.speed = st.sidebar.slider("Speed (Delay)", 0.01, 1.0, 0.2)

# Start/Stop Controls
col_swa, col_swb = st.sidebar.columns(2)
if col_swa.button("Start Simulation", disabled=len(st.session_state.stops)<2):
    st.session_state.simulation_running = True
if col_swb.button("Stop"):
    st.session_state.simulation_running = False
    st.rerun()

# ---------------------------------------------------------
# Main Interface
# ---------------------------------------------------------
st.title("AI Dynamic Routing Manager")

if st.session_state.simulation_running and len(st.session_state.stops) >= 2:
    
    stops = st.session_state.stops
    stop_names = st.session_state.stop_names
    num_orders = len(stops) - 1
    
    controller = SimulationController(st.session_state.api)
    
    # Layout
    metrics_placeholder = st.empty()
    map_placeholder = st.empty()
    
    with st.expander("Mission Logs", expanded=False):
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

    try:
        # OUTER LOOP: Orders Iteration
        for leg_idx in range(num_orders):
            origin = stops[leg_idx]
            dest = stops[leg_idx + 1]
            origin_name = stop_names[leg_idx]
            dest_name = stop_names[leg_idx + 1]
            
            logs.append({"msg": f"Starting Order {leg_idx+1}/{num_orders}: {origin_name} -> {dest_name}", "type": "info"})
            st.toast(f"🚗 Starting Order {leg_idx+1}: {origin_name} -> {dest_name}")
            
            # Reset route state for this order
            st.session_state.current_route_geometry = []
            st.session_state.alternatives_geometry = []
            st.session_state.primary_duration = 0
            
            # Fetch initial routes
            initial_routes = st.session_state.api.get_routes(origin, dest, alternatives=True)
            if initial_routes:
                st.session_state.current_route_geometry = initial_routes[0]['geometry']
                st.session_state.primary_duration = initial_routes[0].get('duration', 0)
                st.session_state.alternatives_geometry = [r['geometry'] for r in initial_routes[1:]]
                st.session_state.alternatives_meta = [
                    {'duration': r.get('duration', 0), 'distance': r.get('distance', 0)}
                    for r in initial_routes[1:]
                ]

            sim_gen = controller.run_simulation(origin, dest)
            leg_distance = 0.0
            leg_time = 0.0
            leg_total_dist = 0.0
            
            for step in sim_gen:
                if "error" in step:
                    st.error(step["error"])
                    break
                
                # Update Data
                if step.get("status") == "started":
                    leg_total_dist = step["route"]["distance"] / 1000.0
                    st.session_state.current_route_geometry = step["route"]["geometry"]
                    
                # Handle Events
                if "event" in step:
                    msg = step['message']
                    log_type = "warning" if step["event"] == "reroute" else "info"
                    logs.append({"msg": msg, "type": log_type})
                    
                    if step["event"] == "reroute":
                        st.toast(f"⚠️ {msg}", icon="🔀")
                        if "alternatives" in step:
                            st.session_state.alternatives_geometry = [alt["geometry"] for alt in step["alternatives"]]
                        if "new_route" in step:
                            st.session_state.current_route_geometry = step["new_route"]["geometry"]

                if step.get("completed"):
                    # Use final values from completed step, fallback to last known
                    leg_final_dist = step.get("total_distance", leg_distance)
                    leg_final_time = step.get("final_time", leg_time)
                    
                    grand_total_distance += leg_final_dist
                    grand_total_time += leg_final_time
                    
                    logs.append({"msg": f"Order {leg_idx+1} Completed: {leg_final_dist:.1f} km", "type": "success"})
                    st.toast(f"✅ Order {leg_idx+1} Completed: {leg_final_dist:.1f} km", icon="🏁")
                    break
                
                # Metrics Updates
                # Use .get with fallback to existing values to prevent overwriting with None/0.0 if key missing
                leg_distance = step.get('distance_covered', leg_distance)
                leg_time = step.get('time_elapsed', leg_time)
                
                with metrics_placeholder.container():
                    # Consolidated Metrics
                    c1, c2, c3, c4, c5 = st.columns(5)
                    
                    current_leg_progress = 0.0
                    if leg_total_dist > 0:
                        current_leg_progress = min(leg_distance / leg_total_dist, 1.0)
                    overall_progress = (leg_idx + current_leg_progress) / num_orders
                    
                    with c1:
                        st.metric("Orders", f"{leg_idx+1}/{num_orders}")
                        st.progress(min(overall_progress, 1.0))
                    
                    cong = step.get('congestion', 1.0)
                    c2.metric("Traffic", f"{cong:.1f}x")
                    
                    # Totals = Accumulated from previous legs + Current leg
                    display_dist = grand_total_distance + leg_distance
                    display_time = grand_total_time + leg_time
                    
                    c3.metric("Total Distance", f"{display_dist:.1f} km")
                    c4.metric("Total Time", f"{display_time:.1f} min")
                    
                    status_color = "red" if "error" in step else "gold"
                    status_text = step.get('status', 'WAITING').upper()
                    
                    # Calculate ETA
                    eta_text = ""
                    if st.session_state.optimized_stops:
                        total_est = st.session_state.optimized_stops.get('total_duration', 0) / 60.0
                        remaining = max(0.0, total_est - display_time)
                        eta_text = f"<br><span style='font-size:0.8em;color:#aaa'>ETA: {remaining:.1f} min</span>"
                    
                    c5.markdown(f"**Status**<br><span style='color:{status_color};font-weight:bold'>{status_text}</span>{eta_text}", unsafe_allow_html=True)

                # Map Update
                if "location" in step:
                    loc = step["location"]
                    visited_path.append(loc)
                    
                    deck = st.session_state.visualizer.create_deck(
                        loc, 
                        st.session_state.current_route_geometry, 
                        visited_path,
                        st.session_state.alternatives_geometry,
                        primary_duration=st.session_state.primary_duration,
                        stops=stops,
                        stop_names=stop_names
                    )
                    map_placeholder.pydeck_chart(deck, width="stretch")
                
                # Logs Rendering
                with log_placeholder:
                    log_html = """
                    <div style='max-height: 300px; overflow-y: auto; padding-right: 5px; border-radius: 5px; background-color: #1e1e1e;'>
                    """
                    for log in reversed(logs):
                        cls = "log-success" if log.get("type") == "success" else "log-warning" if log.get("type") == "warning" else "log-entry"
                        log_html += f"<div class='log-entry {cls}'>{log['msg']}</div>"
                    log_html += "</div>"
                    st.markdown(log_html, unsafe_allow_html=True)

                time.sleep(st.session_state.speed)
            
            # Re-init controller for next leg
            controller = SimulationController(st.session_state.api)

        # FINAL COMPLETION
        st.balloons()
        st.success(f"""
        ### All {num_orders} Orders Completed
        - **Total Distance:** {grand_total_distance:.1f} km
        - **Total Time:** {grand_total_time:.1f} min
        """)
        
    except Exception as e:
        st.error(f"Simulation Error: {e}")

else:
    # Landing Page
    st.info("Load orders or add stops to begin.")
    
    deck = st.session_state.visualizer.create_deck(
        None, 
        st.session_state.full_route_geometry if "full_route_geometry" in st.session_state else [], 
        [], [],
        stops=st.session_state.stops if st.session_state.stops else None,
        stop_names=st.session_state.stop_names if st.session_state.stop_names else None
    )
    st.pydeck_chart(deck, width="stretch")
