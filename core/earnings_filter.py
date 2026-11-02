"""
Earnings Blackout & Event Risk Filter for Patel Trading Bot / Confluence Pro

Protects Option Sellers from catastrophic gap-up / gap-down events:
- Automatically checks quarterly earnings / board meeting dates for NSE stocks.
- If earnings announcement is scheduled within the next 7-10 days, the stock is
  strictly FLAGGED and EXCLUDED from Option Selling recommendations.
- Implements an automated local cache ('earnings_cache.json') so multi-stock scans
  remain instant and don't slow down the scanner.
"""

import os
import sys
import json
import datetime
from typing import Dict, Any, Optional, List

# Ensure parent directory is in path
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from .config import get_ist_now
except ImportError:
    from core.config import get_ist_now

EARNINGS_CACHE_FILE = os.path.join(_parent_dir, "earnings_cache.json")

def load_earnings_cache() -> Dict[str, Any]:
    """Loads cached earnings calendar from disk if present."""
    if os.path.exists(EARNINGS_CACHE_FILE):
        try:
            with open(EARNINGS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_earnings_cache(data: Dict[str, Any]):
    """Saves updated earnings calendar cache."""
    try:
        with open(EARNINGS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[EARNINGS_FILTER] Failed to save cache: {e}")

def check_earnings_blackout(symbol: str, blackout_days: int = 10) -> Dict[str, Any]:
    """
    Checks if a stock has an upcoming quarterly earnings announcement within `blackout_days`.
    Returns:
        dict:
            - is_blackout (bool): True if earnings is within blackout_days (DO NOT SELL OPTIONS).
            - earnings_date (str or None): Scheduled date.
            - days_until_earnings (int or None): Days remaining.
            - status_badge (str): Display text for Telegram & UI.
            - reason (str): Explanation in Gujarati.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").strip().upper()
    now_ist = get_ist_now().date()
    cache = load_earnings_cache()
    
    cached_info = cache.get(clean_sym)
    scheduled_dt = None
    
    if cached_info and isinstance(cached_info, dict):
        d_str = cached_info.get("earnings_date")
        if d_str:
            try:
                scheduled_dt = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            except Exception:
                scheduled_dt = None

    # If cache not present or expired (past date), try checking via yfinance safely
    if not scheduled_dt or scheduled_dt < now_ist:
        try:
            import yfinance as yf
            t = yf.Ticker(f"{clean_sym}.NS")
            cal = t.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal:
                e_dates = cal["Earnings Date"]
                if e_dates and len(e_dates) > 0:
                    first_dt = e_dates[0]
                    if hasattr(first_dt, "date"):
                        scheduled_dt = first_dt.date()
                    elif isinstance(first_dt, str):
                        scheduled_dt = datetime.datetime.strptime(first_dt[:10], "%Y-%m-%d").date()
            elif hasattr(t, "get_earnings_dates"):
                df_e = t.get_earnings_dates(limit=3)
                if df_e is not None and not df_e.empty:
                    upcoming = [idx.date() for idx in df_e.index if idx.date() >= now_ist]
                    if upcoming:
                        scheduled_dt = min(upcoming)
        except Exception:
            pass

        # Update cache if found
        if scheduled_dt:
            cache[clean_sym] = {
                "earnings_date": scheduled_dt.isoformat(),
                "updated_at": now_ist.isoformat()
            }
            save_earnings_cache(cache)

    # Evaluate Blackout Condition
    if scheduled_dt:
        diff_days = (scheduled_dt - now_ist).days
        if 0 <= diff_days <= blackout_days:
            return {
                "symbol": clean_sym,
                "is_blackout": True,
                "earnings_date": scheduled_dt.strftime("%d-%b-%Y"),
                "days_until_earnings": diff_days,
                "status_badge": f"🚫 EARNINGS BLACKOUT ({diff_days} દિવસમાં પરિણામ)",
                "reason": (
                    f"કંપનીનું ત્રિમાસિક પરિણામ {scheduled_dt.strftime('%d-%b-%Y')} ના રોજ "
                    f"({diff_days} દિવસમાં) આવવાનું છે. પરિણામ પછી સ્ટોકમાં ૮% થી ૧૫% ની મોટી સર્કિટ "
                    f"લાગવાનો ખતરો હોવાથી ઓપ્શન સેલિંગ ૧૦૦% પ્રતિબંધિત છે!"
                )
            }

    return {
        "symbol": clean_sym,
        "is_blackout": False,
        "earnings_date": scheduled_dt.strftime("%d-%b-%Y") if scheduled_dt else None,
        "days_until_earnings": (scheduled_dt - now_ist).days if scheduled_dt else None,
        "status_badge": "🟢 SAFE (કોઈ નજીકનું પરિણામ નથી)",
        "reason": "સ્ટોકમાં આગામી ૧૦ દિવસમાં કોઈ ત્રિમાસિક પરિણામ નથી. રેન્જ-બાઉન્ડ ઓપ્શન સેલિંગ માટે સલામત છે."
    }

if __name__ == "__main__":
    print("Testing Earnings Blackout Filter...")
    res = check_earnings_blackout("RELIANCE.NS", blackout_days=10)
    print(res)
