import time
import json
import os
import sys
import datetime
import requests
import yfinance as yf
import pandas as pd
import numpy as np

try:
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
except Exception:
    pass

# -------------------------------------------------------------
# Configuration
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8907823823:AAFqqUDE0H594TIJVoym9n0wJfCXMwmgkuw"
TELEGRAM_CHAT_ID = "1120508907"
SCAN_INTERVAL_SECONDS = 300 # 5 minutes
STATE_FILE = "alert_state.json"
IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    """Returns current datetime in Indian Standard Time (IST), works on any cloud server worldwide."""
    return datetime.datetime.now(IST_TZ)

ENFORCE_MARKET_HOURS = True # False to scan anytime (for testing)
MARKET_OPEN_TIME = datetime.time(9, 15)   # 09:15 AM IST
MARKET_CLOSE_TIME = datetime.time(15, 30) # 03:30 PM IST

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

WATCHLIST = [
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

# -------------------------------------------------------------
# Helper: Send Telegram Alert
# -------------------------------------------------------------
def send_telegram_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"Error sending telegram: {e}")
        return False

# -------------------------------------------------------------
# Indicators
# -------------------------------------------------------------
def calculate_hilega_milega(df, rsi_period=9, ema_period=3, wma_period=21):
    if len(df) < (rsi_period + wma_period):
        return df
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)
    
    green_ema3 = rsi.ewm(span=ema_period, adjust=False).mean()
    weights = np.arange(1, wma_period + 1)
    wma21 = rsi.rolling(wma_period).apply(lambda s: np.dot(s, weights) / weights.sum(), raw=True)
    
    df['RSI_9'] = rsi
    df['Green_EMA3'] = green_ema3
    df['Red_WMA21'] = wma21
    df['Water_50'] = 50.0
    return df

def calculate_trend_craft_ict(df, default_period=45):
    if len(df) < 10:
        return df
    period = default_period if len(df) >= (default_period + 5) else max(8, len(df) // 2)
    df['TC_SMA_High'] = df['High'].rolling(period).mean()
    df['TC_SMA_Low'] = df['Low'].rolling(period).mean()
    return df

def calculate_volume_analysis(df, sma_period=20):
    if 'Volume' not in df.columns or len(df) < 5:
        return df
    actual_period = sma_period if len(df) >= sma_period else max(3, len(df) // 2)
    df['Vol_SMA20'] = df['Volume'].rolling(actual_period).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    return df

def calculate_daily_pivot_points(df_d):
    """
    Standard Daily Pivot Points calculated from previous trading session's High, Low, Close.
    P = (H + L + C) / 3
    R1 = 2P - L, S1 = 2P - H
    R2 = P + (H - L), S2 = P - (H - L)
    R3 = H + 2*(P - L), S3 = L - 2*(H - P)
    """
    if len(df_d) < 2:
        return None
    prev = df_d.iloc[-2]
    h, l, c = float(prev['High']), float(prev['Low']), float(prev['Close'])
    p = (h + l + c) / 3.0
    r1 = (2.0 * p) - l
    s1 = (2.0 * p) - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    r3 = h + 2.0 * (p - l)
    s3 = l - 2.0 * (h - p)
    
    return {
        "p": round(p, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
        "prev_high": round(h, 2),
        "prev_low": round(l, 2),
        "prev_close": round(c, 2)
    }

def analyze_stock(sym):
    try:
        t = yf.Ticker(sym)
        df_d = t.history(period="1y", interval="1d").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_w = t.history(period="3y", interval="1wk").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_m = t.history(period="5y", interval="1mo").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_1h = t.history(period="1mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        
        if df_d.empty or len(df_d) < 30 or df_1h.empty:
            return None
            
        df_m = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_m), 24))
        df_w = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_w), 30))
        df_d = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_d), 45))
        df_1h = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_1h), 45))
        
        # Monthly HM
        m_curr = df_m.iloc[-1]
        m_bull = (m_curr['Green_EMA3'] > m_curr['Red_WMA21']) and (m_curr['Green_EMA3'] >= 50)
        
        # Weekly HM
        w_curr = df_w.iloc[-1]
        w_bull = (w_curr['Green_EMA3'] > w_curr['Red_WMA21']) and (w_curr['Green_EMA3'] >= 50)
        
        # Daily HM & TC (Macro Trend Filter)
        d_curr = df_d.iloc[-1]
        d_prev = df_d.iloc[-2]
        d_hm_bull = (d_curr['Green_EMA3'] > d_curr['Red_WMA21']) and (d_curr['Green_EMA3'] >= 50.0)
        d_hm_bear = (d_curr['Green_EMA3'] < d_curr['Red_WMA21']) and (d_curr['Green_EMA3'] <= 50.0)
        d_bull_gap = d_curr['Green_EMA3'] - d_curr['Red_WMA21']
        d_bear_gap = d_curr['Red_WMA21'] - d_curr['Green_EMA3']
        d_tc_bull = d_curr['Close'] >= d_curr['TC_SMA_Low']
        d_tc_super_bull = d_curr['Close'] > d_curr['TC_SMA_High']
        d_tc_dip = (d_curr['Close'] >= d_curr['TC_SMA_Low']) and (d_curr['Close'] <= d_curr['TC_SMA_High'])
        d_is_positive = d_hm_bull and (d_bull_gap >= 2.5) and d_tc_bull
        d_is_negative = d_hm_bear and (d_bear_gap >= 2.5) and (d_curr['Close'] <= d_curr['TC_SMA_High'])
        
        # 1-Hour Trigger (Image 4 & Image 5 Strict Confluence)
        h1_curr = df_1h.iloc[-1]
        h1_prev = df_1h.iloc[-2]
        h1_prev2 = df_1h.iloc[-3] if len(df_1h) >= 3 else h1_prev
        
        # 1H Slopes (Vertical Steep Angle)
        h1_green_slope = h1_curr['Green_EMA3'] - h1_prev['Green_EMA3']
        h1_two_bar_green_slope = h1_curr['Green_EMA3'] - h1_prev2['Green_EMA3']
        
        # 1H Gap & Expansion from Red Line
        h1_bull_gap = h1_curr['Green_EMA3'] - h1_curr['Red_WMA21']
        h1_prev_bull_gap = h1_prev['Green_EMA3'] - h1_prev['Red_WMA21']
        h1_bear_gap = h1_curr['Red_WMA21'] - h1_curr['Green_EMA3']
        h1_prev_bear_gap = h1_prev['Red_WMA21'] - h1_prev['Green_EMA3']
        
        # 1H Institutional Volume (VPA) - Strictly Require >= 1.2x (Eliminates low-volume traps)
        h1_vol_ratio = h1_curr['Vol_Ratio'] if pd.notna(h1_curr['Vol_Ratio']) else 1.0
        h1_vol_confirmed = h1_vol_ratio >= 1.2
        
        # Image 5: Bullish Rocket Confluence (Daily Positive + 1H Vertical, Gap Expanding, Above Water 50, Vol >= 1.2x)
        h1_is_vertical_up = (h1_green_slope >= 1.8) or (h1_two_bar_green_slope >= 3.0)
        h1_gap_expanding_up = (h1_bull_gap >= 2.5) and (h1_bull_gap >= h1_prev_bull_gap)
        h1_above_water = (h1_curr['RSI_9'] >= 51.5) and (h1_curr['Green_EMA3'] >= 50.0)
        h1_hierarchy_bull = (h1_curr['RSI_9'] >= h1_curr['Green_EMA3'] - 1.5) and (h1_curr['Green_EMA3'] > h1_curr['Red_WMA21'])
        h1_tc_confirmed_bull = (h1_curr['Close'] >= h1_curr['TC_SMA_Low']) and (h1_curr['Close'] >= h1_prev['Close'])
        
        is_sniper_buy = (
            d_is_positive and
            h1_is_vertical_up and
            h1_hierarchy_bull and
            h1_gap_expanding_up and
            h1_above_water and
            h1_tc_confirmed_bull and
            h1_vol_confirmed
        )
        
        # Image 4: Bearish Avalanche Confluence (Daily Negative + 1H Vertical, Gap Expanding, Below Water 50, Vol >= 1.2x)
        h1_is_vertical_down = (h1_green_slope <= -1.8) or (h1_two_bar_green_slope <= -3.0)
        h1_gap_expanding_down = (h1_bear_gap >= 2.5) and (h1_bear_gap >= h1_prev_bear_gap)
        h1_below_water = (h1_curr['RSI_9'] <= 48.5) and (h1_curr['Green_EMA3'] <= 50.0)
        h1_hierarchy_bear = (h1_curr['RSI_9'] <= h1_curr['Green_EMA3'] + 1.5) and (h1_curr['Green_EMA3'] < h1_curr['Red_WMA21'])
        h1_tc_confirmed_bear = (h1_curr['Close'] <= h1_curr['TC_SMA_High']) and (h1_curr['Close'] <= h1_prev['Close'])
        
        is_sniper_short = (
            d_is_negative and
            h1_is_vertical_down and
            h1_hierarchy_bear and
            h1_gap_expanding_down and
            h1_below_water and
            h1_tc_confirmed_bear and
            h1_vol_confirmed
        )
        
        curr_p = d_curr['Close']
        pct_chg = ((curr_p - d_prev['Close']) / d_prev['Close']) * 100
        strike_step = 20 if curr_p < 500 else (50 if curr_p < 2500 else 100)
        
        if is_sniper_short:
            signal = "🩸 SNIPER SHORT SELL (Confirmed)"
            stop_loss = h1_curr['TC_SMA_High'] if h1_curr['TC_SMA_High'] > curr_p else curr_p * 1.015
            risk = stop_loss - curr_p
            if risk <= 0 or risk > (curr_p * 0.12):
                risk = curr_p * 0.015
                stop_loss = curr_p + risk
            t1 = curr_p - (1.5 * risk)
            t2 = curr_p - (2.5 * risk)
            t1_pct = ((curr_p - t1) / curr_p) * 100
            t2_pct = ((curr_p - t2) / curr_p) * 100
            pe_strike = round(curr_p * 0.995 / strike_step) * strike_step
            ce_strike = max(d_curr['TC_SMA_High'], curr_p * 1.025)
        else:
            stop_loss = h1_curr['TC_SMA_Low'] if (h1_curr['TC_SMA_Low'] > 0 and h1_curr['TC_SMA_Low'] < curr_p) else d_curr['TC_SMA_Low']
            risk = curr_p - stop_loss
            if risk <= 0 or risk > (curr_p * 0.12):
                risk = curr_p * 0.015
                stop_loss = curr_p - risk
            t1 = curr_p + (1.5 * risk)
            t2 = curr_p + (2.5 * risk)
            t1_pct = ((t1 - curr_p) / curr_p) * 100
            t2_pct = ((t2 - curr_p) / curr_p) * 100
            ce_strike = round(curr_p * 1.005 / strike_step) * strike_step
            pe_strike = min(d_curr['TC_SMA_Low'], curr_p * 0.975)
            
            is_1h_bull = (h1_curr['Green_EMA3'] > h1_curr['Red_WMA21']) and (h1_curr['Close'] > h1_curr['TC_SMA_High'])
            if is_sniper_buy:
                signal = "🎯 SNIPER DIP BUY (Confirmed)"
            elif d_is_positive and not is_sniper_buy:
                signal = "🎯 BUY ON DIPS (Wait for 1H)"
            elif d_is_negative and not is_sniper_short:
                signal = "⚠️ SHORT ON BOUNCE (Wait for 1H)"
            elif m_bull and w_bull and (d_tc_super_bull or d_tc_dip) and is_1h_bull and h1_vol_confirmed:
                signal = "🚀 STRONG BUY (Confirmed)"
            elif not d_hm_bull and not d_tc_bull and not m_bull and not w_bull:
                signal = "🔴 STRONG SELL / AVOID"
            else:
                signal = "⏳ WAIT / CONSOLIDATION"
                
        risk_pct = (risk / curr_p) * 100
        
        # Daily Pivots & R3 Option Radar
        pivots = calculate_daily_pivot_points(df_d)
        is_r3_radar = False
        otm_call_strike = round(curr_p * 1.015 / strike_step) * strike_step
        if otm_call_strike <= curr_p:
            otm_call_strike = (int(curr_p / strike_step) + 1) * strike_step
        r1_val = 0.0
        r2_val = 0.0
        r3_val = 0.0
        p_val = 0.0
        
        if pivots:
            p_val = pivots['p']
            r1_val = pivots['r1']
            r2_val = pivots['r2']
            r3_val = pivots['r3']
            otm_call_strike = int((int(curr_p / strike_step) + 1) * strike_step)
            is_r3_radar = bool(
                (pct_chg >= 1.5 or curr_p >= r2_val) and
                (curr_p >= r1_val) and
                (d_hm_bull or pct_chg >= 2.0)
            )

        return {
            "symbol": sym.replace(".NS", ""),
            "price": curr_p,
            "change": pct_chg,
            "signal": signal,
            "is_short": is_sniper_short,
            "h1_cross": is_sniper_buy or is_sniper_short,
            "vol_ratio": h1_vol_ratio,
            "stop_loss": stop_loss,
            "t1": t1,
            "t1_pct": t1_pct,
            "t2": t2,
            "t2_pct": t2_pct,
            "risk_pct": risk_pct,
            "pe_strike": pe_strike,
            "ce_strike": ce_strike,
            "is_r3_radar": is_r3_radar,
            "otm_call_strike": otm_call_strike,
            "r1": r1_val,
            "r2": r2_val,
            "r3": r3_val,
            "pivot_p": p_val
        }
    except Exception as e:
        print(f"Error scanning {sym}: {e}")
        return None

# -------------------------------------------------------------
# Main Scan & Alert Loop
# -------------------------------------------------------------

# -------------------------------------------------------------
# Active Trades Risk Watchdog (Hilega-Milega Early Exit & SL Trigger)
# -------------------------------------------------------------
def monitor_active_trades(state):
    trades_file = "active_trades.json"
    if not os.path.exists(trades_file):
        return []
    try:
        with open(trades_file, "r", encoding="utf-8") as f:
            trades = json.load(f)
    except Exception:
        return []
        
    active_trades = [t for t in trades if t.get("status") == "ACTIVE"]
    if not active_trades:
        return []
        
    print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] Monitoring {len(active_trades)} active trades with Hilega-Milega & SL triggers...")
    alerts = []
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    
    for trd in active_trades:
        try:
            tid = trd['id']
            sym = trd['symbol']
            full_sym = trd.get('full_symbol', f"{sym}.NS")
            t_type = trd.get('trade_type', 'BUY')
            entry_p = float(trd['entry_price'])
            
            ticker = yf.Ticker(full_sym)
            df_d = ticker.history(period="5d", interval="1d")
            df_1h = ticker.history(period="1mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume'])
            
            if df_d.empty:
                continue
            curr_p = float(df_d['Close'].iloc[-1])
            pnl_pct = ((curr_p - entry_p) / entry_p) * 100
            
            # Calculate 1-Hour Hilega-Milega for Early Momentum Exit
            hm_status_text = "સામાન્ય"
            is_hm_bear_cross = False
            is_hm_dump = False
            c_green = 50.0
            c_red = 50.0
            rsi_val = 50.0
            
            if not df_1h.empty and len(df_1h) >= 30:
                df_1h = calculate_hilega_milega(df_1h)
                c_green = float(df_1h['Green_EMA3'].iloc[-1])
                p_green = float(df_1h['Green_EMA3'].iloc[-2])
                c_red = float(df_1h['Red_WMA21'].iloc[-1])
                p_red = float(df_1h['Red_WMA21'].iloc[-2])
                rsi_val = float(df_1h['RSI_9'].iloc[-1])
                
                is_fresh_bear = (p_green >= p_red) and (c_green < c_red)
                is_fresh_bull = (p_green <= p_red) and (c_green > c_red)
                is_below_water = (c_green < 50.0)
                is_hm_bear_cross = is_fresh_bear or (c_green < c_red and is_below_water)
                is_hm_dump = (c_green < 40.0) and (c_green < c_red)
                
                if is_fresh_bear:
                    hm_status_text = "🔴 ૧-Hour તાજો બેરિશ ક્રોસઓવર (Fresh Bear Cross)"
                elif is_fresh_bull:
                    hm_status_text = "🟢 ૧-Hour તાજો ગોલ્ડન ક્રોસઓવર (Fresh Bull Cross)"
                elif c_green < c_red and is_below_water:
                    hm_status_text = "🔴 સંપૂર્ણ મંદી (પાણી 50 ની નીચે)"
                elif c_green > c_red and c_green >= 50:
                    hm_status_text = "🟢 સુપર તેજી (પાણી 50 ની ઉપર)"
                else:
                    hm_status_text = "🟡 રિવર્સલ / પુલબેક"
            
            if t_type == "BUY":
                sl = float(trd.get('stop_loss', 0)) if trd.get('stop_loss') else 0
                t1 = float(trd.get('target_1', 0)) if trd.get('target_1') else 0
                t2 = float(trd.get('target_2', 0)) if trd.get('target_2') else 0
                
                # 1. Stop Loss Hit -> EMERGENCY EXIT ALERT (Highest Priority)
                if sl > 0 and curr_p <= sl:
                    alert_key = f"{tid}_SL_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🚨 <b>EMERGENCY EXIT ALERT! (STOP-LOSS HIT)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📉 <b>સ્ટોક:</b> {sym} (BUY Position)\n"
                            f"💰 <b>તમારી એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🛡️ <b>સ્ટોપ-લોસ લેવલ:</b> ₹{sl:.2f}\n"
                            f"🔴 <b>હાલનો ભાવ (LTP):</b> ₹{curr_p:.2f} ({pnl_pct:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>તાત્કાલિક પગલું:</b> સ્ટોક તમારા સ્ટોપલોસ નીચે ગયો છે. મોટી ખોટ અટકાવવા <b>હમણાં જ EXIT કરો!</b>\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} BUY SL HIT")
                        
                # 2. Target 2 Hit -> MAX PROFIT
                elif t2 > 0 and curr_p >= t2:
                    alert_key = f"{tid}_T2_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🎉 <b>TARGET 2 ACHIEVED! (MAX PROFIT)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🚀 <b>સ્ટોક:</b> {sym} (BUY Position)\n"
                            f"💰 <b>એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🎯 <b>Target 2:</b> ₹{t2:.2f}\n"
                            f"🟢 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} (+{pnl_pct:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💰 <b>સલાહ:</b> ૧૦૦% મહત્તમ ટાર્ગેટ આવી ગયો છે. પૂરો પ્રોફિટ બુક કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} BUY T2 HIT")
                        
                # 3. Target 1 Hit -> PARTIAL PROFIT
                elif t1 > 0 and curr_p >= t1:
                    alert_key = f"{tid}_T1_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🎯 <b>TARGET 1 ACHIEVED!</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📈 <b>સ્ટોક:</b> {sym} (BUY Position)\n"
                            f"💰 <b>એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🎯 <b>Target 1:</b> ₹{t1:.2f}\n"
                            f"🟢 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} (+{pnl_pct:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <b>સલાહ:</b> ૫૦% નફો બુક કરો અને બાકીના સ્ટોકનો સ્ટોપ-લોસ એન્ટ્રી ભાવે ટ્રેલ કરો.\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} BUY T1 HIT")
                        
                # 4. Hilega-Milega Early Exit Trigger (Before SL is hit!)
                elif is_hm_bear_cross:
                    alert_key = f"{tid}_HM_EARLY_EXIT"
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>EARLY EXIT WARNING! (HILEGA-MILEGA REVERSAL)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📉 <b>સ્ટોક:</b> {sym} (BUY Position)\n"
                            f"💰 <b>તમારી એન્ટ્રી:</b> ₹{entry_p:.2f} | <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} ({pnl_pct:+.2f}%)\n"
                            f"🛡️ <b>સ્ટોપ-લોસ:</b> ₹{sl:.2f} (હજુ હિટ નથી થયો)\n"
                            f"🚨 <b>Hilega-Milega 1H:</b> {hm_status_text}\n"
                            f"   • Green Line: {c_green:.1f} | Red Line: {c_red:.1f}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <b>સ્માર્ટ સલાહ:</b> 1-Hour ચાર્ટ પર ગ્રીન લાઈન રેડ લાઈન નીચે સરકી ગઈ છે અને મોમેન્ટમ ગુમાવી રહ્યું છે. પૂરો સ્ટોપલોસ હિટ થવાની રાહ જોવાને બદલે અત્યારે જ ઓછા નુકસાને કે પ્રોફિટ બચાવીને <b>Safe Early Exit</b> કરી શકાય!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} HM EARLY EXIT")
                        
            elif t_type == "SHORT":
                sl = float(trd.get('stop_loss', 0)) if trd.get('stop_loss') else 0
                t1 = float(trd.get('target_1', 0)) if trd.get('target_1') else 0
                t2 = float(trd.get('target_2', 0)) if trd.get('target_2') else 0
                pnl_pct_short = ((entry_p - curr_p) / entry_p) * 100
                
                # 1. Short Stop Loss Hit
                if sl > 0 and curr_p >= sl:
                    alert_key = f"{tid}_SHORT_SL_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🚨 <b>EMERGENCY EXIT ALERT! (SHORT STOP-LOSS HIT)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📈 <b>સ્ટોક:</b> {sym} (SHORT Position)\n"
                            f"💰 <b>તમારી એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🛡️ <b>શોર્ટ સ્ટોપ-લોસ:</b> ₹{sl:.2f}\n"
                            f"🔴 <b>હાલનો ભાવ (LTP):</b> ₹{curr_p:.2f} ({pnl_pct_short:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>તાત્કાલિક પગલું:</b> સ્ટોક તમારા શોર્ટ સ્ટોપલોસ ઉપર નીકળી ગયો છે. મોટી ખોટ અટકાવવા <b>હમણાં જ EXIT કરો!</b>\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} SHORT SL HIT")
                        
                # 2. Target 2 Hit (Max Profit Short)
                elif t2 > 0 and curr_p <= t2:
                    alert_key = f"{tid}_SHORT_T2_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🎉 <b>SHORT TARGET 2 ACHIEVED! (MAX PROFIT)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📉 <b>સ્ટોક:</b> {sym} (SHORT Position)\n"
                            f"💰 <b>એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🎯 <b>Target 2:</b> ₹{t2:.2f}\n"
                            f"🟢 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} (+{pnl_pct_short:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💰 <b>સલાહ:</b> ૧૦૦% મહત્તમ શોર્ટ પ્રોફિટ ટાર્ગેટ આવી ગયો છે. પૂરો પ્રોફિટ બુક કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} SHORT T2 HIT")
                        
                # 3. Target 1 Hit (Partial Profit Short)
                elif t1 > 0 and curr_p <= t1:
                    alert_key = f"{tid}_SHORT_T1_HIT"
                    if not state.get(alert_key):
                        msg = (
                            f"🎯 <b>SHORT TARGET 1 ACHIEVED!</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📉 <b>સ્ટોક:</b> {sym} (SHORT Position)\n"
                            f"💰 <b>એન્ટ્રી:</b> ₹{entry_p:.2f}\n"
                            f"🎯 <b>Target 1:</b> ₹{t1:.2f}\n"
                            f"🟢 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} (+{pnl_pct_short:+.2f}%)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <b>સલાહ:</b> ૫૦% નફો બુક કરો અને બાકીના શોર્ટનો સ્ટોપ-લોસ એન્ટ્રી ભાવે ટ્રેલ કરો.\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} SHORT T1 HIT")
                        
                # 4. 1H Bullish Cross Early Exit Warning on Short
                elif is_fresh_bull or (c_green > c_red and c_green >= 50):
                    alert_key = f"{tid}_SHORT_HM_EARLY_EXIT"
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>EARLY EXIT WARNING! (1H HM BULLISH REVERSAL ON SHORT)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📈 <b>સ્ટોક:</b> {sym} (SHORT Position)\n"
                            f"💰 <b>તમારી એન્ટ્રી:</b> ₹{entry_p:.2f} | <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} ({pnl_pct_short:+.2f}%)\n"
                            f"🛡️ <b>સ્ટોપ-લોસ:</b> ₹{sl:.2f} (હજુ હિટ નથી થયો)\n"
                            f"🚨 <b>Hilega-Milega 1H:</b> {hm_status_text}\n"
                            f"   • Green Line: {c_green:.1f} | Red Line: {c_red:.1f}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <b>સ્માર્ટ સલાહ:</b> 1-Hour ચાર્ટ પર ગ્રીન લાઈન રેડ લાઈન ઉપર નીકળી ગઈ છે અને તેજીનું મોમેન્ટમ પકડી રહી છે. શોર્ટ પોઝિશનમાંથી સુરક્ષિત <b>Safe Early Exit</b> કરી શકાય!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} SHORT HM EARLY EXIT")
            elif t_type == "OPTION_SELLING":
                ce = float(trd.get('ce_strike', 0)) if trd.get('ce_strike') else 0
                pe = float(trd.get('pe_strike', 0)) if trd.get('pe_strike') else 0
                
                # Call Breach
                if ce > 0 and curr_p >= ce:
                    alert_key = f"{tid}_CE_BREACH"
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>OPTION SELLING RISK ALERT! (CALL BREACH)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚖️ <b>સ્ટોક:</b> {sym} (ઓપ્શન સેલિંગ)\n"
                            f"📈 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f}\n"
                            f"🚨 <b>જોખમ:</b> ઉપરની Call Strike (₹{ce:.1f}) તૂટી ગઈ છે!\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>સલાહ:</b> શોર્ટ કરેલા Call (CE) માંથી તાત્કાલિક Exit કરો અથવા પોઝિશનને હેજ કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} OPTION CE BREACH")
                        
                # Put Breach
                elif pe > 0 and curr_p <= pe:
                    alert_key = f"{tid}_PE_BREACH"
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>OPTION SELLING RISK ALERT! (PUT BREACH)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚖️ <b>સ્ટોક:</b> {sym} (ઓપ્શન સેલિંગ)\n"
                            f"📉 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f}\n"
                            f"🚨 <b>જોખમ:</b> નીચેની Put Strike (₹{pe:.1f}) તૂટી ગઈ છે!\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>સલાહ:</b> શોર્ટ કરેલા Put (PE) માંથી તાત્કાલિક Exit કરો અથવા પોઝિશનને હેજ કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} OPTION PE BREACH")
                        
                # Early Threat Warning on Momentum Surge
                elif c_green > c_red and rsi_val >= 64 and (ce - curr_p) <= (ce * 0.015):
                    alert_key = f"{tid}_HM_CALL_THREAT"
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>OPTION SELLING MOMENTUM THREAT! (CALL SIDE)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚖️ <b>સ્ટોક:</b> {sym} (ઓપ્શન સેલિંગ)\n"
                            f"📈 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} | <b>Call Strike:</b> > ₹{ce:.1f}\n"
                            f"🔥 <b>Hilega-Milega:</b> તીવ્ર તેજી સ્પાઇક (RSI: {rsi_val:.1f} > 64)\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>સલાહ:</b> સ્ટોકમાં મોટો બુલિશ સ્પાઇક આવ્યો છે. કૉલ લેગ જોખમમાં આવી શકે છે, એલર્ટ રહો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} HM CALL THREAT")
        except Exception as err:
            print(f"Error checking trade {trd.get('symbol')}: {err}")
            
    return alerts

def run_scan_cycle(force=False):
    if ENFORCE_MARKET_HOURS and not force:
        is_open, reason = is_market_open()
        if not is_open:
            print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] ⏸️ Market Closed ({reason}). Skipping scan cycle.")
            return []

    from concurrent.futures import ThreadPoolExecutor
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
            
    print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] Scanning {len(WATCHLIST)} stocks with multi-threading...")
    
    new_alerts = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_stock, WATCHLIST))
        
    # 1. Monitor User's Active Trades for Auto-Exit / Risk
    trade_alerts = monitor_active_trades(state)
    new_alerts.extend(trade_alerts)

    for res in results:
        if not res:
            continue
            
        s_name = res['symbol']
        curr_sig = res['signal']
        prev_sig = state.get(s_name)
        
        # Only alert on meaningful transition
        is_sniper_short = "SNIPER SHORT" in curr_sig
        is_sniper_buy = "SNIPER DIP BUY" in curr_sig or "STRONG BUY" in curr_sig
        is_buy = "BUY" in curr_sig or "BULLISH" in curr_sig
        is_sell = "SELL" in curr_sig or "AVOID" in curr_sig
        
        # 0. Alert for R3 OPTION ROCKET BREAKOUT
        today_str = get_ist_now().date().isoformat()
        r3_alert_key = f"{s_name}_R3_{today_str}"
        if res.get('is_r3_radar') and not state.get(r3_alert_key):
            r3_alert_text = (
                f"⚡ <b>R3 OPTION ROCKET BREAKOUT!</b> ⚡\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
                f"🚀 <b>સેટઅપ:</b> Strong Morning Move + Breakout above Daily R1/R2\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>R3 Option Strategy (Option Leads, Future Follows):</b>\n"
                f"• <b>વોચલિસ્ટ કોલ:</b> <b>₹{res['otm_call_strike']} CE</b>\n"
                f"• <b>સુવર્ણ નિયમ (Golden Rule):</b> જ્યારે આ OTM CE તેના પોતાના <b>Daily R3</b> લેવલને ક્રોસ કરે ત્યારે જ બાય એન્ટ્રી કરવી!\n"
                f"• <b>સ્ટોપલોસ:</b> ઓપ્શનની 5m/15m બ્રેકઆઉટ કેન્ડલનો Low\n"
                f"• <b>ટાર્ગેટ:</b> 100% થી 200%+ (ડબલ / મલ્ટિબેગર કેપિટલ ગેઇન)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Spot Pivots:</b> P: ₹{res['pivot_p']:.1f} | R1: ₹{res['r1']:.1f} | R2: ₹{res['r2']:.1f} | R3: ₹{res['r3']:.1f}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending R3 OPTION RADAR alert for {s_name}")
            send_telegram_alert(r3_alert_text)
            state[r3_alert_key] = True
            new_alerts.append(f"{s_name}: R3 OPTION RADAR")

        # 0.1 Alert for 100% CONFIRMED BUY (R3 Option Rocket + 1H Bull Cross Confluence)
        is_r3_confirmed = bool(
            res.get('is_r3_radar') and 
            (is_sniper_buy or "STRONG BUY" in curr_sig) and
            (res['price'] >= res.get('r1', 0))
        )
        r3_confirmed_key = f"{s_name}_R3_CONFIRMED_{today_str}"
        if is_r3_confirmed and not state.get(r3_confirmed_key):
            vol_emoji = "🔥" if res['vol_ratio'] >= 1.2 else ""
            confirmed_alert_text = (
                f"🚀 <b>૧૦૦% કન્ફર્મ બાય એલર્ટ! (100% CONFIRMED BUY)</b> 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
                f"🎯 <b>સેટઅપ:</b> R3 Option Rocket + 1-Hour Bull Cross કન્ફર્મ!\n"
                f"⚡ <b>Hilega-Milega 1H:</b> Green &gt; Red (પાણી 50 ની ઉપર - ૧૦૦% ખરીદી પાકી)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔥 <b>ACTIONABLE TRADE ENTRY (તાત્કાલિક એન્ટ્રી):</b>\n"
                f"• <b>Call Option Buy (CE):</b> <b>₹{res['otm_call_strike']} CE</b> ખરીદો\n"
                f"• <b>Equity / Future Buy:</b> ₹{res['price']:.2f}\n"
                f"• <b>ચુસ્ત સ્ટોપલોસ:</b> ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
                f"• <b>Target 1 (1:1.5):</b> ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
                f"• <b>Target 2 (1:2.5):</b> ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
                f"• <b>ઓપ્શન ટાર્ગેટ:</b> ૧૦૦% થી ૨૦૦%+ (ડબલ / મલ્ટિબેગર નફો)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Spot Pivots:</b> P: ₹{res['pivot_p']:.1f} | R1: ₹{res['r1']:.1f} | R2: ₹{res['r2']:.1f} | R3: ₹{res['r3']:.1f}\n"
                f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending 100% CONFIRMED BUY alert for {s_name}")
            send_telegram_alert(confirmed_alert_text)
            state[r3_confirmed_key] = True
            new_alerts.append(f"{s_name}: 100% CONFIRMED BUY")

        # 1. Alert for FRESH SNIPER SHORT SELL setups
        if is_sniper_short and (prev_sig != curr_sig):
            alert_text = (
                f"🩸 <b>SNIPER SHORT SELL CONFIRMED!</b> 🩸\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f})\n"
                f"📉 <b>સેટઅપ:</b> Daily Avalanche + 1H Relief Bounce Rejection\n"
                f"⚡ <b>Hilega-Milega:</b> Green &lt; Red (પાણી 50 ની નીચે)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Trade Setup (Bearish Short):</b>\n"
                f"• Entry (Short): ₹{res['price']:.2f}\n"
                f"• Stop Loss: ₹{res['stop_loss']:.2f} (+{res['risk_pct']:.1f}%)\n"
                f"• Target 1 (1:1.5): ₹{res['t1']:.2f} (-{res['t1_pct']:.1f}%)\n"
                f"• Target 2 (1:2.5): ₹{res['t2']:.2f} (-{res['t2_pct']:.1f}%)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>Options Action:</b>\n"
                f"• Put Buyers: ₹{res['pe_strike']} PE બાય કરો\n"
                f"• Option Sellers: &gt; ₹{res['ce_strike']:.0f} CE સેલ કરો (સેફ OTM)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending SNIPER SHORT alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: SNIPER SHORT")
            
        # 2. Alert for FRESH SNIPER BUY setups
        elif is_sniper_buy and (prev_sig != curr_sig):
            vol_emoji = "🔥" if res['vol_ratio'] >= 1.5 else ""
            alert_text = (
                f"🎯 <b>SNIPER DIP BUY CONFIRMED!</b> 🎯\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f})\n"
                f"📈 <b>સેટઅપ:</b> Daily Rocket + 1H Pullback Reversal\n"
                f"⚡ <b>Hilega-Milega:</b> Green &gt; Red (પાણી 50 ની ઉપર)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Trade Setup (Bullish):</b>\n"
                f"• Entry (Buy): ₹{res['price']:.2f}\n"
                f"• Stop Loss: ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
                f"• Target 1 (1:1.5): ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
                f"• Target 2 (1:2.5): ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>Options Action:</b>\n"
                f"• Call Buyers: ₹{res['ce_strike']} CE બાય કરો\n"
                f"• Option Sellers: &lt; ₹{res['pe_strike']:.0f} PE સેલ કરો (સેફ OTM)\n"
                f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending SNIPER BUY alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: SNIPER BUY")
            
        # 3. Alert for General Bullish
        elif is_buy and (prev_sig != curr_sig):
            vol_emoji = "🔥" if res['vol_ratio'] >= 1.5 else ""
            alert_text = (
                f"🚨 <b>{curr_sig} ALERT!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>સ્ટોક:</b> {s_name}\n"
                f"💰 <b>ભાવ:</b> ₹{res['price']:.2f} ({res['change']:+.2f}%)\n"
                f"🎯 <b>Target 1:</b> ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
                f"🚀 <b>Target 2:</b> ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
                f"🛡️ <b>Stop Loss:</b> ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
                f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending BUY alert for {s_name}: {curr_sig}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: {curr_sig}")
            
        # 4. Alert for EXIT ONLY IF stock was previously BUY and now broke down into SELL
        elif is_sell and prev_sig and ("BUY" in prev_sig or "BULLISH" in prev_sig) and not is_sniper_short:
            alert_text = (
                f"⚠️ <b>EXIT / BREAKDOWN ALERT!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📉 <b>સ્ટોક:</b> {s_name}\n"
                f"💰 <b>ભાવ:</b> ₹{res['price']:.2f} ({res['change']:+.2f}%)\n"
                f"🚨 <b>સિગ્નલ:</b> 🔴 STRONG SELL / AVOID\n"
                f"🛑 <b>સલાહ:</b> સ્ટોકમાં મંદીનું દબાણ શરૂ થયું છે. જો તમારી પાસે સ્ટોક હોય તો એક્ઝિટ / પ્રોફિટ બુક કરો. <b>નવી ખરીદી બિલકુલ ટાળવી!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ <i>{get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')}</i> | 🤖 Patel Trading Bot"
            )
            print(f"Sending EXIT alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: EXIT")
            
        state[s_name] = curr_sig
        
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        
    return new_alerts

if __name__ == "__main__":
    force_mode = any(arg in sys.argv for arg in ["--force", "--test", "--ignore-hours"])
    print("Starting Background Auto-Scanner Service...")
    if force_mode:
        print("⚠️ Force mode enabled: Market hours check will be bypassed.")
    
    is_open, reason = is_market_open()
    status_note = "બજાર ખુલ્લું છે (09:15 - 15:30 IST)." if is_open else f"હાલ બજાર બંધ છે ({reason}). બજાર ખુલશે ત્યારે લાઈવ સ્કેન શરૂ થશે."
    
    send_telegram_alert(
        f"🟢 <b>Auto-Scanner Service Started!</b>\n"
        f"• લાઈવ માર્કેટ સ્કેન: સોમ-શુક્ર (09:15 થી 15:30 IST)\n"
        f"• <b>સ્ટેટસ:</b> {status_note}"
    )
    
    while True:
        try:
            if not force_mode and ENFORCE_MARKET_HOURS:
                is_open, reason = is_market_open()
                if not is_open:
                    print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] ⏸️ {reason}. Sleeping {SCAN_INTERVAL_SECONDS}s...")
                    time.sleep(SCAN_INTERVAL_SECONDS)
                    continue

            alerts = run_scan_cycle(force=force_mode)
            print(f"Cycle completed. {len(alerts)} alerts triggered. Sleeping {SCAN_INTERVAL_SECONDS}s...")
        except Exception as e:
            print(f"Cycle error: {e}")
        time.sleep(SCAN_INTERVAL_SECONDS)
