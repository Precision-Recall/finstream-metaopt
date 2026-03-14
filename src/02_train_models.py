import os
import pandas as pd
import joblib
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from tqdm import tqdm

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
    return df_filtered

def train_model(X_train, y_train):
    """
    Train an XGBoost model with fixed parameters.
    """
    model = XGBClassifier(
        max_depth=3,
        learning_rate=0.05,
        n_estimators=100,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_val, y_val, name):
    """
    Evaluate the model on validation data and return metrics.
    """
    preds = model.predict(X_val)
    acc = accuracy_score(y_val, preds)
    prec = precision_score(y_val, preds, zero_division=0)
    rec = recall_score(y_val, preds, zero_division=0)
    f1 = f1_score(y_val, preds, zero_division=0)
    
    return acc, prec, rec, f1

def save_model(model, path):
    """
    Save the trained model to the designated path.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    # Print statement removed to avoid messing up tqdm progress bar

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
        acc, prec, rec, f1 = evaluate_model(model, X_val, y_val, w["name"])
        
        train_period_str = f"{w['start']} to {w['end']}"
        results.append((w['name'], train_period_str, acc, f1))
        
        # 5. Save model
        save_model(model, w["save_path"])
        
    print("\n" + "="*70)
    print(f"{'Model':<15} | {'Train Period':<25} | {'Val Accuracy':<12} | {'F1':<8}")
    print("-" * 70)
    for res in results:
        print(f"{res[0]:<15} | {res[1]:<25} | {res[2]:<12.4f} | {res[3]:<8.4f}")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
