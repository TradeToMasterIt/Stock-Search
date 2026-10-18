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

# Complete Watchlist of all 181 NSE F&O Stocks (Total F&O Universe)
DEFAULT_WATCHLIST = [
    "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ABFRL.NS",
    "ACC.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS",
    "AMBUJACEM.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS",
    "ASTRAL.NS", "ATUL.NS", "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", "BALKRISIND.NS", "BANDHANBNK.NS",
    "BANKBARODA.NS", "BATAINDIA.NS", "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS",
    "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS",
    "BRITANNIA.NS", "BSOFT.NS", "CANBK.NS", "CANFINHOME.NS", "CHAMBLFERT.NS",
    "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS",
    "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS",
    "DABUR.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DIVISLAB.NS", "DIXON.NS",
    "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", "ESCORTS.NS", "EXIDEIND.NS",
    "FEDERALBNK.NS", "GAIL.NS", "GLENMARK.NS", "GMRINFRA.NS", "GNFC.NS",
    "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GUJGASLTD.NS",
    "HAL.NS", "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS",
    "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDCOPPER.NS", "HINDPETRO.NS",
    "HINDUNILVR.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDFCFIRSTB.NS",
    "IEX.NS", "IGL.NS", "INDHOTEL.NS", "INDIAMART.NS", "INDIGO.NS",
    "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS", "IOC.NS", "IPCALAB.NS",
    "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JKCEMENT.NS", "JSWSTEEL.NS",
    "JUBLFOOD.NS", "KOTAKBANK.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LICHSGFIN.NS",
    "LT.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS",
    "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCDOWELL-N.NS",
    "MCX.NS", "METROPOLIS.NS", "MFSL.NS", "MGL.NS", "MOTHERSON.NS",
    "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS",
    "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", "OBEROIRLTY.NS",
    "OFSS.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "POLYCAB.NS", "POWERGRID.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS",
    "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS",
    "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SRF.NS",
    "SUNPHARMA.NS", "SUNTV.NS", "SUZLON.NS", "SYNGENE.NS", "TATACHEM.NS",
    "TATACOMM.NS", "TATACONSUM.NS", "TATAELXSI.NS", "TATAMOTORS.NS", "TATAPOWER.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS",
    "TORNTPOWER.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS",
    "UPL.NS", "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "ZEEL.NS",
    "ZYDUSLIFE.NS"
]
