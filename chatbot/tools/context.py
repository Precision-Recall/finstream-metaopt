import os
import requests
import logging
from strands import tool

# Configure logging
logger = logging.getLogger(__name__)

def parse(doc: dict) -> dict | None:
    """Parse a Firestore document to Python dict (Copied from src/app.py)."""
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

@tool
def firebase_context(collections: list[str] = None) -> str:
    """
    Fetches live context from Firebase Firestore for the chatbot agent.
    
    Args:
        collections: Optional list of collection names to fetch.
    """
    project_id = os.getenv('FIREBASE_PROJECT_ID')
    api_key = os.getenv('FIREBASE_API_KEY')
    
    if not project_id or not api_key:
        return "ERROR: Firebase credentials not configured. Set FIREBASE_PROJECT_ID and FIREBASE_API_KEY."
    
    base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
    
    if collections is None:
        collections = ['predictions', 'evaluations', 'drift_events', 'system/current', 'simulation_summary']
    
    context_parts = []
    
    # ═══════════════════════════════════════════════════════
    # Fetch Collections
    # ═══════════════════════════════════════════════════════
    
    raw_data = {}
    
    for coll in collections:
        try:
            if coll == 'system/current':
                r = requests.get(f"{base_url}/{coll}", params={'key': api_key}, timeout=10)
                raw_data[coll] = r.json() if r.ok else None
            else:
                r = requests.get(f"{base_url}/{coll}", params={'key': api_key, 'pageSize': 50}, timeout=15)
                raw_data[coll] = r.json().get('documents', []) if r.ok else []
        except Exception:
            raw_data[coll] = None
            
    # ═══════════════════════════════════════════════════════
    # Section: SYSTEM STATE
    # ═══════════════════════════════════════════════════════
    if 'system/current' in collections:
        doc = raw_data.get('system/current')
        data = parse(doc)
        if data:
            lines = [f"{k}: {v}" for k, v in data.items()]
            context_parts.append("=== SYSTEM STATE ===\n" + "\n".join(lines))
        else:
            context_parts.append("=== SYSTEM STATE ===\nsystem/current: unavailable")

    # ═══════════════════════════════════════════════════════
    # Section: RECENT PREDICTIONS
    # ═══════════════════════════════════════════════════════
    if 'predictions' in collections:
        docs = raw_data.get('predictions')
        if docs is not None:
            parsed = [parse(d) for d in docs if parse(d)]
            parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
            recent = parsed[:10]
            lines = []
            for p in recent:
                date = p.get('date', 'N/A')
                label = p.get('prediction_label', 'N/A')
                prob = f"{p.get('ensemble_probability', 0):.4f}"
                resolved = p.get('resolved', False)
                error = p.get('error', 'N/A')
                lines.append(f"{date} | {label} | {prob} | {resolved} | {error}")
            context_parts.append("=== RECENT PREDICTIONS (last 10) ===\n" + ("\n".join(lines) if lines else "No predictions found"))
        else:
            context_parts.append("=== RECENT PREDICTIONS (last 10) ===\npredictions: unavailable")

    # ═══════════════════════════════════════════════════════
    # Section: RECENT EVALUATIONS
    # ═══════════════════════════════════════════════════════
    if 'evaluations' in collections:
        docs = raw_data.get('evaluations')
        if docs is not None:
            parsed = [parse(d) for d in docs if parse(d)]
            parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
            recent = parsed[:10]
            lines = []
            for e in recent:
                date = e.get('date', 'N/A')
                truth = e.get('truth', 'N/A')
                error = f"{e.get('error', 0):.4f}"
                drift = e.get('drift_detected', False)
                lines.append(date + f" | {truth} | {error} | {drift}")
            context_parts.append("=== RECENT EVALUATIONS (last 10) ===\n" + ("\n".join(lines) if lines else "No evaluations found"))
        else:
            context_parts.append("=== RECENT EVALUATIONS (last 10) ===\nevaluations: unavailable")

    # ═══════════════════════════════════════════════════════
    # Section: RECENT DRIFT EVENTS
    # ═══════════════════════════════════════════════════════
    if 'drift_events' in collections:
        docs = raw_data.get('drift_events')
        if docs is not None:
            parsed = [parse(d) for d in docs if parse(d)]
            parsed.sort(key=lambda x: str(x.get('date', '')), reverse=True)
            recent = parsed[:5]
            lines = []
            for ev in recent:
                date = ev.get('date', 'N/A')
                fb = ev.get('active_features_before', 'N/A')
                fa = ev.get('active_features_after', 'N/A')
                wb = f"old={ev.get('w_old_before','?')} med={ev.get('w_medium_before','?')} rec={ev.get('w_recent_before','?')}"
                wa = f"old={ev.get('w_old_after','?')} med={ev.get('w_medium_after','?')} rec={ev.get('w_recent_after','?')}"
                lines.append(f"{date} | {fb} → {fa} | {wb} → {wa}")
            context_parts.append("=== RECENT DRIFT EVENTS (last 5) ===\n" + ("\n".join(lines) if lines else "No drift events found"))
        else:
            context_parts.append("=== RECENT DRIFT EVENTS (last 5) ===\ndrift_events: unavailable")

    # ═══════════════════════════════════════════════════════
    # Section: SIMULATION SUMMARY
    # ═══════════════════════════════════════════════════════
    if 'simulation_summary' in collections:
        docs = raw_data.get('simulation_summary')
        if docs:
            # Collection list returned documents, pick first since it's common for 'latest' patterns
            data = parse(docs[0]) if docs else None
            if data:
                lines = [f"{k}: {v}" for k, v in data.items()]
                context_parts.append("=== SIMULATION SUMMARY ===\n" + "\n".join(lines))
            else:
                context_parts.append("=== SIMULATION SUMMARY ===\nsimulation_summary: unavailable")
        else:
            context_parts.append("=== SIMULATION SUMMARY ===\nsimulation_summary: unavailable")

    return "\n\n".join(context_parts)
