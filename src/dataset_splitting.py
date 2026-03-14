import pandas as pd
import os

def split_datasets(df: pd.DataFrame, output_dir: str = "data/processed") -> None:
    """
    Splits the data into TRAIN, TEST and BASELINE EVALUATION sets and saves them.
    
    TRAIN: 2015-01-01 to 2019-12-31
    TEST: 2020-01-01 to Present (includes 2020 crash for ADWIN discovery)
    BASELINE EVALUATION: 2020-01-01 to 2020-12-31 (subset for static model evaluation)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure index is datetime and localized/tz-naive if necessary, usually yfinance returns tz-aware, 
    # but slicing works perfectly with string dates.
    df.index = pd.to_datetime(df.index)
    
    # Splits based on the updated requirements
    train_df = df.loc['2015-01-01':'2019-12-31']
    test_df = df.loc['2020-01-01':]
    baseline_eval_df = df.loc['2020-01-01':'2020-12-31']
    
    # Save to CSV
    train_df.to_csv(os.path.join(output_dir, "train.csv"))
    test_df.to_csv(os.path.join(output_dir, "test.csv"))
    baseline_eval_df.to_csv(os.path.join(output_dir, "baseline_evaluation_period.csv"))
    
    print(f"Data split and saved to {output_dir}/:")
    print(f"  - TRAIN shape: {train_df.shape}")
    print(f"  - TEST shape: {test_df.shape}")
    print(f"  - BASELINE EVALUATION shape: {baseline_eval_df.shape}")
