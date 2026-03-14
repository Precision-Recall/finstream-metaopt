from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.data_loader import load_dashboard_data
from src.dashboard.metrics import compute_dashboard_metrics
from src.dashboard.html_generator import generate_dashboard_bundle

def main():
    # 1. Load data
    data_dict = load_dashboard_data()

    # 2. Compute all derived values and get JS variables
    js_vars = compute_dashboard_metrics(data_dict)

    # 3. Generate modular dashboard bundle + legacy redirect
    generate_dashboard_bundle(js_vars)

if __name__ == '__main__':
    main()

