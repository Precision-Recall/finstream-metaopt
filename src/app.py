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
import threading
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

# Tracks the last run status for each job (in-memory, reset on restart)
_job_status = {}

def require_cron_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Cron-Token', '')
        if not CRON_SECRET or token != CRON_SECRET:
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def _run_job_in_background(job_name: str, job_fn, *args):
    """Run a job function in a daemon thread and record its result in _job_status."""
    def _worker():
        _job_status[job_name] = {'status': 'running', 'started_at': datetime.now().isoformat()}
        try:
            result = job_fn(*args)
            _job_status[job_name] = {
                'status': 'done',
                'result': result,
                'finished_at': datetime.now().isoformat()
            }
            logger.info(f"{job_name} background thread finished: {result}")
        except Exception as e:
            import traceback
            _job_status[job_name] = {
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc(),
                'finished_at': datetime.now().isoformat()
            }
            logger.critical(f"{job_name} background thread crashed: {e}")
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

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
        "delta": 0.2,
        "trigger": "Continuous Error (|pred_prob − truth|)"
    },
    "optimization": {
        "dimensions": 11,
        "algorithms": ["PSO", "GA", "GWO"],
        "fitness": "Brier Score (1 - MSE) + Parsimony Penalty"
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
    try:
        doc = fs_get('system/current')
        data = parse(doc) or {}
        logger.info(f"✓ Retrieved live state: {list(data.keys())}")
        return jsonify(data)
    except Exception as e:
        logger.error(f"✗ Error fetching live state: {e}")
        return jsonify({}), 500

@app.route('/api/live/predictions')
def api_live_predictions():
    """Get recent live predictions."""
    try:
        docs = fs_list('predictions', page_size=100)
        parsed = [parse(d) for d in docs if parse(d)]
        logger.info(f"✓ Retrieved {len(parsed)} live predictions")
        parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
        return jsonify(parsed[:20])
    except Exception as e:
        logger.error(f"✗ Error fetching live predictions: {e}")
        return jsonify([]), 500

@app.route('/api/live/drift')
def api_live_drift():
    """Get live drift events."""
    try:
        docs = fs_list('drift_events', page_size=100)
        parsed = [parse(d) for d in docs if parse(d)]
        logger.info(f"✓ Retrieved {len(parsed)} live drift events")
        parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
        return jsonify(parsed[:10])
    except Exception as e:
        logger.error(f"✗ Error fetching live drift events: {e}")
        return jsonify([]), 500

@app.route('/api/live/evaluations')
def api_live_evaluations():
    """Get recent evaluations."""
    try:
        docs = fs_list('evaluations', page_size=100)
        parsed = [parse(d) for d in docs if parse(d)]
        logger.info(f"✓ Retrieved {len(parsed)} live evaluations")
        parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
        return jsonify(parsed[:30])
    except Exception as e:
        logger.error(f"✗ Error fetching live evaluations: {e}")
        return jsonify([]), 500

@app.route('/run/predict', methods=['GET', 'POST'])
@require_cron_token
def run_predict():
    """Trigger daily prediction job asynchronously."""
    logger.info("INCOMING REQUEST: /run/predict — firing background thread")
    def _predict_job():
        scheduler_module = importlib.import_module('src.07_scheduler')
        scheduler_module.initialize_system()
        return scheduler_module.daily_predict()
    _run_job_in_background('predict', _predict_job)
    return jsonify({
        'status': 'accepted',
        'job': 'predict',
        'message': 'Job started in background. Poll /api/job_status?job=predict for result.',
        'timestamp': datetime.now().isoformat()
    }), 202

@app.route('/run/evaluate', methods=['GET', 'POST'])
@require_cron_token
def run_evaluate():
    """Trigger daily evaluation job asynchronously."""
    logger.info("INCOMING REQUEST: /run/evaluate — firing background thread")
    def _evaluate_job():
        scheduler_module = importlib.import_module('src.07_scheduler')
        scheduler_module.initialize_system()
        return scheduler_module.daily_evaluate()
    _run_job_in_background('evaluate', _evaluate_job)
    return jsonify({
        'status': 'accepted',
        'job': 'evaluate',
        'message': 'Job started in background. Poll /api/job_status?job=evaluate for result.',
        'timestamp': datetime.now().isoformat()
    }), 202

@app.route('/api/job_status')
def api_job_status():
    """Poll the last result of a background job. Use ?job=predict or ?job=evaluate."""
    job = request.args.get('job')
    if not job:
        return jsonify(_job_status)
    return jsonify(_job_status.get(job, {'status': 'not_started'}))

@app.route('/run/evaluate_pending', methods=['GET', 'POST'])
@require_cron_token
def run_evaluate_pending():
    """Trigger pending evaluation job for recent unresolved predictions."""
    try:
        logger.info("=" * 60)
        logger.info("INCOMING REQUEST: /run/evaluate_pending")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        n_preds = int(request.args.get('n', 10))
        
        scheduler_module = importlib.import_module('src.07_scheduler')
        initialize_system = scheduler_module.initialize_system
        evaluate_pending = scheduler_module.evaluate_pending_predictions
        
        logger.info("Calling initialize_system()...")
        initialize_system()
        
        logger.info(f"Calling evaluate_pending_predictions(n={n_preds})...")
        result = evaluate_pending(n=n_preds)
        
        logger.info(f"evaluate_pending_predictions() returned: {result}")
        
        if result.get('status') == 'error':
            logger.critical(f"PENDING EVALUATION JOB FAILED: {result.get('reason')}")
            return jsonify({
                'status': 'error', 
                'job': 'evaluate_pending',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }), 500
        
        logger.info("PENDING EVALUATION JOB COMPLETED SUCCESSFULLY")
        return jsonify({
            'status': 'ok', 
            'job': 'evaluate_pending',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.critical(f"UNHANDLED EXCEPTION in /run/evaluate_pending: {e}")
        logger.critical(f"Error type: {type(e).__name__}")
        import traceback
        logger.critical(traceback.format_exc())
        return jsonify({
            'status': 'error', 
            'job': 'evaluate_pending',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/diagnostics')
def api_diagnostics():
    """Diagnostic endpoint to verify Firestore connectivity and data availability."""
    logger.info("=" * 60)
    logger.info("DIAGNOSTICS: Checking Firestore data...")
    logger.info("=" * 60)
    
    diagnostics = {
        'timestamp': datetime.now().isoformat(),
        'firebase_configured': bool(API_KEY and PROJECT_ID),
        'collections': {}
    }
    
    # Check each collection
    collections = ['predictions', 'evaluations', 'drift_events', 'system/current']
    
    for collection in collections:
        try:
            if collection == 'system/current':
                doc = fs_get('system/current')
                count = 1 if doc else 0
                sample = parse(doc) if doc else None
            else:
                docs = fs_list(collection, page_size=10)
                count = len(docs)
                sample = parse(docs[0]) if docs else None
            
            diagnostics['collections'][collection] = {
                'count': count,
                'sample_keys': list(sample.keys()) if sample else [],
                'status': '✓' if count > 0 else '⚠️ empty'
            }
            logger.info(f"  {collection}: {count} documents")
        except Exception as e:
            diagnostics['collections'][collection] = {
                'error': str(e),
                'status': '✗ error'
            }
            logger.error(f"  {collection}: ERROR - {e}")
    
    logger.info("=" * 60)
    return jsonify(diagnostics)

@app.route('/health')
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
