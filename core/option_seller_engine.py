"""
Range-Bound Option Seller & Defense Engine for Patel Trading Bot / Confluence Pro
Institutional 4-Layer Fortress for Selling Short Strangles & Iron Condors:

Layer 1: Dead Consolidation Mega-Cap Scanner:
  - Daily ADX(14) < 20
  - 20-Day Range Span <= 8.0%
  - 50 EMA Equilibrium Magnet (|Close - 50 EMA| / 50 EMA <= 2.0%)
  - Daily RSI in [42, 58] and Weekly/Monthly RSI < 58
  - Mega-Cap / F&O Bluechip Liquidity Priority

Layer 2: Earnings Blackout Shield:
  - Automatically verifies upcoming quarterly earnings dates
  - Strictly blocks option selling within 7-10 days of results

Layer 3: Hybrid Outer-Strike Selector (Safest of Both Worlds):
  - CE Strike = max(TC High, BB Upper Band (2σ), CMP * 1.03)
  - PE Strike = min(TC Low, BB Lower Band (2σ), CMP * 0.97)
  - Automatically identifies ₹1 to ₹2 OTM Protective Wings (Iron Condor Conversion)

Layer 4: 30-Minute Real-Time Early Warning Defense System:
  - Level 1: Yellow Alert (ADX > 20 rising, RSI drifting) -> Early Alert
  - Level 2: Orange Alert (+DI > 25, Vol > 1.5x, CMP within 1.5% of strike) -> Early Defense Exit (Exit at ~25-30% loss, never wait for 100%!)
  - Level 3: Red Emergency Alert (Strike breach or 100% SL hit)
  - 3:10 PM Overnight Health-Check Alert (Recommends ₹1-₹2 wings before carrying overnight)
"""

import os
import sys
import math
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

# Ensure parent directory is in path
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from .config import get_ist_now
    from .earnings_filter import check_earnings_blackout
    from .option_r3_engine import get_accurate_strike_step, get_current_monthly_expiry
except ImportError:
    from core.config import get_ist_now
    from core.earnings_filter import check_earnings_blackout
    from core.option_r3_engine import get_accurate_strike_step, get_current_monthly_expiry

# -------------------------------------------------------------
# Core Indicator Calculations for Option Selling
# -------------------------------------------------------------
def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Computes Bollinger Bands:
    - Middle Band: 20 SMA of Close
    - Upper Band: Middle + (std_dev * standard deviation)
    - Lower Band: Middle - (std_dev * standard deviation)
    """
    if df is None or len(df) < period:
        df['BB_Mid'] = df['Close'] if 'Close' in df.columns else 0.0
        df['BB_Upper'] = df['BB_Mid'] * 1.05
        df['BB_Lower'] = df['BB_Mid'] * 0.95
        return df

    sma = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    df['BB_Mid'] = sma
    df['BB_Upper'] = sma + (std_dev * std)
    df['BB_Lower'] = sma - (std_dev * std)
    return df

def calculate_50_ema(df: pd.DataFrame, span: int = 50) -> pd.DataFrame:
    """Computes 50 Exponential Moving Average (Institutional Mean Price)."""
    if df is None or len(df) < 5:
        return df
    act_span = span if len(df) >= span else max(5, len(df))
    df['EMA_50'] = df['Close'].ewm(span=act_span, adjust=False).mean()
    return df

# -------------------------------------------------------------
# Layer 1: Dead Consolidation Mega-Cap Rules Checker
# -------------------------------------------------------------
def check_dead_consolidation_rules(
    df_d: pd.DataFrame,
    df_w: Optional[pd.DataFrame] = None,
    df_m: Optional[pd.DataFrame] = None,
    adx_threshold: float = 20.0,
    range_span_threshold: float = 8.0,
    ema_diff_threshold: float = 2.0
) -> Dict[str, Any]:
    """
    Validates user's institutional scanner rules:
    1. Daily ADX(14) < 20
    2. 20-Day Range Span <= 8.0%
    3. 50 EMA Equilibrium: |Close - 50 EMA| / 50 EMA <= 2.0%
    4. Daily RSI in [42, 58]
    5. Weekly RSI < 58 & Monthly RSI < 58
    """
    if df_d is None or len(df_d) < 20:
        return {"passes_all": False, "score": 0, "failed_reasons": ["Insufficient Daily Data"]}

    curr_p = float(df_d['Close'].iloc[-1])

    # 1. 20-Day Range Span <= 8.0%
    h20 = float(df_d['High'].tail(20).max())
    l20 = float(df_d['Low'].tail(20).min())
    span_20d = round(((h20 - l20) / curr_p) * 100, 2)
    pass_span = span_20d <= range_span_threshold

    # 2. 50 EMA Equilibrium (|Close - 50 EMA| <= 2%)
    df_d = calculate_50_ema(df_d, 50)
    ema50 = float(df_d['EMA_50'].iloc[-1]) if 'EMA_50' in df_d.columns else curr_p
    ema_diff_pct = round(abs(curr_p - ema50) / ema50 * 100, 2)
    pass_ema50 = ema_diff_pct <= ema_diff_threshold

    # 3. Daily ADX < 20 & Small DI spread
    adx_val = float(df_d['ADX_14'].iloc[-1]) if 'ADX_14' in df_d.columns else 18.0
    plus_di = float(df_d['Plus_DI_14'].iloc[-1]) if 'Plus_DI_14' in df_d.columns else 20.0
    minus_di = float(df_d['Minus_DI_14'].iloc[-1]) if 'Minus_DI_14' in df_d.columns else 20.0
    di_diff = round(abs(plus_di - minus_di), 2)
    pass_adx = (adx_val <= adx_threshold) and (di_diff <= 8.5)

    # 4. Daily RSI [42, 58]
    d_rsi = float(df_d['RSI_9'].iloc[-1]) if 'RSI_9' in df_d.columns else 50.0
    pass_d_rsi = (42.0 <= d_rsi <= 58.0)

    # 5. Weekly & Monthly RSI < 58
    w_rsi = float(df_w['RSI_9'].iloc[-1]) if df_w is not None and 'RSI_9' in df_w.columns and len(df_w) > 0 else 50.0
    m_rsi = float(df_m['RSI_9'].iloc[-1]) if df_m is not None and 'RSI_9' in df_m.columns and len(df_m) > 0 else 50.0
    pass_macro_rsi = (w_rsi <= 58.0) and (m_rsi <= 58.0)

    failed = []
    checks = []
    
    if pass_adx:
        checks.append(f"✅ ADX(14): {adx_val:.1f} < {adx_threshold} (સંપૂર્ણ ટ્રેન્ડલેસ)")
    else:
        failed.append(f"ADX {adx_val:.1f} >= {adx_threshold} (ટ્રેન્ડિંગ મોમેન્ટમ ચાલુ)")

    if pass_span:
        checks.append(f"✅ 20-Day Range Span: {span_20d:.1f}% <= {range_span_threshold}% (ટાઈટ બોક્સ)")
    else:
        failed.append(f"20-Day Range {span_20d:.1f}% > {range_span_threshold}% (રેન્જ પહોળી છે)")

    if pass_ema50:
        checks.append(f"✅ 50 EMA Magnet: ભાવ EMA50 થી માત્ર {ema_diff_pct:.1f}% દૂર છે (Equilibrium)")
    else:
        failed.append(f"50 EMA થી વિચલન {ema_diff_pct:.1f}% > {ema_diff_threshold}%")

    if pass_d_rsi:
        checks.append(f"✅ Daily RSI: {d_rsi:.1f} [42-58] (શાંત ન્યુટ્રલ)")
    else:
        failed.append(f"Daily RSI {d_rsi:.1f} ન્યુટ્રલ ઝોન બહાર છે")

    if pass_macro_rsi:
        checks.append(f"✅ Weekly RSI ({w_rsi:.1f}) & Monthly RSI ({m_rsi:.1f}) <= 58")
    else:
        failed.append(f"Weekly/Monthly RSI > 58 (મોટા ચાર્ટ પર અનકંટ્રોલ્ડ તેજી)")

    passes_all = pass_adx and pass_span and pass_ema50 and pass_d_rsi and pass_macro_rsi

    return {
        "passes_all": passes_all,
        "span_20d": span_20d,
        "ema50": ema50,
        "ema_diff_pct": ema_diff_pct,
        "adx": adx_val,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "di_diff": di_diff,
        "daily_rsi": d_rsi,
        "weekly_rsi": w_rsi,
        "monthly_rsi": m_rsi,
        "checks": checks,
        "failed_reasons": failed
    }

# -------------------------------------------------------------
# Layer 3: Hybrid Outer-Strike Selector (TC Band + Bollinger Bands)
# -------------------------------------------------------------
def calculate_hybrid_option_selling_strikes(
    symbol: str,
    spot_price: float,
    df_d: pd.DataFrame
) -> Dict[str, Any]:
    """
    Computes the safest possible strikes for Short Strangle / Iron Condor by selecting
    the OUTER-MOST (furthest away) barrier between Trend Craft High/Low and Bollinger Bands (2σ).
    CE Strike = max(TC High, BB Upper, Spot * 1.03)
    PE Strike = min(TC Low, BB Lower, Spot * 0.97)
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    step = get_accurate_strike_step(clean_sym, spot_price)

    # 1. Trend Craft Levels
    tc_high = float(df_d['TC_SMA_High'].iloc[-1]) if 'TC_SMA_High' in df_d.columns and pd.notna(df_d['TC_SMA_High'].iloc[-1]) else spot_price * 1.025
    tc_low = float(df_d['TC_SMA_Low'].iloc[-1]) if 'TC_SMA_Low' in df_d.columns and pd.notna(df_d['TC_SMA_Low'].iloc[-1]) else spot_price * 0.975

    # 2. Bollinger Bands Levels (20, 2σ)
    df_d = calculate_bollinger_bands(df_d, period=20, std_dev=2.0)
    bb_upper = float(df_d['BB_Upper'].iloc[-1]) if 'BB_Upper' in df_d.columns and pd.notna(df_d['BB_Upper'].iloc[-1]) else spot_price * 1.03
    bb_lower = float(df_d['BB_Lower'].iloc[-1]) if 'BB_Lower' in df_d.columns and pd.notna(df_d['BB_Lower'].iloc[-1]) else spot_price * 0.97

    # 3. Hybrid Outer Strike Calculation
    # Minimum 3% buffer from spot price to ensure safety
    min_ce_buffer = spot_price * 1.03
    max_pe_buffer = spot_price * 0.97

    ideal_ce_barrier = max(tc_high, bb_upper, min_ce_buffer)
    ideal_pe_barrier = min(tc_low, bb_lower, max_pe_buffer)

    # Round to exchange strike step
    ce_sell_strike = int(math.ceil(ideal_ce_barrier / step) * step)
    pe_sell_strike = int(math.floor(ideal_pe_barrier / step) * step)

    if ce_sell_strike <= spot_price:
        ce_sell_strike += int(step)
    if pe_sell_strike >= spot_price:
        pe_sell_strike -= int(step)

    # 4. Overnight Protective Wings (Iron Condor Conversion: ₹1 - ₹2 OTM Wings)
    # Typically 2-3 strike steps further out
    wing_distance_steps = 2 if spot_price > 1000 else 3
    wing_ce_strike = ce_sell_strike + (int(step) * wing_distance_steps)
    wing_pe_strike = pe_sell_strike - (int(step) * wing_distance_steps)

    expiry_info = get_current_monthly_expiry()

    # Formatted Contract Names
    ce_sell_contract = f"{clean_sym} {expiry_info['label']} {ce_sell_strike} CE"
    pe_sell_contract = f"{clean_sym} {expiry_info['label']} {pe_sell_strike} PE"
    wing_ce_contract = f"{clean_sym} {expiry_info['label']} {wing_ce_strike} CE"
    wing_pe_contract = f"{clean_sym} {expiry_info['label']} {wing_pe_strike} PE"

    ce_distance_pct = round(((ce_sell_strike - spot_price) / spot_price) * 100, 2)
    pe_distance_pct = round(((spot_price - pe_sell_strike) / spot_price) * 100, 2)

    return {
        "symbol": clean_sym,
        "spot_price": spot_price,
        "step": step,
        "tc_high": round(tc_high, 2),
        "tc_low": round(tc_low, 2),
        "bb_upper": round(bb_upper, 2),
        "bb_lower": round(bb_lower, 2),
        "ce_sell_strike": ce_sell_strike,
        "ce_sell_contract": ce_sell_contract,
        "ce_distance_pct": ce_distance_pct,
        "pe_sell_strike": pe_sell_strike,
        "pe_sell_contract": pe_sell_contract,
        "pe_distance_pct": pe_distance_pct,
        "wing_ce_strike": wing_ce_strike,
        "wing_ce_contract": wing_ce_contract,
        "wing_pe_strike": wing_pe_strike,
        "wing_pe_contract": wing_pe_contract,
        "expiry_info": expiry_info
    }

# -------------------------------------------------------------
# Layer 4: 30-Minute Real-Time Defense Monitor (3-Level Alarm)
# -------------------------------------------------------------
def monitor_option_seller_defense(
    symbol: str,
    spot_price: float,
    ce_strike: float,
    pe_strike: float,
    df_30m: pd.DataFrame,
    entry_premium: float = 10.0
) -> Dict[str, Any]:
    """
    30-Minute Real-Time Watchdog for Option Sellers:
    - Yellow Alert (Caution): ADX > 20, RSI > 55 or < 45
    - Orange Alert (Early Defense Exit): +DI > 25, Vol > 1.5x, CMP within 1.5% of strike
    - Red Emergency Alert: Strike Breach or 100% SL
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    if df_30m is None or len(df_30m) < 5:
        return {"alert_level": "GREEN", "message": "ડેટા અપૂરતો છે"}

    curr = df_30m.iloc[-1]
    prev = df_30m.iloc[-2]
    prev2 = df_30m.iloc[-3] if len(df_30m) >= 3 else prev

    rsi = float(curr.get('RSI_9', 50.0))
    rsi_p2 = float(prev2.get('RSI_9', rsi))
    rsi_slope = rsi - rsi_p2

    adx = float(curr.get('ADX_14', 15.0))
    prev_adx = float(prev.get('ADX_14', 15.0))
    adx_rising = (adx > 20.0) and (adx >= prev_adx)

    plus_di = float(curr.get('Plus_DI_14', 20.0))
    minus_di = float(curr.get('Minus_DI_14', 20.0))

    vol_ratio = float(curr.get('Vol_Ratio', 1.0)) if pd.notna(curr.get('Vol_Ratio')) else 1.0
    vol_spike = (vol_ratio >= 1.5)

    dist_to_ce_pct = ((ce_strike - spot_price) / spot_price) * 100 if ce_strike > 0 else 999.0
    dist_to_pe_pct = ((spot_price - pe_strike) / spot_price) * 100 if pe_strike > 0 else 999.0

    # 1. RED ALERT: Strike Breach
    if spot_price >= ce_strike:
        return {
            "alert_level": "RED",
            "threat_side": "CALL",
            "alert_title": "🚨 RED ALERT: CALL STRIKE BREACHED!",
            "action": "IMMEDIATE_EXIT",
            "message": (
                f"ભાવ (₹{spot_price:.2f}) તમારી Call Strike (₹{ce_strike:.1f}) ને પાર કરી ગયો છે! "
                f"મોટો અનલિમિટેડ લોસ અટકાવવા કૉલ લેગમાંથી તાત્કાલિક 100% EXIT કરો!"
            )
        }
    elif spot_price <= pe_strike:
        return {
            "alert_level": "RED",
            "threat_side": "PUT",
            "alert_title": "🚨 RED ALERT: PUT STRIKE BREACHED!",
            "action": "IMMEDIATE_EXIT",
            "message": (
                f"ભાવ (₹{spot_price:.2f}) તમારી Put Strike (₹{pe_strike:.1f}) ની નીચે ઉતરી ગયો છે! "
                f"મોટો અનલિમિટેડ લોસ અટકાવવા પુટ લેગમાંથી તાત્કાલિક 100% EXIT કરો!"
            )
        }

    # 2. ORANGE ALERT: Early Defense Exit (Exit at ~25-30% loss, don't wait for 100% SL!)
    call_defense_threat = (
        (dist_to_ce_pct <= 1.5) and
        ((plus_di >= 25.0 and adx_rising) or (vol_spike and rsi >= 58.0))
    )
    put_defense_threat = (
        (dist_to_pe_pct <= 1.5) and
        ((minus_di >= 25.0 and adx_rising) or (vol_spike and rsi <= 42.0))
    )

    if call_defense_threat:
        return {
            "alert_level": "ORANGE",
            "threat_side": "CALL",
            "alert_title": "⚠️ ORANGE ALERT: EARLY DEFENSE EXIT (CALL THREAT)",
            "action": "EARLY_EXIT_OR_HEDGE",
            "message": (
                f"સાવચેત! {clean_sym} માં સંસ્થાકીય તેજી શરૂ થઈ છે (+DI: {plus_di:.1f} > 25, Vol: {vol_ratio:.1f}x). "
                f"ભાવ Call Strike થી માત્ર {dist_to_ce_pct:.1f}% દૂર છે. "
                f"પૂરો ૧૦૦% સ્ટોપલોસ હિટ થવાની રાહ જોવાને બદલે ૨૫%-૩૦% ના નાના નુકસાને Call માંથી હમણાં જ SAFE EXIT કરો!"
            )
        }
    elif put_defense_threat:
        return {
            "alert_level": "ORANGE",
            "threat_side": "PUT",
            "alert_title": "⚠️ ORANGE ALERT: EARLY DEFENSE EXIT (PUT THREAT)",
            "action": "EARLY_EXIT_OR_HEDGE",
            "message": (
                f"સાવચેત! {clean_sym} માં સંસ્થાકીય મંદી તૂટી પડી છે (-DI: {minus_di:.1f} > 25, Vol: {vol_ratio:.1f}x). "
                f"ભાવ Put Strike થી માત્ર {dist_to_pe_pct:.1f}% દૂર છે. "
                f"પૂરો ૧૦૦% સ્ટોપલોસ હિટ થવાની રાહ જોવાને બદલે ૨૫%-૩૦% ના નાના નુકસાને Put માંથી હમણાં જ SAFE EXIT કરો!"
            )
        }

    # 3. YELLOW ALERT: Caution / Warning (Trend ignition)
    if (adx_rising and plus_di > (minus_di + 5.0) and rsi >= 55.0) and dist_to_ce_pct <= 2.5:
        return {
            "alert_level": "YELLOW",
            "threat_side": "CALL",
            "alert_title": "🟡 YELLOW ALERT: CALL SIDE MOMENTUM DRIFT",
            "action": "MONITOR_CLOSELY",
            "message": f"૩૦-મિનિટ ચાર્ટ પર ADX {adx:.1f} વધવા લાગ્યો છે અને RSI ૫૫ પાર થયો છે. કૉલ લેગને ચુસ્તપણે મોનિટર કરો."
        }
    elif (adx_rising and minus_di > (plus_di + 5.0) and rsi <= 45.0) and dist_to_pe_pct <= 2.5:
        return {
            "alert_level": "YELLOW",
            "threat_side": "PUT",
            "alert_title": "🟡 YELLOW ALERT: PUT SIDE MOMENTUM DRIFT",
            "action": "MONITOR_CLOSELY",
            "message": f"૩૦-મિનિટ ચાર્ટ પર ADX {adx:.1f} વધવા લાગ્યો છે અને RSI ૪૫ નીચે ગયો છે. પુટ લેગને ચુસ્તપણે મોનિટર કરો."
        }

    return {
        "alert_level": "GREEN",
        "threat_side": "NONE",
        "alert_title": "🟢 ALL SAFE (CALM THETA DECAY)",
        "action": "HOLD",
        "message": f"સ્ટોક શાંત રેન્જમાં છે (ADX: {adx:.1f}, RSI: {rsi:.1f}). પ્રીમિયમ ઝડપથી ઓગળી રહ્યું છે."
    }

# -------------------------------------------------------------
# Telegram Alert Message Formatters
# -------------------------------------------------------------
def format_option_selling_setup_alert(res: Dict[str, Any]) -> str:
    """Formats Telegram alert for newly discovered Range-Bound Option Selling candidates."""
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    sym = res["symbol"]
    spot_p = res["spot_price"]
    ce_contract = res["ce_sell_contract"]
    pe_contract = res["pe_sell_contract"]
    wing_ce = res["wing_ce_contract"]
    wing_pe = res["wing_pe_contract"]

    return (
        f"⚖️ <b>IDEAL RANGE-BOUND OPTION SELLING SETUP</b> ⚖️\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {sym} (LTP: ₹{spot_p:.2f})\n"
        f"🎯 <b>સેટઅપ:</b> Dead Consolidation Box (ADX &lt; 20 + 20D Span &lt;= 8%)\n"
        f"🛡️ <b>Results Check:</b> {res.get('earnings_badge', '🟢 SAFE (કોઈ નજીકનું પરિણામ નથી)')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>SELLING LEGS (Short Strangle / Iron Condor):</b>\n"
        f"• <b>SELL CALL (CE):</b> <b>{ce_contract}</b> (+{res['ce_distance_pct']}%) \n"
        f"• <b>SELL PUT (PE):</b> <b>{pe_contract}</b> (-{res['pe_distance_pct']}%) \n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>OVERNIGHT WINGS (₹1 - ₹2 Insurance / 70% Margin Relief):</b>\n"
        f"• <b>BUY WING CE:</b> {wing_ce}\n"
        f"• <b>BUY WING PE:</b> {wing_pe}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Outer Barriers:</b> TC Band [₹{res['tc_low']} - ₹{res['tc_high']}] | BB 2σ [₹{res['bb_lower']} - ₹{res['bb_upper']}]\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_overnight_health_check_alert(res: Dict[str, Any]) -> str:
    """Formats 3:10 PM Overnight Health-Check Alert."""
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    sym = res["symbol"]
    return (
        f"🔔 <b>3:10 PM OVERNIGHT HEALTH-CHECK ALERT</b> 🔔\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚖️ <b>પોઝિશન:</b> {sym} (ઓપ્શન સેલિંગ)\n"
        f"🛡️ <b>ઓવરનાઇટ સલાહ:</b> રાત્રિ દરમિયાન અણધાર્યા ન્યૂઝ કે ગેપ-ઓપનિંગથી બચવા નીચેના સસ્તા હેજ બાય કરી લો:\n"
        f"• <b>Buy Call Wing:</b> {res['wing_ce_contract']} (~₹1 થી ₹2)\n"
        f"• <b>Buy Put Wing:</b> {res['wing_pe_contract']} (~₹1 થી ₹2)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>ફાયદો:</b> ૧૦૦% શાંતિની ઊંઘ + બ્રોકર તરફથી ૬૫% માર્જિન રિલીફ!\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

# -------------------------------------------------------------
# Standalone CLI Self-Test
# -------------------------------------------------------------
if __name__ == "__main__":
    print("========================================================")
    print("  TESTING RANGE-BOUND OPTION SELLER ENGINE")
    print("========================================================")
    
    # Simulate a dead consolidation stock
    dates = pd.date_range(end=datetime.datetime.now(), periods=50, freq='D')
    np.random.seed(42)
    base = 1300.0
    sim_closes = base + np.cumsum(np.random.randn(50) * 2.0)
    sim_highs = sim_closes + np.random.uniform(1.0, 4.0, 50)
    sim_lows = sim_closes - np.random.uniform(1.0, 4.0, 50)

    df_sample = pd.DataFrame({
        'Open': sim_closes, 'High': sim_highs, 'Low': sim_lows, 'Close': sim_closes, 'Volume': 500000
    }, index=dates)

    df_sample['TC_SMA_High'] = df_sample['High'].rolling(45).mean().fillna(base * 1.02)
    df_sample['TC_SMA_Low'] = df_sample['Low'].rolling(45).mean().fillna(base * 0.98)
    df_sample['ADX_14'] = 16.5
    df_sample['Plus_DI_14'] = 19.0
    df_sample['Minus_DI_14'] = 19.5
    df_sample['RSI_9'] = 48.0

    rules = check_dead_consolidation_rules(df_sample)
    print("Rules Evaluation:", rules)

    strikes = calculate_hybrid_option_selling_strikes("RELIANCE.NS", float(df_sample['Close'].iloc[-1]), df_sample)
    print("\nHybrid Strikes & Overnight Wings:")
    for k, v in strikes.items():
        if "contract" in k or "strike" in k:
            print(f"  {k}: {v}")

    alert_msg = format_option_selling_setup_alert(strikes)
    print("\nSample Alert Message:")
    print("--------------------------------------------------------")
    print(alert_msg)
