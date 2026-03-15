"""
Flask Dashboard Application for Adaptive ML System
Fetches data from Firebase via REST API
"""

from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import requests
import os
import logging
import importlib
from datetime import datetime
from functools import wraps

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase credentials
PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', 'mlmodeldriftusingmho')
API_KEY = os.getenv('FIREBASE_API_KEY')
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# Flask app
app = Flask(__name__,
            static_folder='../static',
            template_folder='../templates')

# CRON authentication
CRON_SECRET = os.getenv('CRON_SECRET', '')

def require_cron_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Cron-Token', '')
        if not CRON_SECRET or token != CRON_SECRET:
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════
# SYSTEM CONFIGURATION (Mirrored from Core Logic)
# ═══════════════════════════════════════════════════════

SYSTEM_CONFIG = {
    "features": [
        'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
        'BB_Position', 'MA_5_20_Ratio',
        'Volume_Change_Pct', 'Yesterday_Return'
    ],
    "models": [
        {"name": "Model_OLD", "period": "2015-2017"},
        {"name": "Model_MEDIUM", "period": "2016-2018"},
        {"name": "Model_RECENT", "period": "2017-2019"}
    ],
    "drift": {
        "method": "ADWIN",
        "delta": 1.0,
        "trigger": "Continuous Error (|pred_prob − truth|)"
    },
    "optimization": {
        "dimensions": 11,
        "algorithms": ["PSO", "GA", "GWO"],
        "fitness": "70% Accuracy + 30% Confidence (Entropy-based)"
    }
}

# ═══════════════════════════════════════════════════════
# FIREBASE HELPERS
# ═══════════════════════════════════════════════════════

def fs_get(path: str) -> dict | None:
    """Get a single Firestore document by path."""
    try:
        r = requests.get(f"{BASE_URL}/{path}",
                         params={'key': API_KEY}, 
                         timeout=10)
        return r.json() if r.ok else None
    except Exception as e:
        logger.error(f"fs_get {path}: {e}")
        return None

def fs_list(collection: str, page_size=2000) -> list:
    """List all documents in a Firestore collection."""
    try:
        r = requests.get(f"{BASE_URL}/{collection}",
                         params={'key': API_KEY,
                                 'pageSize': page_size},
                         timeout=15)
        return r.json().get('documents', []) if r.ok else []
    except Exception as e:
        logger.error(f"fs_list {collection}: {e}")
        return []

def parse(doc: dict) -> dict | None:
    """Parse a Firestore document to Python dict."""
    if not doc or 'fields' not in doc:
        return None
    out = {}
    for k, v in doc['fields'].items():
        if 'stringValue' in v:
            out[k] = v['stringValue']
        elif 'integerValue' in v:
            out[k] = int(v['integerValue'])
        elif 'doubleValue' in v:
            out[k] = v['doubleValue']
        elif 'booleanValue' in v:
            out[k] = v['booleanValue']
        elif 'nullValue' in v:
            out[k] = None
        elif 'arrayValue' in v:
            out[k] = []
            for x in v['arrayValue'].get('values', []):
                if 'stringValue' in x:
                    out[k].append(x['stringValue'])
                elif 'integerValue' in x:
                    out[k].append(int(x['integerValue']))
                elif 'doubleValue' in x:
                    out[k].append(x['doubleValue'])
        elif 'mapValue' in v:
            parsed_map = parse({'fields': v['mapValue'].get('fields', {})})
            out[k] = parsed_map if parsed_map else {}
    return out

# ═══════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════

@app.route('/')
def index():
    """Serve main dashboard."""
    return render_template('dashboard.html')

@app.route('/api/summary')
def api_summary():
    """Get simulation summary."""
    doc = fs_get('simulation_summary/latest')
    data = parse(doc) or {}
    return jsonify(data)

@app.route('/api/config')
def api_config():
    """Get system configuration metadata."""
    return jsonify(SYSTEM_CONFIG)

@app.route('/api/simulation')
def api_simulation():
    """Get all simulation results (adaptive + static)."""
    docs = fs_list('simulation_results', page_size=3000)
    parsed = [parse(d) for d in docs if parse(d)]
    
    adaptive = sorted(
        [r for r in parsed if r.get('type') == 'adaptive'],
        key=lambda x: str(x.get('date', '')))
    static = sorted(
        [r for r in parsed if r.get('type') == 'static'],
        key=lambda x: str(x.get('date', '')))
    
    return jsonify({'adaptive': adaptive, 'static': static})

@app.route('/api/simulation_drift')
def api_simulation_drift():
    """Get all simulation drift events."""
    docs = fs_list('simulation_drift_events', page_size=500)
    parsed = [parse(d) for d in docs if parse(d)]
    parsed.sort(key=lambda x: str(x.get('date', '')))
    return jsonify(parsed)

@app.route('/api/model_registry')
def api_model_registry():
    """Get model training registry."""
    docs = fs_list('model_registry', page_size=100)
    return jsonify([parse(d) for d in docs if parse(d)])

@app.route('/api/live/state')
def api_live_state():
    """Get current live model state."""
    doc = fs_get('system/current')
    return jsonify(parse(doc) or {})

@app.route('/api/live/predictions')
def api_live_predictions():
    """Get recent live predictions."""
    docs = fs_list('predictions', page_size=100)
    parsed = [parse(d) for d in docs if parse(d)]
    parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
    return jsonify(parsed[:20])

@app.route('/api/live/drift')
def api_live_drift():
    """Get live drift events."""
    docs = fs_list('drift_events', page_size=100)
    parsed = [parse(d) for d in docs if parse(d)]
    parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
    return jsonify(parsed[:10])

@app.route('/api/live/evaluations')
def api_live_evaluations():
    """Get recent evaluations."""
    docs = fs_list('evaluations', page_size=100)
    parsed = [parse(d) for d in docs if parse(d)]
    parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
    return jsonify(parsed[:30])

@app.route('/run/predict', methods=['GET', 'POST'])
@require_cron_token
def run_predict():
    """Trigger daily prediction job."""
    try:
        scheduler_module = importlib.import_module('src.07_scheduler')
        initialize_system = scheduler_module.initialize_system
        daily_predict = scheduler_module.daily_predict
        initialize_system()
        daily_predict()
        return jsonify({'status': 'ok', 'job': 'predict',
                        'timestamp': datetime.now().isoformat()})
    except Exception as e:
        logging.error(f"Predict job error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/run/evaluate', methods=['GET', 'POST'])
@require_cron_token
def run_evaluate():
    """Trigger daily evaluation job."""
    try:
        scheduler_module = importlib.import_module('src.07_scheduler')
        initialize_system = scheduler_module.initialize_system
        daily_evaluate = scheduler_module.daily_evaluate
        initialize_system()
        daily_evaluate()
        return jsonify({'status': 'ok', 'job': 'evaluate',
                        'timestamp': datetime.now().isoformat()})
    except Exception as e:
        logging.error(f"Evaluate job error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
