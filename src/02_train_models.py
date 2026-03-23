import os
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from xgboost import XGBClassifier
from sklearn.metrics import f1_score
from tqdm import tqdm

from src.firebase_client import FirebaseClient

FEATURES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_Position', 'MA_5_20_Ratio',
    'Volume_Change_Pct', 'Yesterday_Return'
]
TARGET = 'Target'

def load_window(filepath, start, end):
    """
    Load data from filepath and filter chronologically by Date.
    Returns the dataframe corresponding to [start, end].
    """
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Filter by date range (inclusive)
    mask = (df['Date'] >= start) & (df['Date'] <= end)
    df_filtered = df.loc[mask].copy()
    
    # Sort chronologically by Date
    df_filtered = df_filtered.sort_values(by='Date').reset_index(drop=True)
    
    # XGBoost raises error for inf values when missing parameter is not configured explicitly to handle it
    # We replace inf / -inf with NaN, which xgboost handles natively
    df_filtered.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df_filtered

def train_model(X_train, y_train):
    model = XGBClassifier(
        max_depth=3,
        learning_rate=0.03,      # slower learning than before
        n_estimators=1000,        # fixed, no early stopping
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_weight=3,
        gamma=1,                 # minimum loss reduction to split
        reg_alpha=0.1,           # L1 regularization
        reg_lambda=1.0,          # L2 regularization
        eval_metric='logloss',
        random_state=42
    )
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_val, y_val, name):
    """
    Evaluate the model on validation data and return Brier Score and F1.
    """
    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1]
    
    brier = 1.0 - np.mean((probs - y_val)**2)
    f1 = f1_score(y_val, preds, zero_division=0)
    
    return brier, f1

def save_model(model, path):
    """
    Save the trained model to the designated path.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    # Print statement removed to avoid messing up tqdm progress bar

def push_model_registry(results: list) -> None:
    """Push trained model metadata to Firebase."""
    client = FirebaseClient()
    for name, period, brier, f1 in results:
        client.save_document('model_registry', name.lower().replace(' ', '_'), {
            'model_name': name,
            'train_period': period,
            'val_brier_score': round(float(brier), 4),
            'f1_score': round(float(f1), 4),
            'trained_at': datetime.now().isoformat()
        })
    print("✓ Model registry pushed to Firebase")

def main():
    filepath = 'data/processed/train.csv'
    
    windows = [
        {"name": "Model_OLD", "start": "2015-01-01", "end": "2017-12-31", "save_path": "models/model_old.pkl"},
        {"name": "Model_MEDIUM", "start": "2016-01-01", "end": "2018-12-31", "save_path": "models/model_medium.pkl"},
        {"name": "Model_RECENT", "start": "2017-01-01", "end": "2019-12-31", "save_path": "models/model_recent.pkl"}
    ]
    
    results = []
    
    for w in tqdm(windows, desc="Training Models", unit="window"):
        # 1. Load window data
        df_window = load_window(filepath, w["start"], w["end"])
        
        # 2. Chronological Train/Val split (80/20)
        split_idx = int(len(df_window) * 0.8)
        
        # No shuffle, split strictly by index based on sorted dates
        train_df = df_window.iloc[:split_idx]
        val_df = df_window.iloc[split_idx:]
        
        X_train = train_df[FEATURES]
        y_train = train_df[TARGET]
        
        X_val = val_df[FEATURES]
        y_val = val_df[TARGET]
        
        # 3. Train model
        model = train_model(X_train, y_train)
        
        # 4. Evaluate only on Validation Set
        brier, f1 = evaluate_model(model, X_val, y_val, w["name"])
        
        train_period_str = f"{w['start']} to {w['end']}"
        results.append((w['name'], train_period_str, brier, f1))
        
        # 5. Save model
        save_model(model, w["save_path"])
        
    print("\n" + "="*70)
    print(f"{'Model':<15} | {'Train Period':<25} | {'Val Brier':<12} | {'F1':<8}")
    print("-" * 70)
    for res in results:
        print(f"{res[0]:<15} | {res[1]:<25} | {res[2]:<12.4f} | {res[3]:<8.4f}")
    print("="*70 + "\n")
    
    # Push model registry to Firebase
    try:
        push_model_registry(results)
    except Exception as e:
        print(f"Firebase push failed (non-fatal): {e}")

if __name__ == '__main__':
    main()
