import requests
import logging
import time
import random
import yfinance as yf
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (AppleWebKit/537.36; KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edge/122.0.2365.59"
]

def get_yf_session():
    """
    Create a requests session with a random User-Agent and retry strategy.
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

def yf_fetch_with_retry(ticker_symbol: str, period: str = '60d', start=None, end=None, max_retries: int = 5):
    """
    Fetch yfinance ticker history with exponential backoff on rate limit errors.
    Retries on YFRateLimitError and common 429 errors.
    """
    for attempt in range(max_retries):
        try:
            # Note: We avoid passing session explicitly to Ticker to prevent 
            # strange type-check errors (e.g., Session vs Session mismatch).
            # yfinance handles internal caching and session management.
            ticker = yf.Ticker(ticker_symbol)
            
            if start and end:
                hist = ticker.history(start=start, end=end)
            else:
                hist = ticker.history(period=period)
                
            if hist is not None and not hist.empty:
                return hist
                
            logger.warning(f"yfinance returned empty dataframe for {ticker_symbol} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            else:
                return hist # Return empty if max retries reached
                
        except Exception as e:
            error_name = type(e).__name__
            error_msg = str(e)
            
            # Check for Rate Limit indicators in exception name or message
            if 'RateLimit' in error_name or '429' in error_msg:
                wait = (2 ** attempt) * 15  # 15s, 30s, 60s, 120s, 240s
                logger.warning(f"yfinance rate limited ({error_name}). Retry {attempt+1}/{max_retries} in {wait}s...")
                time.sleep(wait)
            else:
                # If it's a different error, we might still want to retry if it's intermittent
                logger.error(f"Unexpected yfinance error: {error_name}: {error_msg}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                else:
                    raise
                    
    raise Exception(f"yfinance: max retries exceeded for {ticker_symbol}")
