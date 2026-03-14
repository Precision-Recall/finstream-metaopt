import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers the following features:
    - RSI (14 day)
    - MACD
    - Bollinger Band position
    - 5-day & 20-day moving average ratio
    - Volume change %
    - Yesterday's return
    """
    df_feat = df.copy()
    
    # RSI (14 day)
    rsi_indicator = RSIIndicator(close=df_feat['Close'], window=14)
    df_feat['RSI_14'] = rsi_indicator.rsi()
    
    # MACD
    macd_indicator = MACD(close=df_feat['Close'])
    df_feat['MACD'] = macd_indicator.macd()
    df_feat['MACD_Signal'] = macd_indicator.macd_signal()
    df_feat['MACD_Diff'] = macd_indicator.macd_diff()
    
    # Bollinger Band position (%B)
    bb_indicator = BollingerBands(close=df_feat['Close'], window=20, window_dev=2)
    df_feat['BB_Position'] = bb_indicator.bollinger_pband()
    
    # 5-day & 20-day MA ratio
    ma_5 = df_feat['Close'].rolling(window=5).mean()
    ma_20 = df_feat['Close'].rolling(window=20).mean()
    df_feat['MA_5_20_Ratio'] = ma_5 / ma_20
    
    # Volume change % (today's volume over yesterday's)
    df_feat['Volume_Change_Pct'] = df_feat['Volume'].pct_change()
    df_feat['Volume_Change_Pct'] = df_feat['Volume_Change_Pct'].replace([np.inf, -np.inf], np.nan)
    df_feat['Volume_Change_Pct'] = df_feat['Volume_Change_Pct'].fillna(0)
    df_feat['Volume_Change_Pct'] = df_feat['Volume_Change_Pct'].clip(-2, 2)  # cap at ±200%
    
    # Yesterday's return
    df_feat['Yesterday_Return'] = df_feat['Close'].pct_change().shift(1)
    
    return df_feat
