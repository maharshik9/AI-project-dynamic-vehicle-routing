import sys
import os

print("Starting debug...")
try:
    import numpy
    print(f"NumPy version: {numpy.__version__}")
except ImportError as e:
    print(f"Error importing numpy: {e}")

try:
    import requests
    print(f"Requests version: {requests.__version__}")
except ImportError as e:
    print(f"Error importing requests: {e}")

try:
    import streamlit
    print(f"Streamlit version: {streamlit.__version__}")
except ImportError as e:
    print(f"Error importing streamlit: {e}")

# Check project imports
sys.path.insert(0, os.getcwd())
print(f"CWD: {os.getcwd()}")

try:
    from src.traffic_api import TrafficAPI
    print("Imported TrafficAPI")
except ImportError as e:
    print(f"Error importing TrafficAPI: {e}")
    import traceback
    traceback.print_exc()

try:
    from src.environment import TrafficEnvironment
    print("Imported TrafficEnvironment")
except ImportError as e:
    print(f"Error importing TrafficEnvironment: {e}")
    import traceback
    traceback.print_exc()

try:
    from src.simulation import SimulationController
    print("Imported SimulationController")
except ImportError as e:
    print(f"Error importing SimulationController: {e}")
    import traceback
    traceback.print_exc()

print("Debug complete.")
