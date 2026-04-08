import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz

import importlib
from dotenv import load_dotenv

load_dotenv()

scheduler = importlib.import_module('src.07_scheduler')
scheduler.initialize_system()

from src.yfinance_session import yf_fetch_with_retry
from src.feature_engineering import engineer_features

IST = pytz.timezone('Asia/Kolkata')

def backfill_predictions(start_date_str, end_date_str):
    hist = yf_fetch_with_retry(scheduler.NIFTY_TICKER, period='2y')
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get all trading dates in the range
    dates = pd.bdate_range(start=start_date, end=end_date).date
    
    for target_date in dates:
        date_str = target_date.strftime('%Y-%m-%d')
        print(f"Processing prediction for {date_str}...")
        
        # Check if prediction already exists
        existing = scheduler.firebase_client.get_prediction_by_date(date_str)
        if existing:
            print(f"Prediction for {date_str} already exists, skipping...")
            continue
            
        # Slice history up to target_date
        hist_slice = hist[hist.index.date <= target_date].copy()
        if hist_slice.empty:
            print(f"No history for {date_str}, skipping")
            continue
            
        # Engineer features
        try:
            df_feat = engineer_features(hist_slice)
            df_feat = df_feat.dropna()
            if df_feat.empty:
                print(f"No valid features for {date_str}, skipping")
                continue
                
            features_today = df_feat.iloc[[-1]][scheduler.ALL_FEATURES]
        except Exception as e:
            print(f"Feature engineering failed for {date_str}: {e}")
            continue
            
        # Predict
        pred, prob = scheduler.ensemble_predict(
            scheduler.models, scheduler.ensemble_weights,
            features_today,
            scheduler.active_features,
            scheduler.ALL_FEATURES
        )
        
        pred_label = 'UP' if pred == 1 else 'DOWN'
        print(f"Prediction for {date_str}: {pred_label} (prob={prob:.4f})")
        
        prediction_dict = {
            'date': date_str,
            'prediction': int(pred),
            'prediction_label': pred_label,
            'ensemble_probability': round(float(prob), 6),
            'close_at_prediction': round(float(hist_slice['Close'].iloc[-1]), 4),
            'active_features': scheduler.active_features,
            'active_feature_count': len(scheduler.active_features),
            'resolved': False,
            'truth': None,
            'error': None,
            'created_at': datetime.now(IST).isoformat()
        }
        
        for i, field_name in enumerate(scheduler.MODEL_MAPPING.values()):
            prediction_dict[f'w_{field_name}'] = round(float(scheduler.ensemble_weights[i]), 4)
            
        scheduler.firebase_client.save_prediction(prediction_dict)
        print(f"Saved prediction for {date_str}")
        
    print("Running pending evaluations...")
    scheduler.evaluate_pending_predictions(n=20)
    print("Backfill completed.")

if __name__ == "__main__":
    backfill_predictions('2026-03-31', '2026-04-08')
