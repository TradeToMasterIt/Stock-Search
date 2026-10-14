"""
Historical Backtesting Engine for Patel Trading Bot
Simulates trading strategies across historical candles and calculates performance metrics:
- Win Rate %
- Profit Factor
- Max Drawdown
- Net P&L & Equity Curve
- Trade Execution Log
"""

import pandas as pd
import numpy as np
import yfinance as yf
from .indicators import (
    calculate_hilega_milega,
    calculate_trend_craft_ict,
    calculate_volume_analysis,
    calculate_heikin_ashi,
    calculate_donchian_channel,
)

STRATEGIES = {
    "sniper_buy": "🎯 Sniper Dip Buy (Hilega-Milega + Trend Craft + VPA)",
    "sniper_short": "🩸 Sniper Short Sell (Bearish Confluence)",
    "r3_rocket": "🚀 R3 Option Rocket Breakout (Pivot R3 Surge)",
    "ha_trend": "🌊 Brijesh Bhatia Heikin Ashi (Pure 11-Day Donchian Trailing • Open Target)"
}

def run_backtest(
    symbol: str,
    strategy: str = "sniper_buy",
    period: str = "1y",
    initial_capital: float = 100000.0,
    risk_per_trade_pct: float = 2.0
):
    """
    Executes historical backtest on daily data for a given symbol and strategy.
    
    Returns:
        dict containing summary statistics, equity curve DataFrame, and trade log DataFrame.
    """
    full_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.endswith(".BO") and not symbol.startswith("^") else symbol
    
    try:
        tkr = yf.Ticker(full_sym)
        df = tkr.history(period=period, interval="1d")
        # Fallback 1: If requested period is empty or short for recent IPOs, try period="max"
        if df is None or df.empty or len(df) < 15:
            df = tkr.history(period="max", interval="1d")
        # Fallback 2: If .NS is not found, try BSE (.BO)
        if (df is None or df.empty or len(df) < 15) and not symbol.endswith(".BO"):
            base_code = symbol.replace(".NS", "").replace(".BO", "")
            df = yf.Ticker(f"{base_code}.BO").history(period="max", interval="1d")
    except Exception as e:
        return {"error": f"Failed to fetch historical data for {symbol}: {str(e)}"}
        
    if df is None or df.empty or len(df) < 15:
        return {"error": f"Insufficient historical data ({len(df) if df is not None else 0} candles) for {symbol}. Stock may be too newly listed."}

    df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume']).copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Compute Indicators
    df = calculate_volume_analysis(df)
    df = calculate_hilega_milega(df)
    df = calculate_trend_craft_ict(df)
    df = calculate_heikin_ashi(df)
    df = calculate_donchian_channel(df, period=11)
    df['SMA50'] = df['Close'].rolling(window=min(50, max(5, len(df)//2))).mean()
    df['EMA20'] = df['Close'].ewm(span=min(20, max(5, len(df)//2)), adjust=False).mean()

    trades = []
    in_trade = False
    entry_idx = 0
    entry_date = None
    entry_price = 0.0
    stop_loss = 0.0
    target_1 = 0.0
    target_2 = 0.0
    trade_type = "BUY"
    shares = 0
    trailing_sl = 0.0
    breakeven_activated = False

    capital = initial_capital
    equity_curve = []

    # Dynamic Warmup period based on available history (supports fresh IPO stocks)
    warmup = min(20, max(10, len(df) // 4))

    # Iterate through candles
    for i in range(warmup, len(df)):
        cur_date = df.index[i]
        cur_open = float(df['Open'].iloc[i])
        cur_high = float(df['High'].iloc[i])
        cur_low = float(df['Low'].iloc[i])
        cur_close = float(df['Close'].iloc[i])
        prev_close = float(df['Close'].iloc[i - 1])

        # Record current capital into equity curve
        unrealized_pnl = 0.0
        if in_trade:
            if trade_type == "BUY":
                unrealized_pnl = (cur_close - entry_price) * shares
            else:
                unrealized_pnl = (entry_price - cur_close) * shares
        equity_curve.append({
            "Date": cur_date,
            "Equity": round(capital + unrealized_pnl, 2),
            "Close": cur_close
        })

        # --- Check Active Trade Exits ---
        if in_trade:
            exit_trade = False
            exit_price = cur_close
            exit_reason = ""

            if strategy == "ha_trend":
                # Pure Brijesh Bhatia Trend Following Rules:
                # 1. Trailing Stop Loss = Lowest Low of previous 11 completed candles
                donchian_val = df['Donchian_Low_11'].iloc[i - 1] if 'Donchian_Low_11' in df.columns else stop_loss
                if pd.notna(donchian_val):
                    # Monotonic Ratchet: Trailing SL ONLY moves UPWARDS, never down
                    trailing_sl = max(trailing_sl, float(donchian_val))

                # 2. Hard Initial Stop Loss Protection (before Donchian trails up)
                if cur_low <= stop_loss and trailing_sl <= stop_loss:
                    exit_trade = True
                    exit_price = min(cur_open, stop_loss)
                    exit_reason = "Initial Stop Loss Hit (Swing Low)"
                # 3. Primary Exit: DAILY CLOSE breaks below 11-Day Donchian Trailing SL (NO FIXED TARGET - RUN WINNERS!)
                elif cur_close < trailing_sl:
                    exit_trade = True
                    exit_price = cur_open if cur_open < trailing_sl else cur_close
                    exit_reason = f"Daily Close < 11-Day Donchian SL (₹{trailing_sl:.2f})"

            elif trade_type == "BUY":
                if cur_low <= stop_loss:
                    exit_trade = True
                    exit_price = min(cur_open, stop_loss)
                    exit_reason = "Stop Loss Hit"
                elif cur_high >= target_2:
                    exit_trade = True
                    exit_price = max(cur_open, target_2)
                    exit_reason = "Target 2 Hit (Max)"
                elif cur_high >= target_1 and (i - entry_idx >= 5):
                    # Exit at T1 if holding > 5 bars or momentum slows
                    exit_trade = True
                    exit_price = max(cur_open, target_1)
                    exit_reason = "Target 1 Hit"
                elif (i - entry_idx) >= 20:  # Time-based expiration
                    exit_trade = True
                    exit_price = cur_close
                    exit_reason = "Time Stop (20 Bars)"

            elif trade_type == "SHORT":
                if cur_high >= stop_loss:
                    exit_trade = True
                    exit_price = max(cur_open, stop_loss)
                    exit_reason = "Stop Loss Hit"
                elif cur_low <= target_2:
                    exit_trade = True
                    exit_price = min(cur_open, target_2)
                    exit_reason = "Target 2 Hit (Max)"
                elif cur_low <= target_1 and (i - entry_idx >= 5):
                    exit_trade = True
                    exit_price = min(cur_open, target_1)
                    exit_reason = "Target 1 Hit"
                elif (i - entry_idx) >= 20:
                    exit_trade = True
                    exit_price = cur_close
                    exit_reason = "Time Stop (20 Bars)"

            if exit_trade:
                pnl = (exit_price - entry_price) * shares if trade_type == "BUY" else (entry_price - exit_price) * shares
                pnl_pct = ((exit_price - entry_price) / entry_price * 100) if trade_type == "BUY" else ((entry_price - exit_price) / entry_price * 100)
                capital += pnl

                trades.append({
                    "Entry Date": entry_date.strftime("%Y-%m-%d"),
                    "Exit Date": cur_date.strftime("%Y-%m-%d"),
                    "Type": trade_type,
                    "Shares": shares,
                    "Entry (₹)": round(entry_price, 2),
                    "Exit (₹)": round(exit_price, 2),
                    "P&L (₹)": round(pnl, 2),
                    "Return %": round(pnl_pct, 2),
                    "Exit Reason": exit_reason,
                    "Result": "WIN 🟢" if pnl > 0 else "LOSS 🔴"
                })
                in_trade = False
            continue

        # --- Strategy Signal Scanning ---
        row = df.iloc[i]
        p_row = df.iloc[i - 1]

        signal = None
        s_type = "BUY"
        s_sl = 0.0
        s_t1 = 0.0
        s_t2 = 0.0

        if strategy == "sniper_buy":
            # Hilega-Milega Bull Cross or Bull Zone
            hm_bull_cross = (p_row['Green_EMA3'] <= p_row['Red_WMA21']) and (row['Green_EMA3'] > row['Red_WMA21'])
            hm_bull_zone = (row['Green_EMA3'] > row['Red_WMA21']) and (row['Green_EMA3'] >= 50.0)

            # Trend Craft ICT: Close >= TC_SMA_High or Close > TC_SMA_Low
            tc_high = row.get('TC_SMA_High', row['Close'])
            tc_low = row.get('TC_SMA_Low', row['Close'])
            tc_bull = (row['Close'] >= tc_high) or (row['Close'] > tc_low and row['Close'] > p_row['Close'])

            vol_ratio = row.get('Vol_Ratio', 1.0)
            vol_conf = (vol_ratio >= 1.1) and (row['Close'] >= row['Open'])

            if (hm_bull_cross or hm_bull_zone) and tc_bull and vol_conf:
                signal = True
                s_type = "BUY"
                lowest_5 = float(df['Low'].iloc[max(0, i - 5):i].min())
                s_sl = min(cur_close * 0.97, lowest_5)
                risk = max(cur_close * 0.015, cur_close - s_sl)
                s_t1 = cur_close + (risk * 1.5)
                s_t2 = cur_close + (risk * 2.5)

        elif strategy == "sniper_short":
            hm_bear_cross = (p_row['Green_EMA3'] >= p_row['Red_WMA21']) and (row['Green_EMA3'] < row['Red_WMA21'])
            hm_bear_zone = (row['Green_EMA3'] < row['Red_WMA21']) and (row['Green_EMA3'] < 50.0)

            tc_high = row.get('TC_SMA_High', row['Close'])
            tc_low = row.get('TC_SMA_Low', row['Close'])
            tc_bear = (row['Close'] <= tc_low) or (row['Close'] < tc_high and row['Close'] < p_row['Close'])

            vol_ratio = row.get('Vol_Ratio', 1.0)
            vol_conf = (vol_ratio >= 1.1) and (row['Close'] <= row['Open'])

            if (hm_bear_cross or hm_bear_zone) and tc_bear and vol_conf:
                signal = True
                s_type = "SHORT"
                highest_5 = float(df['High'].iloc[max(0, i - 5):i].max())
                s_sl = max(cur_close * 1.03, highest_5)
                risk = max(cur_close * 0.015, s_sl - cur_close)
                s_t1 = cur_close - (risk * 1.5)
                s_t2 = cur_close - (risk * 2.5)

        elif strategy == "r3_rocket":
            # Pivot calculation from previous day
            pp = (p_row['High'] + p_row['Low'] + p_row['Close']) / 3.0
            r3 = p_row['High'] + 2.0 * (pp - p_row['Low'])
            vol_ratio = row.get('Vol_Ratio', 1.0)

            # Cross above R3 with volume
            if cur_close > r3 and prev_close <= r3 and vol_ratio >= 1.3:
                signal = True
                s_type = "BUY"
                s_sl = float(p_row['Close'])
                risk = max(cur_close * 0.015, cur_close - s_sl)
                s_t1 = cur_close + (risk * 1.5)
                s_t2 = cur_close + (risk * 2.5)

        elif strategy == "ha_trend":
            # Brijesh Bhatia Rule 1: Prior Oversold Correction (Pullback)
            # Sequence of consecutive Red or Doji Heikin Ashi candles (at least 2-3 bars)
            red_cnt = 0
            for k in range(1, min(14, i)):
                b = df.iloc[i - k]
                b_c = b.get('HA_Close', 0)
                b_o = b.get('HA_Open', 1)
                if (b_c <= b_o) or b.get('HA_Is_Doji', False):
                    red_cnt += 1
                else:
                    break

            # Brijesh Bhatia Rule 2: Today is the FIRST Flat-Bottom Bullish Heikin Ashi candle
            ha_c = row.get('HA_Close', 0)
            ha_o = row.get('HA_Open', 0)
            ha_l = row.get('HA_Low', 0)
            ha_body = abs(ha_c - ha_o)
            lower_shadow = max(0.0, ha_o - ha_l)
            
            is_bull_ha = (ha_c > ha_o)
            # Flat Bottom: virtually zero lower wick (lower shadow <= 10% of body or <= 0.1% of price)
            is_flat_bottom = lower_shadow <= max(0.001 * ha_o, ha_body * 0.10)
            is_first_green = is_bull_ha and is_flat_bottom and not row.get('HA_Is_Doji', False)

            # Brijesh Bhatia Rule 3: Macro Trend Filter (Multi-Timeframe Principle)
            # Ensure stock is in overall bullish structure (avoid falling knives in deep bear markets)
            sma = row.get('SMA50', cur_close * 0.95)
            ema = row.get('EMA20', cur_close)
            is_uptrend = (cur_close >= sma) or (ema >= sma) if pd.notna(sma) else True

            # Entry Trigger: Pullback in an uptrend reverses with first Flat Bottom Green HA bar!
            if red_cnt >= 2 and is_first_green and is_uptrend:
                signal = True
                s_type = "BUY"
                # Initial SL placed at the base lowest low of the correction pattern
                base_low = float(df['Low'].iloc[max(0, i - red_cnt - 1):i].min())
                s_sl = min(cur_close * 0.985, base_low * 0.998)
                trailing_sl = s_sl
                s_t1 = cur_close * 1.5
                s_t2 = cur_close * 2.0

        if signal:
            in_trade = True
            entry_idx = i
            entry_date = cur_date
            entry_price = cur_close
            trade_type = s_type
            stop_loss = s_sl
            target_1 = s_t1
            target_2 = s_t2

            # Position Sizing based on risk per trade
            risk_amt = capital * (risk_per_trade_pct / 100.0)
            per_share_risk = abs(entry_price - stop_loss)
            if per_share_risk <= 0.05:
                per_share_risk = entry_price * 0.02

            calc_shares = int(risk_amt / per_share_risk)
            # Ensure not buying more than available capital
            max_shares = int(capital * 0.95 / entry_price)
            shares = max(1, min(calc_shares, max_shares))

    # --- Performance Metrics Calculation ---
    df_trades = pd.DataFrame(trades)
    df_equity = pd.DataFrame(equity_curve)

    total_trades = len(df_trades)
    if total_trades == 0:
        return {
            "symbol": symbol,
            "strategy": STRATEGIES.get(strategy, strategy),
            "period": period,
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "total_trades": 0,
            "win_trades": 0,
            "loss_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "df_trades": pd.DataFrame(),
            "df_equity": df_equity
        }

    win_trades = len(df_trades[df_trades["P&L (₹)"] > 0])
    loss_trades = len(df_trades[df_trades["P&L (₹)"] <= 0])
    win_rate = round((win_trades / total_trades) * 100.0, 1)

    gross_profit = df_trades[df_trades["P&L (₹)"] > 0]["P&L (₹)"].sum()
    gross_loss = abs(df_trades[df_trades["P&L (₹)"] < 0]["P&L (₹)"].sum())
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

    final_capital = capital
    net_pnl = round(final_capital - initial_capital, 2)
    return_pct = round((net_pnl / initial_capital) * 100.0, 2)

    # Max Drawdown calculation
    if not df_equity.empty:
        peak = df_equity["Equity"].cummax()
        drawdown = (df_equity["Equity"] - peak) / peak * 100.0
        max_drawdown = round(abs(drawdown.min()), 2)
    else:
        max_drawdown = 0.0

    return {
        "symbol": symbol,
        "strategy": STRATEGIES.get(strategy, strategy),
        "period": period,
        "initial_capital": initial_capital,
        "final_capital": round(final_capital, 2),
        "net_pnl": net_pnl,
        "return_pct": return_pct,
        "total_trades": total_trades,
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "df_trades": df_trades,
        "df_equity": df_equity
    }
