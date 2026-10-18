import pandas as pd
import numpy as np

# -------------------------------------------------------------
# Formatting & Trade Level Helpers
# -------------------------------------------------------------
def format_volume(vol):
    """Format numeric volume into human-friendly strings (Cr, L, K)."""
    if pd.isna(vol) or vol == 0:
        return "0"
    if vol >= 10_000_000:
        return f"{vol / 10_000_000:.2f} Cr"
    elif vol >= 100_000:
        return f"{vol / 100_000:.2f} L"
    elif vol >= 1_000:
        return f"{vol / 1_000:.1f} K"
    return f"{vol:,.0f}"

def calculate_trade_levels(entry_price, stop_loss, is_short=False):
    """Calculates Stop Loss, Risk%, Target 1 (1:1.5), Target 2 (1:2.5)."""
    entry_price = float(entry_price)
    stop_loss = float(stop_loss)
    if is_short:
        risk = stop_loss - entry_price if stop_loss > entry_price else entry_price * 0.015
        if risk <= 0 or risk > (entry_price * 0.12):
            risk = entry_price * 0.015
            stop_loss = entry_price + risk
        t1 = entry_price - (1.5 * risk)
        t2 = entry_price - (2.5 * risk)
        risk_pct = (risk / entry_price) * 100
        t1_pct = ((entry_price - t1) / entry_price) * 100
        t2_pct = ((entry_price - t2) / entry_price) * 100
    else:
        risk = entry_price - stop_loss
        if risk <= 0 or risk > (entry_price * 0.12):
            risk = entry_price * 0.015  # default 1.5% tight risk
            stop_loss = entry_price - risk
            
        t1 = entry_price + (1.5 * risk)
        t2 = entry_price + (2.5 * risk)
        risk_pct = (risk / entry_price) * 100
        t1_pct = ((t1 - entry_price) / entry_price) * 100
        t2_pct = ((t2 - entry_price) / entry_price) * 100
    
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "risk_pct": risk_pct,
        "t1": t1,
        "t1_pct": t1_pct,
        "t2": t2,
        "t2_pct": t2_pct,
        "is_short": is_short
    }

# -------------------------------------------------------------
# Core Indicator Calculations
# -------------------------------------------------------------
def calculate_hilega_milega(df, rsi_period=9, ema_period=3, wma_period=21):
    """
    Hilega Milega System:
    - RSI: 9 period Wilder smoothed
    - Green Line: 3-period EMA of RSI (Fast momentum)
    - Red Line: 21-period WMA of RSI (Slow trend)
    - Water Line: 50.0 baseline
    """
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

def calculate_adx_dmi(df, period=14):
    """
    Wilder's Directional Movement Index (DMI) and Average Directional Index (ADX):
    - +DI (14): Plus Directional Indicator (Bullish pressure)
    - -DI (14): Minus Directional Indicator (Bearish pressure)
    - ADX (14): Trend strength index (non-directional)
    """
    if len(df) < (period + 2):
        df['Plus_DI_14'] = 20.0
        df['Minus_DI_14'] = 20.0
        df['ADX_14'] = 15.0
        return df

    high = df['High']
    low = df['Low']
    prev_close = df['Close'].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    alpha = 1.0 / period
    tr_smooth = pd.Series(tr, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()

    plus_di = 100.0 * (plus_dm_smooth / tr_smooth.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm_smooth / tr_smooth.replace(0, np.nan))

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100.0 * (di_diff / di_sum.replace(0, np.nan))
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    df['Plus_DI_14'] = plus_di.fillna(20.0)
    df['Minus_DI_14'] = minus_di.fillna(20.0)
    df['ADX_14'] = adx.fillna(15.0)
    return df

def analyze_adx_dmi(df, name="Timeframe"):
    """
    Analyzes ADX and +DI/-DI status:
    - Low ADX (<= 22) + small DI difference (|plus_di - minus_di| <= 8.5) = Ideal Option Selling Sideways.
    - +DI >= 25 & ADX rising = Bullish Momentum Breakout (Risk for Call Sellers).
    - -DI >= 25 & ADX rising = Bearish Momentum Breakdown (Risk for Put Sellers).
    """
    if 'ADX_14' not in df.columns or len(df.dropna(subset=['ADX_14'])) < 2:
        return {
            "name": name,
            "adx": 15.0,
            "prev_adx": 15.0,
            "plus_di": 20.0,
            "minus_di": 20.0,
            "di_diff": 0.0,
            "is_sideways": True,
            "is_bull_breakout": False,
            "is_bear_breakdown": False,
            "status": "⚪ ટ્રેન્ડલેસ / સાઈડવેઝ (Sideways)"
        }

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    adx = float(curr.get('ADX_14', 15.0))
    prev_adx = float(prev.get('ADX_14', 15.0))
    plus_di = float(curr.get('Plus_DI_14', 20.0))
    minus_di = float(curr.get('Minus_DI_14', 20.0))
    di_diff = abs(plus_di - minus_di)

    is_sideways = (adx <= 22.0) and (di_diff <= 8.5)
    is_bull_breakout = (plus_di >= 25.0) and (plus_di > minus_di + 4.0) and (adx >= 20.0) and (adx >= prev_adx)
    is_bear_breakdown = (minus_di >= 25.0) and (minus_di > plus_di + 4.0) and (adx >= 20.0) and (adx >= prev_adx)

    if is_bull_breakout:
        status = f"🚀 બુલિશ મોમેન્ટમ બ્રેકઆઉટ (+DI: {plus_di:.1f} > 25 & ADX વધી રહ્યો છે)"
    elif is_bear_breakdown:
        status = f"🩸 બેરિશ મોમેન્ટમ બ્રેકડાઉન (-DI: {minus_di:.1f} > 25 & ADX વધી રહ્યો છે)"
    elif is_sideways:
        status = f"⚖️ શાંત સાઈડવેઝ રેન્જ (ADX: {adx:.1f} • DI તફાવત: {di_diff:.1f})"
    else:
        status = f"🟡 સામાન્ય વધ-ઘટ (ADX: {adx:.1f})"

    return {
        "name": name,
        "adx": round(adx, 1),
        "prev_adx": round(prev_adx, 1),
        "plus_di": round(plus_di, 1),
        "minus_di": round(minus_di, 1),
        "di_diff": round(di_diff, 1),
        "is_sideways": is_sideways,
        "is_bull_breakout": is_bull_breakout,
        "is_bear_breakdown": is_bear_breakdown,
        "status": status
    }

def calculate_trend_craft_ict(df, default_period=45):
    """Trend Craft ICT Band: Rolling SMA of Highs and Lows."""
    if len(df) < 10:
        return df
    
    period = default_period if len(df) >= (default_period + 5) else max(8, len(df) // 2)
    df['TC_SMA_High'] = df['High'].rolling(period).mean()
    df['TC_SMA_Low'] = df['Low'].rolling(period).mean()
    df['TC_Period'] = period
    return df

def calculate_volume_analysis(df, sma_period=20):
    """Volume Spread Analysis: Volume SMA and relative volume ratio."""
    if 'Volume' not in df.columns or len(df) < 5:
        return df
        
    actual_period = sma_period if len(df) >= sma_period else max(3, len(df) // 2)
    df['Vol_SMA20'] = df['Volume'].rolling(actual_period).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    
    if 'Open' in df.columns:
        df['Candle_Color'] = np.where(df['Close'] >= df['Open'], '#00E676', '#FF1744')
        df['Vol_Color'] = df['Candle_Color']
    else:
        df['Candle_Color'] = np.where(df['Close'] >= df['Close'].shift(1).fillna(df['Close']), '#00E676', '#FF1744')
        df['Vol_Color'] = df['Candle_Color']
        
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

def calculate_heikin_ashi(df):
    """Computes Heikin Ashi Open, High, Low, Close and Bullish/Bearish candle classification."""
    if df is None or len(df) < 2:
        return df
    ha_df = df.copy()
    ha_close = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4.0
    
    ha_open = np.zeros(len(df))
    ha_open[0] = (df['Open'].iloc[0] + df['Close'].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i-1] + ha_close.iloc[i-1]) / 2.0
        
    ha_df['HA_Close'] = ha_close
    ha_df['HA_Open'] = ha_open
    ha_df['HA_High'] = np.maximum(df['High'], np.maximum(ha_open, ha_close))
    ha_df['HA_Low'] = np.minimum(df['Low'], np.minimum(ha_open, ha_close))
    
    body = np.abs(ha_df['HA_Close'] - ha_df['HA_Open'])
    rng = np.maximum(ha_df['HA_High'] - ha_df['HA_Low'], 0.001)
    lower_shadow = np.minimum(ha_df['HA_Open'], ha_df['HA_Close']) - ha_df['HA_Low']
    upper_shadow = ha_df['HA_High'] - np.maximum(ha_df['HA_Open'], ha_df['HA_Close'])
    
    is_bull = (ha_df['HA_Close'] > ha_df['HA_Open'])
    is_bear = (ha_df['HA_Close'] < ha_df['HA_Open'])
    
    ha_df['HA_Is_Bullish'] = is_bull & (lower_shadow <= (body * 0.15))
    ha_df['HA_Is_Bearish'] = is_bear & (upper_shadow <= (body * 0.15))
    ha_df['HA_Is_Doji'] = (body / rng <= 0.35) & (upper_shadow > (rng * 0.15)) & (lower_shadow > (rng * 0.15))
    return ha_df

def calculate_donchian_channel(df, period=11):
    """Computes Donchian Channel High and Low for Trailing Stop-Loss."""
    if df is None or len(df) < 2:
        return df
    act_p = period if len(df) >= period else max(2, len(df))
    df[f'Donchian_High_{period}'] = df['High'].rolling(act_p).max()
    df[f'Donchian_Low_{period}'] = df['Low'].rolling(act_p).min()
    return df

def calculate_camarilla_levels(df_d):
    """Camarilla Pivot Points calculation for Option Selling & Straddles."""
    if df_d is None or df_d.empty or len(df_d) < 2:
        return None
    prev = df_d.iloc[-2]
    h, l, c = float(prev['High']), float(prev['Low']), float(prev['Close'])
    rng = h - l
    h4 = c + (rng * 1.1 / 2.0)
    h3 = c + (rng * 1.1 / 4.0)
    h2 = c + (rng * 1.1 / 6.0)
    h1 = c + (rng * 1.1 / 12.0)
    l1 = c - (rng * 1.1 / 12.0)
    l2 = c - (rng * 1.1 / 6.0)
    l3 = c - (rng * 1.1 / 4.0)
    l4 = c - (rng * 1.1 / 2.0)
    h5 = (h / l) * c if l > 0 else h4 * 1.01
    l5 = c - (h5 - c)
    return {
        "prev_h": h, "prev_l": l, "prev_c": c, "range": rng,
        "h5": h5, "h4": h4, "h3": h3, "h2": h2, "h1": h1,
        "l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5": l5
    }

# -------------------------------------------------------------
# Multi-Timeframe Status Evaluators
# -------------------------------------------------------------
def analyze_hm_timeframe(df, name="Timeframe"):
    if 'Red_WMA21' not in df.columns or df['Red_WMA21'].dropna().empty or len(df.dropna(subset=['Red_WMA21'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "bullish": False,
            "crossover": False, "crossover_bull": False, "crossover_bear": False, "above_water": False,
            "green": 50.0, "red": 50.0, "rsi": 50.0, "spread": 0.0,
            "prev_green": 50.0, "prev_red": 50.0,
            "green_slope": 0.0, "two_bar_green_slope": 0.0,
            "rsi_slope": 0.0, "two_bar_rsi_slope": 0.0,
            "is_vertical_rsi_up": False, "is_vertical_rsi_down": False,
            "prev_spread": 0.0
        }
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3] if len(df) >= 3 else prev
    
    c_green = curr['Green_EMA3']
    p_green = prev['Green_EMA3']
    p2_green = prev2['Green_EMA3']
    c_red = curr['Red_WMA21']
    p_red = prev['Red_WMA21']
    c_rsi = curr['RSI_9']
    p_rsi = prev['RSI_9']
    p2_rsi = prev2['RSI_9']
    
    green_slope = c_green - p_green
    two_bar_green_slope = c_green - p2_green
    rsi_slope = c_rsi - p_rsi
    two_bar_rsi_slope = c_rsi - p2_rsi

    # Vertical RSI Spikes: Fast aggressive momentum shifts threatening Option Sellers
    is_vertical_rsi_up = (c_rsi >= 60.0) and ((two_bar_rsi_slope >= 5.5) or (green_slope >= 2.5))
    is_vertical_rsi_down = (c_rsi <= 40.0) and ((two_bar_rsi_slope <= -5.5) or (green_slope <= -2.5))
    
    is_above_water = c_green >= 50.0 and c_red >= 50.0
    is_partly_above_water = c_green >= 50.0 or c_red >= 50.0
    is_green_above_red = c_green > c_red
    is_fresh_cross_bull = (p_green <= p_red) and (c_green > c_red)
    is_fresh_cross_bear = (p_green >= p_red) and (c_green < c_red)
    
    if is_fresh_cross_bull:
        status_text = "🟢 તાજો ગોલ્ડન ક્રોસઓવર (Fresh Buy Cross)"
        bullish = True
    elif is_fresh_cross_bear:
        status_text = "🔴 તાજો બેરિશ ક્રોસઓવર (Fresh Bear Cross)"
        bullish = False
    elif is_green_above_red and is_above_water:
        status_text = "🟢 સુપર તેજી (Bullish - પાણીની ઉપર)"
        bullish = True
    elif is_green_above_red and not is_above_water:
        status_text = "🟡 રિવર્સલ શરૂ (પાણીની નીચે ક્રોસ)"
        bullish = True
    elif not is_green_above_red and is_partly_above_water:
        status_text = "🟠 પ્રોફિટ બુકિંગ / પુલબેક (Pullback)"
        bullish = False
    else:
        status_text = "🔴 સંપૂર્ણ મંદી (Bearish - પાણીની નીચે)"
        bullish = False
        
    return {
        "name": name, "status": status_text, "bullish": bullish,
        "crossover": is_fresh_cross_bull, "crossover_bull": is_fresh_cross_bull,
        "crossover_bear": is_fresh_cross_bear, "above_water": is_above_water,
        "green": c_green, "red": c_red, "rsi": c_rsi, "spread": round(c_green - c_red, 2),
        "prev_green": p_green, "prev_red": p_red,
        "green_slope": green_slope, "two_bar_green_slope": two_bar_green_slope,
        "rsi_slope": round(rsi_slope, 2), "two_bar_rsi_slope": round(two_bar_rsi_slope, 2),
        "is_vertical_rsi_up": is_vertical_rsi_up, "is_vertical_rsi_down": is_vertical_rsi_down,
        "prev_spread": round(p_green - p_red, 2)
    }

def analyze_trend_craft_timeframe(df, name="Timeframe"):
    if 'TC_SMA_High' not in df.columns or len(df.dropna(subset=['TC_SMA_High'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "trend": "NEUTRAL",
            "bullish": False, "color": "gray", "close": 0.0, "tc_high": 0.0, "tc_low": 0.0, "is_pullback": False
        }
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    c = curr['Close']
    h = curr['TC_SMA_High']
    l = curr['TC_SMA_Low']
    
    if c > h:
        trend = "BULLISH"
        color = "green"
        bullish = True
        is_pullback = curr['Low'] <= (h * 1.012) and c >= h
        status_text = "🟢 ગ્રીન ચેનલની ઉપર (Bullish Trend)"
    elif c < l:
        trend = "BEARISH"
        color = "red"
        bullish = False
        is_pullback = False
        status_text = "🔴 રેડ ચેનલની નીચે (Bearish Trend)"
    else:
        if prev['Close'] > prev['TC_SMA_High']:
            trend = "PULLBACK_SUPPORT"
            color = "orange"
            bullish = True
            is_pullback = True
            status_text = "🎯 પુલબેક સપોર્ટ ટેસ્ટ (Inside Band Support)"
        else:
            trend = "CONSOLIDATION"
            color = "gray"
            bullish = False
            is_pullback = False
            status_text = "⚪ રેન્જ બાઉન્ડ / બેન્ડની અંદર (Consolidation)"
            
    return {
        "name": name, "status": status_text, "trend": trend, "bullish": bullish,
        "color": color, "close": c, "tc_high": h, "tc_low": l, "is_pullback": is_pullback
    }

def analyze_volume_timeframe(df, name="Timeframe"):
    if 'Vol_SMA20' not in df.columns or len(df.dropna(subset=['Vol_SMA20'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "curr_vol": 0, "vol_sma": 0,
            "ratio": 1.0, "is_spike": False, "is_healthy_dip": False, "verdict": "Neutral"
        }
        
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    v = curr['Volume']
    v_sma = curr['Vol_SMA20']
    ratio = curr['Vol_Ratio'] if pd.notna(curr['Vol_Ratio']) else 1.0
    price_up = curr['Close'] >= prev['Close']
    
    is_spike = ratio >= 1.5
    is_healthy_dip = (not price_up) and (ratio < 0.85)
    
    if price_up and is_spike:
        status_text = f"🔥 ભારે ઇન્સ્ટિટ્યૂશનલ ખરીદી ({ratio:.1f}x Avg Volume)"
        verdict = "High Volume Bullish"
    elif price_up and ratio >= 1.0:
        status_text = f"🟢 સરેરાશથી વધુ વૉલ્યુમ સાથે તેજી ({ratio:.1f}x)"
        verdict = "Healthy Bullish"
    elif price_up and ratio < 1.0:
        status_text = f"⚠️ લો-વૉલ્યુમ તેજી / ફેકઆઉટ જોખમ ({ratio:.1f}x Avg)"
        verdict = "Weak Volume Bullish"
    elif not price_up and is_healthy_dip:
        status_text = f"🎯 લો-વૉલ્યુમ હેલ્ધી પુલબેક ({ratio:.1f}x - કોઈ મોટો સેલર નથી)"
        verdict = "Healthy Low-Volume Dip"
    elif not price_up and is_spike:
        status_text = f"🔴 પેનિક સેલિંગ / ઇન્સ્ટિટ્યૂશનલ ડિસ્ટ્રિબ્યુશન ({ratio:.1f}x Avg)"
        verdict = "Heavy Volume Selling"
    else:
        status_text = f"🟠 સરેરાશ વૉલ્યુમ સાથે ઘટાડો ({ratio:.1f}x)"
        verdict = "Moderate Selling"
        
    return {
        "name": name, "status": status_text, "curr_vol": v, "vol_sma": v_sma,
        "ratio": ratio, "is_spike": is_spike, "is_healthy_dip": is_healthy_dip,
        "price_up": price_up, "verdict": verdict
    }

def calculate_master_confluence_vpa(m_hm, w_hm, d_hm, h1_hm, m_tc, w_tc, d_tc, h1_tc, m_vol, w_vol, d_vol, h1_vol, d_adx=None):
    """Master Multi-Timeframe Confluence & Institutional Volume spread analysis."""
    score = 0
    checks = []
    
    # 1. Monthly Mega Trend (15 pts)
    if m_hm['bullish'] and m_hm['above_water'] and m_tc['bullish']:
        score += 15
        checks.append("✅ Monthly: HM + Trend Craft બંને 100% તેજીમાં (+15)")
    elif m_hm['bullish'] or m_tc['bullish']:
        score += 10
        checks.append("🟡 Monthly: લાંબો ગાળો આંશિક તેજી (+10)")
    else:
        checks.append("❌ Monthly: મંદી / પાણીની અંદર (0)")

    # 2. Weekly Swing Trend (20 pts)
    if w_hm['bullish'] and w_hm['above_water'] and w_tc['bullish']:
        score += 20
        checks.append("✅ Weekly: HM + Trend Craft મજબૂત સ્વિંગ તેજીમાં (+20)")
    elif w_hm['bullish'] or w_tc['bullish']:
        score += 12
        checks.append("🟡 Weekly: સ્વિંગ ટ્રેન્ડ આંશિક તેજી (+12)")
    else:
        checks.append("❌ Weekly: સ્વિંગ મંદી (0)")

    # 3. Daily Structure & Support (20 pts)
    if d_hm['bullish'] and d_tc['bullish']:
        score += 20
        checks.append("✅ Daily: ડેઇલી ચેનલ અને મોમેન્ટમ બંને બુલિશ (+20)")
    elif d_tc['is_pullback'] or d_tc['trend'] == "PULLBACK_SUPPORT":
        score += 18
        checks.append("🎯 Daily: ડેઇલી બેન્ડ સપોર્ટ પાસે પુલબેક (+18)")
    elif d_hm['bullish'] or d_tc['bullish']:
        score += 12
        checks.append("🟡 Daily: ડેઇલી ટ્રેન્ડ સારો (+12)")
    else:
        checks.append("❌ Daily: ડેઇલી કરેક્શન / મંદી (0)")

    # 4. 1-Hour Sniper Trigger (20 pts)
    if h1_hm['crossover'] and (h1_tc['trend'] in ["BULLISH", "PULLBACK_SUPPORT"]):
        score += 20
        checks.append("🚀 1-Hour: તાજો સ્નાઈપર ગોલ્ડન ક્રોસ + ગ્રીન બેન્ડ સપોર્ટ! (+20)")
    elif h1_hm['bullish'] and h1_tc['bullish']:
        score += 16
        checks.append("✅ 1-Hour: મોમેન્ટમ અને પ્રાઈસ બંને તેજીમાં (+16)")
    elif h1_tc['is_pullback']:
        score += 14
        checks.append("🎯 1-Hour: 1-Hour બેન્ડ સપોર્ટ પર બાઉન્સ (+14)")
    elif h1_hm['bullish']:
        score += 10
        checks.append("🟡 1-Hour: મોમેન્ટમ તેજી તરફી (+10)")
    else:
        checks.append("❌ 1-Hour: શોર્ટ-ટર્મ કરેક્શન / મંદી (0)")

    # 5. Volume (VPA) Confirmation (25 pts)
    vol_pts = 0
    if h1_vol['price_up'] and h1_vol['is_spike']:
        vol_pts += 15
        checks.append(f"🔥 1-Hour Volume: ઇન્સ્ટિટ્યૂશનલ સ્નાઈપર વૉલ્યુમ સ્પાઇક ({h1_vol['ratio']:.1f}x Avg) (+15)")
    elif h1_vol['is_healthy_dip']:
        vol_pts += 15
        checks.append(f"🎯 1-Hour Volume: પરફેક્ટ લો-વૉલ્યુમ ડીપ ({h1_vol['ratio']:.1f}x - કોઈ સેલર નથી) (+15)")
    elif h1_vol['price_up'] and h1_vol['ratio'] >= 1.0:
        vol_pts += 10
        checks.append(f"🟢 1-Hour Volume: એવરેજથી વધુ વૉલ્યુમ (+10)")
    elif h1_vol['price_up'] and h1_vol['ratio'] < 0.7:
        checks.append(f"⚠️ 1-Hour Volume: લો-વૉલ્યુમ ફેકઆઉટ જોખમ ({h1_vol['ratio']:.1f}x) (0)")
        
    if d_vol['price_up'] and d_vol['ratio'] >= 1.0:
        vol_pts += 10
        checks.append(f"✅ Daily Volume: ડેઇલી વૉલ્યુમ સપોર્ટેડ (+10)")
    elif d_vol['is_healthy_dip']:
        vol_pts += 10
        checks.append(f"🎯 Daily Volume: ડેઇલી લો-વૉલ્યુમ પુલબેક (+10)")
        
    score += min(vol_pts, 25)
    score = min(score, 100)

    # Daily HM & TC (Macro Trend Filter)
    d_hm_bull = (d_hm['green'] > d_hm['red']) and (d_hm['green'] >= 50.0)
    d_hm_bear = (d_hm['green'] < d_hm['red']) and (d_hm['green'] <= 50.0)
    d_bull_gap = d_hm['green'] - d_hm['red']
    d_bear_gap = d_hm['red'] - d_hm['green']
    d_is_positive = d_hm_bull and (d_bull_gap >= 2.5) and d_tc['bullish']
    d_is_negative = d_hm_bear and (d_bear_gap >= 2.5) and (not d_tc['bullish'])
    
    # 1-Hour Rocket / Avalanche Trigger (Strict Confluence)
    h1_green_slope = h1_hm.get('green_slope', h1_hm['green'] - h1_hm.get('prev_green', h1_hm['green']))
    h1_two_bar_green_slope = h1_hm.get('two_bar_green_slope', h1_green_slope)
    h1_bull_gap = h1_hm['green'] - h1_hm['red']
    h1_prev_bull_gap = h1_hm.get('prev_green', h1_hm['green']) - h1_hm.get('prev_red', h1_hm['red'])
    h1_bear_gap = h1_hm['red'] - h1_hm['green']
    h1_prev_bear_gap = h1_hm.get('prev_red', h1_hm['red']) - h1_hm.get('prev_green', h1_hm['green'])
    
    h1_vol_ratio = h1_vol.get('ratio', 1.0)
    h1_vol_confirmed = h1_vol_ratio >= 1.2
    
    # Bullish Rocket Confluence
    h1_is_vertical_up = (h1_green_slope >= 1.8) or (h1_two_bar_green_slope >= 3.0)
    h1_gap_expanding_up = (h1_bull_gap >= 2.5) and (h1_bull_gap >= h1_prev_bull_gap)
    h1_above_water = (h1_hm['rsi'] >= 51.5) and (h1_hm['green'] >= 50.0)
    h1_hierarchy_bull = (h1_hm['rsi'] >= h1_hm['green'] - 1.5) and (h1_hm['green'] > h1_hm['red'])
    h1_tc_confirmed_bull = h1_tc.get('bullish', False)
    
    is_sniper_buy = (
        d_is_positive and
        h1_is_vertical_up and
        h1_hierarchy_bull and
        h1_gap_expanding_up and
        h1_above_water and
        h1_tc_confirmed_bull and
        h1_vol_confirmed
    )
    
    # Bearish Avalanche Confluence
    h1_is_vertical_down = (h1_green_slope <= -1.8) or (h1_two_bar_green_slope <= -3.0)
    h1_gap_expanding_down = (h1_bear_gap >= 2.5) and (h1_bear_gap >= h1_prev_bear_gap)
    h1_below_water = (h1_hm['rsi'] <= 48.5) and (h1_hm['green'] <= 50.0)
    h1_hierarchy_bear = (h1_hm['rsi'] <= h1_hm['green'] + 1.5) and (h1_hm['green'] < h1_hm['red'])
    h1_tc_confirmed_bear = not h1_tc.get('bullish', True)
    
    is_sniper_short = (
        d_is_negative and
        h1_is_vertical_down and
        h1_hierarchy_bear and
        h1_gap_expanding_down and
        h1_below_water and
        h1_tc_confirmed_bear and
        h1_vol_confirmed
    )
    
    is_buy_pullback = d_is_positive and not is_sniper_buy
    is_relief_bounce = d_is_negative and not is_sniper_short
    
    is_1h_confirmed_bullish = h1_is_vertical_up and h1_gap_expanding_up and h1_above_water and h1_tc_confirmed_bull
    is_inside_tc = (d_tc['close'] >= d_tc['tc_low'] * 0.985) and (d_tc['close'] <= d_tc['tc_high'] * 1.015)
    
    # Enhanced Range-Bound check using ADX & +DI/-DI
    is_adx_sideways = True
    if d_adx:
        is_adx_sideways = d_adx.get('is_sideways', False)
        
    is_range_bound = is_inside_tc and (36 <= score <= 64) and (38 <= d_hm['rsi'] <= 62) and is_adx_sideways

    if is_sniper_buy:
        verdict = "🎯 SNIPER DIP BUY (તાત્કાલિક ખરીદી સેટઅપ)"
        verdict_type = "success"
        pill_class = "pill-sniper-buy"
        explanation = (
            "Daily ચાર્ટ પર ટ્રેન્ડ સુપર પોઝિટિવ છે (Green > Red + Gap Expanding). "
            "1-Hour ચાર્ટ પર Black (RSI) અને Green (EMA) બંને Red લાઈનથી એકદમ વર્ટિકલ ઉપર છૂટી પડ્યા છે (Rocket Launch) "
            "અને સંસ્થાકીય વોલ્યુમ (>=1.2x) સાથે પાણી (50) ની ઉપર સંપૂર્ણ કન્ફર્મ થઈ ગયા છે!"
        )
        stars = "⭐⭐⭐⭐⭐"
    elif is_buy_pullback:
        verdict = "⏳ BUY ON DIPS (પુલબેક ચાલુ • 1H ક્રોસની રાહ જુઓ)"
        verdict_type = "info"
        pill_class = "pill-buy-dips"
        explanation = (
            "Daily ચાર્ટ પર મોટો ટ્રેન્ડ મજબૂત તેજીમાં છે (Positive Trend), પરંતુ 1-Hour ચાર્ટ પર હજુ સુધી સ્નાઈપર રોકેટ ટ્રિગર નથી થયું. "
            "પડતી કેન્ડલમાં ઉતાવળે ખરીદવાને બદલે 1-Hour માં Green અને Black લાઇન Red થી વર્ટિકલ છૂટી પડે અને વોલ્યુમ આવે ત્યારે જ એન્ટ્રી કરવી!"
        )
        stars = "⭐⭐⭐⭐"
    elif is_sniper_short:
        verdict = "🩸 SNIPER SHORT SELL (ઉછાળે વેચો / શોર્ટ એન્ટ્રી)"
        verdict_type = "error"
        pill_class = "pill-sniper-short"
        explanation = (
            "Daily ચાર્ટ પર ટ્રેન્ડ નેગેટિવ છે (Green < Red + Bear Gap Expanding). "
            "1-Hour ચાર્ટ પર Black (RSI) અને Green (EMA) બંને Red લાઈનથી વર્ટિકલ નીચે ડૂબી ગયા છે (Avalanche Dump) "
            "અને ભારે સેલિંગ વોલ્યુમ (>=1.2x) સાથે પાણી (50) ની નીચે સંપૂર્ણ કન્ફર્મ થઈ ગયા છે!"
        )
        stars = "⭐⭐⭐⭐⭐"
    elif is_relief_bounce:
        verdict = "⚠️ SHORT ON BOUNCE (ઉછાળો પૂરો થવાની રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-sell"
        explanation = (
            "Daily મોટા ટ્રેન્ડમાં મંદી છે, પરંતુ 1-Hour ચાર્ટ પર હજુ શોર્ટ માટે સંપૂર્ણ કન્ફર્મેશન નથી મળ્યું. "
            "તળિયે વેચવાને બદલે 1-Hour માં વર્ટિકલ ડાઉનવર્ડ સ્લોપ અને વોલ્યુમ સાથે એન્ટ્રી મળશે!"
        )
        stars = "⭐⭐⭐⭐"
    elif score >= 80 and is_1h_confirmed_bullish and h1_vol_confirmed:
        verdict = "🚀 PERFECT STRONG BUY (તાત્કાલિક એન્ટ્રી સેટઅપ)"
        verdict_type = "success"
        pill_class = "pill-strong-buy"
        explanation = (
            "Monthly, Weekly, Daily અને 1-Hour ચારેય ટાઇમફ્રેમ્સ પર સંપૂર્ણ કન્ફર્મ તેજી છે અને 1-Hour માં પણ બાય ટ્રિગર થઈ ગયું છે! "
            "મોટું ઇન્સ્ટિટ્યૂશનલ વૉલ્યુમ અને પ્રાઈસ બ્રેકઆઉટ સાથે આ સુપર હાઈ-પ્રોબેબિલિટી બાય સેટઅપ છે."
        )
        stars = "⭐⭐⭐⭐⭐"
    elif score >= 65:
        if not is_1h_confirmed_bullish or h1_vol['is_healthy_dip'] or d_tc['is_pullback']:
            verdict = "⏳ BUY ON DIPS (પુલબેક ચાલુ • 1H ક્રોસની રાહ જુઓ)"
            verdict_type = "info"
            pill_class = "pill-buy-dips"
            explanation = (
                "Monthly, Weekly અને Daily મોટા ટ્રેન્ડ ખૂબ મજબૂત છે, પરંતુ 1-Hour ચાર્ટ પર હાલમાં કરેક્શન/પુલબેક (Dip) ચાલે છે. "
                "પડતી કેન્ડલમાં ખરીદવાને બદલે 1-Hour માં ગ્રીન લાઇન રેડ લાઇનને ક્રોસ કરીને ઉપર વળે ત્યારે સૌથી ઓછા રિસ્કે ઉત્તમ એન્ટ્રી મળશે!"
            )
            stars = "⭐⭐⭐⭐"
        else:
            verdict = "🟢 MODERATE BULLISH (સ્વિંગ બાય સેટઅપ)"
            verdict_type = "success"
            pill_class = "pill-bullish"
            explanation = "મોટાભાગના ટાઇમફ્રેમ્સ તેજીમાં છે. સ્ટોપ-લોસ સાથે પોઝિશન રાખી શકાય છે."
            stars = "⭐⭐⭐"
    elif is_range_bound:
        adx_desc = f" (ADX: {d_adx['adx']:.1f} • +DI: {d_adx['plus_di']:.1f} / -DI: {d_adx['minus_di']:.1f})" if d_adx else ""
        verdict = "⚖️ RANGE-BOUND / OPTION SELLING (ઓપ્શન સેલિંગ)"
        verdict_type = "info"
        pill_class = "pill-option-sell"
        explanation = (
            f"સ્ટોક Daily Trend Craft ચેનલમાં ₹{d_tc['tc_low']:.1f} થી ₹{d_tc['tc_high']:.1f} વચ્ચે સજ્જડ રેન્જ-બાઉન્ડ કન્સોલિડેટ થાય છે{adx_desc}. "
            f"ડાયરેક્શનલ મોમેન્ટમ નહિવત હોવાથી બંને બાજુ OTM Call (>{d_tc['tc_high']:.1f}) અને OTM Put (<{d_tc['tc_low']:.1f}) વેચીને થીટા ડીકે (Theta Decay) "
            f"કમાવા માટે આ આદર્શ સેટઅપ છે (Short Strangle / Iron Condor)."
        )
        stars = "⭐⭐⭐"
    elif is_relief_bounce and score <= 45:
        verdict = "⚠️ SHORT ON BOUNCE (ઉછાળો પૂરો થવાની રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-sell"
        explanation = (
            "Daily મોટા ટ્રેન્ડમાં ભારે મંદી છે, પરંતુ 1-Hour ચાર્ટ પર હાલમાં ટેમ્પરરી ઉછાળો (Relief Bounce) ચાલે છે. "
            "તળિયે વેચવાને બદલે 1-Hour માં Green લાઇન Red લાઇન નીચે ક્રોસ થાય (Bear Cross) ત્યારે શ્રેષ્ઠ સ્નાઈપર શોર્ટ એન્ટ્રી મળશે!"
        )
        stars = "⭐⭐⭐⭐"
    elif score >= 40:
        verdict = "⏳ WAIT FOR CONFIRMATION (રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-neutral"
        explanation = "સિગ્નલો મિશ્ર છે અથવા વૉલ્યુમ સપોર્ટ નથી. 1-Hour અથવા Daily માં વૉલ્યુમ સાથે સ્પષ્ટ ક્રોસઓવર થાય ત્યાં સુધી રાહ જુઓ."
        stars = "⭐⭐"
    else:
        verdict = "🔴 STRONG AVOID / BEARISH (સંપૂર્ણ મંદી - ખરીદી ટાળો)"
        verdict_type = "error"
        pill_class = "pill-sell"
        explanation = "સ્ટોક તમામ ટાઈમફ્રેમ્સમાં મંદીમાં છે અને વૉલ્યુમ સાથે સેલિંગ પ્રેશર દેખાય છે. અત્યારે આ સ્ટોકમાં ખરીદી કરવી જોખમી છે."
        stars = "⭐"

    stoploss_1h = h1_tc['tc_low'] if h1_tc['tc_low'] > 0 else d_tc['tc_low']
    stoploss_1h_short = h1_tc['tc_high'] if h1_tc['tc_high'] > 0 else d_tc['tc_high']

    return {
        "score": score,
        "stars": stars,
        "verdict": verdict,
        "verdict_type": verdict_type,
        "pill_class": pill_class,
        "explanation": explanation,
        "checks": checks,
        "stoploss_1h": stoploss_1h,
        "stoploss_1h_short": stoploss_1h_short,
        "stoploss_daily": d_tc['tc_low'],
        "stoploss_daily_short": d_tc['tc_high'],
        "is_1h_confirmed": is_1h_confirmed_bullish,
        "is_sniper_buy": is_sniper_buy,
        "is_buy_pullback": is_buy_pullback,
        "is_sniper_short": is_sniper_short,
        "is_relief_bounce": is_relief_bounce,
        "d_bull_gap": d_bull_gap,
        "d_bear_gap": d_bear_gap
    }
