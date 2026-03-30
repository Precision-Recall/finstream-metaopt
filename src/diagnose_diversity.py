import numpy as np
import pandas as pd
import joblib

FEATURES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_Position', 'MA_5_20_Ratio',
    'Volume_Change_Pct', 'Yesterday_Return'
]
TARGET = 'Target'

models = {
    'xgboost':   joblib.load('models/xgboost.pkl'),
    'lightgbm':  joblib.load('models/lightgbm.pkl'),
    'extratrees':joblib.load('models/extratrees.pkl'),
    'logistic':  joblib.load('models/logistic.pkl'),
}

df = pd.read_csv('data/processed/test.csv')
df = df.sort_values('Date').reset_index(drop=True)
X = df[FEATURES]
y = df[TARGET].values

probs = {}
for key, model in models.items():
    probs[key] = model.predict_proba(X)[:, 1]

print("=== Per-model Brier Scores ===")
for key, p in probs.items():
    brier = 1.0 - np.mean((p - y)**2)
    print(f"  {key:<12}: {brier:.4f}")

print("\n=== Pairwise Correlation of Probabilities ===")
keys = list(probs.keys())
for i in range(len(keys)):
    for j in range(i+1, len(keys)):
        corr = np.corrcoef(probs[keys[i]], probs[keys[j]])[0,1]
        print(f"  {keys[i]} vs {keys[j]}: {corr:.4f}")

print("\n=== Prediction Agreement Rate ===")
preds = {k: (p > 0.5).astype(int) for k, p in probs.items()}
for i in range(len(keys)):
    for j in range(i+1, len(keys)):
        agree = np.mean(preds[keys[i]] == preds[keys[j]])
        print(f"  {keys[i]} vs {keys[j]}: {agree:.4f}")