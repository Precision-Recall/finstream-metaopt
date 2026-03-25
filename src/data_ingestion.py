import yfinance as yf
import pandas as pd
from src.yfinance_session import get_yf_session

def flatten_multiindex_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance returns MultiIndex columns when downloading.
    This function flattens them to a single string (just the feature name, discarding the ticker).
    """
    if isinstance(df.columns, pd.MultiIndex):
        # We assume the top level is the feature (e.g., 'Close') and second is the ticker (e.g., '^NSEI')
        # We just want the feature name.
        df.columns = [col[0] for col in df.columns]
    return df

def download_nifty50_data(start_date: str = '2015-01-01', end_date: str = None) -> pd.DataFrame:
    """
    Downloads NIFTY50 (^NSEI) data from Yahoo Finance.
    """
    ticker = "^NSEI"
    if end_date is None:
        # yfinance will default to today if not provided
        df = yf.download(ticker, start=start_date)
    else:
        df = yf.download(ticker, start=start_date, end=end_date)
    
    df = flatten_multiindex_columns(df)
    return df
