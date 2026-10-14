import os
import sys
import datetime

# Fix Windows console UTF-8 output if needed
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
except Exception:
    pass

# Load environment variables safely
try:
    from dotenv import load_dotenv
    _env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(_env_file):
        load_dotenv(dotenv_path=_env_file)
    else:
        load_dotenv()
except ImportError:
    pass

def get_config_val(key, default=""):
    val = os.getenv(key)
    if not val:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and key in st.secrets:
                val = st.secrets[key]
        except Exception:
            pass
    return str(val).strip() if val else default

# Telegram configuration
TELEGRAM_BOT_TOKEN = get_config_val("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = get_config_val("TELEGRAM_CHAT_ID", "")
SCAN_INTERVAL_SECONDS = int(get_config_val("SCAN_INTERVAL_SECONDS", 300))

# State & Cache files
STATE_FILE = "alert_state.json"
ACTIVE_TRADES_FILE = "active_trades.json"
SCREENER_CACHE_FILE = "screener_cache.json"

# Timezone & Market Hours
IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
ENFORCE_MARKET_HOURS = True
MARKET_OPEN_TIME = datetime.time(9, 15)   # 09:15 AM IST
MARKET_CLOSE_TIME = datetime.time(15, 30) # 03:30 PM IST

def get_ist_now():
    """Returns current datetime in Indian Standard Time (IST)."""
    return datetime.datetime.now(IST_TZ)

def is_market_open():
    """
    Check if the Indian Stock Market (NSE) is currently open in IST.
    - Trading Days: Monday to Friday (weekday 0 to 4 in IST)
    - Trading Hours: 09:15 AM to 03:30 PM IST
    """
    now_ist = get_ist_now()
    weekday = now_ist.weekday()
    
    # Check weekend (5 = Saturday, 6 = Sunday)
    if weekday == 5:
        return False, "શનિવાર (Weekend - Market Closed)"
    elif weekday == 6:
        return False, "રવિવાર (Weekend - Market Closed)"
        
    curr_time = now_ist.time()
    if curr_time < MARKET_OPEN_TIME:
        return False, f"પ્રી-માર્કેટ સવારના 09:15 પહેલાં ({curr_time.strftime('%H:%M:%S')} IST)"
    elif curr_time > MARKET_CLOSE_TIME:
        return False, f"પોસ્ટ-માર્કેટ બપોરના 03:30 પછી ({curr_time.strftime('%H:%M:%S')} IST)"
        
    return True, "Market is Open"

# Default Watchlist of 75 high-liquid NSE F&O Stocks
DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS",
    "HINDUNILVR.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TATASTEEL.NS", "NTPC.NS",
    "POWERGRID.NS", "COALINDIA.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ONGC.NS",
    "M&M.NS", "BAJAJFINSV.NS", "ULTRACEMCO.NS", "BEL.NS", "HAL.NS",
    "BHEL.NS", "ZYDUSLIFE.NS", "ADANIPOWER.NS", "VEDL.NS", "SUZLON.NS",
    "TRENT.NS", "DIXON.NS", "POLYCAB.NS", "PERSISTENT.NS", "COFORGE.NS",
    "HAVELLS.NS", "WIPRO.NS", "TECHM.NS", "HCLTECH.NS", "DLF.NS",
    "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS", "RECLTD.NS", "PFC.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS",
    "INDUSINDBK.NS", "AUBANK.NS", "SIEMENS.NS", "ABB.NS", "CUMMINSIND.NS",
    "TVSMOTOR.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "ASHOKLEY.NS", "BHARATFORG.NS",
    "CIPLA.NS", "DRREDDY.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS",
    "AMBUJACEM.NS", "ACC.NS", "GAIL.NS", "BPCL.NS", "IOC.NS"
]
