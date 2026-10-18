import os
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import pandas as pd
import numpy as np

from .config import (
    DEFAULT_WATCHLIST, STATE_FILE, ACTIVE_TRADES_FILE,
    get_ist_now, is_market_open, ENFORCE_MARKET_HOURS
)
from .database import load_active_trades, load_alert_state, save_alert_state
from .indicators import (
    calculate_hilega_milega,
    calculate_adx_dmi,
    analyze_adx_dmi,
    calculate_trend_craft_ict,
    calculate_volume_analysis,
    calculate_daily_pivot_points,
    calculate_heikin_ashi,
    calculate_donchian_channel
)
from .alerts import (
    send_telegram_alert,
    format_r3_radar_alert,
    format_100_confirmed_buy_alert,
    format_ha_reversal_alert,
    format_sniper_short_alert,
    format_sniper_buy_alert,
    format_general_buy_alert,
    format_exit_alert
)

def analyze_stock(sym):
    """
    Performs multi-timeframe indicator calculation and confluence analysis for a single stock.
    Returns dictionary with signals, price, targets, stops, pivots, and Heikin Ashi data.
    """
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
        
        # 1-Hour Trigger
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
        
        # 1H Institutional Volume (VPA >= 1.2x)
        h1_vol_ratio = h1_curr['Vol_Ratio'] if pd.notna(h1_curr['Vol_Ratio']) else 1.0
        h1_vol_confirmed = h1_vol_ratio >= 1.2
        
        # Bullish Rocket Confluence
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
        
        # Bearish Avalanche Confluence
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
        r1_val, r2_val, r3_val, p_val = 0.0, 0.0, 0.0, 0.0
        
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

        # Heikin Ashi Brijesh Bhatia System
        ha_d = calculate_heikin_ashi(df_d)
        ha_d = calculate_donchian_channel(ha_d, period=11)
        curr_ha = ha_d.iloc[-1]
        prev_ha = ha_d.iloc[-2]
        
        ha_red_count = 0
        for i in range(2, min(16, len(ha_d))):
            bar = ha_d.iloc[-i]
            if bar['HA_Close'] < bar['HA_Open'] or bar.get('HA_Is_Doji', False):
                ha_red_count += 1
            else:
                break
                
        ha_reversal_buy = bool(
            curr_ha['HA_Is_Bullish'] and 
            (prev_ha['HA_Close'] < prev_ha['HA_Open'] or prev_ha['HA_Is_Doji']) and 
            (ha_red_count >= 5) and
            w_bull
        )
        ha_donchian_sl = float(curr_ha['Donchian_Low_11']) if 'Donchian_Low_11' in curr_ha and pd.notna(curr_ha['Donchian_Low_11']) else curr_p * 0.95
        if ha_donchian_sl >= curr_p:
            ha_donchian_sl = curr_p * 0.96
        ha_risk_pct = ((curr_p - ha_donchian_sl) / curr_p) * 100

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
            "pivot_p": p_val,
            "ha_reversal_buy": ha_reversal_buy,
            "ha_red_count": ha_red_count,
            "ha_donchian_sl": ha_donchian_sl,
            "ha_risk_pct": ha_risk_pct
        }
    except Exception as e:
        print(f"Error scanning {sym}: {e}")
        return None

def monitor_active_trades(state):
    """
    Monitors user's active trades from active_trades.json.
    Triggers emergency SL, target, early momentum exit alerts to Telegram.
    """
    active_trades = load_active_trades()
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
            opt_interval = "30m" if (t_type == "OPTION_SELLING" and trd.get("timeframe") == "30m") else "1h"
            df_1h = ticker.history(period="1mo", interval=opt_interval).dropna(subset=['Close', 'High', 'Low', 'Volume'])
            
            if df_d.empty:
                continue
            curr_p = float(df_d['Close'].iloc[-1])
            pnl_pct = ((curr_p - entry_p) / entry_p) * 100
            
            # Calculate 1-Hour Hilega-Milega & ADX/DMI for Early Momentum Exit
            hm_status_text = "સામાન્ય"
            is_hm_bear_cross = False
            c_green, c_red, rsi_val = 50.0, 50.0, 50.0
            rsi_two_bar_slope = 0.0
            h1_adx, h1_plus_di, h1_minus_di = 15.0, 20.0, 20.0
            
            if not df_1h.empty and len(df_1h) >= 30:
                df_1h = calculate_hilega_milega(df_1h)
                df_1h = calculate_adx_dmi(df_1h)
                c_green = float(df_1h['Green_EMA3'].iloc[-1])
                p_green = float(df_1h['Green_EMA3'].iloc[-2])
                c_red = float(df_1h['Red_WMA21'].iloc[-1])
                p_red = float(df_1h['Red_WMA21'].iloc[-2])
                rsi_val = float(df_1h['RSI_9'].iloc[-1])
                p2_rsi = float(df_1h['RSI_9'].iloc[-3]) if len(df_1h) >= 3 else float(df_1h['RSI_9'].iloc[-2])
                rsi_two_bar_slope = rsi_val - p2_rsi
                h1_adx = float(df_1h['ADX_14'].iloc[-1]) if 'ADX_14' in df_1h.columns else 15.0
                h1_plus_di = float(df_1h['Plus_DI_14'].iloc[-1]) if 'Plus_DI_14' in df_1h.columns else 20.0
                h1_minus_di = float(df_1h['Minus_DI_14'].iloc[-1]) if 'Minus_DI_14' in df_1h.columns else 20.0
                
                is_fresh_bear = (p_green >= p_red) and (c_green < c_red)
                is_fresh_bull = (p_green <= p_red) and (c_green > c_red)
                is_below_water = (c_green < 50.0)
                is_hm_bear_cross = is_fresh_bear or (c_green < c_red and is_below_water)
                
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
                
                # 1. Stop Loss Hit
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
                        
                # 2. Target 2 Hit
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
                        
                # 3. Target 1 Hit
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
                        
                # 4. Hilega-Milega Early Exit Trigger
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
                # Call Side Early Warning: Vertical RSI (>60) or +DI Bull Breakout
                elif (
                    (rsi_val >= 60.0 and rsi_two_bar_slope >= 3.0) or
                    (h1_plus_di >= 25.0 and h1_plus_di > (h1_minus_di + 3.0) and h1_adx >= 20.0 and c_green > c_red)
                ) and ce > 0 and (ce - curr_p) <= (ce * 0.025):
                    alert_key = f"{tid}_CALL_MOMENTUM_THREAT"
                    tf_lbl = trd.get('timeframe', '60m')
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>OPTION SELLING MOMENTUM THREAT! (CALL SIDE)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚖️ <b>સ્ટોક:</b> {sym} (ઓપ્શન સેલિંગ)\n"
                            f"📈 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} | <b>Call Strike:</b> > ₹{ce:.1f}\n"
                            f"🚀 <b>અર્લી વોર્નિંગ:</b> {tf_lbl} ચાર્ટ પર તીવ્ર વર્ટિકલ તેજી સ્પાઇક શરૂ થયો છે!\n"
                            f"   • RSI {tf_lbl}: <b>{rsi_val:.1f}</b> (Slope: +{rsi_two_bar_slope:.1f})\n"
                            f"   • +DI: <b>{h1_plus_di:.1f}</b> | ADX: <b>{h1_adx:.1f}</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>સલાહ:</b> સ્ટોકમાં એકતરફી તેજી શરૂ થઈ છે. કૉલ લેગ (CE) નુકસાનમાં જાય તે પહેલાં સલામત <b>Exit</b> કરો અથવા ઉપર શિફ્ટ કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} CALL MOMENTUM THREAT")

                # Put Side Early Warning: Vertical RSI (<40) or -DI Bear Breakdown
                elif (
                    (rsi_val <= 40.0 and rsi_two_bar_slope <= -3.0) or
                    (h1_minus_di >= 25.0 and h1_minus_di > (h1_plus_di + 3.0) and h1_adx >= 20.0 and c_green < c_red)
                ) and pe > 0 and (curr_p - pe) <= (pe * 0.025):
                    alert_key = f"{tid}_PUT_MOMENTUM_THREAT"
                    tf_lbl = trd.get('timeframe', '60m')
                    if not state.get(alert_key):
                        msg = (
                            f"⚠️ <b>OPTION SELLING MOMENTUM THREAT! (PUT SIDE)</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚖️ <b>સ્ટોક:</b> {sym} (ઓપ્શન સેલિંગ)\n"
                            f"📉 <b>હાલનો ભાવ:</b> ₹{curr_p:.2f} | <b>Put Strike:</b> < ₹{pe:.1f}\n"
                            f"🩸 <b>અર્લી વોર્નિંગ:</b> {tf_lbl} ચાર્ટ પર તીવ્ર વર્ટિકલ મંદી બ્રેકડાઉન શરૂ થયો છે!\n"
                            f"   • RSI {tf_lbl}: <b>{rsi_val:.1f}</b> (Slope: {rsi_two_bar_slope:.1f})\n"
                            f"   • -DI: <b>{h1_minus_di:.1f}</b> | ADX: <b>{h1_adx:.1f}</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛑 <b>સલાહ:</b> સ્ટોકમાં એકતરફી ઘટાડો શરૂ થયો છે. પુટ લેગ (PE) નુકસાનમાં જાય તે પહેલાં સલામત <b>Exit</b> કરો અથવા નીચે શિફ્ટ કરો!\n"
                            f"⏰ <i>{now_str}</i>"
                        )
                        send_telegram_alert(msg)
                        state[alert_key] = True
                        alerts.append(f"{sym} PUT MOMENTUM THREAT")
        except Exception as err:
            print(f"Error checking trade {trd.get('symbol')}: {err}")
            
    return alerts

def run_scan_cycle(force=False, watchlist=None):
    """
    Executes a complete scan cycle across the watchlist.
    Checks market hours, monitors active trades, and dispatches Telegram alerts.
    """
    if watchlist is None:
        watchlist = DEFAULT_WATCHLIST
        
    if ENFORCE_MARKET_HOURS and not force:
        is_open, reason = is_market_open()
        if not is_open:
            print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] ⏸️ Market Closed ({reason}). Skipping scan cycle.")
            return []

    state = load_alert_state()
            
    print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] Scanning {len(watchlist)} stocks with multi-threading...")
    new_alerts = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_stock, watchlist))
        
    # Monitor User's Active Trades
    trade_alerts = monitor_active_trades(state)
    new_alerts.extend(trade_alerts)

    today_str = get_ist_now().date().isoformat()
    for res in results:
        if not res:
            continue
            
        s_name = res['symbol']
        curr_sig = res['signal']
        prev_sig = state.get(s_name)
        
        is_sniper_short = "SNIPER SHORT" in curr_sig
        is_sniper_buy = "SNIPER DIP BUY" in curr_sig or "STRONG BUY" in curr_sig
        is_buy = "BUY" in curr_sig or "BULLISH" in curr_sig
        is_sell = "SELL" in curr_sig or "AVOID" in curr_sig
        
        # 0. R3 Option Breakout
        r3_alert_key = f"{s_name}_R3_{today_str}"
        if res.get('is_r3_radar') and not state.get(r3_alert_key):
            alert_text = format_r3_radar_alert(res)
            print(f"Sending R3 OPTION RADAR alert for {s_name}")
            send_telegram_alert(alert_text)
            state[r3_alert_key] = True
            new_alerts.append(f"{s_name}: R3 OPTION RADAR")

        # 0.1 100% Confirmed Buy
        is_r3_confirmed = bool(
            res.get('is_r3_radar') and 
            (is_sniper_buy or "STRONG BUY" in curr_sig) and
            (res['price'] >= res.get('r1', 0))
        )
        r3_confirmed_key = f"{s_name}_R3_CONFIRMED_{today_str}"
        if is_r3_confirmed and not state.get(r3_confirmed_key):
            confirmed_alert_text = format_100_confirmed_buy_alert(res)
            print(f"Sending 100% CONFIRMED BUY alert for {s_name}")
            send_telegram_alert(confirmed_alert_text)
            state[r3_confirmed_key] = True
            new_alerts.append(f"{s_name}: 100% CONFIRMED BUY")

        # 0.2 Heikin Ashi Reversal Buy
        ha_alert_key = f"{s_name}_HA_REVERSAL_{today_str}"
        if res.get('ha_reversal_buy') and not state.get(ha_alert_key):
            ha_alert_text = format_ha_reversal_alert(res)
            print(f"Sending HEIKIN ASHI REVERSAL alert for {s_name}")
            send_telegram_alert(ha_alert_text)
            state[ha_alert_key] = True
            new_alerts.append(f"{s_name}: HEIKIN ASHI REVERSAL")

        # 1. Fresh Sniper Short
        if is_sniper_short and (prev_sig != curr_sig):
            alert_text = format_sniper_short_alert(res)
            print(f"Sending SNIPER SHORT alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: SNIPER SHORT")
            
        # 2. Fresh Sniper Buy
        elif is_sniper_buy and (prev_sig != curr_sig):
            alert_text = format_sniper_buy_alert(res)
            print(f"Sending SNIPER BUY alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: SNIPER BUY")
            
        # 3. General Bullish
        elif is_buy and (prev_sig != curr_sig):
            alert_text = format_general_buy_alert(res)
            print(f"Sending BUY alert for {s_name}: {curr_sig}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: {curr_sig}")
            
        # 4. Exit Alert
        elif is_sell and prev_sig and ("BUY" in prev_sig or "BULLISH" in prev_sig) and not is_sniper_short:
            alert_text = format_exit_alert(res)
            print(f"Sending EXIT alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: EXIT")
            
        state[s_name] = curr_sig
        
    save_alert_state(state)
        
    return new_alerts
