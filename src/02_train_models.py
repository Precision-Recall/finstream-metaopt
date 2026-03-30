import os
import warnings
warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed should be used with.*")

import numpy as np
import pandas as pd
import joblib
from datetime import datetime

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from tqdm import tqdm

from src.firebase_client import FirebaseClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEATURES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_Position', 'MA_5_20_Ratio',
    'Volume_Change_Pct', 'Yesterday_Return',
    'MA_50', 'MA_200', 'Institutional_Flow'
]
TARGET = 'Target'

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
# Each entry maps an algo_type string to:
#   base_fn  — factory that returns an untrained estimator (for RandomizedSearchCV)
#   default  — factory that returns a fully configured estimator (for optimize=False)
#   space    — hyperparameter search space (None = skip RandomizedSearchCV)
#
# To add a new model: add one entry here. Nothing else needs to change.
# ---------------------------------------------------------------------------

def _xgb_base():
    return XGBClassifier(eval_metric='logloss', random_state=42)

def _xgb_default():
    return XGBClassifier(
        max_depth=3, learning_rate=0.03, n_estimators=1000,
        subsample=0.7, colsample_bytree=0.7, min_child_weight=3,
        gamma=1, reg_alpha=0.1, reg_lambda=1.0,
        eval_metric='logloss', random_state=42
    )

def _lgbm_base():
    return LGBMClassifier(random_state=42, verbosity=-1)

def _lgbm_default():
    return LGBMClassifier(
        n_estimators=1000, learning_rate=0.03, max_depth=3,
        num_leaves=7, subsample=0.7, colsample_bytree=0.7,
        reg_alpha=0.1, reg_lambda=1.0,
        random_state=42, importance_type='gain', verbosity=-1
    )

def _et_base():
    return ExtraTreesClassifier(random_state=42, n_jobs=-1)

def _et_default():
    return ExtraTreesClassifier(
        n_estimators=500, max_depth=5,
        min_samples_split=5, min_samples_leaf=2,
        random_state=42, n_jobs=-1
    )

def _logistic_default():
    # Logistic Regression: linear decision boundary gives architecturally
    # decorrelated errors vs tree ensemble — key for MHO Council diversity.
    # StandardScaler pipeline: LR is sensitive to feature scale.
    # No RandomizedSearchCV: hyperparams are stable for a linear model on 8 features.
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(
            C=0.1, max_iter=1000, random_state=42, solver='lbfgs'
        ))
    ])

MODEL_REGISTRY = {
    "xgboost": {
        "base_fn":  _xgb_base,
        "default":  _xgb_default,
        "space": {
            'n_estimators':    [500, 1000, 1500],
            'max_depth':       [3, 4, 5, 6],
            'learning_rate':   [0.01, 0.03, 0.05, 0.1],
            'subsample':       [0.7, 0.8, 0.9],
            'colsample_bytree':[0.7, 0.8, 0.9],
            'gamma':           [0, 1, 5],
            'reg_alpha':       [0, 0.1, 1],
            'reg_lambda':      [0, 1, 10],
        },
    },
    "lightgbm": {
        "base_fn":  _lgbm_base,
        "default":  _lgbm_default,
        "space": {
            'n_estimators':    [500, 1000, 1500],
            'max_depth':       [3, 5, 7, -1],
            'num_leaves':      [7, 15, 31, 63],
            'learning_rate':   [0.01, 0.03, 0.05, 0.1],
            'subsample':       [0.7, 0.8, 0.9],
            'colsample_bytree':[0.7, 0.8, 0.9],
            'reg_alpha':       [0, 0.1, 1],
            'reg_lambda':      [0, 1, 10],
        },
    },
    "extratrees": {
        "base_fn":  _et_base,
        "default":  _et_default,
        "space": {
            'n_estimators':    [100, 300, 500],
            'max_depth':       [5, 10, 20, None],
            'min_samples_split':[2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features':    ['sqrt', 'log2', None],
        },
    },
    "logistic": {
        "base_fn":  None,           # no RandomizedSearchCV for linear model
        "default":  _logistic_default,
        "space":    None,
    },
}

# ---------------------------------------------------------------------------
# Ensemble configuration
# ---------------------------------------------------------------------------
# Slice strategy — WHY these choices:
#   xgboost    → oldest 50%:  learns the older market regime
#   lightgbm   → full 100%:   trained on full history for stable probability
#                              calibration. Previously trained on "recent 50%"
#                              which caused NEGATIVE correlation with XGBoost
#                              (-0.35), actively degrading ensemble quality.
#   extratrees → full 100%:   stable all-eras baseline; diversity from algo type
#   logistic   → full 100%:   linear boundary; diversity from architecture, not data
# ---------------------------------------------------------------------------

MODELS_CONFIG = [
    {"name": "Model_OLD",    "type": "xgboost",    "save_path": "models/xgboost.pkl",    "slice": "old"},
    {"name": "Model_MEDIUM", "type": "lightgbm",   "save_path": "models/lightgbm.pkl",   "slice": "full"},
    {"name": "Model_RECENT", "type": "extratrees", "save_path": "models/extratrees.pkl", "slice": "full"},
    {"name": "Model_LINEAR", "type": "logistic",   "save_path": "models/logistic.pkl",   "slice": "full"},
]

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_training_data(filepath: str) -> pd.DataFrame:
    """Load, sort chronologically, and sanitise the training CSV."""
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    # XGBoost errors on inf values — replace with NaN which it handles natively
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df


def build_slice_map(df: pd.DataFrame) -> dict:
    """
    Return the three temporal slices used across model configs.
    Slices share the underlying DataFrame memory — no copies made.
    """
    n = len(df)
    return {
        "old":    df.iloc[:int(n * 0.50)],   # oldest 50%
        "recent": df.iloc[int(n * 0.50):],   # newest 50%
        "full":   df,                         # all rows
    }


def train_model(X_train, y_train, algo_type: str, optimize: bool = True):
    """
    Train a model of the given algo_type.

    Args:
        X_train    : feature DataFrame
        y_train    : target Series
        algo_type  : key into MODEL_REGISTRY
        optimize   : if True, run RandomizedSearchCV; else use default hyperparams

    Returns:
        Fitted estimator
    """
    if algo_type not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown algo_type '{algo_type}'. "
            f"Valid options: {list(MODEL_REGISTRY.keys())}"
        )

    entry = MODEL_REGISTRY[algo_type]

    # Models with no search space (e.g. logistic) always use default params
    if not optimize or entry["space"] is None:
        if entry["space"] is None and optimize:
            print(f"  [{algo_type}] No search space defined — using default hyperparams.")
        model = entry["default"]()
        model.fit(X_train, y_train)
        return model

    # RandomizedSearchCV path
    print(f"  [{algo_type}] Running RandomizedSearchCV (n_iter=20, cv=3)...")
    search = RandomizedSearchCV(
        entry["base_fn"](),
        param_distributions=entry["space"],
        n_iter=20,
        scoring='neg_log_loss',
        cv=TimeSeriesSplit(n_splits=5),
        verbose=0,
        random_state=42,
        n_jobs=-1,
    )
    search.fit(X_train, y_train)
    print(f"  [{algo_type}] Best params: {search.best_params_}")
    return search.best_estimator_


def evaluate_model(model, X_val, y_val) -> tuple:
    """
    Evaluate a fitted model on validation data.

    Returns:
        (brier_score, f1_score) — both higher-is-better
    """
    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1]
    brier = 1.0 - float(np.mean((probs - y_val) ** 2))
    f1    = f1_score(y_val, preds, zero_division=0)
    return brier, f1


def save_model(model, path: str) -> None:
    """Persist a fitted model to disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)


def push_model_registry(results: list) -> None:
    """Push trained model metadata to Firebase model_registry collection."""
    client = FirebaseClient()
    for name, period, brier, f1 in results:
        client.save_document(
            'model_registry',
            name.lower().replace(' ', '_'),
            {
                'model_name':      name,
                'train_period':    period,
                'val_brier_score': round(float(brier), 4),
                'f1_score':        round(float(f1), 4),
                'trained_at':      datetime.now().isoformat(),
            }
        )
    print("✓ Model registry pushed to Firebase")


def print_results_table(results: list) -> None:
    """Print a formatted summary table of training results."""
    print("\n" + "=" * 70)
    print(f"{'Model Slot':<15} | {'Algorithm':<12} | {'Slice':<8} | {'Val Brier':<12} | {'F1':<8}")
    print("-" * 70)
    for cfg, (name, period, brier, f1) in zip(MODELS_CONFIG, results):
        print(
            f"{name:<15} | {cfg['type'].upper():<12} | "
            f"{cfg['slice']:<8} | {brier:<12.4f} | {f1:<8.4f}"
        )
    print("=" * 70 + "\n")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    filepath = 'data/processed/train.csv'

    print(f"Loading training data from {filepath}...")
    df_full = load_training_data(filepath)
    print(f"Loaded {len(df_full)} training rows.\n")

    slice_map = build_slice_map(df_full)
    results   = []

    for m in tqdm(MODELS_CONFIG, desc="Training Ensemble Components", unit="model"):
        df_slice  = slice_map[m["slice"]]
        split_idx = int(len(df_slice) * 0.80)   # 80/20 temporal train/val split

        X_train = df_slice.iloc[:split_idx][FEATURES]
        y_train = df_slice.iloc[:split_idx][TARGET]
        X_val   = df_slice.iloc[split_idx:][FEATURES]
        y_val   = df_slice.iloc[split_idx:][TARGET]

        print(
            f"\n  [{m['name']} / {m['type']}] slice={m['slice']}  "
            f"train={len(X_train)}  val={len(X_val)}"
        )

        model         = train_model(X_train, y_train, m["type"], optimize=True)
        brier, f1     = evaluate_model(model, X_val, y_val)
        results.append((m['name'], f"temporal-slice={m['slice']}", brier, f1))
        save_model(model, m["save_path"])

    print_results_table(results)

    try:
        push_model_registry(results)
    except Exception as e:
        print(f"Firebase push failed (non-fatal): {e}")


if __name__ == '__main__':
    main()