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

from src.yfinance_session import yf_fetch_with_retry

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from river.drift import ADWIN

from src.feature_engineering import engineer_features
from src.firebase_client import FirebaseClient

# Import modules with numeric prefixes using importlib
_stream_module = importlib.import_module('src.03_stream_loop')
load_models = _stream_module.load_models
ensemble_predict = _stream_module.ensemble_predict
MODEL_MAPPING = _stream_module.MODEL_MAPPING

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
    'Volume_Change_Pct', 'Yesterday_Return',
    'MA_50', 'MA_200', 'Institutional_Flow'
]

# Global state (loaded at startup)
_system_initialized = False
models = None
firebase_client = None
council = None
adwin = None
active_features = None
ensemble_weights = None


def initialize_system():
    """
    Load models, initialize Firebase client, and restore state.
    Called once at startup or when importing from Flask.
    Uses guard flag to prevent re-initialization.
    """
    global models, firebase_client, council, adwin, active_features, ensemble_weights, _system_initialized
    
    if _system_initialized:
        return  # Already initialized, skip
    
    logger.info("Initializing adaptive ML system...")
    logger.info(f"Environment: PROJECT_ID={os.getenv('FIREBASE_PROJECT_ID', 'NOT SET')}, API_KEY={'SET' if os.getenv('FIREBASE_API_KEY') else 'NOT SET'}")
    
    # Load models
    try:
        models = load_models(MODEL_DIR)
        logger.info(f"✓ Models loaded: {list(models.keys())} (Diverse Ensemble)")
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        sys.exit(1)
    
    # Initialize Firebase client
    try:
        firebase_client = FirebaseClient()
        logger.info("✓ Firebase client initialized successfully")
    except ValueError as e:
        logger.critical(f"FIREBASE INITIALIZATION FAILED - Missing credentials: {e}")
        logger.critical(f"  FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID', 'NOT SET')}")
        logger.critical(f"  FIREBASE_API_KEY: {'SET' if os.getenv('FIREBASE_API_KEY') else 'NOT SET'}")
        logger.critical("Aborting - cannot proceed without Firebase credentials")
        firebase_client = None
    except Exception as e:
        logger.critical(f"FIREBASE INITIALIZATION FAILED - Unexpected error: {e}")
        logger.critical(f"Error type: {type(e).__name__}")
        logger.critical("Will attempt to continue, but data will NOT be saved")
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
                w_dict.get(field_name, 1.0/len(MODEL_MAPPING))
                for field_name in MODEL_MAPPING.values()
            ]
            logger.info(f"✓ State restored from Firebase")
            logger.info(f"  Active features: {active_features}")
            logger.info(f"  Ensemble weights: {ensemble_weights}")
        else:
            active_features = ALL_FEATURES.copy()
            ensemble_weights = [1.0/len(MODEL_MAPPING)] * len(MODEL_MAPPING)
            logger.info("✓ Initialized with default state (first run)")
    else:
        active_features = ALL_FEATURES.copy()
        ensemble_weights = [1.0/len(MODEL_MAPPING)] * len(MODEL_MAPPING)
        logger.info("✓ Initialized with default state (Firebase unavailable)")
    
    _system_initialized = True
    logger.info("System initialization complete")


def is_market_holiday() -> bool:
    """
    Check if today is a weekend or market holiday (NIFTY doesn't trade).
    """
    today = datetime.now(IST)
    # Weekends: 5=Saturday, 6=Sunday
    return today.weekday() >= 5


def engineer_today_features() -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], str]:
    """
    Fetch NIFTY data and engineer features for today.
    
    Returns:
        (features_df, raw_hist_df, error_string)
    """
    try:
        if is_market_holiday() and not TEST_MODE:
            logger.info("Market holiday — skipping prediction")
            return None, "market_holiday"
        
        # Fetch last 2 years of NIFTY data using retry wrapper to ensure enough history for MA_200
        hist = yf_fetch_with_retry(NIFTY_TICKER, period='2y')
        
        if hist is None or len(hist) == 0:
            logger.error("Failed to fetch NIFTY data")
            return None, None, "yfinance_returned_empty_dataframe"
        
        # Engineer features
        df = engineer_features(hist)
        
        # Drop NaN and take last row
        df = df.dropna()
        if len(df) == 0:
            logger.error("No valid features after dropping NaN")
            return None, None, "no_valid_features_after_dropna"
        
        # Keep only the features we need
        features_today = df.iloc[[-1]][ALL_FEATURES]
        logger.info(f"✓ Features engineered for {len(df)} days available")
        return features_today, hist, ""
    
    except Exception as e:
        logger.error(f"Error engineering features: {e}")
        import traceback
        return None, None, f"Exception: {str(e)} | Traceback: {traceback.format_exc()}"


def daily_predict():
    """
    JOB 1: Make today's NIFTY prediction @ 09:30 IST.
    
    Steps:
      1. Engineer features for today
      2. Make ensemble prediction
      3. Save to Firebase
      4. Update model state (last_prediction_date)
    
    Returns:
      dict with status: 'success', 'warning', or 'error'
    """
    global active_features, ensemble_weights
    
    logger.info("=" * 60)
    logger.info("JOB: daily_predict @ 09:30 IST")
    logger.info("=" * 60)
    
    if datetime.now(IST).weekday() >= 5 and not TEST_MODE:
        logger.info("Market holiday — skipping")
        return {'status': 'skipped', 'reason': 'weekend'}
    
    try:
        # Check Firebase availability
        if not firebase_client:
            logger.critical("FIREBASE CLIENT NOT AVAILABLE - CANNOT SAVE PREDICTIONS")
            logger.critical("Check environment variables: FIREBASE_PROJECT_ID, FIREBASE_API_KEY")
            return {'status': 'error', 'reason': 'firebase_unavailable'}
        
        # Engineer features
        features_today, hist, error_msg = engineer_today_features()
        if features_today is None:
            logger.error(f"Failed to engineer features: {error_msg}")
            return {'status': 'error', 'reason': 'feature_engineering_failed', 'details': error_msg}
        
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
        prediction_dict = {
            'date': today_str,
            'prediction': int(pred),
            'prediction_label': pred_label,
            'ensemble_probability': round(float(prob), 6),
            'close_at_prediction': round(float(hist['Close'].iloc[-1]), 4),
            'active_features': active_features,
            'active_feature_count': len(active_features),
            'resolved': False,
            'truth': None,
            'error': None,
            'created_at': datetime.now(IST).isoformat()
        }
        for i, field_name in enumerate(MODEL_MAPPING.values()):
            prediction_dict[f'w_{field_name}'] = round(float(ensemble_weights[i]), 4)
        
        save_success = firebase_client.save_prediction(prediction_dict)
        if not save_success:
            logger.critical(f"FAILED TO SAVE PREDICTION TO FIREBASE")
            logger.critical(f"Prediction data: {prediction_dict}")
            return {'status': 'error', 'reason': 'save_prediction_failed'}
        
        logger.info("✓ Prediction saved to Firebase")
        
        # Update model state
        state_update = {
            'last_prediction_date': today_str,
            'updated_at': datetime.now(IST).isoformat()
        }
        state_save_success = firebase_client.update_model_state(state_update)
        if not state_save_success:
            logger.warning(f"Failed to update model state")
            # Don't fail the whole job for this
        
        logger.info("daily_predict completed successfully")
        return {'status': 'success'}
    
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in daily_predict: {e}")
        logger.critical(f"Error type: {type(e).__name__}")
        import traceback
        logger.critical(f"Traceback: {traceback.format_exc()}")
        return {'status': 'error', 'reason': 'exception', 'error_message': str(e)}


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
    
    Returns:
      dict with status: 'success', 'skipped', or 'error'
    """
    global active_features, ensemble_weights, adwin
    
    logger.info("=" * 60)
    logger.info("JOB: daily_evaluate @ 09:35 IST")
    logger.info("=" * 60)
    
    if datetime.now(IST).weekday() >= 5 and not TEST_MODE:
        logger.info("Market holiday — skipping")
        return {'status': 'skipped', 'reason': 'weekend'}
    
    try:
        # Check Firebase availability
        if not firebase_client:
            logger.critical("FIREBASE CLIENT NOT AVAILABLE - CANNOT EVALUATE")
            return {'status': 'error', 'reason': 'firebase_unavailable'}
        
        # Calculate target date (5 business days ago)
        today = datetime.now(IST).date()
        dates = pd.bdate_range(end=today, periods=6)
        target_date = dates[0].date()
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        logger.info(f"Evaluating prediction from {target_date_str}")
        
        # Get prediction from Firebase
        prediction = firebase_client.get_prediction_by_date(target_date_str)
        if not prediction:
            logger.warning(f"Prediction not found for {target_date_str}")
            if TEST_MODE:
                logger.info("TEST MODE: No prediction to evaluate — this is expected on first run")
                logger.info("In production, predictions from 5 days ago will be evaluated here")
            return {'status': 'skipped', 'reason': 'no_prediction_found'}
        
        # Fetch actual price data
        try:
            # Step A: Get close_at_prediction (Price on the day of prediction)
            # Try to read from Firebase first to avoid yfinance call
            close_at_prediction = prediction.get('close_at_prediction')
            
            if close_at_prediction is None:
                logger.warning(f"close_at_prediction missing from Firebase for {target_date_str}, falling back to yfinance")
                # Fallback: fetch 10 days around target_date to find its close
                hist_fallback = yf_fetch_with_retry(NIFTY_TICKER, period='10d')
                # Filter indices <= target_date to find the closest available close
                hist_target = hist_fallback[hist_fallback.index.date <= target_date]
                if hist_target.empty:
                    logger.error(f"Could not find historical data for {target_date_str} in fallback")
                    return {'status': 'error', 'reason': 'fallback_price_fetch_failed'}
                close_at_prediction = float(hist_target['Close'].iloc[-1])
            
            # Step B: Get close_5_days_later (Price today, or whenever the 5-day horizon matured)
            # Use retry wrapper with 10d period
            hist_eval = yf_fetch_with_retry(NIFTY_TICKER, period='10d')
            # The calculation date for truth is today (or relative to target_date + 5 biz days)
            # To be safe, we look for the last available close that is <= today (which should be the current price)
            hist_eval_filtered = hist_eval[hist_eval.index.date <= today]
            if hist_eval_filtered.empty:
                logger.warning(f"No price data available for evaluation as of {today}")
                return {'status': 'error', 'reason': 'eval_price_fetch_failed'}
            
            close_5_days_later = float(hist_eval_filtered['Close'].iloc[-1])
            
            # Truth: did price go UP (1) or DOWN (0) over 5 days?
            truth = 1 if close_5_days_later > close_at_prediction else 0
            actual_label = 'UP' if truth == 1 else 'DOWN'
            
            predicted_value = prediction.get('prediction', 0)
            predicted_prob = prediction.get('ensemble_probability', 0.5)
            error = 1 if predicted_value != truth else 0
            # Brier Score based continuous error: (prob - truth)^2
            continuous_error = (predicted_prob - truth)**2
            
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
            
            if not firebase_client.save_evaluation(evaluation_dict):
                logger.error("Failed to save evaluation to Firebase")
                return {'status': 'error', 'reason': 'save_evaluation_failed'}
            
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
                    'MA_50': [100.0] * 60,
                    'MA_200': [100.0] * 60,
                    'Institutional_Flow': [0.5] * 60,
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
                for i, field_name in enumerate(MODEL_MAPPING.values()):
                    drift_dict[f'w_{field_name}_before'] = round(float(old_ensemble_weights[i]), 4)
                    drift_dict[f'w_{field_name}_after'] = round(float(ensemble_weights[i]), 4)
                
                if not firebase_client.save_drift_event(drift_dict):
                    logger.error("Failed to save drift event to Firebase")
                else:
                    logger.info("✓ Drift event saved to Firebase")
                
                # Update model state
                state_update = {
                    'active_features': active_features,
                    'ensemble_weights': {
                        field_name: ensemble_weights[i]
                        for i, field_name in enumerate(MODEL_MAPPING.values())
                    },
                    'council_weights': result['council_weights'],
                    'drift_count': 1,  # In production: increment from Firebase
                    'last_drift_date': target_date_str,
                    'updated_at': datetime.now(IST).isoformat()
                }
                if not firebase_client.update_model_state(state_update):
                    logger.error("Failed to update model state after drift")
                
                # Reset ADWIN
                adwin = ADWIN(delta=ADWIN_DELTA)
                logger.info("✓ ADWIN reset")
            
            logger.info("daily_evaluate completed successfully")
            return {'status': 'success', 'drift_detected': drift_flag}
        
        except Exception as e:
            logger.critical(f"CRITICAL ERROR in price data processing: {type(e).__name__}: {e}")
            import traceback
            logger.critical(f"Traceback: {traceback.format_exc()}")
            return {'status': 'error', 'reason': 'price_data_error', 'error_message': str(e)}
    
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in daily_evaluate: {type(e).__name__}: {e}")
        import traceback
        logger.critical(f"Traceback: {traceback.format_exc()}")
        return {'status': 'error', 'reason': 'exception', 'error_message': str(e)}


def evaluate_pending_predictions(n: int = 10):
    """
    Evaluate pending predictions that have not been evaluated yet.
    Useful for manual triggers or backfilling.
    """
    global active_features, ensemble_weights, adwin, models, council, ALL_FEATURES
    
    logger.info("=" * 60)
    logger.info(f"JOB: evaluate_pending_predictions (last {n})")
    logger.info("=" * 60)
    
    try:
        if not firebase_client:
            logger.critical("FIREBASE CLIENT NOT AVAILABLE - CANNOT EVALUATE")
            return {'status': 'error', 'reason': 'firebase_unavailable'}
            
        recent_preds = firebase_client.get_recent_predictions(n)
        if not recent_preds:
            logger.info("No recent predictions found.")
            return {'status': 'success', 'evaluated_count': 0}
            
        evaluated_count = 0
        today = datetime.now(IST).date()
        ticker = yf.Ticker(NIFTY_TICKER)
        
        # We process oldest to newest within the recent batch to maintain temporal order roughly
        recent_preds = list(reversed(recent_preds))
        
        for pred in recent_preds:
            if pred.get('resolved', False):
                continue
                
            pred_date_str = pred.get('date')
            if not pred_date_str:
                continue
                
            pred_date = datetime.strptime(pred_date_str, '%Y-%m-%d').date()
            
            # Target maturity date: 5 business days later
            dates = pd.bdate_range(start=pred_date, periods=6)
            eval_date = dates[-1].date()
            
            if today < eval_date:
                logger.info(f"Prediction for {pred_date_str} not yet mature (matures on {eval_date}).")
                continue
                
            logger.info(f"Evaluating pending prediction from {pred_date_str}")
            
            try:
                # Fetch price history using retry wrapper
                hist = yf_fetch_with_retry(
                    NIFTY_TICKER, 
                    start=pred_date - timedelta(days=2),
                    end=eval_date + timedelta(days=5) 
                )
                
                if len(hist) < 2:
                    logger.warning(f"Insufficient price data for {pred_date_str}")
                    continue
                
                # Get close on pred_date (or last available before it)
                hist_pred = hist[hist.index.date <= pred_date]
                close_at_prediction = hist_pred['Close'].iloc[-1] if not hist_pred.empty else hist['Close'].iloc[0]
                
                # Get close on eval_date (or last available before it)
                hist_eval = hist[hist.index.date <= eval_date]
                close_5_days_later = hist_eval['Close'].iloc[-1] if not hist_eval.empty else hist['Close'].iloc[-1]
                
                truth = 1 if close_5_days_later > close_at_prediction else 0
                
                predicted_value = pred.get('prediction', 0)
                predicted_prob = pred.get('ensemble_probability', 0.5)
                error = 1 if predicted_value != truth else 0
                # Brier Score based continuous error: (prob - truth)^2
                continuous_error = (predicted_prob - truth)**2
                
                # Update ADWIN
                adwin.update(continuous_error)
                drift_flag = adwin.drift_detected
                
                evaluation_dict = {
                    'date': pred_date_str,
                    'prediction': int(predicted_value),
                    'truth': int(truth),
                    'error': int(error),
                    'continuous_error': round(float(continuous_error), 6),
                    'adwin_updated': True,
                    'drift_detected': drift_flag,
                    'evaluated_at': datetime.now(IST).isoformat()
                }
                
                if not firebase_client.save_evaluation(evaluation_dict):
                    logger.error(f"Failed to save evaluation for {pred_date_str}")
                    continue
                    
                evaluated_count += 1
                logger.info(f"✓ Evaluation saved for {pred_date_str}. Error: {error}, Drift: {drift_flag}")
                
                if drift_flag:
                    logger.info("⚠️ DRIFT DETECTED during pending evaluation!")
                    
                    old_active_features = active_features.copy()
                    old_ensemble_weights = ensemble_weights.copy()
                    
                    resolved_df_mock = pd.DataFrame({
                        'RSI_14': [0.5] * 60, 'MACD': [0.0] * 60, 'MACD_Signal': [0.0] * 60,
                        'MACD_Diff': [0.0] * 60, 'BB_Position': [0.5] * 60, 'MA_5_20_Ratio': [1.0] * 60,
                        'Volume_Change_Pct': [0.01] * 60, 'Yesterday_Return': [0.005] * 60,
                        'MA_50': [100.0] * 60, 'MA_200': [100.0] * 60, 'Institutional_Flow': [0.5] * 60,
                        'Target': [1] * 60
                    })
                    
                    result = council.optimize(
                        models=models,
                        resolved_df=resolved_df_mock,
                        all_features=ALL_FEATURES
                    )
                    
                    active_features = result['active_features']
                    ensemble_weights = result['ensemble_weights']
                    
                    drift_dict = {
                        'date': pred_date_str,
                        'row_index': 0,
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
                    for i, field_name in enumerate(MODEL_MAPPING.values()):
                        drift_dict[f'w_{field_name}_before'] = round(float(old_ensemble_weights[i]), 4)
                        drift_dict[f'w_{field_name}_after'] = round(float(ensemble_weights[i]), 4)
                    firebase_client.save_drift_event(drift_dict)
                    
                    state_update = {
                        'active_features': active_features,
                        'ensemble_weights': {
                            field_name: ensemble_weights[i]
                            for i, field_name in enumerate(MODEL_MAPPING.values())
                        },
                        'council_weights': result['council_weights'],
                        'drift_count': 1,
                        'last_drift_date': pred_date_str,
                        'updated_at': datetime.now(IST).isoformat()
                    }
                    firebase_client.update_model_state(state_update)
                    
                    adwin = ADWIN(delta=ADWIN_DELTA)
                    logger.info("✓ ADWIN reset")

            except Exception as e:
                logger.error(f"Error evaluating {pred_date_str}: {e}")
                continue
                
        logger.info(f"evaluate_pending_predictions completed. Evaluated: {evaluated_count}")
        return {'status': 'success', 'evaluated_count': evaluated_count}
        
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in evaluate_pending_predictions: {e}")
        import traceback
        logger.critical(f"Traceback: {traceback.format_exc()}")
        return {'status': 'error', 'reason': 'exception', 'error_message': str(e)}



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
