"""
Thread-Safe SQLite Database Manager for Patel Trading Bot / Confluence Pro
Manages Active Trades, History, and Alert State with automatic JSON migration and backup.
"""
import os
import json
import sqlite3
import datetime
from .config import get_ist_now, ACTIVE_TRADES_FILE, STATE_FILE

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trades.db")

def get_db_connection():
    """Returns a SQLite connection with timeout and Row factory."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates database tables and performs automatic JSON migration if needed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                full_symbol TEXT,
                trade_type TEXT DEFAULT 'BUY',
                entry_price REAL NOT NULL,
                qty INTEGER DEFAULT 1,
                entry_date TEXT,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                ce_strike REAL,
                pe_strike REAL,
                status TEXT DEFAULT 'ACTIVE',
                exit_price REAL,
                exit_date TEXT,
                pnl REAL,
                pnl_pct REAL,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # 2. Alert state table (replaces alert_state.json)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_state (
                alert_key TEXT PRIMARY KEY,
                alert_value TEXT,
                alert_date TEXT,
                created_at TEXT
            )
        """)

        # 3. Meta KV table for migrations and settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta_kv (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("SELECT value FROM meta_kv WHERE key = 'json_migrated'")
        is_migrated = cursor.fetchone()
        
        if not is_migrated:
            _migrate_json_trades()
            _migrate_json_alert_state()
            cursor.execute("INSERT OR REPLACE INTO meta_kv (key, value) VALUES ('json_migrated', '1')")
            
        conn.commit()

def _migrate_json_trades():
    """Migrates trades from active_trades.json if present into SQLite."""
    trades_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ACTIVE_TRADES_FILE)
    if not os.path.exists(trades_path):
        return
        
    try:
        with open(trades_path, "r", encoding="utf-8") as f:
            trades = json.load(f)
            
        if not isinstance(trades, list):
            return
            
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for t in trades:
                tid = t.get("id")
                if not tid:
                    continue
                # Check if exists
                cursor.execute("SELECT id FROM trades WHERE id = ?", (tid,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO trades (
                            id, symbol, full_symbol, trade_type, entry_price, qty, entry_date,
                            stop_loss, target_1, target_2, ce_strike, pe_strike, status, notes,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        tid,
                        t.get("symbol", ""),
                        t.get("full_symbol", f"{t.get('symbol', '')}.NS"),
                        t.get("trade_type", "BUY"),
                        float(t.get("entry_price", 0.0)),
                        int(t.get("qty", 1)),
                        t.get("entry_date", get_ist_now().strftime("%Y-%m-%d %H:%M")),
                        float(t.get("stop_loss", 0.0)) if t.get("stop_loss") else None,
                        float(t.get("target_1", 0.0)) if t.get("target_1") else None,
                        float(t.get("target_2", 0.0)) if t.get("target_2") else None,
                        float(t.get("ce_strike")) if t.get("ce_strike") else None,
                        float(t.get("pe_strike")) if t.get("pe_strike") else None,
                        t.get("status", "ACTIVE"),
                        t.get("notes", ""),
                        get_ist_now().isoformat(),
                        get_ist_now().isoformat()
                    ))
            conn.commit()
    except Exception as e:
        print(f"Error during trades migration: {e}")

def _migrate_json_alert_state():
    """Migrates alert_state.json if present into SQLite."""
    state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), STATE_FILE)
    if not os.path.exists(state_path):
        return
        
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        if not isinstance(state, dict):
            return
            
        now_iso = get_ist_now().isoformat()
        today_date = get_ist_now().date().isoformat()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for k, v in state.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO alert_state (alert_key, alert_value, alert_date, created_at)
                    VALUES (?, ?, ?, ?)
                """, (k, str(v), today_date, now_iso))
            conn.commit()
    except Exception as e:
        print(f"Error during alert state migration: {e}")

# -------------------------------------------------------------
# Trades CRUD Operations
# -------------------------------------------------------------
def load_all_trades():
    """Returns all trades as a list of dictionaries."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def load_active_trades():
    """Returns only ACTIVE trades as a list of dictionaries."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'ACTIVE' ORDER BY created_at DESC")
        rows = cursor.fetchall()
        trades = [dict(r) for r in rows]
        
    # Sync to JSON backup file for external tools or backward compatibility
    _sync_trades_json_backup(load_all_trades())
    return trades

def save_active_trades(trades_list):
    """
    Saves/replaces trades in the database and updates JSON backup.
    Backward-compatible drop-in for save_active_trades().
    """
    init_db()
    now_iso = get_ist_now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for t in trades_list:
            tid = t.get("id")
            if not tid:
                continue
            cursor.execute("""
                INSERT INTO trades (
                    id, symbol, full_symbol, trade_type, entry_price, qty, entry_date,
                    stop_loss, target_1, target_2, ce_strike, pe_strike, status, notes,
                    exit_price, exit_date, pnl, pnl_pct, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol=excluded.symbol,
                    full_symbol=excluded.full_symbol,
                    trade_type=excluded.trade_type,
                    entry_price=excluded.entry_price,
                    qty=excluded.qty,
                    entry_date=excluded.entry_date,
                    stop_loss=excluded.stop_loss,
                    target_1=excluded.target_1,
                    target_2=excluded.target_2,
                    ce_strike=excluded.ce_strike,
                    pe_strike=excluded.pe_strike,
                    status=excluded.status,
                    notes=excluded.notes,
                    exit_price=excluded.exit_price,
                    exit_date=excluded.exit_date,
                    pnl=excluded.pnl,
                    pnl_pct=excluded.pnl_pct,
                    updated_at=excluded.updated_at
            """, (
                tid,
                t.get("symbol", ""),
                t.get("full_symbol", f"{t.get('symbol', '')}.NS"),
                t.get("trade_type", "BUY"),
                float(t.get("entry_price", 0.0)),
                int(t.get("qty", 1)),
                t.get("entry_date", get_ist_now().strftime("%Y-%m-%d %H:%M")),
                float(t.get("stop_loss", 0.0)) if t.get("stop_loss") else None,
                float(t.get("target_1", 0.0)) if t.get("target_1") else None,
                float(t.get("target_2", 0.0)) if t.get("target_2") else None,
                float(t.get("ce_strike")) if t.get("ce_strike") else None,
                float(t.get("pe_strike")) if t.get("pe_strike") else None,
                t.get("status", "ACTIVE"),
                t.get("notes", ""),
                float(t.get("exit_price")) if t.get("exit_price") else None,
                t.get("exit_date"),
                float(t.get("pnl")) if t.get("pnl") is not None else None,
                float(t.get("pnl_pct")) if t.get("pnl_pct") is not None else None,
                t.get("created_at", now_iso),
                now_iso
            ))
        conn.commit()
        
    _sync_trades_json_backup(load_all_trades())
    return True

def delete_trade(trade_id):
    """Deletes a trade from the database by ID."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
    _sync_trades_json_backup(load_all_trades())
    return True

def _sync_trades_json_backup(trades):
    """Safely synchronizes trades to active_trades.json as an export backup."""
    try:
        trades_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ACTIVE_TRADES_FILE)
        with open(trades_path, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2)
    except Exception:
        pass

# -------------------------------------------------------------
# Alert State Operations (Thread-safe key-value store)
# -------------------------------------------------------------
def load_alert_state():
    """Loads alert state dictionary from SQLite database."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT alert_key, alert_value FROM alert_state")
        rows = cursor.fetchall()
        state = {}
        for r in rows:
            val = r["alert_value"]
            if val == "True":
                state[r["alert_key"]] = True
            elif val == "False":
                state[r["alert_key"]] = False
            else:
                state[r["alert_key"]] = val
        return state

def save_alert_state(state_dict):
    """Saves alert state dictionary into SQLite database and syncs JSON backup."""
    init_db()
    now_iso = get_ist_now().isoformat()
    today_date = get_ist_now().date().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for k, v in state_dict.items():
            cursor.execute("""
                INSERT INTO alert_state (alert_key, alert_value, alert_date, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(alert_key) DO UPDATE SET
                    alert_value=excluded.alert_value,
                    alert_date=excluded.alert_date
            """, (k, str(v), today_date, now_iso))
        conn.commit()
        
    # Sync to JSON backup
    try:
        state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), STATE_FILE)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)
    except Exception:
        pass
    return True
