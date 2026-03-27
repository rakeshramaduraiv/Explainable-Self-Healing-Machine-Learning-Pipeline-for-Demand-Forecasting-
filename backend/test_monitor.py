import sys
import traceback
sys.stdout.reconfigure(line_buffering=True)

print("Starting test...")

from main import run_monitor_pipeline

try:
    print("Running monitor pipeline with upload_2023_full.csv...")
    result = run_monitor_pipeline('upload_2023_full.csv')
    print("SUCCESS!")
    print(f"Result: {result}")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
