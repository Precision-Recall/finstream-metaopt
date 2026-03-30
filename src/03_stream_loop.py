import os
import warnings
warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed should be used with.*")

import random
import numpy as np
import pandas as pd
import joblib
from tqdm import tqdm
import importlib
import asyncio
import concurrent.futures
from datetime import datetime

# Import MHOCouncil from 05_mho_council.py (number prefix requires importlib)
_mho_module = importlib.import_module('src.05_mho_council')
MHOCouncil = _mho_module.MHOCouncil

from src.firebase_client import FirebaseClient

FEATURES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_Position', 'MA_5_20_Ratio',
    'Volume_Change_Pct', 'Yesterday_Return',
    'MA_50', 'MA_200', 'Institutional_Flow'
]
TARGET = 'Target'

# Keys: model filename prefix. Values: resulting Firebase w_field suffix
MODEL_MAPPING = {
    'xgboost': 'old',
    'lightgbm': 'medium',
    'extratrees': 'recent',
    'logistic': 'logistic'
}

class SlidingWindowDriftDetector:
    """
    Custom drift detector using a dual sliding-window approach.

    RCA why ADWIN failed:
      ADWIN fires only when the MEAN of the stream shifts significantly.
      The error stream here has mean ≈ 0.49 and std ≈ 0.076 throughout
      the entire 1530-day test period — it's stationary. No delta tuning
      fixes a flat signal; ADWIN has nothing to detect.

    This detector instead:
      1. Compares a small RECENT window against a larger BASELINE window.
         If recent_error_rate > baseline_error_rate + THRESHOLD → drift.
      2. Falls back to a PERIODIC trigger every `periodic_step` resolved
         samples so the MHO Council always runs at regular intervals.

    Parameters
    ----------
    recent_window  : int   — size of the short 'recent' error window (default 60)
    baseline_window: int   — size of the historical baseline window (default 200)
    threshold      : float — error-rate delta to declare drift (default 0.05 = 5pp)
    periodic_step  : int   — force a drift trigger every N resolved samples (default 250)
    min_baseline   : int   — don't fire until the baseline is this full (default 100)
    """

    def __init__(
        self,
        recent_window: int   = 60,
        baseline_window: int = 200,
        threshold: float     = 0.05,
        periodic_step: int   = 250,
        min_baseline: int    = 100,
    ):
        self.recent_window   = recent_window
        self.baseline_window = baseline_window
        self.threshold       = threshold
        self.periodic_step   = periodic_step
        self.min_baseline    = min_baseline

        self._buffer: list   = []   # all binary errors so far
        self._n_resolved     = 0
        self._last_periodic  = 0
        self.drift_detected  = False
        self.reason: str     = ""   # 'window' or 'periodic'

    def update(self, error: int) -> None:
        """
        Feed one binary error (0 = correct, 1 = wrong).
        Sets self.drift_detected = True if drift is signalled.
        """
        self._buffer.append(int(error))
        self._n_resolved += 1
        self.drift_detected = False
        self.reason = ""

        n = len(self._buffer)

        # FIX #1: Cooldown to avoid continuous window-based back-to-back triggers
        # If we just fired a drift event, we wait to test the window again
        if self._n_resolved - self._last_periodic < self.recent_window:
            return

        # Window-based detection — need enough baseline data first
        if n >= self.min_baseline + self.recent_window:
            recent_errors   = self._buffer[-self.recent_window:]
            baseline_errors = self._buffer[
                max(0, n - self.recent_window - self.baseline_window)
                : n - self.recent_window
            ]
            recent_rate   = sum(recent_errors)   / max(len(recent_errors),   1)
            baseline_rate = sum(baseline_errors) / max(len(baseline_errors), 1)

            if recent_rate - baseline_rate > self.threshold:
                self.drift_detected = True
                self.reason = (
                    f"window: recent={recent_rate:.3f} "
                    f"baseline={baseline_rate:.3f} "
                    f"delta={recent_rate - baseline_rate:.3f}"
                )
                return

        # Periodic fallback — fire every `periodic_step` resolved samples
        if (
            self._n_resolved >= self.min_baseline
            and self._n_resolved - self._last_periodic >= self.periodic_step
        ):
            self.drift_detected = True
            self.reason = f"periodic: resolved #{self._n_resolved}"

    def reset(self) -> None:
        """Call after a drift event to avoid back-to-back triggers."""
        self._last_periodic = self._n_resolved
        self.drift_detected = False
        self.reason = ""


def load_models(model_dir):
    """Loads and returns the ensemble models dynamically."""
    return {
        model_key: joblib.load(os.path.join(model_dir, f'{model_key}.pkl'))
        for model_key in MODEL_MAPPING.keys()
    }

def ensemble_predict(models, weights, features_row_df,
                      active_features, all_features):
    """
    Returns (prediction, probability) using dynamic ensemble weights.
    features_row_df should be a DataFrame with 1 row.

    Critical: Trees were trained on all 8 features.
    Zero out deselected features instead of dropping columns.
    """
    # Always use all features, but zero out deselected ones
    full_row = pd.DataFrame(
        features_row_df[all_features].values,
        columns=all_features
    )
    dropped = [f for f in all_features if f not in active_features]
    full_row[dropped] = 0.0

    prob = 0.0
    # Weights follow the exact order of MODEL_MAPPING.keys()
    for i, model_key in enumerate(MODEL_MAPPING.keys()):
        p_val = models[model_key].predict_proba(full_row)[0, 1]
        prob += weights[i] * p_val

    pred = 1 if prob > 0.5 else 0
    return pred, prob


def run_stream(models, df, feature_cols, adaptive=True):
    """
    Main loop with prediction buffer, SlidingWindowDriftDetector, and optional MHO Council.
    Returns results_log, drift_log.
    """
    # Initialize council ONCE — persists across all drift events
    council = MHOCouncil()

    # All 8 features available for selection
    active_features   = list(feature_cols)
    # Equal initial weights for all mapping models
    num_models = len(MODEL_MAPPING)
    ensemble_weights  = [1.0 / num_models] * num_models
    weights           = ensemble_weights

    buffer            = []
    results_log       = []
    drift_log         = []
    resolved_indices  = []

    MIN_WINDOW = 100   # Focus optimization on recent ~100 rows where signal exists

    # Detector: tightened for more responsive adaptation.
    # recent_window=30  → reacts to last 30 days instead of 60 (catches short regime shifts faster)
    # threshold=0.04    → 4pp degradation triggers drift instead of 5pp (more sensitive)
    # periodic_step=150 → forced re-opt every 150 days (~10x over 1525 days, up from 5x)
    # min_baseline=100  → first drift eligible after 100 resolved days instead of 150
    detector = SlidingWindowDriftDetector(
        recent_window   = 30,
        baseline_window = 200,
        threshold       = 0.04,
        periodic_step   = 150,
        min_baseline    = 100,
    ) if adaptive else None

    desc = "Adaptive Stream" if adaptive else "Static Stream"
    drift_count = 0
    
    for current_index in tqdm(range(len(df)), desc=desc, unit="step"):
        # ... existing logic ...
        # (I will keep the loop structure but ensure my variables are correct)
        row = df.iloc[current_index]
        date_str = row['Date']
        
        # 1. Prediction for current row
        features_row_df = df.iloc[[current_index]][feature_cols]
        pred, prob = ensemble_predict(models, weights, features_row_df,
                                      active_features, feature_cols)
        
        buffer.append({
            'row_index': current_index,
            'prediction': pred,
            'probability': prob,
            'weights': list(weights),
            'active_features': list(active_features),
            'resolve_at_index': current_index + 5
        })
        
        # 2. Check for resolved predictions
        resolved_entries = [e for e in buffer if e['resolve_at_index'] == current_index]
        buffer = [e for e in buffer if e['resolve_at_index'] > current_index]
        
        for entry in resolved_entries:
            past_idx = entry['row_index']
            truth  = int(df.iloc[past_idx][TARGET])
            error  = 1 if entry['prediction'] != truth else 0
            
            resolved_indices.append(past_idx)
            drift_detected = False

            if adaptive:
                detector.update(error)
                if detector.drift_detected:
                    drift_reason = detector.reason
                    detector.reset() # ← ALWAYS reset first, unconditionally
                    
                    drift_detected = True
                    drift_count   += 1
                    print(f"\n[DRIFT #{drift_count}] at index {past_idx} "
                          f"(Date: {df.iloc[past_idx]['Date']}) Reason: {drift_reason}")
                    
                    old_weights = list(ensemble_weights)
                    old_features = list(active_features)
                    
                    # Cap to most recent MIN_WINDOW rows only
                    if len(resolved_indices) > MIN_WINDOW:
                        window_indices = resolved_indices[-MIN_WINDOW:]
                    else:
                        window_indices = resolved_indices
                    
                    # Pass only feature columns + target label
                    resolved_df = df.iloc[window_indices][feature_cols + [TARGET]].copy()
                    
                    # Run MHO Council optimization
                    result = council.optimize(
                        models=models,
                        resolved_df=resolved_df,
                        all_features=feature_cols,
                        current_features=active_features,
                        current_weights=ensemble_weights
                    )
                    
                    active_features = result['active_features']
                    ensemble_weights = [np.round(w, 4) for w in result['ensemble_weights']]
                    weights = ensemble_weights
                    
                    # Flatten nested dicts for CSV serialization dynamically
                    drift_event = {
                        'date': df.iloc[past_idx]['Date'],
                        'row_index': past_idx,
                        'active_features_before': ','.join(old_features),
                        'active_features_after': ','.join(active_features),
                        'fit_pso': result['algorithm_fitnesses']['pso'],
                        'fit_ga':  result['algorithm_fitnesses']['ga'],
                        'fit_gwo': result['algorithm_fitnesses']['gwo'],
                        'cw_pso':  result['council_weights']['pso'],
                        'cw_ga':   result['council_weights']['ga'],
                        'cw_gwo':  result['council_weights']['gwo']
                    }
                    
                    assert list(models.keys()) == list(MODEL_MAPPING.keys()), "Model mapping order mismatch"
                    for i, (model_key, field_name) in enumerate(MODEL_MAPPING.items()):
                        drift_event[f'w_{field_name}_before'] = old_weights[i]
                        drift_event[f'w_{field_name}_after'] = ensemble_weights[i]
                        
                    drift_log.append(drift_event)
            
            res_entry = {
                'date': df.iloc[past_idx]['Date'],
                'row_index': past_idx,
                'prediction': entry['prediction'],
                'truth': truth,
                'error': error,
                'ensemble_probability': entry['probability'],
                'active_feature_count': len(entry['active_features']),
                'drift_detected': drift_detected
            }
            
            for i, (model_key, field_name) in enumerate(MODEL_MAPPING.items()):
                res_entry[f'w_{field_name}'] = entry['weights'][i]
                
            results_log.append(res_entry)
            
    return results_log, drift_log



def push_to_firebase_batch(
    results_adaptive: list,
    results_static: list,
    drift_events: list,
    summary: dict
) -> None:
    """
    Batch push all simulation results to Firebase.
    Uses ThreadPoolExecutor for parallel writes.
    Called ONCE at end of simulation — not inside loop.
    """
    client = FirebaseClient()

    print("\nPushing simulation data to Firebase...")
    print(f"  {len(results_adaptive)} adaptive results")
    print(f"  {len(results_static)} static results")
    print(f"  {len(drift_events)} drift events")

    def push_adaptive_row(row):
        doc_id = str(row['date']).replace(' ', '_')
        payload = {
            'date': str(row['date']),
            'row_index': int(row['row_index']),
            'prediction': int(row['prediction']),
            'truth': int(row['truth']),
            'error': int(row['error']),
            'ensemble_probability': float(row['ensemble_probability']),
            'active_feature_count': int(row['active_feature_count']),
            'drift_detected': bool(row['drift_detected']),
            'type': 'adaptive'
        }
        for field_name in MODEL_MAPPING.values():
            payload[f'w_{field_name}'] = float(row[f'w_{field_name}'])
        return client.save_document('simulation_results', doc_id, payload)

    def push_static_row(row):
        doc_id = 'static_' + str(row['date']).replace(' ', '_')
        payload = {
            'date': str(row['date']),
            'row_index': int(row['row_index']),
            'prediction': int(row['prediction']),
            'truth': int(row['truth']),
            'error': int(row['error']),
            'ensemble_probability': float(row['ensemble_probability']),
            'drift_detected': False,
            'type': 'static'
        }
        for field_name in MODEL_MAPPING.values():
            payload[f'w_{field_name}'] = float(row[f'w_{field_name}'])
        return client.save_document('simulation_results', doc_id, payload)

    def push_drift_event(event):
        doc_id = f"{event['date']}_{event['row_index']}"
        payload = {
            'date': str(event['date']),
            'row_index': int(event['row_index']),
            'active_features_before': str(event['active_features_before']),
            'active_features_after':  str(event['active_features_after']),
            'fit_pso': float(event['fit_pso']),
            'fit_ga':  float(event['fit_ga']),
            'fit_gwo': float(event['fit_gwo']),
            'cw_pso':  float(event['cw_pso']),
            'cw_ga':   float(event['cw_ga']),
            'cw_gwo':  float(event['cw_gwo'])
        }
        for field_name in MODEL_MAPPING.values():
            payload[f'w_{field_name}_before'] = float(event[f'w_{field_name}_before'])
            payload[f'w_{field_name}_after'] = float(event[f'w_{field_name}_after'])
        return client.save_document('simulation_drift_events', doc_id, payload)

    # Push simulation summary
    client.save_document('simulation_summary', 'latest', summary)
    print("  ✓ Summary pushed")

    # Push adaptive + static results in parallel
    # Use max_workers=20 to avoid overwhelming Firestore
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # Adaptive results
        futures_a = [executor.submit(push_adaptive_row, r)
                     for r in results_adaptive]
        # Static results
        futures_s = [executor.submit(push_static_row, r)
                     for r in results_static]
        # Drift events
        futures_d = [executor.submit(push_drift_event, e)
                     for e in drift_events]

        all_futures = futures_a + futures_s + futures_d
        done = 0
        for f in concurrent.futures.as_completed(all_futures):
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(all_futures)} documents written...")

    succeeded = sum(1 for f in all_futures if f.result())
    print(f"  ✓ {succeeded}/{len(all_futures)} documents pushed")
    print("Firebase batch push complete.")


def main():
    # REPRODUCIBILITY
    random.seed(42)
    np.random.seed(42)
    
    # Load Models & Data
    models = load_models('models')
    df_test = pd.read_csv('data/processed/test.csv')
    df_test = df_test.sort_values('Date').reset_index(drop=True)
    
    print("Running Static Baseline Protocol...")
    results_static, _ = run_stream(models, df_test, FEATURES, adaptive=False)

    print("\nRunning Adaptive MHO Council Protocol...")
    results_adaptive, drift_events = run_stream(models, df_test, FEATURES, adaptive=True)

    print("\n" + "="*50)
    print("SIMULATION SUMMARY")
    print("="*50)
    print(f"Total days simulated:       {len(df_test)}")
    print(f"Total predictions resolved: {len(results_adaptive)}")
    print(f"Drift events detected:      {len(drift_events)}")
    if drift_events:
        print("Drift dates:")
        for event in drift_events:
            print(f"  - {event['date']} (Row {event['row_index']})")
            
    # Use Brier-based score (1 - BS) for simulation performance
    brier_static = sum(1.0 - (r['ensemble_probability'] - r['truth'])**2 for r in results_static) / len(results_static) if results_static else 0.0
    brier_adaptive = sum(1.0 - (r['ensemble_probability'] - r['truth'])**2 for r in results_adaptive) / len(results_adaptive) if results_adaptive else 0.0
    
    print(f"\nFinal Static Brier Score:   {brier_static:.4f}")
    print(f"Final Adaptive Brier Score: {brier_adaptive:.4f}")
    print(f"Brier Score Delta:          {(brier_adaptive - brier_static):.4f}")
    
    # Council Weight Evolution
    print("\nCouncil Weight Evolution:")
    for event in drift_events:
        print(f"  {event['date']}")
        print(f"    Fitnesses: PSO={event['fit_pso']:.4f}, GA={event['fit_ga']:.4f}, GWO={event['fit_gwo']:.4f}")
        print(f"    Council:   PSO={event['cw_pso']:.4f}, GA={event['cw_ga']:.4f}, GWO={event['cw_gwo']:.4f}")
    
    # Feature Selection per Drift
    print("\nFeature Selection per Drift:")
    for event in drift_events:
        before = event['active_features_before'].split(',')
        after = event['active_features_after'].split(',')
        print(f"  {event['date']}")
        print(f"    Before: {before}")
        print(f"    After:  {after}")
    
    # Build summary dict and push to Firebase (required)
    simulation_summary = {
        'static_brier_score': round(brier_static, 4),
        'adaptive_brier_score': round(brier_adaptive, 4),
        'delta': round(brier_adaptive - brier_static, 4),
        'drift_count': len(drift_events),
        'total_days': len(df_test),
        'resolved_predictions': len(results_adaptive),
        'run_at': datetime.now().isoformat()
    }
    
    print("\nPushing results to Firebase...")
    push_to_firebase_batch(
        results_adaptive=results_adaptive,
        results_static=results_static,
        drift_events=drift_events,
        summary=simulation_summary
    )
    print("✅ All results successfully pushed to Firebase")
    print("="*50)

if __name__ == '__main__':
    main()