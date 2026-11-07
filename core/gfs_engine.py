"""
GFS Confluence Engine (Grandfather, Father, Son) & RSI Divergence Module
Integrated from GFS Bot into Stock Search Institutional Terminal.

Core Philosophy:
- Grandfather (Monthly): RSI >= 60 (Macro Bullish Trend / Institutional Holding)
- Father (Weekly): RSI >= 60 (Structural Bullish Trend / Multi-Week Momentum)
- Son (Daily / Intraday): RSI 37-49 (Deep Pullback / Dip Buy Zone into Dynamic Support)
- Confluence Multipliers:
  1. Bollinger Bands Middle/Lower Band Proximity (<= 1.5%)
  2. Candlestick Reversal Formations (Hammer 🔨, Doji ➕)
  3. Scipy-powered Mathematical RSI Divergence (Bullish / Bearish)
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from typing import Dict, Any, Tuple, Optional

# -------------------------------------------------------------
# 1. Bollinger Bands Calculation
# -------------------------------------------------------------
def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """
    Calculates Middle Band (SMA 20), Upper Band, and Lower Band.
    """
    df = df.copy()
    if len(df) < period:
        df['BBM'] = df['Close']
        df['BBU'] = df['Close'] * 1.05
        df['BBL'] = df['Close'] * 0.95
        return df

    sma = df['Close'].rolling(window=period).mean()
    rolling_std = df['Close'].rolling(window=period).std()
    df['BBM'] = sma
    df['BBU'] = sma + (std * rolling_std)
    df['BBL'] = sma - (std * rolling_std)
    return df

# -------------------------------------------------------------
# 2. Candlestick Reversal Pattern Detection
# -------------------------------------------------------------
def detect_candlestick_patterns(df: pd.DataFrame, direction: str = "Bullish") -> str:
    """
    Analyzes the latest completed candle row to detect Hammer, Doji, or Shooting Star.
    """
    if df.empty or len(df) < 1:
        return "RED CANDLE 🔴" if direction == "Bullish" else "GREEN CANDLE 🟢"

    o = float(df['Open'].iloc[-1])
    h = float(df['High'].iloc[-1])
    l = float(df['Low'].iloc[-1])
    c = float(df['Close'].iloc[-1])

    body = abs(c - o)
    candle_range = h - l if (h - l) > 0 else 0.0001
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    is_doji = body <= (candle_range * 0.10)

    if direction == "Bullish":
        is_hammer = (lower_shadow >= (2.0 * body)) and (body > 0) and (upper_shadow <= (body * 0.5))
        if is_hammer:
            return "HAMMER 🔨"
        elif is_doji:
            return "DOJI ➕"
        elif c >= o:
            return "STANDARD GREEN 🟢"
        else:
            return "RED CANDLE 🔴"
    else:
        is_shooting_star = (upper_shadow >= (2.0 * body)) and (body > 0) and (lower_shadow <= (body * 0.5))
        if is_shooting_star:
            return "SHOOTING STAR ☄️"
        elif is_doji:
            return "DOJI ➕"
        elif c <= o:
            return "STANDARD RED 🔴"
        else:
            return "GREEN CANDLE 🟢"

# -------------------------------------------------------------
# 3. Scipy-Powered RSI Divergence Engine
# -------------------------------------------------------------
def check_bullish_divergence(df: pd.DataFrame, lookback: int = 30) -> Tuple[str, Optional[int], Optional[float]]:
    """
    Scans historical Close and RSI arrays to detect a Regular Bullish Divergence
    (Price makes lower low, RSI makes higher low while RSI <= 48).
    """
    if len(df) < lookback:
        return "NO", None, None

    rsi_col = 'RSI_9' if 'RSI_9' in df.columns else ('RSI_14' if 'RSI_14' in df.columns else 'RSI_Daily')
    if rsi_col not in df.columns:
        return "NO", None, None

    price_array = df['Close'].values
    rsi_array = df[rsi_col].values

    # Find local minima
    local_minima_indices = argrelextrema(price_array, np.less, order=3)[0]
    valid_mins = [idx for idx in local_minima_indices if idx >= (len(df) - lookback)]

    if len(valid_mins) < 2:
        return "NO", None, None

    idx1 = valid_mins[-2]
    idx2 = valid_mins[-1]

    if idx2 <= idx1 or (idx2 - idx1) < 4:
        return "NO", None, None

    price_low1 = price_array[idx1]
    price_low2 = price_array[idx2]
    rsi_low1 = rsi_array[idx1]
    rsi_low2 = rsi_array[idx2]

    # Price Lower Low + RSI Higher Low
    if price_low2 < price_low1 and rsi_low2 > rsi_low1:
        if rsi_low2 <= 50.0:
            bar_distance = int(idx2 - idx1)
            return "BULLISH_DIVERGENCE 💥", bar_distance, round(float(rsi_low2), 2)

    return "NO", None, None

def check_bearish_divergence(df: pd.DataFrame, lookback: int = 30) -> Tuple[str, Optional[int], Optional[float]]:
    """
    Scans historical Close and RSI arrays to detect a Regular Bearish Divergence
    (Price makes higher high, RSI makes lower high while RSI >= 52).
    """
    if len(df) < lookback:
        return "NO", None, None

    rsi_col = 'RSI_9' if 'RSI_9' in df.columns else ('RSI_14' if 'RSI_14' in df.columns else 'RSI_Daily')
    if rsi_col not in df.columns:
        return "NO", None, None

    price_array = df['Close'].values
    rsi_array = df[rsi_col].values

    # Find local maxima
    local_maxima_indices = argrelextrema(price_array, np.greater, order=3)[0]
    valid_maxs = [idx for idx in local_maxima_indices if idx >= (len(df) - lookback)]

    if len(valid_maxs) < 2:
        return "NO", None, None

    idx1 = valid_maxs[-2]
    idx2 = valid_maxs[-1]

    if idx2 <= idx1 or (idx2 - idx1) < 4:
        return "NO", None, None

    price_high1 = price_array[idx1]
    price_high2 = price_array[idx2]
    rsi_high1 = rsi_array[idx1]
    rsi_high2 = rsi_array[idx2]

    # Price Higher High + RSI Lower High
    if price_high2 > price_high1 and rsi_high2 < rsi_high1:
        if rsi_high2 >= 50.0:
            bar_distance = int(idx2 - idx1)
            return "BEARISH_DIVERGENCE 💥", bar_distance, round(float(rsi_high2), 2)

    return "NO", None, None

# -------------------------------------------------------------
# 4. Master GFS Confluence Evaluator
# -------------------------------------------------------------
def evaluate_gfs_confluence(
    df_m: pd.DataFrame,
    df_w: pd.DataFrame,
    df_d: pd.DataFrame,
    current_price: float
) -> Dict[str, Any]:
    """
    Combines Monthly, Weekly, and Daily RSI with Bollinger Bands and Candlestick Analysis.
    Returns structured GFS confluence scorecard.
    """
    # 1. Monthly & Weekly RSIs (Grandfather & Father)
    rsi_m = float(df_m['RSI_9'].iloc[-1]) if ('RSI_9' in df_m.columns and len(df_m) > 0) else 50.0
    rsi_w = float(df_w['RSI_9'].iloc[-1]) if ('RSI_9' in df_w.columns and len(df_w) > 0) else 50.0
    rsi_d = float(df_d['RSI_9'].iloc[-1]) if ('RSI_9' in df_d.columns and len(df_d) > 0) else 50.0

    # 2. Bollinger Bands on Daily Chart
    df_d_bb = calculate_bollinger_bands(df_d, period=20, std=2.0)
    bbm = float(df_d_bb['BBM'].iloc[-1]) if 'BBM' in df_d_bb.columns else current_price
    bbl = float(df_d_bb['BBL'].iloc[-1]) if 'BBL' in df_d_bb.columns else current_price * 0.95
    bbu = float(df_d_bb['BBU'].iloc[-1]) if 'BBU' in df_d_bb.columns else current_price * 1.05

    near_bbm = abs(current_price - bbm) / bbm <= 0.020  # Within 2.0% of Middle Band (20 SMA)
    near_bbl = abs(current_price - bbl) / bbl <= 0.020  # Within 2.0% of Lower Band
    bb_support_active = (near_bbm or near_bbl or current_price <= bbl)

    # 3. Candlestick Pattern Detection
    candle_pattern = detect_candlestick_patterns(df_d, direction="Bullish")
    candle_bear_pattern = detect_candlestick_patterns(df_d, direction="Bearish")

    # 4. Scipy RSI Divergences
    bull_div_status, bull_div_bars, bull_div_rsi = check_bullish_divergence(df_d, lookback=35)
    bear_div_status, bear_div_bars, bear_div_rsi = check_bearish_divergence(df_d, lookback=35)
    has_bull_div = (bull_div_status != "NO")
    has_bear_div = (bear_div_status != "NO")

    # 5. Core GFS Multi-Timeframe Alignment
    is_grandfather_bull = (rsi_m >= 58.0)
    is_father_bull = (rsi_w >= 58.0)
    is_son_in_dip = (36.0 <= rsi_d <= 49.5)

    gfs_action = "⏳ CONSOLIDATION"
    gfs_score = 0
    gfs_badge = "⚪ NEUTRAL"

    if is_grandfather_bull and is_father_bull:
        gfs_score += 50
        if is_son_in_dip:
            gfs_score += 25
            if bb_support_active and (candle_pattern in ["HAMMER 🔨", "DOJI ➕"] or has_bull_div):
                gfs_action = "💥 HIGH-CONFIDENCE GFS ENTRY"
                gfs_score += 25
                gfs_badge = "💥 GFS 3-TF BUY"
            elif candle_pattern in ["HAMMER 🔨", "DOJI ➕", "STANDARD GREEN 🟢"]:
                gfs_action = "⚡ ACTIVE GFS DIP INTERSECTION"
                gfs_score += 15
                gfs_badge = "⚡ GFS DIP BUY"
            else:
                gfs_action = "⏳ GFS DIP (Waiting for Trigger)"
                gfs_score += 10
                gfs_badge = "⏳ GFS PULLBACK"
        elif rsi_d >= 60.0:
            gfs_action = "🚀 GFS MOMENTUM CONTINUATION"
            gfs_score += 35
            gfs_badge = "🚀 GFS TRENDING"
        else:
            gfs_action = "⏳ GFS WATCHLIST (Waiting for Son Dip)"
            gfs_score += 15
            gfs_badge = "👀 GFS WATCH"

    return {
        "rsi_m": round(rsi_m, 1),
        "rsi_w": round(rsi_w, 1),
        "rsi_d": round(rsi_d, 1),
        "is_grandfather_bull": is_grandfather_bull,
        "is_father_bull": is_father_bull,
        "is_son_in_dip": is_son_in_dip,
        "bb_middle": round(bbm, 2),
        "bb_lower": round(bbl, 2),
        "bb_upper": round(bbu, 2),
        "bb_support_active": bb_support_active,
        "candle_pattern": candle_pattern,
        "candle_bear_pattern": candle_bear_pattern,
        "has_bull_div": has_bull_div,
        "bull_div_bars": bull_div_bars,
        "bull_div_rsi": bull_div_rsi,
        "has_bear_div": has_bear_div,
        "bear_div_bars": bear_div_bars,
        "bear_div_rsi": bear_div_rsi,
        "gfs_score": min(100, gfs_score),
        "gfs_action": gfs_action,
        "gfs_badge": gfs_badge,
        "is_gfs_high_confidence": bool("HIGH-CONFIDENCE" in gfs_action)
    }
