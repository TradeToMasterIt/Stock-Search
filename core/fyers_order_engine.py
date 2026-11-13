"""
Patel Trading Bot - Fyers Auto-Algo Order Execution Engine
Supports Paper Trading (Demo Mode) and Live Fyers API Broker Trading.
Implements Institutional Risk Guards, Position Sizing, 3-Stage Profit Booking & Trailing Stoploss.
"""

import os
import json
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from core.config import get_ist_now, is_market_open, IST_TZ
from core.alerts import send_telegram_alert

ALGO_CONFIG_FILE = "algo_config.json"
ALGO_TRADES_FILE = "algo_trades.json"

# Standard NSE F&O Lot Sizes (Indexed by clean symbol)
NSE_LOT_SIZES = {
    # Major Indices
    "NIFTY": 25,
    "NIFTY 50": 25,
    "BANKNIFTY": 15,
    "BANK NIFTY": 15,
    "FINNIFTY": 25,
    "SENSEX": 10,
    "BANKEX": 15,
    
    # Heavyweight F&O Stocks
    "RELIANCE": 250,
    "TCS": 175,
    "INFY": 400,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "SBIN": 750,
    "BHARTIARTL": 475,
    "LT": 150,
    "KOTAKBANK": 400,
    "AXISBANK": 625,
    "TATASTEEL": 5500,
    "DLF": 825,
    "TATAMOTORS": 1425,
    "BAJFINANCE": 125,
    "ITC": 1600,
    "MARUTI": 50,
    "SUNPHARMA": 350,
    "TITAN": 175,
    "HCLTECH": 350,
    "WIPRO": 1500,
    "TECHM": 300,
    "M&M": 350,
    "ADANIENT": 300,
    "ADANIPORTS": 400,
    "BEL": 2850,
    "HAL": 150,
    "BHEL": 2625,
    "COALINDIA": 2100,
    "NTPC": 1500,
    "POWERGRID": 1800,
    "BPCL": 1800,
    "ONGC": 2250,
    "TRENT": 100,
    "DIXON": 50,
    "POLYCAB": 75,
    "SUZLON": 10000,
    "VEDL": 1150,
    "JIOFIN": 2000,
    "ZOMATO": 2000,
    "PERSISTENT": 100,
    "COFORGE": 75,
    "SIEMENS": 75,
    "ABB": 62,
    "CUMMINSIND": 150,
    "HAVELLS": 250,
    "CHOLAFIN": 625,
    "SHRIRAMFIN": 300,
    "MUTHOOTFIN": 275,
    "DRREDDY": 62,
    "CIPLA": 325,
    "DIVISLAB": 100,
    "EICHERMOT": 175,
    "HEROMOTOCO": 150,
    "TVSMOTOR": 175,
    "BAJAJFINSV": 250,
    "INDUSINDBK": 250,
    "ULTRACEMCO": 50,
    "GRASIM": 225,
    "AMBUJACEM": 900,
    "ACC": 150
}

def get_lot_size(symbol: str) -> int:
    """Returns lot size for given stock/index, defaulting to 100 for unknown equities."""
    clean = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    return NSE_LOT_SIZES.get(clean, 100)

# -------------------------------------------------------------
# Configuration Manager
# -------------------------------------------------------------
DEFAULT_ALGO_CONFIG = {
    "is_enabled": True,
    "mode": "PAPER",                     # "PAPER" (Demo) or "LIVE" (Fyers Real Broker)
    "trading_basket": "ALL",            # "ALL", "INDICES", or "MOMENTUM"
    "trading_direction": "BOTH",        # "BOTH", "CALL_ONLY", or "PUT_ONLY"
    "max_risk_per_trade": 1500.0,       # Risk per trade (1.5% of 1L)
    "max_capital_per_trade": 15000.0,   # Max margin allocated per trade
    "daily_max_loss": 3000.0,           # Daily Kill-Switch limit
    "max_open_positions": 2,            # Max active concurrent positions
    "target_1_ratio": 1.5,              # 1:1.5 RR (First 50% exit)
    "target_2_ratio": 2.5,              # 1:2.5 RR (Next 30% exit)
    "t1_qty_exit_pct": 50,              # Exit 50% on T1
    "t2_qty_exit_pct": 30,              # Exit 30% on T2
    "trail_t1_to_cost": True,           # Move SL to Entry price on T1 (Zero Risk)
    "auto_square_off_time": "15:15",    # Intraday auto exit
    "start_time": "09:20",              # Skip first 5 mins opening volatility
    "end_time": "15:00",                # No new trades after 15:00
    "kill_switch_triggered": False,
    "last_reset_date": ""
}

def load_algo_config() -> Dict[str, Any]:
    """Loads algo configuration, creating default file if missing."""
    today_str = get_ist_now().strftime("%Y-%m-%d")
    cfg = DEFAULT_ALGO_CONFIG.copy()
    if os.path.exists(ALGO_CONFIG_FILE):
        try:
            with open(ALGO_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
            
    # Reset daily kill-switch on new trading day
    if cfg.get("last_reset_date") != today_str:
        cfg["kill_switch_triggered"] = False
        cfg["last_reset_date"] = today_str
        save_algo_config(cfg)
        
    return cfg

def save_algo_config(cfg: Dict[str, Any]):
    """Persists algo configuration to disk."""
    try:
        with open(ALGO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving algo config: {e}")

# -------------------------------------------------------------
# Trades State Manager
# -------------------------------------------------------------
def load_algo_trades() -> Dict[str, Any]:
    """Loads active and closed algo trades."""
    today_str = get_ist_now().strftime("%Y-%m-%d")
    default_data = {
        "active_trades": [],
        "closed_trades": [],
        "daily_summary": {
            "date": today_str,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0
        }
    }
    if not os.path.exists(ALGO_TRADES_FILE):
        return default_data
    try:
        with open(ALGO_TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("daily_summary", {}).get("date") != today_str:
                # Archive past days' closed trades and start fresh daily ledger
                past_closed = data.get("closed_trades", [])
                archived = data.get("archived_trades", [])
                archived.extend(past_closed)
                data["archived_trades"] = archived
                data["closed_trades"] = []
                data["daily_summary"] = default_data["daily_summary"]
                try:
                    with open(ALGO_TRADES_FILE, "w", encoding="utf-8") as fw:
                        json.dump(data, fw, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            return data
    except Exception:
        return default_data

def save_algo_trades(data: Dict[str, Any]):
    """Saves algo trades state to disk."""
    try:
        with open(ALGO_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving algo trades: {e}")

# -------------------------------------------------------------
# Position Sizing & Lot Calculator
# -------------------------------------------------------------
def calculate_algo_quantity(
    symbol: str, 
    entry_price: float, 
    stop_loss: float, 
    cfg: Dict[str, Any]
) -> Tuple[int, int, int, float]:
    """
    Computes exact lot size & total quantity respecting 1-2% capital risk and max capital limits.
    Returns: (lots, total_qty, lot_size, allocated_capital)
    """
    lot_size = get_lot_size(symbol)
    risk_per_share = max(0.50, entry_price - stop_loss)
    max_risk = float(cfg.get("max_risk_per_trade", 1500.0))
    max_capital = float(cfg.get("max_capital_per_trade", 15000.0))
    
    # 1. Quantity derived from maximum risk tolerance
    raw_qty = max_risk / risk_per_share
    lots_by_risk = max(1, int(round(raw_qty / lot_size)))
    
    # 2. Capital constraint check
    total_investment = lots_by_risk * lot_size * entry_price
    if total_investment > max_capital:
        lots_by_capital = max(1, int(math.floor(max_capital / (lot_size * entry_price))))
        final_lots = min(lots_by_risk, lots_by_capital)
    else:
        final_lots = lots_by_risk
        
    final_lots = max(1, final_lots)
    total_qty = final_lots * lot_size
    allocated_capital = round(total_qty * entry_price, 2)
    
    return final_lots, total_qty, lot_size, allocated_capital

# -------------------------------------------------------------
# Live Order Placement via Fyers API v3
# -------------------------------------------------------------
def place_fyers_broker_order(
    symbol: str,
    qty: int,
    side: int,  # 1 = Buy, -1 = Sell
    order_type: int = 2,  # 2 = Market, 1 = Limit
    limit_price: float = 0.0,
    stop_price: float = 0.0
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Executes live market/limit order through Fyers API v3.
    """
    try:
        from core.fyers_auth import get_fyers_client
        ok_fyers, fyers_client = get_fyers_client()
        if not ok_fyers or not fyers_client:
            return False, f"Fyers Authentication Failed: {fyers_client}", {}
            
        order_data = {
            "symbol": symbol,
            "qty": int(qty),
            "type": order_type,
            "side": side,
            "productType": "INTRADAY",
            "limitPrice": float(limit_price),
            "stopPrice": float(stop_price),
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False
        }
        res = fyers_client.place_order(data=order_data)
        if isinstance(res, dict) and res.get("s") == "ok":
            order_id = res.get("id", "LIVE_ORDER")
            return True, order_id, res
        else:
            err_msg = res.get("message", str(res)) if isinstance(res, dict) else str(res)
            return False, err_msg, res if isinstance(res, dict) else {}
    except Exception as ex:
        return False, f"Exception placing Fyers order: {str(ex)}", {}

# -------------------------------------------------------------
# Quote Calibration & Trade Closure Helpers
# -------------------------------------------------------------
def _resolve_spot_yf_symbol(sym: str) -> str:
    """Maps NSE/BSE symbol names to Yahoo Finance spot tickers."""
    clean = str(sym or "").strip().upper()
    idx_yf_map = {
        "NIFTY": "^NSEI",
        "NIFTY 50": "^NSEI",
        "^NSEI": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "NIFTYBANK": "^NSEBANK",
        "^NSEBANK": "^NSEBANK",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
        "NIFTY_FIN_SERVICE": "NIFTY_FIN_SERVICE.NS",
        "MIDCPNIFTY": "NIFTY_MIDCAP_100.NS",
        "SENSEX": "^BSESN",
        "BSESN": "^BSESN",
        "^BSESN": "^BSESN",
        "BANKEX": "BSE-BANK.BO",
    }
    base = clean.replace(".NS", "").replace(".BO", "")
    if clean in idx_yf_map:
        return idx_yf_map[clean]
    if base in idx_yf_map:
        return idx_yf_map[base]
    if clean.startswith("^") or clean.endswith(".NS") or clean.endswith(".BO"):
        return clean
    return f"{base}.NS"


def _extract_valid_fyers_ltp(q_res: Any) -> Optional[float]:
    """Extracts a verified positive LTP from Fyers quotes response, else None."""
    if not isinstance(q_res, dict) or q_res.get("s") != "ok":
        return None
    items = q_res.get("d")
    if not isinstance(items, list) or not items:
        return None
    item = items[0] if isinstance(items[0], dict) else {}
    if item.get("s") == "error":
        return None
    val = item.get("v") or {}
    raw_lp = val.get("lp")
    if raw_lp is None:
        return None
    try:
        lp = float(raw_lp)
    except (TypeError, ValueError):
        return None
    return lp if lp > 0 else None


def _estimate_paper_option_ltp_from_spot(tr: Dict[str, Any]) -> Optional[float]:
    """
    Paper-mode fallback when broker option quotes are unavailable:
    approximates option premium change from underlying spot move via ~0.42 ATM/OTM delta.
    """
    spot_entry = float(tr.get("spot_entry_price") or 0.0)
    entry_price = float(tr.get("entry_price") or 0.0)
    if spot_entry <= 0 or entry_price <= 0:
        return None

    yf_sym = tr.get("spot_yf_symbol") or _resolve_spot_yf_symbol(tr.get("symbol", ""))
    try:
        import yfinance as yf
        hist = yf.Ticker(yf_sym).history(period="1d", interval="1m")
        if hist is None or hist.empty:
            return None
        spot_now = float(hist["Close"].iloc[-1])
        if spot_now <= 0:
            return None
    except Exception:
        return None

    opt_type = str(tr.get("opt_type", "CE")).upper()
    direction = 1.0 if opt_type == "CE" else -1.0
    delta_approx = 0.42
    est_ltp = entry_price + ((spot_now - spot_entry) * direction * delta_approx)
    min_floor = max(0.05, round(entry_price * 0.05, 2))
    return round(max(min_floor, est_ltp), 2)


def _fetch_live_or_paper_option_ltp(
    fyers_client: Any,
    safe_fyers_quotes_fn: Any,
    tr: Dict[str, Any],
) -> Tuple[float, bool, str]:
    """Returns (ltp, quote_ok, quote_source). Never fabricates a triggerable quote from entry_price."""
    fyers_sym = tr.get("fyers_symbol", "")
    if fyers_client and safe_fyers_quotes_fn and fyers_sym:
        try:
            q_res = safe_fyers_quotes_fn(fyers_client, {"symbols": fyers_sym})
            live_lp = _extract_valid_fyers_ltp(q_res)
            if live_lp is not None:
                return round(live_lp, 2), True, "FYERS"
        except Exception:
            pass

    if tr.get("mode", "PAPER") == "PAPER":
        paper_lp = _estimate_paper_option_ltp_from_spot(tr)
        if paper_lp is not None and paper_lp > 0:
            return round(paper_lp, 2), True, "PAPER_YF_SPOT"

    fallback_ltp = float(tr.get("last_valid_price") or tr.get("current_price") or tr.get("entry_price") or 0.0)
    return round(fallback_ltp, 2), False, "UNAVAILABLE"


def finalize_algo_trade_closure(
    tr: Dict[str, Any],
    status: str,
    exit_price: float,
    final_slice_pnl: float,
    closed_trades: List[Dict[str, Any]],
    daily_summary: Dict[str, Any],
    now_ist: Optional[datetime] = None,
) -> float:
    """
    Reconciles partial T1/T2 bookings with the final exit slice, writes tr['realized_pnl'],
    updates daily_summary totals, and counts wins strictly on positive net P&L (> 0).
    """
    if now_ist is None:
        now_ist = get_ist_now()

    booked_pnl = float(tr.get("booked_pnl", 0.0) or 0.0)
    final_slice = float(final_slice_pnl or 0.0)
    total_trade_pnl = round(booked_pnl + final_slice, 2)

    tr["status"] = status
    tr["exit_price"] = round(float(exit_price), 2)
    tr["exit_time"] = now_ist.strftime("%d %b %Y | %H:%M:%S IST")
    tr["realized_pnl"] = total_trade_pnl
    closed_trades.append(tr)

    # T1/T2 partial profits were already added to daily_summary['realized_pnl'] when hit,
    # so add only the closing slice here to keep daily_summary synced with trade history.
    daily_summary["realized_pnl"] = round(float(daily_summary.get("realized_pnl", 0.0) or 0.0) + final_slice, 2)
    daily_summary["total_trades"] = int(daily_summary.get("total_trades", 0) or 0) + 1

    if total_trade_pnl > 0:
        daily_summary["winning_trades"] = int(daily_summary.get("winning_trades", 0) or 0) + 1
    elif total_trade_pnl < 0:
        daily_summary["losing_trades"] = int(daily_summary.get("losing_trades", 0) or 0) + 1
    else:
        daily_summary["breakeven_trades"] = int(daily_summary.get("breakeven_trades", 0) or 0) + 1

    return total_trade_pnl


# -------------------------------------------------------------
# Core Algo Entry Trigger
# -------------------------------------------------------------
def execute_algo_entry(scan_res: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Evaluates entry conditions and automatically executes order (Paper or Live).
    Triggered when 100% Confirmed Buy (Spot R2 + Option Daily R3 + 5m RSI 58-74 + Vol >= 1.2x) fires.
    """
    cfg = load_algo_config()
    
    # Safety Check 1: Is Algo Enabled?
    if not cfg.get("is_enabled", False):
        return False, "Algo Trading is PAUSED in settings"
        
    # Safety Check 2: Kill-Switch Check
    if cfg.get("kill_switch_triggered", False):
        return False, "Daily Kill-Switch is ACTIVE (Max Loss Hit)"
        
    # Safety Check 3: Time Window Check (09:20 to 15:00 IST)
    now_ist = get_ist_now()
    curr_time_str = now_ist.strftime("%H:%M")
    if curr_time_str < cfg.get("start_time", "09:20") or curr_time_str > cfg.get("end_time", "15:00"):
        return False, f"Outside Algo Entry Time Window ({curr_time_str} IST)"
        
    # Safety Check 4: Market Hours
    market_open, _ = is_market_open()
    if not market_open:
        return False, "Market is Closed"
        
    trades_data = load_algo_trades()
    active_trades = trades_data.get("active_trades", [])
    
    # Safety Check 5: Max Open Positions
    max_open = int(cfg.get("max_open_positions", 2))
    if len(active_trades) >= max_open:
        return False, f"Max concurrent positions reached ({len(active_trades)}/{max_open})"
        
    sym = scan_res.get("symbol", "")
    opt_type = scan_res.get("opt_type", "CE")

    # Safety Check 5.2: Direction Filter (BOTH / CALL_ONLY / PUT_ONLY)
    trading_dir = cfg.get("trading_direction", "BOTH")
    if trading_dir == "CALL_ONLY" and opt_type == "PE":
        return False, f"Skipped {sym}: Algo is restricted to CALL ONLY in settings"
    elif trading_dir == "PUT_ONLY" and opt_type == "CE":
        return False, f"Skipped {sym}: Algo is restricted to PUT ONLY in settings"

    # Safety Check 5.3: Anti-FOMO Chasing Guard (Never chase >8% above R3)
    if scan_res.get("is_chasing", False) or (opt_type == "PE" and scan_res.get("is_put_chasing", False)):
        return False, f"Skipped {sym}: Price is overextended (>8% above Option R3 level)"

    # Safety Check 5.4: Late Session (14:15 - 15:00 IST) Volume Guard
    if curr_time_str > "14:15" and not scan_res.get("is_gamma_blast", False):
        v_rat = float(scan_res.get("vol_5m", scan_res.get("vol_ratio", 1.0)))
        if v_rat < 1.5:
            return False, f"Skipped {sym}: Post-14:15 non-gamma trade requires >= 1.5x volume (current: {v_rat:.1f}x)"

    # Select exact Call or Put symbols and levels
    if opt_type == "PE":
        fyers_sym = scan_res.get("opt_put_fyers_symbol", scan_res.get("opt_fyers_symbol", ""))
        contract_name = scan_res.get("opt_put_contract_name", scan_res.get("opt_contract_name", f"{sym} OTM Put"))
        entry_price = float(scan_res.get("opt_put_ltp", scan_res.get("opt_ltp", 0.0)))
        stop_loss = float(scan_res.get("opt_put_sl", entry_price * 0.80))
        target_1 = float(scan_res.get("opt_put_t1", entry_price * 1.35))
        target_2 = float(scan_res.get("opt_put_t2", entry_price * 1.70))
    else:
        fyers_sym = scan_res.get("opt_fyers_symbol", "")
        contract_name = scan_res.get("opt_contract_name", f"{sym} OTM Call")
        entry_price = float(scan_res.get("opt_ltp", 0.0))
        stop_loss = float(scan_res.get("opt_sl", entry_price * 0.75))
        target_1 = float(scan_res.get("opt_t1", entry_price * 1.35))
        target_2 = float(scan_res.get("opt_t2", entry_price * 1.70))

    if entry_price <= 0:
        entry_price = float(scan_res.get("price", 0.0))

    # Ensure option stoploss and targets are ALWAYS calibrated to option entry price (never spot stock/index price)
    if stop_loss >= entry_price or stop_loss <= 0:
        stop_loss = round(entry_price * 0.75, 2)
    if target_1 <= entry_price or target_1 > entry_price * 2.5:
        target_1 = round(entry_price * 1.35, 2)
    if target_2 <= target_1 or target_2 > entry_price * 3.5:
        target_2 = round(entry_price * 1.70, 2)

    # Safety Check 5.5: Basket Filter (All / Indices / Momentum)
    basket_choice = cfg.get("trading_basket", "ALL")
    from core.option_r3_engine import is_index_symbol, TOP_MOMENTUM_FNO_BASKET
    if basket_choice == "INDICES" and not is_index_symbol(sym):
        return False, f"Skipped {sym}: Algo is restricted to INDICES ONLY in settings"
    elif basket_choice == "MOMENTUM":
        clean_s = sym.replace(".NS", "").replace(".BO", "").strip().upper()
        allowed = [s.replace(".NS", "").replace(".BO", "").strip().upper() for s in TOP_MOMENTUM_FNO_BASKET]
        if not is_index_symbol(sym) and clean_s not in allowed:
            return False, f"Skipped {sym}: Algo is restricted to TOP MOMENTUM F&O ONLY in settings"
            
    # Safety Check 6: Duplicate Position Prevention
    for tr in active_trades:
        if tr.get("symbol") == sym or tr.get("fyers_symbol") == fyers_sym:
            return False, f"Position already active for {sym}"
    
    lots, total_qty, lot_size, allocated_capital = calculate_algo_quantity(
        symbol=sym,
        entry_price=entry_price,
        stop_loss=stop_loss,
        cfg=cfg
    )
    
    trade_id = f"ALG_{now_ist.strftime('%Y%m%d%H%M%S')}_{sym}"
    trade_mode = cfg.get("mode", "PAPER")
    
    order_id = "SIMULATED_PAPER_ORDER"
    if trade_mode == "LIVE":
        ok_order, order_id_or_err, raw_res = place_fyers_broker_order(
            symbol=fyers_sym,
            qty=total_qty,
            side=1,  # Buy
            order_type=2 # Market Order for instant execution
        )
        if not ok_order:
            err_alert = (
                f"🚨 <b>FYERS LIVE ALGO ORDER FAILED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Stock:</b> {sym} ({contract_name})\n"
                f"• <b>Symbol:</b> <code>{fyers_sym}</code>\n"
                f"• <b>Error:</b> {order_id_or_err}\n"
                f"• ⏰ {now_ist.strftime('%H:%M:%S IST')}"
            )
            send_telegram_alert(err_alert)
            return False, f"Fyers Order Failed: {order_id_or_err}"
        order_id = order_id_or_err
        
    is_synthetic_test = bool(scan_res.get("is_synthetic_test", False))
    spot_entry_price = 0.0
    if not is_synthetic_test:
        raw_spot = scan_res.get("spot_price")
        if raw_spot is not None:
            spot_entry_price = float(raw_spot or 0.0)
        elif scan_res.get("price") is not None and (
            float(scan_res.get("opt_ltp", 0.0) or 0.0) > 0
            or float(scan_res.get("opt_put_ltp", 0.0) or 0.0) > 0
        ):
            spot_entry_price = float(scan_res.get("price") or 0.0)
    spot_yf_symbol = _resolve_spot_yf_symbol(sym)

    # Record Active Trade
    new_trade = {
        "id": trade_id,
        "symbol": sym,
        "opt_type": opt_type,
        "contract_name": contract_name,
        "fyers_symbol": fyers_sym,
        "mode": trade_mode,
        "entry_price": round(entry_price, 2),
        "current_price": round(entry_price, 2),
        "last_valid_price": round(entry_price, 2),
        "spot_entry_price": round(spot_entry_price, 2),
        "spot_yf_symbol": spot_yf_symbol,
        "initial_qty": total_qty,
        "remaining_qty": total_qty,
        "lots": lots,
        "lot_size": lot_size,
        "stop_loss": round(stop_loss, 2),
        "initial_stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "allocated_capital": allocated_capital,
        "entry_time": now_ist.strftime("%d %b %Y | %H:%M:%S IST"),
        "t1_hit": False,
        "t2_hit": False,
        "booked_pnl": 0.0,
        "order_id": order_id,
        "status": "ACTIVE",
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0
    }
    
    active_trades.append(new_trade)
    trades_data["active_trades"] = active_trades
    save_algo_trades(trades_data)
    
    # Save to SQLite database for historical reporting
    try:
        from core.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades 
                (id, symbol, full_symbol, trade_type, entry_price, qty, entry_date, stop_loss, target_1, target_2, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, sym, fyers_sym, f"ALGO_{trade_mode}", entry_price, total_qty, now_ist.isoformat(), stop_loss, target_1, target_2, "ACTIVE")
            )
            conn.commit()
    except Exception:
        pass
        
    # Dispatch Instant Telegram Notification
    mode_icon = "🟢 [LIVE BROKER ORDER]" if trade_mode == "LIVE" else "📄 [PAPER SIMULATION ORDER]"
    telegram_msg = (
        f"🤖 <b>FYERS AUTO-ALGO ORDER EXECUTED!</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Status:</b> {mode_icon}\n"
        f"• <b>Instrument:</b> {sym} ({contract_name})\n"
        f"• <b>Fyers Symbol:</b> <code>{fyers_sym}</code>\n"
        f"• <b>Action:</b> BUY (Call Option / CE)\n"
        f"• <b>Lots / Qty:</b> <b>{lots} Lots</b> ({total_qty} Shares)\n"
        f"• <b>Entry Price:</b> <b>₹{entry_price:.2f}</b>\n"
        f"• <b>Total Investment:</b> ₹{allocated_capital:.2f}\n"
        f"• <b>Stop Loss:</b> <b>₹{stop_loss:.2f}</b> (5m Bar Low / Option R3)\n"
        f"• <b>Target 1 (+35%):</b> ₹{target_1:.2f} (50% Qty Exit)\n"
        f"• <b>Target 2 (+70%):</b> ₹{target_2:.2f} (30% Qty Exit)\n"
        f"• <b>Order ID:</b> <code>{order_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {now_ist.strftime('%d %b %Y | %H:%M:%S IST')} | 🤖 Patel Trading Bot"
    )
    send_telegram_alert(telegram_msg)
    return True, f"Successfully executed {trade_mode} order for {sym} ({contract_name})"

# -------------------------------------------------------------
# Live Position Manager & Profit Booking Engine
# -------------------------------------------------------------
def monitor_and_manage_algo_positions() -> List[str]:
    """
    Monitors all active algo trades against real-time live quotes:
    1. Target 1 (+35%): Exits 50% Qty & Trails SL to Cost (Zero Risk).
    2. Target 2 (+70%+): Exits 30% Qty & Keeps 20% Runner.
    3. Stoploss: Exits all remaining quantity on breach.
    4. Auto Square-off: Exits all open intraday positions at 15:15 IST.
    5. Daily Kill-Switch: Freezes system if daily loss exceeds limit.
    """
    cfg = load_algo_config()
    trades_data = load_algo_trades()
    active_trades = trades_data.get("active_trades", [])
    closed_trades = trades_data.get("closed_trades", [])
    daily_summary = trades_data.get("daily_summary", {})
    
    if not active_trades:
        return []
        
    now_ist = get_ist_now()
    curr_time_str = now_ist.strftime("%H:%M")
    auto_square_off_time = cfg.get("auto_square_off_time", "15:15")
    is_eod_square_off = (curr_time_str >= auto_square_off_time)
    
    # Acquire Fyers client for live quote fetching
    fyers_client = None
    safe_fyers_quotes_fn = None
    try:
        from core.fyers_auth import get_fyers_client, safe_fyers_quotes
        safe_fyers_quotes_fn = safe_fyers_quotes
        ok_f, cl_f = get_fyers_client()
        if ok_f and cl_f:
            fyers_client = cl_f
    except Exception:
        pass
        
    remaining_active = []
    actions_taken = []
    
    for tr in active_trades:
        sym = tr["symbol"]
        fyers_sym = tr["fyers_symbol"]
        contract_name = tr["contract_name"]
        entry_price = float(tr["entry_price"])
        rem_qty = int(tr["remaining_qty"])
        trade_mode = tr.get("mode", "PAPER")
        stop_loss = float(tr["stop_loss"])
        target_1 = float(tr["target_1"])
        target_2 = float(tr["target_2"])
        
        # 1. Fetch verified live LTP (or Paper spot-calibrated fallback; never fabricate SL hits on missing quotes)
        current_ltp, quote_ok, quote_src = _fetch_live_or_paper_option_ltp(
            fyers_client, safe_fyers_quotes_fn, tr
        )
        tr["quote_source"] = quote_src
        if quote_ok:
            tr["last_valid_price"] = round(current_ltp, 2)

        tr["current_price"] = round(current_ltp, 2)
        unrealized = round((current_ltp - entry_price) * rem_qty, 2)
        pnl_pct = round(((current_ltp - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0
        tr["unrealized_pnl"] = unrealized
        tr["pnl_pct"] = pnl_pct
        
        # Case A: EOD Auto Square-off (15:15 IST)
        if is_eod_square_off:
            if trade_mode == "LIVE" and rem_qty > 0:
                place_fyers_broker_order(symbol=fyers_sym, qty=rem_qty, side=-1, order_type=2)
            eod_status = (
                "CLOSED (EOD 15:15 - NO VALID QUOTE)"
                if (not quote_ok and float(tr.get("booked_pnl", 0.0) or 0.0) == 0.0 and current_ltp == entry_price)
                else "CLOSED (EOD 15:15 SQUARE-OFF)"
            )
            realized_total = finalize_algo_trade_closure(
                tr=tr,
                status=eod_status,
                exit_price=current_ltp,
                final_slice_pnl=unrealized,
                closed_trades=closed_trades,
                daily_summary=daily_summary,
                now_ist=now_ist,
            )
                
            msg = (
                f"⏰ <b>AUTO-ALGO EOD SQUARE-OFF (15:15 IST)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Instrument:</b> {contract_name}\n"
                f"• <b>Exit Price:</b> ₹{current_ltp:.2f} (Entry: ₹{entry_price:.2f})\n"
                f"• <b>P&L:</b> <b>₹{realized_total:+.2f} ({pnl_pct:+.1f}%)</b>\n"
                f"• <b>Mode:</b> {trade_mode}"
            )
            send_telegram_alert(msg)
            actions_taken.append(f"{sym} EOD Squared Off")
            continue

        # Safety Guard: Never trigger SL or Targets without a verified quote or Paper spot estimate
        if not quote_ok:
            remaining_active.append(tr)
            continue
            
        # Case B: Stop Loss Hit
        if current_ltp <= stop_loss:
            if trade_mode == "LIVE" and rem_qty > 0:
                place_fyers_broker_order(symbol=fyers_sym, qty=rem_qty, side=-1, order_type=2)
            realized_total = finalize_algo_trade_closure(
                tr=tr,
                status="CLOSED (STOP LOSS HIT)",
                exit_price=current_ltp,
                final_slice_pnl=unrealized,
                closed_trades=closed_trades,
                daily_summary=daily_summary,
                now_ist=now_ist,
            )
                
            msg = (
                f"🛑 <b>ALGO STOP LOSS EXECUTED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Instrument:</b> {contract_name}\n"
                f"• <b>Exit Price:</b> ₹{current_ltp:.2f} (SL: ₹{stop_loss:.2f})\n"
                f"• <b>Realized P&L:</b> <b>₹{realized_total:+.2f} ({pnl_pct:+.1f}%)</b>\n"
                f"• <b>Capital Protected:</b> શિસ્તબદ્ધ એક્ઝિટ પૂર્ણ!"
            )
            send_telegram_alert(msg)
            actions_taken.append(f"{sym} Stop Loss Hit")
            continue
            
        # Case C: Target 1 Hit (Book 50% & Trail SL to Cost)
        if current_ltp >= target_1 and not tr.get("t1_hit", False):
            exit_qty = max(1, int(tr["initial_qty"] * (cfg.get("t1_qty_exit_pct", 50) / 100.0)))
            exit_qty = min(exit_qty, rem_qty)
            if trade_mode == "LIVE" and exit_qty > 0:
                place_fyers_broker_order(symbol=fyers_sym, qty=exit_qty, side=-1, order_type=2)
            tr["t1_hit"] = True
            tr["remaining_qty"] = max(0, rem_qty - exit_qty)
            rem_qty = tr["remaining_qty"]
            
            # Trail SL to Cost (Zero Risk Trade!)
            if cfg.get("trail_t1_to_cost", True):
                tr["stop_loss"] = entry_price
                
            t1_realized = round((current_ltp - entry_price) * exit_qty, 2)
            tr["booked_pnl"] = round(float(tr.get("booked_pnl", 0.0) or 0.0) + t1_realized, 2)
            daily_summary["realized_pnl"] = round(float(daily_summary.get("realized_pnl", 0.0) or 0.0) + t1_realized, 2)
            unrealized = round((current_ltp - entry_price) * rem_qty, 2)
            tr["unrealized_pnl"] = unrealized
            
            msg = (
                f"🎯 <b>ALGO TARGET 1 ACHIEVED (+35%)!</b> 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Instrument:</b> {contract_name}\n"
                f"• <b>LTP:</b> ₹{current_ltp:.2f} (Target 1: ₹{target_1:.2f})\n"
                f"• <b>Action:</b> <b>૫૦% ક્વોન્ટિટી ({exit_qty} Shares) નફો બુક કર્યો!</b>\n"
                f"• <b>બુક કરેલ નફો:</b> <b>+₹{t1_realized:.2f}</b>\n"
                f"• 🛡️ <b>સુવર્ણ નિયમ:</b> સ્ટોપલોસ ખસેડીને ખરીદ કિંમત (₹{entry_price:.2f}) પર મૂક્યો! (ટ્રેડ હવે ZERO RISK બની ગયો છે)!\n"
                f"• <b>બાકી ક્વોન્ટિટી:</b> {rem_qty} Shares (Target 2 તરફ ગતિ)"
            )
            send_telegram_alert(msg)
            actions_taken.append(f"{sym} Target 1 Hit (SL Moved to Cost)")
            
        # Case D: Target 2 Hit (Book 30% & Trail remaining 20% for Multibagger)
        if current_ltp >= target_2 and tr.get("t1_hit", False) and not tr.get("t2_hit", False) and rem_qty > 0:
            exit_qty = max(1, int(tr["initial_qty"] * (cfg.get("t2_qty_exit_pct", 30) / 100.0)))
            exit_qty = min(exit_qty, rem_qty)
            if trade_mode == "LIVE" and exit_qty > 0:
                place_fyers_broker_order(symbol=fyers_sym, qty=exit_qty, side=-1, order_type=2)
            tr["t2_hit"] = True
            tr["remaining_qty"] = max(0, rem_qty - exit_qty)
            rem_qty = tr["remaining_qty"]
            
            # Trail SL higher to lock in profits
            tr["stop_loss"] = target_1
            
            t2_realized = round((current_ltp - entry_price) * exit_qty, 2)
            tr["booked_pnl"] = round(float(tr.get("booked_pnl", 0.0) or 0.0) + t2_realized, 2)
            daily_summary["realized_pnl"] = round(float(daily_summary.get("realized_pnl", 0.0) or 0.0) + t2_realized, 2)
            unrealized = round((current_ltp - entry_price) * rem_qty, 2)
            tr["unrealized_pnl"] = unrealized
            
            msg = (
                f"🚀🔥 <b>ALGO TARGET 2 ACHIEVED (+70% થી +100%)!</b> 🔥🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Instrument:</b> {contract_name}\n"
                f"• <b>LTP:</b> ₹{current_ltp:.2f} (Target 2: ₹{target_2:.2f})\n"
                f"• <b>Action:</b> <b>વધુ ૩૦% ક્વોન્ટિટી બુક કરી!</b>\n"
                f"• <b>બુક કરેલ નફો:</b> <b>+₹{t2_realized:.2f}</b>\n"
                f"• <b>મલ્ટિબેગર રનર:</b> બાકીના {rem_qty} શેરો સુપર ટ્રેઇલિંગ સાથે ખુલ્લા છે (જેકપોટ રાઇડ)!"
            )
            send_telegram_alert(msg)
            actions_taken.append(f"{sym} Target 2 Hit")
            
        # If all quantities exited, close trade with full reconciled P&L & Win Rate update
        if rem_qty <= 0:
            finalize_algo_trade_closure(
                tr=tr,
                status="CLOSED (TARGETS FULLY HIT)",
                exit_price=current_ltp,
                final_slice_pnl=0.0,
                closed_trades=closed_trades,
                daily_summary=daily_summary,
                now_ist=now_ist,
            )
        else:
            remaining_active.append(tr)
            
    # Check Daily Kill-Switch
    total_daily_loss = daily_summary.get("realized_pnl", 0.0)
    for r_tr in remaining_active:
        total_daily_loss += min(0.0, r_tr.get("unrealized_pnl", 0.0))
        
    daily_max_loss = float(cfg.get("daily_max_loss", 3000.0))
    if total_daily_loss <= -daily_max_loss and not cfg.get("kill_switch_triggered", False):
        cfg["kill_switch_triggered"] = True
        save_algo_config(cfg)
        kill_alert = (
            f"🚨 <b>DAILY ALGO KILL-SWITCH TRIGGERED!</b> 🛑\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>દૈનિક નુકસાન મર્યાદા હિટ:</b> ₹{total_daily_loss:.2f} (મહત્તમ મર્યાદા: -₹{daily_max_loss:.2f})\n"
            f"• <b>સુરક્ષા પગલું:</b> આજ માટે તમામ નવા આલ્ગો ઓર્ડર્સ સ્થગિત (Frozen) કરી દેવાયા છે!\n"
            f"• <b>મૂડી સલામતી:</b> બાકીની મૂડી ૧૦૦% સુરક્ષિત છે."
        )
        send_telegram_alert(kill_alert)
        actions_taken.append("Daily Kill-Switch Triggered")

    # Update Trades Data
    trades_data["active_trades"] = remaining_active
    trades_data["closed_trades"] = closed_trades
    trades_data["daily_summary"] = daily_summary
    save_algo_trades(trades_data)
    
    return actions_taken

# -------------------------------------------------------------
# Emergency Manual Controls
# -------------------------------------------------------------
def emergency_square_off_all_algo_trades() -> Tuple[int, float]:
    """
    Emergency Kill Switch: Instantly closes all active algo positions (Paper and Live)
    and disables algo trading to prevent further execution.
    """
    cfg = load_algo_config()
    cfg["is_enabled"] = False
    save_algo_config(cfg)
    
    trades_data = load_algo_trades()
    active_trades = trades_data.get("active_trades", [])
    closed_trades = trades_data.get("closed_trades", [])
    daily_summary = trades_data.get("daily_summary", {})
    
    now_ist = get_ist_now()
    closed_count = 0
    total_exit_pnl = 0.0
    
    for tr in active_trades:
        rem_qty = tr.get("remaining_qty", tr.get("initial_qty", 0))
        fyers_sym = tr.get("fyers_symbol", "")
        if tr.get("mode") == "LIVE" and fyers_sym and rem_qty > 0:
            place_fyers_broker_order(symbol=fyers_sym, qty=rem_qty, side=-1, order_type=2)

        exit_p = float(tr.get("current_price", tr.get("entry_price", 0.0)) or 0.0)
        rem_slice_pnl = float(tr.get("unrealized_pnl", 0.0) or 0.0)
        trade_total_pnl = finalize_algo_trade_closure(
            tr=tr,
            status="CLOSED (EMERGENCY MANUAL SQUARE-OFF)",
            exit_price=exit_p,
            final_slice_pnl=rem_slice_pnl,
            closed_trades=closed_trades,
            daily_summary=daily_summary,
            now_ist=now_ist,
        )
        total_exit_pnl = round(total_exit_pnl + trade_total_pnl, 2)
        closed_count += 1
    trades_data["active_trades"] = []
    trades_data["closed_trades"] = closed_trades
    trades_data["daily_summary"] = daily_summary
    save_algo_trades(trades_data)
    
    msg = (
        f"🚨 <b>EMERGENCY ALGO SQUARE-OFF EXECUTED!</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>બંધ કરાયેલ ટ્રેડ:</b> {closed_count}\n"
        f"• <b>P&L:</b> ₹{total_exit_pnl:+.2f}\n"
        f"• <b>આલ્ગો સ્ટેટસ:</b> PAUSED (બંધ કરી દેવાયો છે)\n"
        f"• ⏰ {now_ist.strftime('%d %b %Y | %H:%M:%S IST')}"
    )
    send_telegram_alert(msg)
    return closed_count, total_exit_pnl
