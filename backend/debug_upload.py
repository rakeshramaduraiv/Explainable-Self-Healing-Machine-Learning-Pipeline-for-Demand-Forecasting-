#!/usr/bin/env python3
"""
Debug script to test upload-monitor functionality
"""
import pandas as pd
import traceback
from pathlib import Path

def test_upload_monitor():
    """Test the upload monitor pipeline with a simple CSV"""
    
    # Create a simple test CSV
    test_data = {
        'Date': ['05-01-2024', '05-01-2024', '12-01-2024', '12-01-2024'],
        'Product': ['item_1', 'item_2', 'item_1', 'item_2'],
        'Demand': [152, 89, 167, 95],
        'Store': ['store_1', 'store_1', 'store_2', 'store_2'],
        'Price': [54.99, 32.50, 54.99, 32.50],
        'Promo': [0, 1, 0, 0]
    }
    
    df = pd.DataFrame(test_data)
    test_file = Path("test_debug.csv")
    df.to_csv(test_file, index=False)
    print(f"Created test file: {test_file}")
    print("Test data:")
    print(df)
    print(f"Store column dtype: {df['Store'].dtype}")
    print(f"Product column dtype: {df['Product'].dtype}")
    
    try:
        # Test the monitor pipeline
        from main import run_monitor_pipeline
        print("\nTesting run_monitor_pipeline...")
        result = run_monitor_pipeline(str(test_file))
        print("SUCCESS!")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print("Full traceback:")
        traceback.print_exc()
    
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    test_upload_monitor()