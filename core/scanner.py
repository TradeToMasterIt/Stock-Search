import os
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import pandas as pd
import numpy as np

from .config import (
    DEFAULT_WATCHLIST, INDEX_WATCHLIST, STATE_FILE, ACTIVE_TRADES_FILE,
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
from .option_r3_engine import (
    analyze_put_r3_setup,
    build_option_contract,
    analyze_option_r3_setup,
    TOP_MOMENTUM_FNO_BASKET,
    is_index_symbol,
    normalize_symbol_and_exchange
)
from .earnings_filter import check_earnings_blackout
from .option_seller_engine import (
    calculate_hybrid_option_selling_strikes,
    check_dead_consolidation_rules,
    monitor_option_seller_defense,
    format_option_selling_setup_alert,
    format_overnight_health_check_alert
)
from .gfs_engine import evaluate_gfs_confluence
from .alerts import (
    send_telegram_alert,
    format_stage1_pre_breakout_alert,
    format_gfs_swing_alert,
    format_pre_r3_radar_alert,
    format_pre_put_r3_radar_alert,
    format_r3_radar_alert,
    format_100_confirmed_buy_alert,
    format_100_confirmed_put_alert,
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
        is_index = is_index_symbol(sym)
        t = yf.Ticker(sym)
        subset_cols = ['Close', 'High', 'Low'] if is_index else ['Close', 'High', 'Low', 'Volume']
        df_d = t.history(period="1y", interval="1d").dropna(subset=subset_cols)
        df_w = t.history(period="3y", interval="1wk").dropna(subset=subset_cols)
        df_m = t.history(period="5y", interval="1mo").dropna(subset=subset_cols)
        df_1h = t.history(period="1mo", interval="1h").dropna(subset=subset_cols)
        
        if df_d.empty or len(df_d) < 30 or df_1h.empty:
            return None
            
        if is_index:
            for df_item in [df_d, df_w, df_m, df_1h]:
                if 'Volume' not in df_item.columns or df_item['Volume'].sum() == 0:
                    df_item['Volume'] = 1_000_000
            
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
        
        # 1H Institutional Volume (VPA >= 1.2x, auto-confirmed for Index)
        h1_vol_ratio = h1_curr['Vol_Ratio'] if pd.notna(h1_curr['Vol_Ratio']) else 1.0
        h1_vol_confirmed = True if is_index else (h1_vol_ratio >= 1.2)
        
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
        
        # GFS Multi-Timeframe Confluence & Scipy RSI Divergence Engine
        gfs_eval = evaluate_gfs_confluence(df_m, df_w, df_d, curr_p)
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
            # Compute Hybrid Outer Strikes (TC Band + Bollinger Bands) & Overnight Wings
            seller_strikes = calculate_hybrid_option_selling_strikes(sym, curr_p, df_d)
            earnings_info = {"is_blackout": False} if is_index else check_earnings_blackout(sym, blackout_days=10)
            dead_rules = check_dead_consolidation_rules(df_d, df_w, df_m)
            is_dead_consolidation = dead_rules.get("passes_all", False)
            is_earnings_blackout = earnings_info.get("is_blackout", False)

            ce_strike = seller_strikes["ce_sell_strike"]
            pe_strike = seller_strikes["pe_sell_strike"]
            wing_ce_strike = seller_strikes["wing_ce_strike"]
            wing_pe_strike = seller_strikes["wing_pe_strike"]
            
            is_1h_bull = (h1_curr['Green_EMA3'] > h1_curr['Red_WMA21']) and (h1_curr['Close'] > h1_curr['TC_SMA_High'])
            if is_sniper_buy:
                signal = "🎯 SNIPER DIP BUY (Confirmed)"
            elif is_dead_consolidation and not is_earnings_blackout:
                signal = "⚖️ OPTION SELLING (Dead Box)"
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
        r1_val, r2_val, r3_val, p_val = 0.0, 0.0, 0.0, 0.0
        
        # Build exact Option Contract details (e.g. 'DLF 26 NOV 700 CE')
        opt_info = build_option_contract(sym, curr_p, "CE")
        opt_contract_name = opt_info["contract_name"]
        opt_fyers_symbol = opt_info["fyers_symbol"]
        otm_call_strike = opt_info["strike"]
        
        s1_val, s2_val, s3_val = 0.0, 0.0, 0.0
        if pivots:
            p_val = pivots['p']
            r1_val = pivots['r1']
            r2_val = pivots['r2']
            r3_val = pivots['r3']
            s1_val = pivots.get('s1', 0.0)
            s2_val = pivots.get('s2', 0.0)
            s3_val = pivots.get('s3', 0.0)
            is_r3_radar = bool(
                (pct_chg >= 1.5 or curr_p >= r2_val) and
                (curr_p >= r1_val) and
                (d_hm_bull or pct_chg >= 2.0)
            )

        # Ultra-Fast Candle Sweet Spot RSI, Direction & Rejection Analysis (2m/3m -> 5m -> 15m)
        # Primary: 2m/3m ultra-fast chart for timely option entry before gamma blast escapes.
        # Secondary: 5-minute chart; Fallback: 15-minute chart.
        m_rsi = float(h1_curr['RSI_9'])
        m_prev_rsi = float(h1_prev['RSI_9'])
        m_rsi_slope = round(m_rsi - m_prev_rsi, 2)
        m_vol_ratio = h1_vol_ratio
        is_wick_rejected = False
        timeframe_used = "1H"
        is_candle_green = bool(h1_curr['Close'] >= h1_curr['Open'])
        is_candle_red = bool(h1_curr['Close'] <= h1_curr['Open'])
        
        is_candidate_bear = bool(is_sniper_short or (s1_val > 0 and curr_p <= s1_val) or (pct_chg <= -0.8))
        is_candidate = bool(is_sniper_buy or is_r3_radar or (curr_p >= r1_val) or (pct_chg >= 0.35 and d_is_positive) or (pct_chg >= 0.7) or is_candidate_bear)
        is_lower_wick_rejected = False
        if is_candidate:
            try:
                # 1. Try 2m/3m ultra-fast intraday candles first (2 days data)
                df_intra = None
                try:
                    df_2m = t.history(period="2d", interval="2m").dropna(subset=subset_cols)
                    if df_2m is not None and not df_2m.empty and len(df_2m) >= 20:
                        df_intra = df_2m
                        timeframe_used = "3m"
                except Exception:
                    df_intra = None

                # 2. Try 5-minute candles if 2m is not available (3 days data)
                if df_intra is None or df_intra.empty or len(df_intra) < 20:
                    try:
                        df_5m = t.history(period="3d", interval="5m").dropna(subset=subset_cols)
                        if df_5m is not None and not df_5m.empty and len(df_5m) >= 20:
                            df_intra = df_5m
                            timeframe_used = "5m"
                    except Exception:
                        df_intra = None
                
                # 3. Fallback to 15-minute if 5m is not available
                if df_intra is None or df_intra.empty or len(df_intra) < 20:
                    try:
                        df_15m = t.history(period="5d", interval="15m").dropna(subset=subset_cols)
                        if df_15m is not None and not df_15m.empty and len(df_15m) >= 20:
                            df_intra = df_15m
                            timeframe_used = "15m"
                    except Exception:
                        df_intra = None

                if df_intra is not None and not df_intra.empty and len(df_intra) >= 20:
                    if is_index and ('Volume' not in df_intra.columns or df_intra['Volume'].sum() == 0):
                        df_intra['Volume'] = 1_000_000
                    df_intra = calculate_volume_analysis(calculate_hilega_milega(df_intra))
                    c_intra = df_intra.iloc[-1]
                    p_intra = df_intra.iloc[-2]
                    m_rsi = float(c_intra.get('RSI_9', 50.0))
                    m_prev_rsi = float(p_intra.get('RSI_9', 50.0))
                    m_rsi_slope = round(m_rsi - m_prev_rsi, 2)
                    m_vol_ratio = float(c_intra.get('Vol_Ratio', 1.0))
                    
                    # Candle Color & Span Analysis (Mandates Green for CE / Red for PE)
                    c_h = float(c_intra['High'])
                    c_l = float(c_intra['Low'])
                    c_o = float(c_intra['Open'])
                    c_c = float(c_intra['Close'])
                    is_candle_green = bool(c_c >= c_o)
                    is_candle_red = bool(c_c <= c_o)

                    # Stage-1 Early Pre-Breakout Squeeze Radar Detection
                    # Catches momentum 5 to 8 minutes EARLY (e.g. 13:45 at ₹4.50 instead of 13:53 at ₹5.44)
                    try:
                        from .gfs_engine import calculate_bollinger_bands
                        df_bb = calculate_bollinger_bands(df_intra, period=20, std=2.0)
                        c_bb = df_bb.iloc[-1]
                        p_bb = df_bb.iloc[-2]
                        # Bollinger squeeze bandwidth <= 2.5%
                        bw_history = (df_bb['BBU'].iloc[-12:-1] - df_bb['BBL'].iloc[-12:-1]) / df_bb['BBM'].iloc[-12:-1]
                        is_tight_squeeze = bool(bw_history.mean() <= 0.025)
                        is_bb_upper_blast = bool(c_c >= c_bb['BBU'] or (p_bb['Close'] <= c_bb['BBM'] and c_c > c_bb['BBM'] * 1.003))
                        is_early_rsi_sweet = bool(55.0 <= m_rsi <= 68.0 and m_rsi_slope >= 0.2)
                        macro_is_bull = bool(d_is_positive or (m_bull and w_bull))
                        is_stage1_pre_breakout = bool(macro_is_bull and (is_bb_upper_blast or is_tight_squeeze) and is_early_rsi_sweet and is_candle_green)
                    except Exception:
                        is_stage1_pre_breakout = False

                    # Upper wick rejection check (Rejection at R2/R3 barrier)
                    total_bar_span = c_h - c_l
                    upper_wick = c_h - max(c_o, c_c)
                    if total_bar_span > 0:
                        wick_ratio = upper_wick / total_bar_span
                        if wick_ratio >= 0.45 and c_c < r2_val:
                            is_wick_rejected = True
                        lower_wick = min(c_o, c_c) - c_l
                        lower_wick_ratio = lower_wick / total_bar_span
                        if lower_wick_ratio >= 0.45 and c_c > s2_val:
                            is_lower_wick_rejected = True
            except Exception:
                pass

        # Intraday Timing & Institutional Volume Guard:
        # - Post-15:00 IST: Fresh entries BLOCKED (30m to close, delivery/liquidity hazard)
        # - 14:15 - 15:00 IST: 0DTE Gamma Blast on expiry days ALLOWED; non-gamma requires Vol >= 1.5x
        # - Pre-14:15 IST: Strict Base Volume >= 1.0x (Eliminates 0.1x dead volume traps like CROMPTON)
        now_ist = get_ist_now()
        curr_min_val = now_ist.hour * 60 + now_ist.minute
        time_1415 = 14 * 60 + 15
        time_1500 = 15 * 60
        is_after_1415 = bool(curr_min_val >= time_1415)
        is_after_1500 = bool(curr_min_val >= time_1500)
        is_gamma_blast = opt_info.get("is_gamma_blast", False)

        if is_after_1500:
            vol_sweet_confirmed = False
        elif is_after_1415:
            vol_sweet_confirmed = True if is_index else (is_gamma_blast or m_vol_ratio >= 1.5)
        else:
            vol_sweet_confirmed = True if is_index else (m_vol_ratio >= 1.0)

        # Golden RSI Sweet Spot Filter (58 to 74 with Positive Slope, Green Candle & Strict Volume)
        is_r3_rsi_confirmed = bool(
            (58.0 <= m_rsi <= 74.0) and
            (m_rsi_slope >= -0.5) and
            (not is_wick_rejected) and
            is_candle_green and
            vol_sweet_confirmed
        )
        # Bearish Sweet Spot Filter (26 to 42 with Downward Momentum, Red Candle & Strict Volume)
        is_put_rsi_confirmed = bool(
            (26.0 <= m_rsi <= 42.0) and
            (m_rsi_slope <= 0.5) and
            (not is_lower_wick_rejected) and
            is_candle_red and
            vol_sweet_confirmed
        )

        # Deep Option R3 Analysis (Both Call & Put Option Engines)
        opt_ltp = 0.0
        opt_r3_val = 0.0
        is_option_r3_crossed = False
        opt_analysis = None
        if is_candidate and not is_candidate_bear:
            try:
                opt_analysis = analyze_option_r3_setup(
                    symbol=sym,
                    spot_price=curr_p,
                    spot_pct_change=pct_chg,
                    spot_is_bullish=d_is_positive,
                    spot_is_1h_confirmed=is_sniper_buy,
                    spot_prev_high=float(d_prev['High']),
                    spot_prev_low=float(d_prev['Low']),
                    spot_prev_close=float(d_prev['Close']),
                    spot_r1=r1_val,
                    spot_r2=r2_val,
                    spot_r3=r3_val
                )
                if opt_analysis:
                    opt_ltp = opt_analysis.get("opt_ltp", 0.0)
                    opt_r3_val = opt_analysis.get("opt_r3", 0.0)
                    is_option_r3_crossed = opt_analysis.get("is_option_r3_crossed", False)
                    if is_option_r3_crossed:
                        is_r3_radar = True
            except Exception:
                pass

        # Deep Put Option R3 Analysis (Bearish Mandi Setup)
        opt_put_analysis = None
        if is_candidate_bear:
            try:
                opt_put_analysis = analyze_put_r3_setup(
                    symbol=sym,
                    spot_price=curr_p,
                    spot_pct_change=pct_chg,
                    spot_is_bearish=d_is_negative,
                    spot_is_1h_confirmed=is_sniper_short,
                    spot_prev_high=float(d_prev['High']),
                    spot_prev_low=float(d_prev['Low']),
                    spot_prev_close=float(d_prev['Close']),
                    spot_s1=s1_val,
                    spot_s2=s2_val,
                    spot_s3=s3_val
                )
            except Exception:
                pass
        
        is_pre_r3_radar = bool(opt_analysis.get("is_pre_r3_radar", False)) if opt_analysis else False
        is_chasing = bool(opt_analysis.get("is_chasing", False)) if opt_analysis else False
        is_pre_put_r3_radar = bool(opt_put_analysis.get("is_pre_r3_radar", False)) if opt_put_analysis else False
        is_put_chasing = bool(opt_put_analysis.get("is_chasing", False)) if opt_put_analysis else False
        is_gamma_blast = opt_analysis.get("is_gamma_blast", False) if opt_analysis else opt_info.get("is_gamma_blast", False)

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

        clean_sym, _, display_name = normalize_symbol_and_exchange(sym)
        s_display = display_name if is_index else sym.replace(".NS", "")
        return {
            "symbol": s_display,
            "raw_symbol": sym,
            "is_index": is_index,
            "is_gamma_blast": is_gamma_blast,
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
            "wing_ce_strike": wing_ce_strike,
            "wing_pe_strike": wing_pe_strike,
            "is_dead_consolidation": is_dead_consolidation,
            "is_earnings_blackout": is_earnings_blackout,
            "gfs_score": gfs_eval.get("gfs_score", 0),
            "gfs_action": gfs_eval.get("gfs_action", "⚪ NEUTRAL"),
            "gfs_badge": gfs_eval.get("gfs_badge", "⚪ NEUTRAL"),
            "is_gfs_high_confidence": gfs_eval.get("is_gfs_high_confidence", False),
            "has_bull_div": gfs_eval.get("has_bull_div", False),
            "bull_div_bars": gfs_eval.get("bull_div_bars"),
            "has_bear_div": gfs_eval.get("has_bear_div", False),
            "bear_div_bars": gfs_eval.get("bear_div_bars"),
            "bb_middle": gfs_eval.get("bb_middle", 0.0),
            "bb_lower": gfs_eval.get("bb_lower", 0.0),
            "bb_support_active": gfs_eval.get("bb_support_active", False),
            "candle_pattern": gfs_eval.get("candle_pattern", "STANDARD GREEN 🟢"),
            "earnings_badge": earnings_info.get("status_badge", "🟢 SAFE"),
            "is_r3_radar": is_r3_radar,
            "is_pre_r3_radar": is_pre_r3_radar,
            "is_chasing": is_chasing,
            "is_pre_put_r3_radar": is_pre_put_r3_radar,
            "is_put_chasing": is_put_chasing,
            "otm_call_strike": otm_call_strike,
            "r1": r1_val,
            "r2": r2_val,
            "r3": r3_val,
            "s1": s1_val,
            "s2": s2_val,
            "s3": s3_val,
            "pivot_p": p_val,
            "opt_put_contract_name": opt_put_analysis.get("contract_name") if opt_put_analysis else "",
            "opt_put_fyers_symbol": opt_put_analysis.get("fyers_symbol") if opt_put_analysis else "",
            "opt_put_ltp": opt_put_analysis.get("opt_ltp", 0.0) if opt_put_analysis else 0.0,
            "opt_put_r3": opt_put_analysis.get("opt_r3", 0.0) if opt_put_analysis else 0.0,
            "otm_put_strike": opt_put_analysis.get("strike", 0) if opt_put_analysis else 0,
            "is_put_r3_crossed": opt_put_analysis.get("is_option_r3_crossed", False) if opt_put_analysis else False,
            "is_put_rsi_confirmed": is_put_rsi_confirmed,
            "opt_put_sl": opt_put_analysis.get("stop_loss", 0.0) if opt_put_analysis else 0.0,
            "opt_put_t1": opt_put_analysis.get("t1", 0.0) if opt_put_analysis else 0.0,
            "opt_put_t2": opt_put_analysis.get("t2", 0.0) if opt_put_analysis else 0.0,
            "opt_contract_name": opt_contract_name,
            "opt_fyers_symbol": opt_fyers_symbol,
            "opt_ltp": opt_ltp,
            "opt_sl": round(opt_ltp * 0.75, 2) if opt_ltp > 0 else 0.0,
            "opt_t1": round(opt_ltp * 1.35, 2) if opt_ltp > 0 else 0.0,
            "opt_t2": round(opt_ltp * 1.70, 2) if opt_ltp > 0 else 0.0,
            "opt_r3": opt_r3_val,
            "is_option_r3_crossed": is_option_r3_crossed,
            "rsi_5m": round(m_rsi, 1),
            "rsi_15m": round(m_rsi, 1),
            "rsi_5m_slope": round(m_rsi_slope, 1),
            "rsi_15m_slope": round(m_rsi_slope, 1),
            "is_r3_rsi_confirmed": is_r3_rsi_confirmed,
            "is_candle_green": is_candle_green,
            "is_candle_red": is_candle_red,
            "is_5m_wick_rejected": is_wick_rejected,
            "is_15m_wick_rejected": is_wick_rejected,
            "vol_5m": round(m_vol_ratio, 1),
            "vol_15m": round(m_vol_ratio, 1),
            "timeframe_used": timeframe_used,
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
        watchlist = INDEX_WATCHLIST + DEFAULT_WATCHLIST
        
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

    # Monitor & Manage Auto-Algo Trading Positions (Target 1, Target 2, Trailing SL, Kill-Switch)
    try:
        from .fyers_order_engine import monitor_and_manage_algo_positions
        algo_mgr_alerts = monitor_and_manage_algo_positions()
        if algo_mgr_alerts:
            new_alerts.extend(algo_mgr_alerts)
    except Exception as algo_m_err:
        print(f"Error in algo order manager: {algo_m_err}")

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
        
        # -1.0 Stage-1 Early Pre-Breakout Squeeze Radar (5 to 8 minutes early warning at cheaper price)
        stage1_key = f"{s_name}_STAGE1_{today_str}"
        if res.get('is_stage1_pre_breakout') and not res.get('is_option_r3_crossed') and not state.get(stage1_key):
            stage1_alert_text = format_stage1_pre_breakout_alert(res)
            print(f"Sending STAGE-1 PRE-BREAKOUT RADAR alert for {s_name}")
            send_telegram_alert(stage1_alert_text)
            state[stage1_key] = True
            new_alerts.append(f"{s_name}: STAGE-1 PRE-BREAKOUT")

        # -1. Pre-R3 Advance Radar (Call Side - 2 to 3 minutes advance notice before blast)
        pre_r3_key = f"{s_name}_PRE_R3_{today_str}"
        if res.get('is_pre_r3_radar') and not res.get('is_option_r3_crossed') and not state.get(pre_r3_key):
            pre_alert_text = format_pre_r3_radar_alert(res)
            print(f"Sending PRE-R3 ADVANCE RADAR alert for {s_name}")
            send_telegram_alert(pre_alert_text)
            state[pre_r3_key] = True
            new_alerts.append(f"{s_name}: PRE-R3 ADVANCE RADAR")

        # -1.05 Pre-Put R3 Advance Radar (Put Side - 2 to 3 minutes advance notice before breakdown)
        pre_put_r3_key = f"{s_name}_PRE_PUT_R3_{today_str}"
        if res.get('is_pre_put_r3_radar') and not res.get('is_put_r3_crossed') and not state.get(pre_put_r3_key):
            pre_put_alert_text = format_pre_put_r3_radar_alert(res)
            print(f"Sending PRE-PUT R3 ADVANCE RADAR alert for {s_name}")
            send_telegram_alert(pre_put_alert_text)
            state[pre_put_r3_key] = True
            new_alerts.append(f"{s_name}: PRE-PUT R3 ADVANCE RADAR")

        # 0. R3 Option Breakout / 100% Confirmed Buy Alert
        # Fires when Option crosses R3 + Spot at/above R1 OR R2 + RSI Sweet Spot confirmed (Anti-FOMO protected)
        spot_p = res.get('price', 0)
        spot_r1 = res.get('r1', 0)
        spot_r2 = res.get('r2', 0)
        spot_at_or_above_r1 = bool(spot_r1 > 0 and spot_p >= spot_r1)
        spot_at_or_above_r2 = bool(spot_r2 > 0 and spot_p >= spot_r2)

        r3_confirmed_key = f"{s_name}_R3_CONFIRMED_{today_str}"
        is_r3_confirmed = bool(
            (spot_at_or_above_r1 or spot_at_or_above_r2 or is_sniper_buy or "STRONG BUY" in curr_sig) and
            res.get('is_option_r3_crossed') and
            res.get('is_r3_rsi_confirmed', True) and
            not res.get('is_chasing', False)
        )
        if is_r3_confirmed and not state.get(r3_confirmed_key):
            confirmed_alert_text = format_100_confirmed_buy_alert(res)
            print(f"Sending 100% CONFIRMED BUY (OPTION R3 CROSSED) alert for {s_name}")
            send_telegram_alert(confirmed_alert_text)
            state[r3_confirmed_key] = True
            new_alerts.append(f"{s_name}: 100% CONFIRMED BUY")

            # Execute Auto-Algo Entry (Paper or Live Fyers broker execution)
            try:
                from .fyers_order_engine import execute_algo_entry
                algo_ok, algo_msg = execute_algo_entry(res)
                if algo_ok:
                    print(f"🤖 Auto-Algo Execution Success: {algo_msg}")
                    new_alerts.append(f"🤖 ALGO EXEC: {s_name}")
                else:
                    print(f"🤖 Auto-Algo Skipped/Standby: {algo_msg}")
            except Exception as algo_err:
                print(f"Error executing algo entry: {algo_err}")

        # 0.05 Bearish Put Option Breakout / 100% Confirmed Put Buy Alert
        spot_s1 = res.get('s1', 0)
        spot_s2 = res.get('s2', 0)
        spot_at_or_below_s1 = bool(spot_s1 > 0 and spot_p <= spot_s1)
        spot_at_or_below_s2 = bool(spot_s2 > 0 and spot_p <= spot_s2)
        r3_put_confirmed_key = f"{s_name}_PUT_R3_CONFIRMED_{today_str}"
        is_put_r3_confirmed = bool(
            (spot_at_or_below_s1 or spot_at_or_below_s2 or is_sniper_short or "STRONG SELL" in curr_sig) and
            res.get('is_put_r3_crossed') and
            res.get('is_put_rsi_confirmed', True) and
            not res.get('is_put_chasing', False)
        )
        if is_put_r3_confirmed and not state.get(r3_put_confirmed_key):
            confirmed_put_text = format_100_confirmed_put_alert(res)
            print(f"Sending 100% CONFIRMED PUT BUY (PUT R3 CROSSED) alert for {s_name}")
            send_telegram_alert(confirmed_put_text)
            state[r3_put_confirmed_key] = True
            new_alerts.append(f"{s_name}: 100% CONFIRMED PUT BUY")

            # Execute Auto-Algo Entry for Put Option
            try:
                from .fyers_order_engine import execute_algo_entry
                put_trade_res = res.copy()
                put_trade_res['opt_type'] = 'PE'
                algo_ok, algo_msg = execute_algo_entry(put_trade_res)
                if algo_ok:
                    print(f"🤖 Auto-Algo Execution (PUT): {algo_msg}")
                    new_alerts.append(f"🤖 ALGO PUT EXEC: {s_name}")
                else:
                    print(f"🤖 Auto-Algo Put Skipped: {algo_msg}")
            except Exception as algo_err:
                print(f"Error executing algo put entry: {algo_err}")

        # 0.1 Standalone Option R3 Breakout (Option LTP >= Option R3 + Spot >= R2 + RSI 58-74)
        r3_alert_key = f"{s_name}_R3_{today_str}"
        if res.get('is_option_r3_crossed') and res.get('is_r3_rsi_confirmed', True) and not res.get('is_chasing', False) and not state.get(r3_alert_key) and not is_r3_confirmed:
            alert_text = format_r3_radar_alert(res)
            print(f"Sending R3 OPTION RADAR alert for {s_name}")
            send_telegram_alert(alert_text)
            state[r3_alert_key] = True
            new_alerts.append(f"{s_name}: R3 OPTION RADAR")

        # 0.2 Heikin Ashi Reversal Buy
        ha_alert_key = f"{s_name}_HA_REVERSAL_{today_str}"
        if res.get('ha_reversal_buy') and not state.get(ha_alert_key):
            ha_alert_text = format_ha_reversal_alert(res)
            print(f"Sending HEIKIN ASHI REVERSAL alert for {s_name}")
            send_telegram_alert(ha_alert_text)
            state[ha_alert_key] = True
            new_alerts.append(f"{s_name}: HEIKIN ASHI REVERSAL")

        # 0.3 GFS Swing Multibagger Dip Alert (Grandfather-Father-Son 3-TF Confluence)
        gfs_alert_key = f"{s_name}_GFS_SWING_{today_str}"
        if res.get('is_gfs_high_confidence') and not state.get(gfs_alert_key):
            gfs_alert_text = format_gfs_swing_alert(res)
            print(f"Sending GFS SWING MULTIBAGGER alert for {s_name}")
            send_telegram_alert(gfs_alert_text)
            state[gfs_alert_key] = True
            new_alerts.append(f"{s_name}: GFS SWING MULTIBAGGER")

        # 1. Confirmed Sniper Buy (Includes exact OTM Call Strike & Option R3 level)
        if is_sniper_buy and (prev_sig != curr_sig) and not state.get(r3_confirmed_key):
            alert_text = format_sniper_buy_alert(res)
            print(f"Sending SNIPER BUY alert for {s_name}")
            send_telegram_alert(alert_text)
            new_alerts.append(f"{s_name}: SNIPER BUY")

        # NOTE: Unconfirmed "BUY ON DIPS (Wait for 1H)" and general weak bullish alerts
        # are intentionally suppressed from Telegram to prevent message spam.
        # Only 100% Confirmed Buy, Sniper Dip Buy, and R3 Breakout alerts are sent.
        
        # NOTE: Exit alerts are STRICTLY restricted to positions actively monitored 
        # in Risk Guardian (handled above in monitor_active_trades()). General unowned
        # stock exit alerts are suppressed to keep the Telegram feed clean.
            
        state[s_name] = curr_sig
        
    save_alert_state(state)
        
    return new_alerts
