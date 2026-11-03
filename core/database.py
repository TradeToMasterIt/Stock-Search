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
SNAPSHOTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scan_snapshots.json")

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
        
        # 4. Scan snapshots table for historical tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_snapshots (
                id TEXT PRIMARY KEY,
                scan_date TEXT NOT NULL,
                strategy TEXT NOT NULL,
                basket TEXT,
                timeframe TEXT,
                filter_type TEXT,
                stock_count INTEGER,
                stocks_json TEXT NOT NULL,
                created_at TEXT
            )
        """)
        
        cursor.execute("SELECT value FROM meta_kv WHERE key = 'json_migrated'")
        is_migrated = cursor.fetchone()
        
        if not is_migrated:
            _migrate_json_trades()
            _migrate_json_alert_state()
            cursor.execute("INSERT OR REPLACE INTO meta_kv (key, value) VALUES ('json_migrated', '1')")
            
        # Ensure scan snapshots are always imported into SQLite on startup
        _ensure_snapshots_imported(conn)
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

# -------------------------------------------------------------
# Scan Snapshot Operations (Historical Screener Archive)
# -------------------------------------------------------------
def _ensure_snapshots_imported(conn=None):
    """
    Ensures all snapshots from scan_snapshots.json are imported into SQLite.
    Runs idempotently on every snapshot operation so historical data is never lost.
    """
    if not os.path.exists(SNAPSHOTS_FILE):
        return
    try:
        with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as f:
            cached_snaps = json.load(f)
        if not isinstance(cached_snaps, list) or len(cached_snaps) == 0:
            return

        def _do_insert(c):
            for s in cached_snaps:
                sid = s.get("id")
                if not sid:
                    continue
                c.execute("""
                    INSERT OR IGNORE INTO scan_snapshots (
                        id, scan_date, strategy, basket, timeframe, filter_type, stock_count, stocks_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sid,
                    s.get("scan_date", ""),
                    s.get("strategy", "Heikin Ashi Trend Rider"),
                    s.get("basket", "Total F&O"),
                    s.get("timeframe", "Daily"),
                    s.get("filter_type", "ALL"),
                    int(s.get("stock_count", len(s.get("stocks", [])))),
                    json.dumps(s.get("stocks", []), ensure_ascii=False),
                    s.get("created_at", get_ist_now().isoformat())
                ))

        if conn is not None:
            cursor = conn.cursor()
            _do_insert(cursor)
            conn.commit()
        else:
            with get_db_connection() as c:
                cur = c.cursor()
                _do_insert(cur)
                c.commit()
    except Exception as e:
        print(f"[DB] Error ensuring snapshots imported: {e}")

def _sync_snapshots_to_json():
    """Syncs all SQLite snapshots to scan_snapshots.json backup."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_snapshots ORDER BY created_at DESC")
            rows = cursor.fetchall()
            snaps = []
            for r in rows:
                try:
                    stocks = json.loads(r["stocks_json"])
                except Exception:
                    stocks = []
                snaps.append({
                    "id": r["id"],
                    "scan_date": r["scan_date"],
                    "strategy": r["strategy"],
                    "basket": r["basket"],
                    "timeframe": r["timeframe"],
                    "filter_type": r["filter_type"],
                    "stock_count": r["stock_count"],
                    "stocks": stocks,
                    "created_at": r["created_at"]
                })
        if snaps:
            with open(SNAPSHOTS_FILE, "w", encoding="utf-8") as f:
                json.dump(snaps, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[DB] Error syncing snapshots to JSON: {e}")

def save_scan_snapshot(snap_dict):
    """Saves a scan result snapshot into SQLite database and syncs to JSON."""
    init_db()
    with get_db_connection() as conn:
        # 1. Guarantee all previous JSON snapshots are imported first
        _ensure_snapshots_imported(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scan_snapshots (
                id, scan_date, strategy, basket, timeframe, filter_type, stock_count, stocks_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snap_dict.get("id", f"SNAP_{int(datetime.datetime.now().timestamp())}"),
            snap_dict.get("scan_date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
            snap_dict.get("strategy", "Heikin Ashi Trend Rider"),
            snap_dict.get("basket", "Total F&O"),
            snap_dict.get("timeframe", "Daily"),
            snap_dict.get("filter_type", "ALL"),
            int(snap_dict.get("stock_count", len(snap_dict.get("stocks", [])))),
            json.dumps(snap_dict.get("stocks", []), ensure_ascii=False),
            snap_dict.get("created_at", get_ist_now().isoformat())
        ))
        conn.commit()
    _sync_snapshots_to_json()
    return True

def load_scan_snapshots(strategy=None):
    """Loads scan snapshots ordered by created_at DESC, always guaranteed from DB or JSON."""
    init_db()
    snaps = []
    try:
        with get_db_connection() as conn:
            _ensure_snapshots_imported(conn)
            cursor = conn.cursor()
            if strategy:
                cursor.execute("SELECT * FROM scan_snapshots WHERE strategy LIKE ? ORDER BY created_at DESC", (f"%{strategy}%",))
            else:
                cursor.execute("SELECT * FROM scan_snapshots ORDER BY created_at DESC")
            rows = cursor.fetchall()
            for r in rows:
                try:
                    stocks = json.loads(r["stocks_json"])
                except Exception:
                    stocks = []
                snaps.append({
                    "id": r["id"],
                    "scan_date": r["scan_date"],
                    "strategy": r["strategy"],
                    "basket": r["basket"],
                    "timeframe": r["timeframe"],
                    "filter_type": r["filter_type"],
                    "stock_count": r["stock_count"],
                    "stocks": stocks,
                    "created_at": r["created_at"]
                })
    except Exception as e:
        print(f"[DB] Error reading snapshots from SQLite: {e}")

    # Rock-solid fallback: If DB returned empty, read directly from scan_snapshots.json
    if not snaps and os.path.exists(SNAPSHOTS_FILE):
        try:
            with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as f:
                cached_snaps = json.load(f)
            if isinstance(cached_snaps, list):
                if strategy:
                    snaps = [s for s in cached_snaps if strategy.lower() in s.get("strategy", "").lower()]
                else:
                    snaps = cached_snaps
        except Exception as e:
            print(f"[DB] Fallback reading scan_snapshots.json failed: {e}")

    return snaps

def delete_scan_snapshot(snap_id):
    """Deletes a scan snapshot by ID and updates JSON."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scan_snapshots WHERE id = ?", (snap_id,))
        conn.commit()
    _sync_snapshots_to_json()
    return True

