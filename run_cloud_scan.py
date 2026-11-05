"""
Patel Trading Bot - Cloud One-Shot Scanner (GitHub Actions & VPS Runner)
Executes a single institutional scan cycle, triggers 100% Confirmed Buy orders,
monitors active trades, manages 3-stage profit exits, and logs status.
"""
import sys
import os
from datetime import datetime

# Add workspace directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import get_ist_now, is_market_open, ENFORCE_MARKET_HOURS
from core.scanner import run_scan_cycle
from core.fyers_order_engine import load_algo_config, load_algo_trades

def main():
    force_mode = any(arg in sys.argv for arg in ["--force", "--test", "--ignore-hours"])
    now_ist = get_ist_now()
    now_str = now_ist.strftime("%d %b %Y | %H:%M:%S IST")

    print("========================================================")
    print("  PATEL TRADING BOT - CLOUD RUNNER (GITHUB ACTIONS / VPS)")
    print("========================================================")
    print(f"⏰ Execution Time: {now_str}")
    
    is_open, reason = is_market_open()
    print(f"🏛️ Market Status: {'OPEN' if is_open else 'CLOSED'} ({reason})")

    if not force_mode and ENFORCE_MARKET_HOURS and not is_open:
        print(f"⏸️ Market is closed. Skipping scan cycle.")
        return 0

    cfg = load_algo_config()
    algo_enabled = cfg.get("is_enabled", False)
    algo_mode = cfg.get("mode", "PAPER")
    print(f"🤖 Algo Status: {'ACTIVE' if algo_enabled else 'PAUSED'} | Mode: {algo_mode}")

    print("\n🚀 Starting scan cycle across Major Indices and F&O Universe...")
    alerts = run_scan_cycle(force=force_mode)

    print(f"\n✅ Scan cycle completed! Total alerts / actions: {len(alerts)}")
    if alerts:
        for idx, alt in enumerate(alerts, 1):
            print(f"   [{idx}] {alt}")

    trades_state = load_algo_trades()
    active_cnt = len(trades_state.get("active_trades", []))
    summary = trades_state.get("daily_summary", {})
    print(f"\n📊 Summary: Active Trades: {active_cnt} | Daily Realized P&L: ₹{summary.get('realized_pnl', 0.0):+,.2f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
