import os
import random
import numpy as np
import pandas as pd
import joblib
from tqdm import tqdm
from river.drift import ADWIN
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
    'Volume_Change_Pct', 'Yesterday_Return'
]
TARGET = 'Target'

def load_models(model_dir):
    """Loads and returns all 3 pkl models."""
    return {
        'old': joblib.load(os.path.join(model_dir, 'model_old.pkl')),
        'medium': joblib.load(os.path.join(model_dir, 'model_medium.pkl')),
        'recent': joblib.load(os.path.join(model_dir, 'model_recent.pkl'))
    }

def ensemble_predict(models, weights, features_row_df,
                      active_features, all_features):
    """
    Returns (prediction, probability) using ensemble weights.
    features_row_df should be a DataFrame with 1 row.
    
    Critical: XGBoost was trained on all 8 features.
    Zero out deselected features instead of dropping columns.
    """
    # Always use all features, but zero out deselected ones
    full_row = features_row_df[all_features].copy()
    dropped = [f for f in all_features if f not in active_features]
    full_row[dropped] = 0.0
    
    p_old = models['old'].predict_proba(full_row)[0, 1]
    p_medium = models['medium'].predict_proba(full_row)[0, 1]
    p_recent = models['recent'].predict_proba(full_row)[0, 1]
    
    prob = weights[0] * p_old + weights[1] * p_medium + weights[2] * p_recent
    pred = 1 if prob > 0.5 else 0
    return pred, prob


def run_stream(models, df, feature_cols, adaptive=True):
    """
    Main loop with prediction buffer, ADWIN, and optional MHO Council.
    Returns results_log, drift_log.
    """
    # Initialize council ONCE — persists across all drift events
    council = MHOCouncil()
    
    # All 8 features available for selection
    active_features = list(feature_cols)
    ensemble_weights = [np.round(1/3, 4), np.round(1/3, 4), np.round(1/3, 4)]
    weights = ensemble_weights
    
    buffer = []
    results_log = []
    drift_log = []
    resolved_indices = []
    
    adwin = ADWIN(delta=1) if adaptive else None
    
    desc = "Adaptive Stream" if adaptive else "Static Stream"
    
    for current_index in tqdm(range(len(df)), desc=desc, unit="step"):
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
            truth = int(df.iloc[past_idx][TARGET])
            error = 1 if entry['prediction'] != truth else 0
            
            # Continuous error for ADWIN — lower variance, faster detection
            continuous_error = abs(entry['probability'] - truth)
            
            resolved_indices.append(past_idx)
            drift_detected = False
            
            if adaptive:
                adwin.update(continuous_error)
                if adwin.drift_detected:
                    drift_detected = True
                    
                    old_weights = list(ensemble_weights)
                    old_features = list(active_features)
                    
                    # Select last 60 resolved rows for optimization
                    if len(resolved_indices) >= 60:
                        eval_indices = resolved_indices[-60:]
                    else:
                        eval_indices = resolved_indices
                    
                    # Pass only feature columns + target label
                    resolved_df = df.iloc[eval_indices][feature_cols + [TARGET]].copy()
                    
                    # Run MHO Council optimization
                    result = council.optimize(
                        models=models,
                        resolved_df=resolved_df,
                        all_features=feature_cols
                    )
                    
                    active_features = result['active_features']
                    ensemble_weights = [np.round(w, 4) for w in result['ensemble_weights']]
                    weights = ensemble_weights
                    
                    # Flatten nested dicts for CSV serialization
                    drift_event = {
                        'date': df.iloc[past_idx]['Date'],
                        'row_index': past_idx,
                        'w_old_before': old_weights[0],
                        'w_medium_before': old_weights[1],
                        'w_recent_before': old_weights[2],
                        'w_old_after': ensemble_weights[0],
                        'w_medium_after': ensemble_weights[1],
                        'w_recent_after': ensemble_weights[2],
                        'active_features_before': ','.join(old_features),
                        'active_features_after': ','.join(active_features),
                        'fit_pso': result['algorithm_fitnesses']['pso'],
                        'fit_ga': result['algorithm_fitnesses']['ga'],
                        'fit_gwo': result['algorithm_fitnesses']['gwo'],
                        'cw_pso': result['council_weights']['pso'],
                        'cw_ga': result['council_weights']['ga'],
                        'cw_gwo': result['council_weights']['gwo']
                    }
                    drift_log.append(drift_event)
                    
                    # Reset ADWIN
                    adwin = ADWIN(delta=1)
            
            results_log.append({
                'date': df.iloc[past_idx]['Date'],
                'row_index': past_idx,
                'prediction': entry['prediction'],
                'truth': truth,
                'error': error,
                'ensemble_probability': entry['probability'],
                'w_old': entry['weights'][0],
                'w_medium': entry['weights'][1],
                'w_recent': entry['weights'][2],
                'active_feature_count': len(entry['active_features']),
                'drift_detected': drift_detected
            })
            
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
        return client.save_document(
            'simulation_results', doc_id, {
                'date': str(row['date']),
                'row_index': int(row['row_index']),
                'prediction': int(row['prediction']),
                'truth': int(row['truth']),
                'error': int(row['error']),
                'ensemble_probability': float(row['ensemble_probability']),
                'w_old': float(row['w_old']),
                'w_medium': float(row['w_medium']),
                'w_recent': float(row['w_recent']),
                'active_feature_count': int(row['active_feature_count']),
                'drift_detected': bool(row['drift_detected']),
                'type': 'adaptive'
            })

    def push_static_row(row):
        doc_id = 'static_' + str(row['date']).replace(' ', '_')
        return client.save_document(
            'simulation_results', doc_id, {
                'date': str(row['date']),
                'row_index': int(row['row_index']),
                'prediction': int(row['prediction']),
                'truth': int(row['truth']),
                'error': int(row['error']),
                'ensemble_probability': float(row['ensemble_probability']),
                'w_old': float(row['w_old']),
                'w_medium': float(row['w_medium']),
                'w_recent': float(row['w_recent']),
                'drift_detected': False,
                'type': 'static'
            })

    def push_drift_event(event):
        doc_id = f"{event['date']}_{event['row_index']}"
        return client.save_document(
            'simulation_drift_events', doc_id, {
                'date': str(event['date']),
                'row_index': int(event['row_index']),
                'w_old_before': float(event['w_old_before']),
                'w_medium_before': float(event['w_medium_before']),
                'w_recent_before': float(event['w_recent_before']),
                'w_old_after': float(event['w_old_after']),
                'w_medium_after': float(event['w_medium_after']),
                'w_recent_after': float(event['w_recent_after']),
                'active_features_before': str(event['active_features_before']),
                'active_features_after': str(event['active_features_after']),
                'fit_pso': float(event['fit_pso']),
                'fit_ga': float(event['fit_ga']),
                'fit_gwo': float(event['fit_gwo']),
                'cw_pso': float(event['cw_pso']),
                'cw_ga': float(event['cw_ga']),
                'cw_gwo': float(event['cw_gwo'])
            })

    # Push simulation summary
    client.save_document('simulation_summary', 'latest', summary)
    print("  ✓ Summary pushed")

    # Push adaptive + static results in parallel
    # Use max_workers=20 to avoid overwhelming Firestore
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
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
    print(f"Total predictions resolved: {len(results_static)}")
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
        'resolved_predictions': len(results_static),
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
