import os
import random
import numpy as np
import pandas as pd
import joblib
from tqdm import tqdm
from river.drift import ADWIN

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

def ensemble_predict(models, weights, features_row_df):
    """
    Returns (prediction, probability) using ensemble weights.
    features_row_df should be a DataFrame with 1 row.
    """
    p_old = models['old'].predict_proba(features_row_df)[0, 1]
    p_medium = models['medium'].predict_proba(features_row_df)[0, 1]
    p_recent = models['recent'].predict_proba(features_row_df)[0, 1]
    
    prob = weights[0] * p_old + weights[1] * p_medium + weights[2] * p_recent
    pred = 1 if prob > 0.5 else 0
    return pred, prob

def pso_optimize(models, df, resolved_indices, feature_cols):
    """
    Runs PSO on resolved rows.
    Returns best weights [w1, w2, w3].
    """
    if len(resolved_indices) >= 60:
        eval_indices = resolved_indices[-60:]
    else:
        eval_indices = resolved_indices
        
    if len(eval_indices) == 0:
        return [1/3, 1/3, 1/3]
        
    X_eval = df.iloc[eval_indices][feature_cols]
    y_eval = df.iloc[eval_indices][TARGET].values
    
    # Pre-calculate probabilities to avoid repeated model inference
    p_old = models['old'].predict_proba(X_eval)[:, 1]
    p_medium = models['medium'].predict_proba(X_eval)[:, 1]
    p_recent = models['recent'].predict_proba(X_eval)[:, 1]
    
    n_particles = 20
    n_iterations = 30
    w = 0.7
    c1 = 1.5
    c2 = 1.5
    
    particles = np.random.rand(n_particles, 3)
    velocities = np.random.randn(n_particles, 3) * 0.1
    
    personal_best_positions = np.copy(particles)
    personal_best_fitness = np.zeros(n_particles) - 1.0
    
    global_best_position = None
    global_best_fitness = -1.0
    
    def calculate_fitness(w_cur):
        w_norm = np.abs(w_cur)
        if np.sum(w_norm) > 0:
            w_norm = w_norm / np.sum(w_norm)
        else:
            w_norm = np.array([1/3, 1/3, 1/3])
            
        probs = w_norm[0] * p_old + w_norm[1] * p_medium + w_norm[2] * p_recent
        preds = (probs > 0.5).astype(int)
        return np.mean(preds == y_eval)

    # Evaluate initial particles
    for i in range(n_particles):
        fitness = calculate_fitness(particles[i])
        personal_best_fitness[i] = fitness
        if fitness > global_best_fitness:
            global_best_fitness = fitness
            global_best_position = np.copy(particles[i])
            
    # PSO optimization loop
    for _ in range(n_iterations):
        for i in range(n_particles):
            r1 = np.random.rand(3)
            r2 = np.random.rand(3)
            
            velocities[i] = (w * velocities[i] + 
                             c1 * r1 * (personal_best_positions[i] - particles[i]) +
                             c2 * r2 * (global_best_position - particles[i]))
            
            particles[i] = particles[i] + velocities[i]
            
            fitness = calculate_fitness(particles[i])
            if fitness > personal_best_fitness[i]:
                personal_best_fitness[i] = fitness
                personal_best_positions[i] = np.copy(particles[i])
                
            if fitness > global_best_fitness:
                global_best_fitness = fitness
                global_best_position = np.copy(particles[i])
                
    best_w = np.abs(global_best_position)
    if np.sum(best_w) > 0:
        best_w = best_w / np.sum(best_w)
    else:
        best_w = np.array([1/3, 1/3, 1/3])
        
    return best_w.tolist()

def run_stream(models, df, feature_cols, adaptive=True):
    """
    Main loop with prediction buffer, ADWIN, and optional PSO.
    Returns results_log, drift_log.
    """
    weights = [np.round(1/3, 4), np.round(1/3, 4), np.round(1/3, 4)]
    
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
        pred, prob = ensemble_predict(models, weights, features_row_df)
        
        buffer.append({
            'row_index': current_index,
            'prediction': pred,
            'probability': prob,
            'weights': list(weights),
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
                    
                    old_weights = list(weights)
                    w_new = pso_optimize(models, df, resolved_indices, feature_cols)
                    weights = [np.round(w_new[0], 4), np.round(w_new[1], 4), np.round(w_new[2], 4)]
                    
                    drift_log.append({
                        'date': df.iloc[past_idx]['Date'],  # date of the row that triggered drift
                        'row_index': past_idx,
                        'w_old_before': old_weights[0],
                        'w_medium_before': old_weights[1],
                        'w_recent_before': old_weights[2],
                        'w_old_after': weights[0],
                        'w_medium_after': weights[1],
                        'w_recent_after': weights[2]
                    })
                    
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
                'drift_detected': drift_detected
            })
            
    return results_log, drift_log

def main():
    # REPRODUCIBILITY
    random.seed(42)
    np.random.seed(42)
    
    # Load Models & Data
    models = load_models('models')
    df_test = pd.read_csv('data/processed/test.csv')
    df_test = df_test.sort_values('Date').reset_index(drop=True)
    
    os.makedirs('results', exist_ok=True)
    
    print("Running Static Baseline Protocol...")
    results_static, _ = run_stream(models, df_test, FEATURES, adaptive=False)
    df_static = pd.DataFrame(results_static)
    df_static.to_csv('results/static_results.csv', index=False)
    
    print("\nRunning Adaptive PSO Protocol...")
    results_adaptive, drift_events = run_stream(models, df_test, FEATURES, adaptive=True)
    df_adaptive = pd.DataFrame(results_adaptive)
    df_adaptive.to_csv('results/stream_results.csv', index=False)
    
    if drift_events:
        df_drift = pd.DataFrame(drift_events)
        df_drift.to_csv('results/drift_events.csv', index=False)
    else:
        df_drift = pd.DataFrame()
        
    print("\n" + "="*50)
    print("SIMULATION SUMMARY")
    print("="*50)
    print(f"Total days simulated:       {len(df_test)}")
    print(f"Total predictions resolved: {len(results_static)}")
    print(f"Drift events detected:      {len(drift_events)}")
    if not df_drift.empty:
        print("Drift dates:")
        for idx, row in df_drift.iterrows():
            print(f"  - {row['date']} (Row {row['row_index']})")
            
    acc_static = 1.0 - df_static['error'].mean()
    acc_adaptive = 1.0 - df_adaptive['error'].mean()
    
    print(f"\nFinal Static Accuracy:   {acc_static:.4f}")
    print(f"Final Adaptive Accuracy: {acc_adaptive:.4f}")
    print(f"Accuracy Delta:          {(acc_adaptive - acc_static):.4f}")
    print("="*50)

if __name__ == '__main__':
    main()
