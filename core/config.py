import os
import sys
import datetime
import json

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
            if hasattr(st, "secrets"):
                if key in st.secrets:
                    val = st.secrets[key]
                elif "fyers" in st.secrets and key in st.secrets["fyers"]:
                    val = st.secrets["fyers"][key]
                elif "FYERS" in st.secrets and key in st.secrets["FYERS"]:
                    val = st.secrets["FYERS"][key]
        except Exception:
            pass
    return str(val).strip() if val else default

# Telegram configuration
TELEGRAM_BOT_TOKEN = get_config_val("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = get_config_val("TELEGRAM_CHAT_ID", "")
SCAN_INTERVAL_SECONDS = int(get_config_val("SCAN_INTERVAL_SECONDS", 300))

# Fyers API Configuration
FYERS_CLIENT_ID = get_config_val("FYERS_CLIENT_ID", "")
FYERS_PIN = get_config_val("FYERS_PIN", "")
FYERS_TOTP_KEY = get_config_val("FYERS_TOTP_KEY", "")
FYERS_APP_ID = get_config_val("FYERS_APP_ID", "")
FYERS_SECRET_KEY = get_config_val("FYERS_SECRET_KEY", "")
FYERS_REDIRECT_URI = get_config_val("FYERS_REDIRECT_URI", "https://trade.fyers.in/api-login/redirect-uri/index.html")
FYERS_TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fyers_token.json")

# Security & Authentication Configuration
APP_ACCESS_PIN = get_config_val("APP_ACCESS_PIN", "4082")
GMAIL_USER = get_config_val("GMAIL_USER", "")
GMAIL_APP_PASSWORD = get_config_val("GMAIL_APP_PASSWORD", "")
GMAIL_RECIPIENT = get_config_val("GMAIL_RECIPIENT", "ggp305ggp@gmail.com")

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

def get_nifty_market_regime() -> dict:
    """
    Returns cached or live Nifty sentiment: {price, change, pct, is_bullish}.
    Uses nifty_last_quote.json cache with fallback.
    """
    cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nifty_last_quote.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "pct" in data:
                    return data
        except Exception:
            pass
    return {"price": 0.0, "change": 0.0, "pct": 0.0, "is_bullish": True}

# Major Indian Indices (Nifty 50, Bank Nifty, Sensex, FinNifty)
INDEX_WATCHLIST = [
    "^NSEI",             # NIFTY 50
    "^NSEBANK",          # BANK NIFTY
    "^BSESN",            # BSE SENSEX
    "NIFTY_FIN_SERVICE.NS" # FIN NIFTY
]

# Complete Watchlist of all 181 NSE F&O Stocks (Total F&O Universe)
DEFAULT_WATCHLIST = [
    "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ACC.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBUJACEM.NS", "ANGELONE.NS",
    "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS",
    "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS",
    "BAJFINANCE.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS", "BERGEPAINT.NS",
    "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS",
    "BPCL.NS", "BRITANNIA.NS", "BSE.NS", "CANBK.NS", "CDSL.NS",
    "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS",
    "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS", "DALBHARAT.NS",
    "DEEPAKNTR.NS", "DELHIVERY.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "FEDERALBNK.NS", "GAIL.NS", "GLENMARK.NS",
    "GMRAIRPORT.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRASIM.NS", "HAL.NS",
    "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HUDCO.NS",
    "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDFCFIRSTB.NS", "IEX.NS",
    "IGL.NS", "INDHOTEL.NS", "INDIGO.NS", "INDUSINDBK.NS", "INDUSTOWER.NS",
    "INFY.NS", "IOC.NS", "IRCTC.NS", "IRFC.NS", "ITC.NS",
    "JINDALSTEL.NS", "JIOFIN.NS", "JSWSTEEL.NS", "JUBLFOOD.NS", "KOTAKBANK.NS",
    "LAURUSLABS.NS", "LICHSGFIN.NS", "LT.NS", "LTIM.NS", "LUPIN.NS",
    "M&M.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS",
    "MCX.NS", "MFSL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS",
    "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NESTLEIND.NS", "NHPC.NS",
    "NMDC.NS", "NTPC.NS", "NYKAA.NS", "OBEROIRLTY.NS", "OFSS.NS",
    "OIL.NS", "ONGC.NS", "PAGEIND.NS", "PERSISTENT.NS", "PETRONET.NS",
    "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS",
    "POWERGRID.NS", "PRESTIGE.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS",
    "RELIANCE.NS", "RVNL.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS",
    "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SOLARINDS.NS",
    "SRF.NS", "SUNPHARMA.NS", "SUZLON.NS", "SYNGENE.NS", "TATACHEM.NS",
    "TATACOMM.NS", "TATACONSUM.NS", "TATAELXSI.NS", "TATAMOTORS.NS", "TATAPOWER.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS",
    "TORNTPOWER.NS", "TRENT.NS", "TVSMOTOR.NS", "ULTRACEMCO.NS", "UNITDSPR.NS",
    "UPL.NS", "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "ZOMATO.NS",
    "ZYDUSLIFE.NS"
]
