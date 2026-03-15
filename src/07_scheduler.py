"""
Daily Scheduler for Adaptive ML Pipeline.

Two jobs run daily:
  1. daily_predict()  @ 09:30 IST — Make today's NIFTY prediction
  2. daily_evaluate() @ 09:35 IST — Evaluate predictions from 5 days ago

State persists in Firestore between runs.
Council weights update when drift is detected.

Run with --test flag to execute jobs once immediately without scheduling.
"""

import os
import sys
import argparse
import logging
import importlib
import numpy as np
import pandas as pd
import yfinance as yf
import ta
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import pytz

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from river.drift import ADWIN

from src.feature_engineering import engineer_features
from src.firebase_client import FirebaseClient

# Import modules with numeric prefixes using importlib
_stream_module = importlib.import_module('src.03_stream_loop')
load_models = _stream_module.load_models
ensemble_predict = _stream_module.ensemble_predict

_mho_module = importlib.import_module('src.05_mho_council')
MHOCouncil = _mho_module.MHOCouncil

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# India Standard Time
IST = pytz.timezone('Asia/Kolkata')

# Test mode flag (set to True for --test runs)
TEST_MODE = False

# Configuration from .env
NIFTY_TICKER = os.getenv('NIFTY_TICKER', '^NSEI')
PREDICTION_HORIZON = int(os.getenv('PREDICTION_HORIZON', 5))
ADWIN_DELTA = float(os.getenv('ADWIN_DELTA', 1.0))
MODEL_DIR = os.getenv('MODEL_DIR', 'models')
DATA_DIR = os.getenv('DATA_DIR', 'data/processed')

ALL_FEATURES = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_Position', 'MA_5_20_Ratio',
    'Volume_Change_Pct', 'Yesterday_Return'
]

# Global state (loaded at startup)
models = None
firebase_client = None
council = None
adwin = None
active_features = None
ensemble_weights = None


def initialize_system():
    """
    Load models, initialize Firebase client, and restore state.
    Called once at startup.
    """
    global models, firebase_client, council, adwin, active_features, ensemble_weights
    
    logger.info("Initializing adaptive ML system...")
    
    # Load models
    try:
        models = load_models(MODEL_DIR)
        logger.info(f"✓ Models loaded: {list(models.keys())}")
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        sys.exit(1)
    
    # Initialize Firebase client
    try:
        firebase_client = FirebaseClient()
        logger.info("✓ Firebase client initialized")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        logger.warning("Continuing without Firebase (predictions won't be saved)")
        firebase_client = None
    
    # Initialize council and ADWIN
    council = MHOCouncil()
    adwin = ADWIN(delta=ADWIN_DELTA)
    logger.info("✓ Council and ADWIN initialized")
    
    # Restore state from Firebase
    if firebase_client:
        state = firebase_client.get_model_state()
        if state:
            active_features = state.get('active_features', ALL_FEATURES.copy())
            w_dict = state.get('ensemble_weights', {})
            ensemble_weights = [
                w_dict.get('old', 1/3),
                w_dict.get('medium', 1/3),
                w_dict.get('recent', 1/3)
            ]
            logger.info(f"✓ State restored from Firebase")
            logger.info(f"  Active features: {active_features}")
            logger.info(f"  Ensemble weights: {ensemble_weights}")
        else:
            active_features = ALL_FEATURES.copy()
            ensemble_weights = [1/3, 1/3, 1/3]
            logger.info("✓ Initialized with default state (first run)")
    else:
        active_features = ALL_FEATURES.copy()
        ensemble_weights = [1/3, 1/3, 1/3]
        logger.info("✓ Initialized with default state (Firebase unavailable)")
    
    logger.info("System initialization complete")


def is_market_holiday() -> bool:
    """
    Check if today is a weekend or market holiday (NIFTY doesn't trade).
    """
    today = datetime.now(IST)
    # Weekends: 5=Saturday, 6=Sunday
    return today.weekday() >= 5


def engineer_today_features() -> Optional[pd.DataFrame]:
    """
    Fetch NIFTY data and engineer features for today.
    
    Returns:
        DataFrame with one row of features, or None on error.
    """
    try:
        if is_market_holiday() and not TEST_MODE:
            logger.info("Market holiday — skipping prediction")
            return None
        
        # Fetch last 60 days of NIFTY data
        ticker = yf.Ticker(NIFTY_TICKER)
        hist = ticker.history(period='60d')
        
        if hist is None or len(hist) == 0:
            logger.error("Failed to fetch NIFTY data")
            return None
        
        # Engineer features
        close = hist['Close']
        high = hist['High']
        low = hist['Low']
        volume = hist['Volume']
        
        # RSI_14
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
        
        # MACD
        macd_ind = ta.trend.MACD(close)
        macd = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()
        macd_diff = macd_ind.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_high = bb.bollinger_hband()
        bb_low = bb.bollinger_lband()
        bb_position = (close - bb_low) / (bb_high - bb_low)
        
        # Moving Average Ratio
        ma_5 = close.rolling(5).mean()
        ma_20 = close.rolling(20).mean()
        ma_ratio = ma_5 / ma_20
        
        # Volume Change %
        vol_change = volume.pct_change().clip(-2, 2)
        
        # Yesterday Return
        yesterday_return = close.pct_change()
        
        # Combine into DataFrame
        df = pd.DataFrame({
            'RSI_14': rsi,
            'MACD': macd,
            'MACD_Signal': macd_signal,
            'MACD_Diff': macd_diff,
            'BB_Position': bb_position,
            'MA_5_20_Ratio': ma_ratio,
            'Volume_Change_Pct': vol_change,
            'Yesterday_Return': yesterday_return
        })
        
        # Drop NaN and take last row
        df = df.dropna()
        if len(df) == 0:
            logger.error("No valid features after dropping NaN")
            return None
        
        features_today = df.iloc[[-1]]  # Last row as DataFrame
        logger.info(f"✓ Features engineered for {len(df)} days available")
        return features_today
    
    except Exception as e:
        logger.error(f"Error engineering features: {e}")
        return None


def daily_predict():
    """
    JOB 1: Make today's NIFTY prediction @ 09:30 IST.
    
    Steps:
      1. Engineer features for today
      2. Make ensemble prediction
      3. Save to Firebase
      4. Update model state (last_prediction_date)
    """
    global active_features, ensemble_weights
    
    logger.info("=" * 60)
    logger.info("JOB: daily_predict @ 09:30 IST")
    logger.info("=" * 60)
    
    if datetime.now(IST).weekday() >= 5 and not TEST_MODE:
        logger.info("Market holiday — skipping")
        return
    
    try:
        # Engineer features
        features_today = engineer_today_features()
        if features_today is None:
            logger.warning("Failed to engineer features")
            return
        
        # Make prediction
        today_str = datetime.now(IST).strftime('%Y-%m-%d')
        pred, prob = ensemble_predict(
            models, ensemble_weights,
            features_today,
            active_features,
            ALL_FEATURES
        )
        
        pred_label = 'UP' if pred == 1 else 'DOWN'
        logger.info(f"Prediction: {pred_label} (prob={prob:.4f})")
        
        # Save to Firebase
        if firebase_client:
            prediction_dict = {
                'date': today_str,
                'prediction': int(pred),
                'prediction_label': pred_label,
                'ensemble_probability': round(float(prob), 6),
                'w_old': round(float(ensemble_weights[0]), 4),
                'w_medium': round(float(ensemble_weights[1]), 4),
                'w_recent': round(float(ensemble_weights[2]), 4),
                'active_features': active_features,
                'active_feature_count': len(active_features),
                'resolved': False,
                'truth': None,
                'error': None,
                'created_at': datetime.now(IST).isoformat()
            }
            
            if firebase_client.save_prediction(prediction_dict):
                logger.info("✓ Prediction saved to Firebase")
            else:
                logger.warning("Failed to save prediction to Firebase")
            
            # Update model state
            state_update = {
                'last_prediction_date': today_str,
                'updated_at': datetime.now(IST).isoformat()
            }
            firebase_client.update_model_state(state_update)
        
        logger.info("daily_predict completed successfully")
    
    except Exception as e:
        logger.error(f"Error in daily_predict: {e}")


def daily_evaluate():
    """
    JOB 2: Evaluate predictions from 5 business days ago @ 09:35 IST.
    
    Steps:
      1. Calculate target date (5 business days ago)
      2. Fetch actual NIFTY close price
      3. Get prediction from Firebase
      4. Compute truth and error
      5. Update ADWIN
      6. If drift detected: run council optimization
      7. Save evaluation and drift event to Firebase
    """
    global active_features, ensemble_weights, adwin
    
    logger.info("=" * 60)
    logger.info("JOB: daily_evaluate @ 09:35 IST")
    logger.info("=" * 60)
    
    if datetime.now(IST).weekday() >= 5 and not TEST_MODE:
        logger.info("Market holiday — skipping")
        return
    
    try:
        # Calculate target date (5 business days ago)
        today = datetime.now(IST).date()
        dates = pd.bdate_range(end=today, periods=6)
        target_date = dates[0].date()
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        logger.info(f"Evaluating prediction from {target_date_str}")
        
        # Get prediction from Firebase
        if not firebase_client:
            logger.warning("Firebase client unavailable — skipping evaluation")
            return
        
        prediction = firebase_client.get_prediction_by_date(target_date_str)
        if not prediction:
            logger.warning(f"Prediction not found for {target_date_str}")
            if TEST_MODE:
                logger.info("TEST MODE: No prediction to evaluate — this is expected on first run")
                logger.info("In production, predictions from 5 days ago will be evaluated here")
            return
        
        # Fetch actual price data
        try:
            ticker = yf.Ticker(NIFTY_TICKER)
            # Get close price on target date and check if it went up
            hist = ticker.history(
                start=target_date - timedelta(days=1),
                end=today + timedelta(days=1)
            )
            
            if len(hist) < 2:
                logger.warning(f"Insufficient price data for {target_date_str}")
                return
            
            close_at_prediction = hist['Close'].iloc[0]
            close_5_days_later = hist['Close'].iloc[-1]
            
            # Truth: did price go UP (1) or DOWN (0) over 5 days?
            truth = 1 if close_5_days_later > close_at_prediction else 0
            actual_label = 'UP' if truth == 1 else 'DOWN'
            
            predicted_value = prediction.get('prediction', 0)
            predicted_prob = prediction.get('ensemble_probability', 0.5)
            error = 1 if predicted_value != truth else 0
            continuous_error = abs(predicted_prob - truth)
            
            logger.info(f"  Predicted: {'UP' if predicted_value == 1 else 'DOWN'} "
                       f"(prob={predicted_prob:.4f})")
            logger.info(f"  Actual: {actual_label}")
            logger.info(f"  Error: {error}")
            
            # Update ADWIN
            adwin.update(continuous_error)
            drift_flag = adwin.drift_detected
            
            if drift_flag:
                logger.warning("⚠️  DRIFT DETECTED!")
            
            # Save evaluation
            evaluation_dict = {
                'date': target_date_str,
                'prediction': int(predicted_value),
                'truth': int(truth),
                'error': int(error),
                'continuous_error': round(float(continuous_error), 6),
                'adwin_updated': True,
                'drift_detected': drift_flag,
                'evaluated_at': datetime.now(IST).isoformat()
            }
            
            if firebase_client.save_evaluation(evaluation_dict):
                logger.info("✓ Evaluation saved to Firebase")
            
            # If drift detected, run council optimization
            if drift_flag:
                logger.info("Starting council optimization...")
                
                old_active_features = active_features.copy()
                old_ensemble_weights = ensemble_weights.copy()
                
                # Build resolved_df from last 60 evaluations
                # For this demo, just trigger council optimization
                # In production, would fetch last 60 evaluation dates and rebuild features
                
                # Mock resolved_df (just for illustration)
                # In production: fetch from Firebase, engineer features, build real DataFrame
                resolved_df_mock = pd.DataFrame({
                    'RSI_14': [0.5] * 60,
                    'MACD': [0.0] * 60,
                    'MACD_Signal': [0.0] * 60,
                    'MACD_Diff': [0.0] * 60,
                    'BB_Position': [0.5] * 60,
                    'MA_5_20_Ratio': [1.0] * 60,
                    'Volume_Change_Pct': [0.01] * 60,
                    'Yesterday_Return': [0.005] * 60,
                    'Target': [1] * 60  # Mock truth values
                })
                
                # Run council
                result = council.optimize(
                    models=models,
                    resolved_df=resolved_df_mock,
                    all_features=ALL_FEATURES
                )
                
                active_features = result['active_features']
                ensemble_weights = result['ensemble_weights']
                
                logger.info(f"✓ Council optimization complete")
                logger.info(f"  New active features: {active_features}")
                logger.info(f"  New ensemble weights: {ensemble_weights}")
                logger.info(f"  Algorithm fitnesses: {result['algorithm_fitnesses']}")
                logger.info(f"  Council weights: {result['council_weights']}")
                
                # Save drift event
                drift_dict = {
                    'date': target_date_str,
                    'row_index': 0,
                    'w_old_before': round(float(old_ensemble_weights[0]), 4),
                    'w_medium_before': round(float(old_ensemble_weights[1]), 4),
                    'w_recent_before': round(float(old_ensemble_weights[2]), 4),
                    'w_old_after': round(float(ensemble_weights[0]), 4),
                    'w_medium_after': round(float(ensemble_weights[1]), 4),
                    'w_recent_after': round(float(ensemble_weights[2]), 4),
                    'active_features_before': ','.join(old_active_features),
                    'active_features_after': ','.join(active_features),
                    'fit_pso': result['algorithm_fitnesses']['pso'],
                    'fit_ga': result['algorithm_fitnesses']['ga'],
                    'fit_gwo': result['algorithm_fitnesses']['gwo'],
                    'cw_pso': result['council_weights']['pso'],
                    'cw_ga': result['council_weights']['ga'],
                    'cw_gwo': result['council_weights']['gwo'],
                    'detected_at': datetime.now(IST).isoformat()
                }
                
                if firebase_client.save_drift_event(drift_dict):
                    logger.info("✓ Drift event saved to Firebase")
                
                # Update model state
                state_update = {
                    'active_features': active_features,
                    'ensemble_weights': {
                        'old': ensemble_weights[0],
                        'medium': ensemble_weights[1],
                        'recent': ensemble_weights[2]
                    },
                    'council_weights': result['council_weights'],
                    'drift_count': 1,  # In production: increment from Firebase
                    'last_drift_date': target_date_str,
                    'updated_at': datetime.now(IST).isoformat()
                }
                firebase_client.update_model_state(state_update)
                
                # Reset ADWIN
                adwin = ADWIN(delta=ADWIN_DELTA)
                logger.info("✓ ADWIN reset")
            
            logger.info("daily_evaluate completed successfully")
        
        except Exception as e:
            logger.error(f"Error fetching price data: {e}")
    
    except Exception as e:
        logger.error(f"Error in daily_evaluate: {e}")


def start_scheduler():
    """Start APScheduler with the two daily jobs."""
    logger.info("Starting APScheduler...")
    
    scheduler = BlockingScheduler(timezone='Asia/Kolkata')
    
    # Job 1: Daily prediction @ 09:30 IST
    scheduler.add_job(
        daily_predict,
        trigger='cron',
        hour=9,
        minute=30,
        id='daily_predict',
        name='Daily NIFTY Prediction'
    )
    
    # Job 2: Daily evaluation @ 09:35 IST
    scheduler.add_job(
        daily_evaluate,
        trigger='cron',
        hour=9,
        minute=35,
        id='daily_evaluate',
        name='Daily Prediction Evaluation'
    )
    
    print("\n" + "=" * 70)
    print("NIFTY50 Adaptive ML Scheduler Started")
    print("=" * 70)
    print(f"Project ID:      {firebase_client.project_id if firebase_client else 'N/A'}")
    print(f"Models:          {list(models.keys())}")
    print(f"Active Features: {active_features}")
    print(f"Ensemble Weights: {[round(w, 4) for w in ensemble_weights]}")
    print("\nScheduled Jobs:")
    print("  [1] daily_predict    @ 09:30 IST (Make prediction)")
    print("  [2] daily_evaluate   @ 09:35 IST (Evaluate & detect drift)")
    print("\nPress Ctrl+C to stop.\n")
    print("=" * 70 + "\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


def main():
    """Main entry point."""
    global TEST_MODE
    
    parser = argparse.ArgumentParser(
        description='NIFTY50 Adaptive ML Pipeline Scheduler'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run jobs once immediately (test mode, no scheduling)'
    )
    
    args = parser.parse_args()
    
    # Initialize system
    initialize_system()
    
    if args.test:
        # Test mode: run jobs once, bypassing weekend guard
        TEST_MODE = True
        logger.info("TEST MODE: Running jobs once")
        logger.info("-" * 70)
        
        daily_predict()
        logger.info("-" * 70)
        
        daily_evaluate()
        logger.info("-" * 70)
        
        logger.info("TEST MODE: Jobs completed")
        sys.exit(0)
    else:
        # Scheduler mode: run indefinitely
        start_scheduler()


if __name__ == '__main__':
    main()
