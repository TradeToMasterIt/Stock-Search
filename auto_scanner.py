"""
Patel Trading Bot - Auto Scanner (Live Market Daemon)
Refactored to use modular `core` package while keeping 100% backward compatibility.
"""
import sys
import time
import os

# Import modular components from core
from core.config import (
    DEFAULT_WATCHLIST as WATCHLIST,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SCAN_INTERVAL_SECONDS,
    STATE_FILE,
    IST_TZ,
    ENFORCE_MARKET_HOURS,
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
    get_ist_now,
    is_market_open
)
from core.indicators import (
    calculate_hilega_milega,
    calculate_trend_craft_ict,
    calculate_volume_analysis,
    calculate_daily_pivot_points,
    calculate_heikin_ashi,
    calculate_donchian_channel
)
from core.alerts import (
    send_telegram_alert,
    format_r3_radar_alert,
    format_100_confirmed_buy_alert,
    format_ha_reversal_alert,
    format_sniper_short_alert,
    format_sniper_buy_alert,
    format_general_buy_alert,
    format_exit_alert
)
from core.scanner import (
    analyze_stock,
    monitor_active_trades,
    run_scan_cycle
)

# -------------------------------------------------------------
# Standalone CLI Entry Point (Runs in Background / Bat file)
# -------------------------------------------------------------
if __name__ == "__main__":
    force_mode = any(arg in sys.argv for arg in ["--force", "--test", "--ignore-hours"])
    print("========================================================")
    print("  PATEL TRADING BOT - AUTO SCANNER (LIVE MARKET)")
    print("========================================================")
    print("Starting Background Auto-Scanner Service...")
    if force_mode:
        print("⚠️ Force mode enabled: Market hours check will be bypassed.")
    
    is_open, reason = is_market_open()
    status_note = "બજાર ખુલ્લું છે (09:15 - 15:30 IST)." if is_open else f"હાલ બજાર બંધ છે ({reason}). બજાર ખુલશે ત્યારે લાઈવ સ્કેન શરૂ થશે."
    
    send_telegram_alert(
        f"🟢 <b>Auto-Scanner Service Started!</b>\n"
        f"• લાઈવ માર્કેટ સ્કેન: સોમ-શુક્ર (09:15 થી 15:30 IST)\n"
        f"• <b>સ્ટેટસ:</b> {status_note}"
    )
    
    while True:
        try:
            if not force_mode and ENFORCE_MARKET_HOURS:
                is_open, reason = is_market_open()
                if not is_open:
                    print(f"[{get_ist_now().strftime('%H:%M:%S IST')}] ⏸️ {reason}. Sleeping {SCAN_INTERVAL_SECONDS}s...")
                    time.sleep(SCAN_INTERVAL_SECONDS)
                    continue

            alerts = run_scan_cycle(force=force_mode)
            print(f"Cycle completed. {len(alerts)} alerts triggered. Sleeping {SCAN_INTERVAL_SECONDS}s...")
        except Exception as e:
            print(f"Cycle error: {e}")
        time.sleep(SCAN_INTERVAL_SECONDS)
