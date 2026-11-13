"""
Patel Trading Bot - GFS (Grandfather, Father, Son) Multi-Timeframe Swing Paper Trading Engine
Completely isolated from Intraday Options Auto-Algo.
Manages Multi-Day Swing Equity Positions, Profit Targets (+8%, +15%, +25%), Trailing SL, and Portfolio Ledger.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import yfinance as yf
from core.config import get_ist_now, IST_TZ
from core.alerts import send_telegram_alert

GFS_CONFIG_FILE = "gfs_config.json"
GFS_TRADES_FILE = "gfs_trades.json"

DEFAULT_GFS_CONFIG: Dict[str, Any] = {
    "paper_trading_enabled": True,
    "auto_trade_enabled": False,       # Auto-entry when high confidence 3-TF setup is scanned
    "capital_per_trade": 50000.0,       # Default INR per swing position
    "max_active_trades": 10,           # Max simultaneous swing positions
    "target1_pct": 8.0,                # T1: 8%
    "target2_pct": 15.0,               # T2: 15%
    "target3_pct": 25.0,               # T3: 25% (Multibagger runner)
    "stoploss_pct": 4.5,               # Default SL 4.5% if dynamic SL not provided
    "trailing_sl_enabled": True,       # Trail SL to Cost when T1 is reached
    "telegram_alerts": True
}

DEFAULT_GFS_TRADES_DATA: Dict[str, Any] = {
    "active_trades": [],
    "closed_trades": [],
    "stats": {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "total_realized_pnl": 0.0,
        "win_rate": 0.0
    }
}


def load_gfs_config() -> Dict[str, Any]:
    """Loads GFS swing configuration from gfs_config.json safely."""
    if not os.path.exists(GFS_CONFIG_FILE):
        save_gfs_config(DEFAULT_GFS_CONFIG)
        return DEFAULT_GFS_CONFIG.copy()
    try:
        with open(GFS_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            merged = DEFAULT_GFS_CONFIG.copy()
            merged.update(cfg)
            return merged
    except Exception:
        return DEFAULT_GFS_CONFIG.copy()


def save_gfs_config(cfg: Dict[str, Any]):
    """Persists GFS swing configuration to gfs_config.json."""
    try:
        with open(GFS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving GFS config: {e}")


def load_gfs_trades() -> Dict[str, Any]:
    """Loads GFS swing positions and ledger safely from gfs_trades.json."""
    if not os.path.exists(GFS_TRADES_FILE):
        save_gfs_trades(DEFAULT_GFS_TRADES_DATA)
        return DEFAULT_GFS_TRADES_DATA.copy()
    try:
        with open(GFS_TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "active_trades" not in data:
                data["active_trades"] = []
            if "closed_trades" not in data:
                data["closed_trades"] = []
            if "stats" not in data:
                data["stats"] = DEFAULT_GFS_TRADES_DATA["stats"].copy()
            return data
    except Exception:
        return DEFAULT_GFS_TRADES_DATA.copy()


def save_gfs_trades(data: Dict[str, Any]):
    """Persists GFS swing trades to gfs_trades.json."""
    try:
        with open(GFS_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving GFS trades: {e}")


def fetch_live_stock_price(symbol: str) -> Optional[float]:
    """Fetches real-time or latest available price for a stock symbol via yfinance."""
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    yf_symbol = f"{clean_sym}.NS"
    try:
        tkr = yf.Ticker(yf_symbol)
        # Try fast_info first
        p = tkr.fast_info.get("lastPrice", None)
        if p and not (isinstance(p, float) and p != p):  # Check for NaN
            return float(p)
    except Exception:
        pass

    try:
        df = yf.download(yf_symbol, period="2d", interval="1d", progress=False)
        if df is not None and not df.empty:
            close_col = df['Close']
            if hasattr(close_col, 'iloc'):
                val = float(close_col.iloc[-1])
                return val
    except Exception:
        pass
    return None


def execute_gfs_paper_entry(stock_row: Dict[str, Any], custom_capital: Optional[float] = None) -> Tuple[bool, str]:
    """
    Executes a Multi-Timeframe GFS Swing Paper Trade for a given stock.
    Calculates quantity based on allocated capital, sets multi-day targets (+8%, +15%, +25%),
    and dynamic Bollinger/Candle stop loss.
    """
    cfg = load_gfs_config()
    trades_data = load_gfs_trades()

    symbol = str(stock_row.get("Symbol", "")).strip().upper()
    if not symbol:
        return False, "અમાન્ય સ્ટોક સિમ્બોલ."

    # Check for duplicate active trade
    for t in trades_data.get("active_trades", []):
        if t.get("symbol", "").upper() == symbol:
            return False, f"⚠️ {symbol} માટે અગાઉથી એક GFS સ્વિંગ પેપર ટ્રેડ ચાલુ છે."

    # Check max open positions
    max_trades = cfg.get("max_active_trades", 10)
    if len(trades_data.get("active_trades", [])) >= max_trades:
        return False, f"⚠️ મહત્તમ એક્ટિવ સ્વિંગ પોઝિશન્સ ({max_trades}) પૂર્ણ થઈ ગઈ છે."

    entry_price = float(stock_row.get("Price", 0.0))
    if entry_price <= 0:
        return False, f"અમાન્ય સ્ટોક પ્રાઈસ: ₹{entry_price}"

    capital = custom_capital if (custom_capital and custom_capital > 0) else cfg.get("capital_per_trade", 50000.0)
    qty = max(1, int(capital / entry_price))
    invested = round(qty * entry_price, 2)

    # Calculate Targets and Stoploss
    t1_pct = float(cfg.get("target1_pct", 8.0))
    t2_pct = float(cfg.get("target2_pct", 15.0))
    t3_pct = float(cfg.get("target3_pct", 25.0))
    sl_pct = float(cfg.get("stoploss_pct", 4.5))

    # Prefer dynamic GFS stoploss if provided in row, else standard percentage
    default_sl = round(entry_price * (1.0 - (sl_pct / 100.0)), 2)
    sl = float(stock_row.get("StopLoss", default_sl))
    if sl <= 0 or sl >= entry_price:
        sl = default_sl

    t1 = round(float(stock_row.get("Target1", entry_price * (1.0 + (t1_pct / 100.0)))), 2)
    t2 = round(float(stock_row.get("Target2", entry_price * (1.0 + (t2_pct / 100.0)))), 2)
    t3 = round(float(stock_row.get("Target3", entry_price * (1.0 + (t3_pct / 100.0)))), 2)

    now_ist = get_ist_now()
    now_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
    trade_id = f"GFS_{now_ist.strftime('%Y%m%d%H%M%S')}_{symbol}"

    trade = {
        "trade_id": trade_id,
        "symbol": symbol,
        "full_symbol": stock_row.get("FullSymbol", f"{symbol}.NS"),
        "entry_time": now_str,
        "entry_date": now_ist.strftime("%Y-%m-%d"),
        "entry_price": round(entry_price, 2),
        "quantity": qty,
        "invested_amount": invested,
        "current_price": round(entry_price, 2),
        "stop_loss": round(sl, 2),
        "trailing_sl_price": round(sl, 2),
        "trailing_sl_active": False,
        "target1": t1,
        "target2": t2,
        "target3": t3,
        "unrealized_pnl": 0.0,
        "unrealized_pnl_pct": 0.0,
        "target1_hit": False,
        "target2_hit": False,
        "target3_hit": False,
        "gfs_badge": stock_row.get("GFS_Badge", "💥 GFS 3-TF BUY"),
        "gfs_action": stock_row.get("GFS_Action", "GFS Swing Trade"),
        "rsi_m": float(stock_row.get("RSI_M", 0.0)),
        "rsi_w": float(stock_row.get("RSI_W", 0.0)),
        "rsi_d": float(stock_row.get("RSI_D", 0.0)),
        "candle_pattern": stock_row.get("Candle_Pattern", "STANDARD"),
        "status": "OPEN"
    }

    trades_data["active_trades"].append(trade)
    save_gfs_trades(trades_data)

    # Telegram Alert
    if cfg.get("telegram_alerts", True):
        risk_pct = round(((entry_price - sl) / entry_price) * 100.0, 1)
        tg_msg = (
            f"🏔️ <b>NEW GFS MULTI-TIMEFRAME SWING PAPER TRADE</b>\n\n"
            f"📈 <b>Stock:</b> {symbol}\n"
            f"💵 <b>Entry Price:</b> ₹{entry_price:.2f}\n"
            f"📦 <b>Quantity:</b> {qty} Shares\n"
            f"💰 <b>Capital Invested:</b> ₹{invested:,.2f}\n"
            f"🛡️ <b>Swing SL:</b> ₹{sl:.2f} (-{risk_pct}%)\n"
            f"🎯 <b>Target 1 (+{t1_pct}%):</b> ₹{t1:.2f}\n"
            f"🎯 <b>Target 2 (+{t2_pct}%):</b> ₹{t2:.2f}\n"
            f"🚀 <b>Target 3 (+{t3_pct}%):</b> ₹{t3:.2f}\n"
            f"📊 <b>GFS Confluence:</b> {trade['gfs_badge']}\n"
            f"👴 M-RSI: {trade['rsi_m']:.1f} | 👨 W-RSI: {trade['rsi_w']:.1f} | 👦 D-RSI: {trade['rsi_d']:.1f}\n"
            f"⏰ <b>Entry Time:</b> {now_str} IST\n"
            f"<i>Mode: GFS Swing Paper Trading</i>"
        )
        try:
            send_telegram_alert(tg_msg)
        except Exception:
            pass

    return True, f"✅ {symbol} માટે {qty} શેર્સનો GFS સ્વિંગ પેપર ટ્રેડ (મૂડી ₹{invested:,.2f}) સફળતાપૂર્વક શરૂ થઈ ગયો છે!"


def close_gfs_paper_trade(
    trade_id: str,
    exit_reason: str = "MANUAL_EXIT",
    exit_price: Optional[float] = None
) -> Tuple[bool, str]:
    """Closes an active GFS swing paper trade, records realized P&L, holding period, and updates stats."""
    trades_data = load_gfs_trades()
    cfg = load_gfs_config()

    target_idx = None
    for idx, t in enumerate(trades_data.get("active_trades", [])):
        if t.get("trade_id") == trade_id:
            target_idx = idx
            break

    if target_idx is None:
        return False, "ટ્રેડ આઈડી મળ્યો નથી."

    trade = trades_data["active_trades"].pop(target_idx)
    now_ist = get_ist_now()
    exit_time_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")

    # Determine final exit price
    if exit_price is None or exit_price <= 0:
        latest_p = fetch_live_stock_price(trade["symbol"])
        exit_price = latest_p if latest_p else trade.get("current_price", trade["entry_price"])

    exit_price = round(float(exit_price), 2)
    entry_price = float(trade["entry_price"])
    qty = int(trade["quantity"])

    realized_pnl = round((exit_price - entry_price) * qty, 2)
    realized_pnl_pct = round(((exit_price - entry_price) / entry_price) * 100.0, 2)

    # Calculate holding days
    holding_days = 0
    try:
        e_date = datetime.strptime(trade["entry_date"], "%Y-%m-%d").date()
        holding_days = max(0, (now_ist.date() - e_date).days)
    except Exception:
        pass

    closed_record = {
        "trade_id": trade["trade_id"],
        "symbol": trade["symbol"],
        "entry_time": trade["entry_time"],
        "entry_date": trade["entry_date"],
        "exit_time": exit_time_str,
        "exit_date": now_ist.strftime("%Y-%m-%d"),
        "holding_days": holding_days,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": qty,
        "invested_amount": trade["invested_amount"],
        "realized_pnl": realized_pnl,
        "realized_pnl_pct": realized_pnl_pct,
        "exit_reason": exit_reason,
        "gfs_badge": trade.get("gfs_badge", ""),
        "status": "CLOSED"
    }

    trades_data["closed_trades"].insert(0, closed_record)

    # Update stats
    stats = trades_data.get("stats", {})
    all_closed = trades_data["closed_trades"]
    stats["total_trades"] = len(all_closed)
    stats["wins"] = sum(1 for c in all_closed if c.get("realized_pnl", 0.0) > 0)
    stats["losses"] = sum(1 for c in all_closed if c.get("realized_pnl", 0.0) < 0)
    stats["total_realized_pnl"] = round(sum(c.get("realized_pnl", 0.0) for c in all_closed), 2)
    stats["win_rate"] = round((stats["wins"] / stats["total_trades"]) * 100.0, 1) if stats["total_trades"] > 0 else 0.0
    trades_data["stats"] = stats

    save_gfs_trades(trades_data)

    # Telegram Alert
    if cfg.get("telegram_alerts", True):
        res_emoji = "🟢 PROFIT" if realized_pnl >= 0 else "🔴 LOSS"
        tg_msg = (
            f"🏔️ <b>GFS SWING TRADE SQUARED OFF ({res_emoji})</b>\n\n"
            f"📈 <b>Stock:</b> {trade['symbol']}\n"
            f"💵 <b>Entry:</b> ₹{entry_price:.2f} ➔ <b>Exit:</b> ₹{exit_price:.2f}\n"
            f"📦 <b>Qty:</b> {qty} | 📅 <b>Holding:</b> {holding_days} Days\n"
            f"💰 <b>Realized P&L:</b> ₹{realized_pnl:+,.2f} ({realized_pnl_pct:+.2f}%)\n"
            f"🎯 <b>Exit Reason:</b> {exit_reason}\n"
            f"⏰ <b>Exit Time:</b> {exit_time_str} IST"
        )
        try:
            send_telegram_alert(tg_msg)
        except Exception:
            pass

    return True, f"✅ {trade['symbol']} સફળતાપૂર્વક સ્ક્વેર ઓફ થયો. Realized P&L: ₹{realized_pnl:+,.2f} ({realized_pnl_pct:+.2f}%)"


def monitor_gfs_paper_positions(price_cache: Optional[Dict[str, float]] = None) -> List[str]:
    """
    Monitors all active GFS swing positions:
    - Updates LTP and unrealized P&L
    - Checks Target 1 (+8%), Target 2 (+15%), Target 3 (+25%)
    - Implements Trailing Stop Loss to Cost/Breakeven upon reaching Target 1
    - Auto-closes position if Target 3 or Stop Loss is reached
    """
    trades_data = load_gfs_trades()
    active_list = trades_data.get("active_trades", [])
    if not active_list:
        return []

    cfg = load_gfs_config()
    logs = []
    trades_to_close = []

    for t in active_list:
        sym = t["symbol"]
        current_p = None
        if price_cache and sym in price_cache and price_cache[sym] > 0:
            current_p = price_cache[sym]
        else:
            current_p = fetch_live_stock_price(sym)

        if not current_p or current_p <= 0:
            continue

        current_p = round(float(current_p), 2)
        entry_p = float(t["entry_price"])
        qty = int(t["quantity"])

        t["current_price"] = current_p
        t["unrealized_pnl"] = round((current_p - entry_p) * qty, 2)
        t["unrealized_pnl_pct"] = round(((current_p - entry_p) / entry_p) * 100.0, 2)

        t1 = float(t.get("target1", entry_p * 1.08))
        t2 = float(t.get("target2", entry_p * 1.15))
        t3 = float(t.get("target3", entry_p * 1.25))
        sl = float(t.get("trailing_sl_price", t.get("stop_loss", entry_p * 0.95)))

        # Target 1 Check (+8%)
        if current_p >= t1 and not t.get("target1_hit", False):
            t["target1_hit"] = True
            if cfg.get("trailing_sl_enabled", True):
                t["trailing_sl_active"] = True
                t["trailing_sl_price"] = entry_p  # Move SL to Cost
            logs.append(f"🎯 GFS Target 1 Hit for {sym} (+8%) at ₹{current_p:.2f}! Trailing SL moved to Cost ₹{entry_p:.2f}")
            if cfg.get("telegram_alerts", True):
                try:
                    send_telegram_alert(
                        f"🎯 <b>GFS TARGET 1 HIT (+8%)!</b>\n\n"
                        f"📈 <b>{sym}</b> reached ₹{current_p:.2f}\n"
                        f"🛡️ Trailing Stop Loss moved to Breakeven (Cost): ₹{entry_p:.2f}\n"
                        f"💰 Unrealized P&L: ₹{t['unrealized_pnl']:+,.2f} ({t['unrealized_pnl_pct']:+.2f}%)"
                    )
                except Exception:
                    pass

        # Target 2 Check (+15%)
        if current_p >= t2 and not t.get("target2_hit", False):
            t["target2_hit"] = True
            if cfg.get("trailing_sl_enabled", True):
                t["trailing_sl_price"] = t1  # Lock in Target 1 profit
            logs.append(f"🎯 GFS Target 2 Hit for {sym} (+15%) at ₹{current_p:.2f}! Trailing SL locked at T1 ₹{t1:.2f}")
            if cfg.get("telegram_alerts", True):
                try:
                    send_telegram_alert(
                        f"🚀 <b>GFS TARGET 2 HIT (+15%)!</b>\n\n"
                        f"📈 <b>{sym}</b> reached ₹{current_p:.2f}\n"
                        f"🛡️ Trailing Stop Loss locked at Target 1: ₹{t1:.2f}\n"
                        f"💰 Unrealized P&L: ₹{t['unrealized_pnl']:+,.2f} ({t['unrealized_pnl_pct']:+.2f}%)"
                    )
                except Exception:
                    pass

        # Target 3 Jackpot Check (+25%) -> Auto Exit
        if current_p >= t3:
            logs.append(f"🏆 GFS Target 3 Jackpot (+25%) Hit for {sym} at ₹{current_p:.2f}!")
            trades_to_close.append((t["trade_id"], "🎯 TARGET 3 HIT (+25% JACKPOT)", current_p))
            continue

        # Stop Loss Check (Trailing or Initial)
        active_sl = float(t.get("trailing_sl_price", t.get("stop_loss", entry_p * 0.95)))
        if current_p <= active_sl:
            reason = "🛡️ TRAILING SL HIT (Protected Profit / Breakeven)" if t.get("trailing_sl_active", False) else "🛑 STOPLOSS HIT"
            logs.append(f"{reason} for {sym} at ₹{current_p:.2f}")
            trades_to_close.append((t["trade_id"], reason, current_p))
            continue

    save_gfs_trades(trades_data)

    # Execute auto closures
    for tr_id, reason, px in trades_to_close:
        close_gfs_paper_trade(tr_id, exit_reason=reason, exit_price=px)

    return logs
