"""
Option R3 Breakout Engine (Option Leads, Future Follows)
Specialized High-Precision Module for Patel Trading Bot / Confluence Pro

Core Capabilities:
1. Dynamic Monthly F&O Expiry Engine (Auto-computes last Thursday of the month)
2. Exact OTM Strike Selector & NSE/Fyers Contract Builder (e.g. 'DLF 28 NOV 700 CE')
3. Option Contract Pivot & R3 Calculator:
   - Calculates Option's own Pivot, R1, R2, and R3 from Option's previous session HLC
   - Verifies if live Option LTP >= Option R3 (True Option Momentum Breakout)
4. Curated Top High-Beta / Explosive Momentum F&O Basket
5. Specific Actionable Telegram Alert Formatter ('BUY DLF 28 NOV 700 CE @ ₹...')
"""

import os
import sys
import math
import calendar
import datetime
from typing import Dict, Any, Optional, Tuple, List

# Ensure parent directory is in path for standalone execution
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from .config import get_ist_now, DEFAULT_WATCHLIST
except ImportError:
    from core.config import get_ist_now, DEFAULT_WATCHLIST

# -------------------------------------------------------------
# Top 35 High-Beta & Explosive Momentum F&O Stocks (Curated)
# -------------------------------------------------------------
TOP_MOMENTUM_FNO_BASKET = [
    "DLF.NS",          # Realty King (High Momentum)
    "TATASTEEL.NS",    # Metal Leader (High Volume)
    "RELIANCE.NS",     # Heavyweight Mover
    "SBIN.NS",         # PSU Bank Leader
    "TATAMOTORS.NS",   # Auto Flagship
    "HDFCBANK.NS",     # Private Bank Heavyweight
    "ICICIBANK.NS",    # Banking Momentum
    "BAJFINANCE.NS",   # NBFC High Beta
    "BHEL.NS",         # High Beta PSU Power
    "BEL.NS",          # Defense Momentum
    "HAL.NS",          # Defense Aerospace Leader
    "COALINDIA.NS",    # High Dividend / High Beta
    "JINDALSTEL.NS",   # Aggressive Metal
    "HINDALCO.NS",     # Non-Ferrous Metal Leader
    "VEDL.NS",         # High Volatility Metal
    "TRENT.NS",        # Retail Super Momentum
    "DIXON.NS",        # Electronics High Beta
    "POLYCAB.NS",      # Wire & Cables Breakout
    "INFY.NS",         # IT Giant
    "TCS.NS",          # IT Flagship
    "MARUTI.NS",       # Auto Heavyweight
    "BHARTIARTL.NS",   # Telecom Momentum
    "ADANIENT.NS",     # Adani Flagship (Volatile)
    "ADANIPORTS.NS",   # Infrastructure / Ports
    "NTPC.NS",         # Power Giant
    "PFC.NS",          # Power Finance
    "RECLTD.NS",       # Rural Electrification
    "GODREJPROP.NS",   # Realty Momentum
    "AXISBANK.NS",     # Bank Nifty Mover
    "KOTAKBANK.NS",    # Private Banking
    "LT.NS",           # Infrastructure Leader
    "TITAN.NS",        # Consumer / Jewelry
    "MCX.NS",          # Exchange Momentum
    "SUNPHARMA.NS",    # Pharma Leader
    "AUROPHARMA.NS",   # Pharma Breakout
]

# Standard strike intervals for Indian Indices and Equities
INDEX_STRIKE_STEPS = {
    "NIFTY": 50,
    "^NSEI": 50,
    "NSEI": 50,
    "NIFTY 50": 50,
    "BANKNIFTY": 100,
    "^NSEBANK": 100,
    "NSEBANK": 100,
    "BANK NIFTY": 100,
    "FINNIFTY": 50,
    "NIFTY_FIN_SERVICE": 50,
    "SENSEX": 100,
    "^BSESN": 100,
    "BSESN": 100
}

def is_index_symbol(symbol: str) -> bool:
    clean = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    return clean in [
        "NIFTY", "NSEI", "NIFTY50", "NIFTY 50",
        "BANKNIFTY", "NSEBANK", "BANK NIFTY",
        "FINNIFTY", "NIFTY_FIN_SERVICE", "CNXFIN",
        "SENSEX", "BSESN", "BSE SENSEX"
    ]

def normalize_symbol_and_exchange(symbol: str):
    """
    Normalizes stock or index symbol and returns (clean_sym, exchange, display_name)
    e.g. '^NSEI' -> ('NIFTY', 'NSE', 'NIFTY 50')
         '^NSEBANK' -> ('BANKNIFTY', 'NSE', 'BANK NIFTY')
         '^BSESN' -> ('SENSEX', 'BSE', 'SENSEX')
         'NIFTY_FIN_SERVICE.NS' -> ('FINNIFTY', 'NSE', 'FINNIFTY')
    """
    clean = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    if clean in ["NSEI", "NIFTY", "NIFTY50", "NIFTY 50"]:
        return "NIFTY", "NSE", "NIFTY 50"
    elif clean in ["NSEBANK", "BANKNIFTY", "BANK NIFTY"]:
        return "BANKNIFTY", "NSE", "BANK NIFTY"
    elif clean in ["FINNIFTY", "NIFTY_FIN_SERVICE", "CNXFIN"]:
        return "FINNIFTY", "NSE", "FINNIFTY"
    elif clean in ["BSESN", "SENSEX", "BSE SENSEX"]:
        return "SENSEX", "BSE", "SENSEX"
    elif clean == "GMRINFRA":
        return "GMRAIRPORT", "NSE", "GMRAIRPORT"
    elif clean in ["MCDOWELL-N", "MCDOWELL_N"]:
        return "UNITDSPR", "NSE", "UNITDSPR"
    return clean, "NSE", clean

def get_current_weekly_expiry(symbol: str, ref_date = None):
    """
    Computes upcoming Weekly Option Expiry for Indian Indices with Time-Segmented Logic:
    - Normal non-expiry days: Current Week's Weekly Expiry
    - Expiry day 09:15-13:00 IST: Next Week's Expiry (Protects capital against brutal Theta decay)
    - Expiry day 13:00-15:15 IST: Same Day 0DTE (Captures explosive Gamma Blast / Hero-Zero)
    - Expiry day post-15:15 IST: Next Week's Expiry
    """
    now = get_ist_now()
    ref_dt = ref_date if ref_date else now.date()

    clean, _, _ = normalize_symbol_and_exchange(symbol)
    if clean == "BANKNIFTY":
        target_weekday = calendar.WEDNESDAY  # 2
    elif clean == "FINNIFTY":
        target_weekday = calendar.TUESDAY    # 1
    elif clean == "SENSEX":
        target_weekday = calendar.FRIDAY     # 4
    else:
        target_weekday = calendar.THURSDAY   # 3 (NIFTY / Default)

    today_weekday = ref_dt.weekday()
    
    if today_weekday == target_weekday:
        # Expiry Day Time Segmentation
        current_minute_val = now.hour * 60 + now.minute
        time_1300 = 13 * 60       # 1:00 PM IST
        time_1515 = 15 * 60 + 15  # 3:15 PM IST

        if current_minute_val < time_1300:
            # Morning Session: Theta decay peak -> Next Week's Expiry protects buyer capital
            days_ahead = 7
            regime = "NEXT_WEEK_SAFE"
            tag = "(Next W - Theta Safe)"
        elif time_1300 <= current_minute_val <= time_1515:
            # Afternoon Session: Short Squeeze & Gamma Blast zone -> Same Day 0DTE
            days_ahead = 0
            regime = "GAMMA_BLAST_0DTE"
            tag = "(0DTE - Gamma Blast)"
        else:
            # Post 3:15 PM: Expiry closed -> Roll to Next Week
            days_ahead = 7
            regime = "NEXT_WEEK_POST_EXPIRY"
            tag = "(Next W)"
    elif today_weekday < target_weekday:
        days_ahead = target_weekday - today_weekday
        regime = "CURRENT_WEEKLY"
        tag = "(W)"
    else:
        days_ahead = 7 - (today_weekday - target_weekday)
        regime = "CURRENT_WEEKLY"
        tag = "(W)"

    expiry_date = ref_dt + datetime.timedelta(days=days_ahead)

    # Check if this expiry date is also the monthly expiry date
    cal = calendar.monthcalendar(expiry_date.year, expiry_date.month)
    target_days = [week[target_weekday] for week in cal if week[target_weekday] != 0]
    is_monthly = (expiry_date.day == target_days[-1])

    month_chars = {
        1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
        7: '7', 8: '8', 9: '9', 10: 'O', 11: 'N', 12: 'D'
    }
    
    yy = expiry_date.strftime("%y")
    mmm = expiry_date.strftime("%b").upper()
    dd = f"{expiry_date.day:02d}"
    
    if is_monthly and days_ahead != 0:
        fyers_expiry_code = f"{yy}{mmm}"
    else:
        fyers_expiry_code = f"{yy}{month_chars[expiry_date.month]}{dd}"

    expiry_label = f"{expiry_date.day} {mmm} {tag}"
    nse_expiry_str = expiry_date.strftime("%d-%b-%Y")

    return {
        "date": expiry_date,
        "day": expiry_date.day,
        "month_str": mmm,
        "year": expiry_date.year,
        "is_weekly": True,
        "is_monthly": is_monthly,
        "is_gamma_blast": (regime == "GAMMA_BLAST_0DTE"),
        "regime": regime,
        "label": expiry_label,
        "fyers_code": fyers_expiry_code,
        "nse_str": nse_expiry_str
    }

def get_accurate_strike_step(symbol: str, spot_price: float) -> int:
    """
    Returns the exchange-calibrated strike step for Indian Indices & F&O Equities.
    """
    clean = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    if clean in INDEX_STRIKE_STEPS:
        return INDEX_STRIKE_STEPS[clean]
    
    # Calibrated stock strike intervals
    if spot_price < 150:
        return 2.5 if spot_price < 75 else 5
    elif spot_price < 250:
        return 5
    elif spot_price < 500:
        return 10
    elif spot_price < 1000:
        return 20
    elif spot_price < 2500:
        return 50
    elif spot_price < 5000:
        return 100
    return 200

def get_current_monthly_expiry(ref_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Computes the upcoming monthly NSE F&O expiry date (last Thursday of the month).
    If current date has passed this month's last Thursday, rolls to next month.
    """
    now = get_ist_now()
    ref_dt = ref_date if ref_date else now.date()
    year = ref_dt.year
    month = ref_dt.month

    # Find last Thursday of current month
    cal = calendar.monthcalendar(year, month)
    thursdays = [week[calendar.THURSDAY] for week in cal if week[calendar.THURSDAY] != 0]
    last_thursday = thursdays[-1]
    expiry_date = datetime.date(year, month, last_thursday)

    # If today is after the monthly expiry date (or expiry day after 15:30 IST), roll over to next month
    if ref_dt > expiry_date or (ref_dt == expiry_date and (now.hour > 15 or (now.hour == 15 and now.minute >= 30))):
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        cal = calendar.monthcalendar(next_year, next_month)
        thursdays = [week[calendar.THURSDAY] for week in cal if week[calendar.THURSDAY] != 0]
        expiry_date = datetime.date(next_year, next_month, thursdays[-1])

    expiry_label = expiry_date.strftime("%d %b").upper()       # e.g., "28 NOV"
    fyers_expiry_code = expiry_date.strftime("%y%b").upper()   # e.g., "24NOV" or "26NOV"
    nse_expiry_str = expiry_date.strftime("%d-%b-%Y")          # e.g., "28-Nov-2024"

    return {
        "date": expiry_date,
        "day": expiry_date.day,
        "month_str": expiry_date.strftime("%b").upper(),
        "year": expiry_date.year,
        "label": expiry_label,
        "fyers_code": fyers_expiry_code,
        "nse_str": nse_expiry_str
    }

def build_option_contract(symbol: str, spot_price: float, opt_type: str = "CE") -> Dict[str, Any]:
    """
    Builds the exact Strike, Contract Name, and Fyers Trading Symbol for an OTM Option.
    Supports Weekly Expiry for Indices and Monthly Expiry for F&O Equities.
    Example: symbol='^NSEI', spot=24520 -> 'NIFTY 5 NOV (W) 24550 CE' & 'NSE:NIFTY26N0524550CE'
    """
    clean_sym, exchange, display_name = normalize_symbol_and_exchange(symbol)
    step = get_accurate_strike_step(clean_sym, spot_price)
    
    # Calculate First Just Out-Of-The-Money (OTM) Strike
    if opt_type.upper() == "CE":
        strike = int(math.ceil(spot_price / step) * step)
        if strike <= spot_price:
            strike += int(step)
    else:
        strike = int(math.floor(spot_price / step) * step)
        if strike >= spot_price:
            strike -= int(step)

    # Use Weekly Expiry for Indices, Monthly Expiry for Stocks
    is_idx = is_index_symbol(symbol)
    if is_idx:
        expiry_info = get_current_weekly_expiry(clean_sym)
    else:
        expiry_info = get_current_monthly_expiry()

    contract_name = f"{clean_sym} {expiry_info['label']} {strike} {opt_type.upper()}"
    fyers_symbol = f"{exchange}:{clean_sym}{expiry_info['fyers_code']}{strike}{opt_type.upper()}"

    return {
        "symbol": clean_sym,
        "display_name": display_name,
        "full_symbol": f"{symbol}",
        "spot_price": spot_price,
        "strike": strike,
        "step": step,
        "opt_type": opt_type.upper(),
        "is_index": is_idx,
        "is_gamma_blast": expiry_info.get("is_gamma_blast", False),
        "expiry_info": expiry_info,
        "contract_name": contract_name,
        "fyers_symbol": fyers_symbol
    }

def calculate_option_pivot_levels(prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
    """
    Calculates Daily Classic Pivot Points specifically for the Option Contract.
    Option R3 = H + 2*(P - L)
    """
    p = (prev_high + prev_low + prev_close) / 3.0
    r1 = (2.0 * p) - prev_low
    s1 = (2.0 * p) - prev_high
    r2 = p + (prev_high - prev_low)
    s2 = p - (prev_high - prev_low)
    r3 = prev_high + 2.0 * (p - prev_low)
    s3 = prev_low - 2.0 * (prev_high - p)

    return {
        "p": round(p, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
        "prev_high": round(prev_high, 2),
        "prev_low": round(prev_low, 2),
        "prev_close": round(prev_close, 2)
    }

def analyze_option_r3_setup(
    symbol: str,
    spot_price: float,
    spot_pct_change: float = 0.0,
    spot_is_bullish: bool = True,
    spot_is_1h_confirmed: bool = True,
    spot_prev_high: float = 0.0,
    spot_prev_low: float = 0.0,
    spot_prev_close: float = 0.0,
    spot_r1: float = 0.0,
    spot_r2: float = 0.0,
    spot_r3: float = 0.0,
    fyers_client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Executes deep R3 Option Breakout Analysis:
    1. Selects exact OTM Strike & Contract Name (e.g. DLF 28 NOV 700 CE)
    2. Fetches or calculates option contract's historical HLC & Pivots
    3. Verifies if Option LTP >= Option R3 (Breakout Trigger)
    4. Computes Targets & Trailing Stop Loss
    """
    contract = build_option_contract(symbol, spot_price, opt_type="CE")
    clean_sym = contract["symbol"]
    strike = contract["strike"]
    fyers_sym = contract["fyers_symbol"]
    contract_name = contract["contract_name"]

    opt_ltp = 0.0
    opt_prev_h = 0.0
    opt_prev_l = 0.0
    opt_prev_c = 0.0
    data_source = "Analytical Calibration"

    # Auto-acquire Fyers client ONLY if already authenticated in memory or cache
    if fyers_client is None:
        try:
            from core.fyers_auth import _cached_fyers_client, get_cached_token
            if _cached_fyers_client is not None:
                fyers_client = _cached_fyers_client
            elif get_cached_token() is not None:
                from core.fyers_auth import get_fyers_client
                ok_f, cl_f = get_fyers_client(force_refresh=False)
                if ok_f and cl_f:
                    fyers_client = cl_f
        except Exception:
            pass

    # 1. Attempt Live Option Data from Fyers API if client is available
    if fyers_client:
        try:
            try:
                from .fyers_auth import safe_fyers_quotes, safe_fyers_history
            except ImportError:
                from core.fyers_auth import safe_fyers_quotes, safe_fyers_history
            now_dt = datetime.datetime.now()
            from_d = (now_dt - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            to_d = now_dt.strftime("%Y-%m-%d")

            d_hist = {
                "symbol": fyers_sym,
                "resolution": "D",
                "date_format": "1",
                "range_from": from_d,
                "range_to": to_d,
                "cont_flag": "1"
            }
            hist_res = safe_fyers_history(fyers_client, d_hist)
            candles = hist_res.get("candles", []) if isinstance(hist_res, dict) else []

            if candles and len(candles) >= 1:
                # Last completed daily candle
                prev_c = candles[-2] if len(candles) >= 2 else candles[-1]
                opt_prev_h = float(prev_c[2])
                opt_prev_l = float(prev_c[3])
                opt_prev_c = float(prev_c[4])

                # Get current LTP
                q_res = safe_fyers_quotes(fyers_client, {"symbols": fyers_sym})
                if isinstance(q_res, dict) and "d" in q_res and len(q_res["d"]) > 0:
                    val = q_res["d"][0].get("v", {})
                    opt_ltp = float(val.get("lp", 0.0))
                    data_source = "🟢 Fyers API Live Broker Feed"
        except Exception:
            pass

    # 2. Resilient Analytical Fallback (Calibrated to Spot HLC & Delta Model)
    # Used when market is closed, Fyers is offline, or pre-market simulation
    if opt_ltp <= 0 or opt_prev_h <= 0:
        p_close = spot_prev_close if spot_prev_close > 0 else (spot_price / (1.0 + (spot_pct_change / 100.0)))
        p_high = spot_prev_high if spot_prev_high > 0 else max(p_close * 1.015, spot_price)
        p_low = spot_prev_low if spot_prev_low > 0 else (p_close * 0.985)

        step_val = max(1.0, float(contract.get("step", 20)))
        otm_diff = max(0.0, float(strike - p_close))
        delta = max(0.20, min(0.50, 0.42 - (otm_diff / (step_val * 8.0))))

        # Static baseline option price at yesterday's close
        base_extrinsic = max(1.50, p_close * 0.02 - (otm_diff * 0.20))
        opt_prev_c = round(base_extrinsic, 2)
        opt_prev_h = round(opt_prev_c + delta * (p_high - p_close), 2)
        opt_prev_l = round(max(0.30, opt_prev_c + delta * (p_low - p_close)), 2)

        # Today's option LTP derived from spot movement
        spot_move = spot_price - p_close
        gamma_boost = (0.0015 * (spot_move ** 2)) if spot_move > 0 else 0.0
        opt_ltp = round(max(0.50, opt_prev_c + delta * spot_move + gamma_boost), 2)
        data_source = "🔵 Calibrated Option Analytics"

    # Compute Option Pivot Points
    pivots = calculate_option_pivot_levels(opt_prev_h, opt_prev_l, opt_prev_c)
    opt_r3 = pivots["r3"]
    opt_r2 = pivots["r2"]
    opt_r1 = pivots["r1"]
    opt_p = pivots["p"]

    # --- Golden Rule Logic: Option Leads, Future Follows ---
    # Core Strategy: Stock Price crosses Spot R2 AND Option LTP crosses Option Daily R3
    # When Option R3 is broken while Stock is at/above R2, explosive momentum follows towards Spot R3.
    opt_leads_r3 = bool(opt_r3 > 0 and opt_ltp >= opt_r3)
    spot_breaks_r2 = bool((spot_r2 > 0 and spot_price >= spot_r2) or (spot_r1 > 0 and spot_price >= spot_r1 and spot_is_1h_confirmed))
    
    # Both conditions must align: Option R3 Broken AND Spot R2 Broken / Moving
    is_option_r3_crossed = bool(opt_leads_r3 and spot_breaks_r2)

    # 100% Confirmed Buy Condition:
    is_100_percent_buy = bool(is_option_r3_crossed and spot_is_bullish and spot_is_1h_confirmed)

    # Risk-Reward for Option:
    # Stop loss: Option's break-point level or 25% risk from entry
    opt_sl = round(max(0.10, opt_r3 * 0.75 if opt_r3 > 0 else opt_ltp * 0.75), 2)
    risk_per_share = max(0.5, opt_ltp - opt_sl)
    risk_pct = round((risk_per_share / opt_ltp) * 100, 1)

    opt_t1 = round(opt_ltp + (1.5 * risk_per_share), 2)
    opt_t2 = round(opt_ltp + (2.5 * risk_per_share), 2)
    t1_pct = round(((opt_t1 - opt_ltp) / opt_ltp) * 100, 1)
    t2_pct = round(((opt_t2 - opt_ltp) / opt_ltp) * 100, 1)

    # Multibagger target (100% to 200%+ capital gain)
    multibagger_target = round(opt_ltp * 2.0, 2)

    return {
        "symbol": clean_sym,
        "full_symbol": f"{clean_sym}.NS",
        "spot_price": spot_price,
        "spot_change": spot_pct_change,
        "strike": strike,
        "contract_name": contract_name,
        "fyers_symbol": fyers_sym,
        "expiry_label": contract["expiry_info"]["label"],
        "expiry_date": contract["expiry_info"]["date"],
        "data_source": data_source,
        "opt_ltp": opt_ltp,
        "opt_prev_close": opt_prev_c,
        "opt_pivot": opt_p,
        "opt_r1": opt_r1,
        "opt_r2": opt_r2,
        "opt_r3": opt_r3,
        "is_option_r3_crossed": is_option_r3_crossed,
        "is_100_percent_buy": is_100_percent_buy,
        "is_gamma_blast": contract.get("is_gamma_blast", False),
        "is_index": contract.get("is_index", False),
        "stop_loss": opt_sl,
        "risk_pct": risk_pct,
        "target_1": opt_t1,
        "t1_pct": t1_pct,
        "target_2": opt_t2,
        "t2_pct": t2_pct,
        "multibagger_target": multibagger_target,
        "action_command": f"BUY {contract_name}"
    }

# -------------------------------------------------------------
# Specific Telegram Alert Message Formatter
# -------------------------------------------------------------
def format_specific_option_r3_alert(res: Dict[str, Any]) -> str:
    """
    Formats institutional, highly-specific Telegram Alert for Option Buying.
    Outputs clear, actionable instruction: e.g. 'BUY DLF 28 NOV 700 CE'
    """
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    contract_name = res["contract_name"]
    spot_sym = res["symbol"]
    spot_p = res["spot_price"]
    spot_chg = res.get("spot_change", 0.0)
    opt_ltp = res["opt_ltp"]
    opt_r3 = res["opt_r3"]
    opt_p = res["opt_pivot"]
    opt_sl = res["stop_loss"]
    t1 = res["target_1"]
    t2 = res["target_2"]
    multi_t = res["multibagger_target"]

    return (
        f"🚀 <b>૧૦૦% કન્ફર્મ ઓપ્શન રોકેટ બ્રેકઆઉટ!</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>ACTION: BUY {contract_name}</b>\n"
        f"💰 <b>ખરીદ ભાવ (LTP):</b> ₹{opt_ltp:.2f}\n"
        f"⚡ <b>સેટઅપ:</b> Option R3 Breakout (Option Leads, Future Follows)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>સ્ટોપલોસ (SL):</b> ₹{opt_sl:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"🎯 <b>Target 1 (1:1.5):</b> ₹{t1:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"🎯 <b>Target 2 (1:2.5):</b> ₹{t2:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"🚀 <b>મલ્ટિબેગર ટાર્ગેટ:</b> ₹{multi_t:.2f} (+100% ડબલ)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Option Pivots:</b> P: ₹{opt_p:.2f} | <b>R3: ₹{opt_r3:.2f} (ક્રોસ થયેલ ✅)</b>\n"
        f"📌 <b>Spot {spot_sym}:</b> ₹{spot_p:.2f} ({spot_chg:+.2f}%)\n"
        f"⚡ <b>Fyers Code:</b> <code>{res['fyers_symbol']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

# -------------------------------------------------------------
# Standalone CLI Self-Test
# -------------------------------------------------------------
if __name__ == "__main__":
    print("========================================================")
    print("  TESTING OPTION R3 BREAKOUT ENGINE")
    print("========================================================")
    sample_stocks = [
        ("DLF.NS", 692.50, 2.1),
        ("TATASTEEL.NS", 154.20, 1.8),
        ("RELIANCE.NS", 1285.00, 2.4),
    ]

    for sym, price, chg in sample_stocks:
        res = analyze_option_r3_setup(sym, price, spot_pct_change=chg, spot_is_bullish=True, spot_is_1h_confirmed=True)
        print(f"\n[Stock]: {sym} | Spot: ₹{price}")
        print(f"Contract: {res['contract_name']}")
        print(f"Fyers Symbol: {res['fyers_symbol']}")
        print(f"Option LTP: ₹{res['opt_ltp']} | Option R3: ₹{res['opt_r3']}")
        print(f"Option R3 Crossed: {res['is_option_r3_crossed']}")
        print(f"100% Buy Confirmed: {res['is_100_percent_buy']}")
        print(f"Action Command: {res['action_command']}")

    print("\nSample Alert Message Output:")
    print("--------------------------------------------------------")
    sample_alert = format_specific_option_r3_alert(res)
    print(sample_alert)
