import pandas as pd
import os

def load_dashboard_data():
    """Loads all necessary CSV files for the dashboard."""
    stream_df = pd.read_csv('results/stream_results.csv')
    static_df = pd.read_csv('results/static_results.csv')
    test_df = pd.read_csv('data/processed/test.csv')
    
    try:
        drift_df = pd.read_csv('results/drift_events.csv')
    except FileNotFoundError:
        drift_df = pd.DataFrame()
        
    return {
        'stream_df': stream_df,
        'static_df': static_df,
        'test_df': test_df,
        'drift_df': drift_df
    }
