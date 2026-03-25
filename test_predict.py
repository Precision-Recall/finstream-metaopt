"""
Local test for daily_predict().
Run from the project root:  uv run python test_predict.py
"""
import importlib
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Loading src.07_scheduler ...")
scheduler = importlib.import_module('src.07_scheduler')

print("Initializing system ...")
scheduler.TEST_MODE = True          # bypass weekend / holiday guard
scheduler.initialize_system()

print("\nCalling daily_predict() ...")
result = scheduler.daily_predict()

print("\n" + "=" * 60)
print("RESULT:", result)
print("=" * 60)
