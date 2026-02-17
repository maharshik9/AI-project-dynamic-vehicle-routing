import sys
import os
import json
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.order_processing import process_orders

def test_processing():
    print("Testing order processing...")
    
    # Create a dummy JSON content
    orders = {
        "orders": [
            { "order_no": "TEST001", "address": "Malleswaram, Bangalore" },
            { "order_no": "TEST002", "address": "InvalidAddress12345" } 
        ]
    }
    content = json.dumps(orders).encode('utf-8')
    
    start_time = time.time()
    results = process_orders(content)
    end_time = time.time()
    
    print(f"Processed in {end_time - start_time:.2f} seconds")
    print(f"Total Processed: {results['total_processed']}")
    print(f"Valid Stops: {len(results['valid_stops'])}")
    print(f"Failed Orders: {len(results['failed_orders'])}")
    
    if len(results['valid_stops']) == 1:
        print("PASS: Correct number of valid stops.")
    else:
        print("FAIL: Incorrect number of valid stops.")
        
    if len(results['failed_orders']) == 1:
        print("PASS: Correct number of failed orders.")
    else:
        print("FAIL: Incorrect number of failed orders.")

if __name__ == "__main__":
    test_processing()
