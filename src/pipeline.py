import os
import random
import numpy as np
from src.data_ingestion import download_nifty50_data
from src.feature_engineering import engineer_features
from src.target_generation import generate_target, clean_data
from src.dataset_splitting import split_datasets

def set_seed(seed: int = 42):
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)

def run_pipeline():
    print("Starting adaptive ML data pipeline...")
    
    # 1. Set seed
    set_seed(42)
    
    # 2. Ingest Data
    print("Downloading NIFTY50 data from Yahoo Finance...")
    df_raw = download_nifty50_data(start_date='2015-01-01')
    print(f"Raw data shape: {df_raw.shape}")
    
    # 3. Engineer Features
    print("Engineering features...")
    df_features = engineer_features(df_raw)
    
    # 4. Generate Target & Clean Data
    print("Generating target and cleaning data...")
    df_target = generate_target(df_features)
    df_clean = clean_data(df_target)
    print(f"Cleaned data shape: {df_clean.shape}")
    
    # 5. Split and Save
    print("Splitting datasets...")
    # Explicitly set the output dir to be correctly relative to project root
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'processed')
    split_datasets(df_clean, output_dir=output_dir)
    
    print("Pipeline completed successfully.")

if __name__ == "__main__":
    run_pipeline()
