import json
import pandas as pd

def compute_dashboard_metrics(data_dict):
    """Computes derived metrics and formats data for HTML injection."""
    stream_df = data_dict['stream_df']
    static_df = data_dict['static_df']
    test_df = data_dict['test_df']
    drift_df = data_dict['drift_df']

    # ROLLING_STATIC
    static_errors = static_df['error']
    rolling_static = (1 - static_errors).rolling(window=30, min_periods=1).mean().bfill().round(4).tolist()
    
    # ROLLING_ADAPTIVE
    adaptive_errors = stream_df['error']
    rolling_adaptive = (1 - adaptive_errors).rolling(window=30, min_periods=1).mean().bfill().round(4).tolist()

    # WEIGHTS over time
    w_old = stream_df['w_old'].tolist()
    w_medium = stream_df['w_medium'].tolist()
    w_recent = stream_df['w_recent'].tolist()
    
    # DATES
    dates = stream_df['date'].tolist()

    # CLOSE_PRICES
    close_prices = test_df['Close'].round(2).tolist()
    close_dates = test_df['Date'].tolist()

    # RAW_TABLE
    raw_table_df = stream_df.head(300).copy()
    raw_table_df['ensemble_probability'] = raw_table_df['ensemble_probability'].round(4)
    raw_table = raw_table_df[['date', 'prediction', 'truth', 'error', 'ensemble_probability', 'w_old', 'w_medium', 'w_recent']].to_dict(orient='records')

    # SUMMARY
    static_acc = round(1 - static_errors.mean(), 4)
    adaptive_acc = round(1 - adaptive_errors.mean(), 4)
    summary = {
        'static_accuracy': static_acc,
        'adaptive_accuracy': adaptive_acc,
        'delta': round(adaptive_acc - static_acc, 4),
        'drift_count': len(drift_df),
        'total_days': len(test_df),
        'resolved_predictions': len(stream_df)
    }

    # DRIFT_EVENTS
    if not drift_df.empty:
        drift_events = drift_df.round(4).to_dict(orient='records')
    else:
        drift_events = []

    # THINNING (to reduce payload size)
    dates_thin = dates[::3]
    rolling_static_thin = rolling_static[::3]
    rolling_adaptive_thin = rolling_adaptive[::3]
    w_old_thin = w_old[::3]
    w_medium_thin = w_medium[::3]
    w_recent_thin = w_recent[::3]
    close_prices_thin = close_prices[::3]
    close_dates_thin = close_dates[::3]

    # JSON Serialize
    js_vars = f"""
    const DATES = {json.dumps(dates_thin)};
    const ROLLING_STATIC = {json.dumps(rolling_static_thin)};
    const ROLLING_ADAPTIVE = {json.dumps(rolling_adaptive_thin)};
    const W_OLD = {json.dumps(w_old_thin)};
    const W_MEDIUM = {json.dumps(w_medium_thin)};
    const W_RECENT = {json.dumps(w_recent_thin)};
    const CLOSE_DATES = {json.dumps(close_dates_thin)};
    const CLOSE = {json.dumps(close_prices_thin)};
    const RAW_TABLE = {json.dumps(raw_table)};
    const SUMMARY = {json.dumps(summary)};
    const DRIFT_EVENTS = {json.dumps(drift_events)};
    """
    
    return js_vars
