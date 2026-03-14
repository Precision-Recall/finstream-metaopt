import pandas as pd

def generate_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates the binary target: 
    1 if next day closes higher than today's close, 0 if lower or equal.
    """
    df_target = df.copy()
    
    # Target: Next day's close > Today's close
    next_day_close = df_target['Close'].shift(-1)
    
    # Temporarily set to boolean, then to int. Using np.where is safer for NaN propagation
    df_target['Target'] = (next_day_close > df_target['Close']).astype(float)
    
    # The last row won't have a next day close, so its target is inherently unknown.
    # Marking it as NaN ensures it gets dropped.
    df_target.loc[df_target.index[-1], 'Target'] = None
    
    return df_target

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drops NaN rows (due to indicator warmup periods and the shifted target).
    And converts target to integer after dropping NaNs.
    """
    df_cleaned = df.dropna().copy()
    df_cleaned['Target'] = df_cleaned['Target'].astype(int)
    return df_cleaned
