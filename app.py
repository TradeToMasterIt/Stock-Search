import os
import json
import time
import datetime
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

def serialize_screener_data(obj):
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    return str(obj)

# -------------------------------------------------------------
# Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="Confluence Pro | Institutional Trading Terminal",
    page_icon="🎯",
    layout="wide"
)

# -------------------------------------------------------------
# Cloud Auto-Scanner (Background Telegram Worker)
# -------------------------------------------------------------
import threading

@st.cache_resource
def init_cloud_telegram_scanner():
    """Starts background Telegram Auto-Scanner thread on Streamlit Cloud."""
    try:
        from auto_scanner import run_scan_cycle, is_market_open, send_telegram_alert
        def worker():
            time.sleep(15)
            try:
                send_telegram_alert(
                    "🚀 <b>Streamlit Cloud Auto-Scanner Online!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "• <b>ક્લાઉડ મોડ:</b> હવે તમારા લેપટોપ વગર સીધું Streamlit Cloud માંથી ઓટોમેટિક એલર્ટ્સ ચાલુ રહેશે!\n"
                    "• <b>સમયગાળો:</b> સોમ-શુક્ર (09:15 થી 15:30 IST દર ૫ મિનિટે સ્કેન)\n"
                    "• 🤖 Patel Trading Bot"
                )
            except Exception:
                pass
            while True:
                try:
                    is_open, _ = is_market_open()
                    if is_open:
                        run_scan_cycle(force=False)
                except Exception as ex:
                    print(f"Cloud scanner error: {ex}")
                time.sleep(300)

        scanner_thread = threading.Thread(target=worker, daemon=True, name="CloudAutoScanner")
        scanner_thread.start()
        return True
    except Exception as e:
        print(f"Error initializing cloud scanner: {e}")
        return False

init_cloud_telegram_scanner()

# -------------------------------------------------------------
# Global Professional Terminal CSS Styling
# -------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Background & Main Canvas */
.stApp {
    background: radial-gradient(circle at 50% 0%, #111827 0%, #080c14 100%);
    color: #F3F4F6;
}

header[data-testid="stHeader"] {
    background: transparent;
}

/* Custom Header Bar */
.brand-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 22px;
    background: linear-gradient(135deg, rgba(26, 35, 53, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    margin-bottom: 12px;
}

.brand-title {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: linear-gradient(90deg, #FFFFFF 0%, #38BDF8 60%, #818CF8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-badge {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    background: linear-gradient(135deg, #2563EB, #7C3AED);
    color: #FFFFFF;
    padding: 3px 10px;
    border-radius: 9999px;
    box-shadow: 0 0 14px rgba(37, 99, 235, 0.5);
}

.brand-subtitle {
    color: #94A3B8;
    font-size: 12px;
    margin-top: 4px;
    font-weight: 500;
}

/* Ticker Bar */
.ticker-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    padding: 10px 16px;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    margin-bottom: 20px;
}

.ticker-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    color: #E2E8F0;
}

.ticker-chip-bull {
    border-color: rgba(16, 185, 129, 0.4);
    background: rgba(16, 185, 129, 0.12);
    color: #34D399;
}

.ticker-chip-bear {
    border-color: rgba(239, 68, 68, 0.4);
    background: rgba(239, 68, 68, 0.12);
    color: #F87171;
}

.ticker-chip-bot {
    border-color: rgba(59, 130, 246, 0.4);
    background: rgba(59, 130, 246, 0.12);
    color: #60A5FA;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10B981;
    box-shadow: 0 0 10px #10B981;
    animation: pulse 1.8s infinite;
}

@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { transform: scale(1.1); box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

/* KPI Summary Cards Grid */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin: 16px 0 20px 0;
}

.kpi-card {
    padding: 16px 18px;
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(23, 31, 48, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.kpi-green {
    border-top: 3px solid #10B981;
}

.kpi-cyan {
    border-top: 3px solid #06B6D4;
}

.kpi-amber {
    border-top: 3px solid #F59E0B;
}

.kpi-red {
    border-top: 3px solid #EF4444;
}

.kpi-purple {
    border-top: 3px solid #A855F7;
}

.kpi-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #94A3B8;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.kpi-value {
    font-size: 26px;
    font-weight: 800;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.1;
}

.kpi-subtitle {
    font-size: 11px;
    color: #64748B;
    margin-top: 6px;
    font-weight: 500;
}

/* Interactive KPI Clickable Buttons */
div[class*="st-key-btn_kpi_"] {
    margin-bottom: 12px;
}

div[class*="st-key-btn_kpi_"] > button {
    height: 115px !important;
    min-height: 115px !important;
    width: 100% !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, rgba(23, 31, 48, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
    padding: 14px 16px !important;
    text-align: left !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
    align-items: flex-start !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

div[class*="st-key-btn_kpi_"] > button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45) !important;
}

/* Card 1: Sniper Dip Buy (Green) */
div.st-key-btn_kpi_sniper_buy > button {
    border-top: 3.5px solid #10B981 !important;
}
div.st-key-btn_kpi_sniper_buy > button:hover {
    border-color: #10B981 !important;
    background: rgba(16, 185, 129, 0.12) !important;
}
div.st-key-btn_kpi_sniper_buy > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_sniper_buy > button:active {
    background: rgba(16, 185, 129, 0.2) !important;
    border: 1.5px solid #10B981 !important;
    border-top: 3.5px solid #10B981 !important;
    box-shadow: 0 0 22px rgba(16, 185, 129, 0.45) !important;
}

/* Card 2: Buy on Dips (Cyan) */
div.st-key-btn_kpi_buy_dips > button {
    border-top: 3.5px solid #06B6D4 !important;
}
div.st-key-btn_kpi_buy_dips > button:hover {
    border-color: #06B6D4 !important;
    background: rgba(6, 182, 212, 0.12) !important;
}
div.st-key-btn_kpi_buy_dips > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_buy_dips > button:active {
    background: rgba(6, 182, 212, 0.2) !important;
    border: 1.5px solid #06B6D4 !important;
    border-top: 3.5px solid #06B6D4 !important;
    box-shadow: 0 0 22px rgba(6, 182, 212, 0.45) !important;
}

/* Card 3: R3 Option Radar (Gold / Amber) */
div.st-key-btn_kpi_r3_radar > button {
    border-top: 3.5px solid #F59E0B !important;
}
div.st-key-btn_kpi_r3_radar > button:hover {
    border-color: #F59E0B !important;
    background: rgba(245, 158, 11, 0.12) !important;
}
div.st-key-btn_kpi_r3_radar > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_r3_radar > button:active {
    background: rgba(245, 158, 11, 0.22) !important;
    border: 1.5px solid #F59E0B !important;
    border-top: 3.5px solid #F59E0B !important;
    box-shadow: 0 0 24px rgba(245, 158, 11, 0.45) !important;
}

/* Card 4: Sniper Short (Red / Crimson) */
div.st-key-btn_kpi_sniper_short > button {
    border-top: 3.5px solid #EF4444 !important;
    background: rgba(239, 68, 68, 0.08) !important;
}
div.st-key-btn_kpi_sniper_short > button:hover {
    border-color: #EF4444 !important;
    background: rgba(239, 68, 68, 0.18) !important;
}
div.st-key-btn_kpi_sniper_short > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_sniper_short > button:active {
    background: rgba(239, 68, 68, 0.25) !important;
    border: 1.5px solid #EF4444 !important;
    border-top: 3.5px solid #EF4444 !important;
    box-shadow: 0 0 22px rgba(239, 68, 68, 0.45) !important;
}

/* Card 4: Option Selling (Purple) */
div.st-key-btn_kpi_option_sell > button {
    border-top: 3.5px solid #A855F7 !important;
}
div.st-key-btn_kpi_option_sell > button:hover {
    border-color: #A855F7 !important;
    background: rgba(168, 85, 247, 0.12) !important;
}
div.st-key-btn_kpi_option_sell > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_option_sell > button:active {
    background: rgba(168, 85, 247, 0.2) !important;
    border: 1.5px solid #A855F7 !important;
    border-top: 3.5px solid #A855F7 !important;
    box-shadow: 0 0 22px rgba(168, 85, 247, 0.45) !important;
}

/* Card 5: Sell / Caution (Rose / Red) */
div.st-key-btn_kpi_sell_caution > button {
    border-top: 3.5px solid #F43F5E !important;
}
div.st-key-btn_kpi_sell_caution > button:hover {
    border-color: #F43F5E !important;
    background: rgba(244, 63, 94, 0.12) !important;
}
div.st-key-btn_kpi_sell_caution > button[data-testid="stBaseButton-primary"],
div.st-key-btn_kpi_sell_caution > button:active {
    background: rgba(244, 63, 94, 0.2) !important;
    border: 1.5px solid #F43F5E !important;
    border-top: 3.5px solid #F43F5E !important;
    box-shadow: 0 0 22px rgba(244, 63, 94, 0.45) !important;
}

/* Content Typography inside KPI Buttons */
div[class*="st-key-btn_kpi_"] > button div[data-testid="stMarkdownContainer"] {
    width: 100% !important;
    text-align: left !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
}

div[class*="st-key-btn_kpi_"] > button p {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    text-align: left !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    margin-bottom: 2px !important;
}
div.st-key-btn_kpi_sniper_buy > button p { color: #34D399 !important; }
div.st-key-btn_kpi_buy_dips > button p { color: #38BDF8 !important; }
div.st-key-btn_kpi_sniper_short > button p { color: #F87171 !important; }
div.st-key-btn_kpi_option_sell > button p { color: #C084FC !important; }
div.st-key-btn_kpi_sell_caution > button p { color: #F87171 !important; }

/* Number Value */
div[class*="st-key-btn_kpi_"] > button strong {
    font-size: 26px !important;
    font-weight: 800 !important;
    font-family: 'JetBrains Mono', monospace !important;
    line-height: 1.1 !important;
    margin: 4px 0 !important;
    color: #FFFFFF !important;
    display: block !important;
}
div.st-key-btn_kpi_sniper_buy > button strong { color: #34D399 !important; }
div.st-key-btn_kpi_sniper_short > button strong { color: #F87171 !important; }

/* Subtitle */
div[class*="st-key-btn_kpi_"] > button em {
    font-size: 11px !important;
    font-style: normal !important;
    color: #64748B !important;
    font-weight: 500 !important;
    display: block !important;
    margin-top: 2px !important;
}

/* Trading Stock Ticket Card */
.stock-card {
    background: linear-gradient(180deg, #151d2d 0%, #0e1626 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 16px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
    transition: all 0.25s ease;
}

.stock-card:hover {
    border-color: rgba(56, 189, 248, 0.4);
    box-shadow: 0 8px 25px rgba(56, 189, 248, 0.15);
    transform: translateY(-2px);
}

.signal-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

.pill-strong-buy {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid #10B981;
    color: #34D399;
}

.pill-buy-dips {
    background: rgba(6, 182, 212, 0.2);
    border: 1px solid #06B6D4;
    color: #38BDF8;
}

.pill-bullish {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid #059669;
    color: #6EE7B7;
}

.pill-sell {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid #EF4444;
    color: #F87171;
}

.pill-sniper-short {
    background: rgba(239, 68, 68, 0.28);
    border: 1.5px solid #EF4444;
    color: #FFA4A4;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
}

.pill-sniper-buy {
    background: rgba(16, 185, 129, 0.28);
    border: 1.5px solid #10B981;
    color: #6EE7B7;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
}

.pill-option-sell {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid #A855F7;
    color: #C084FC;
}

.pill-neutral {
    background: rgba(100, 116, 139, 0.2);
    border: 1px solid #64748B;
    color: #94A3B8;
}

.targets-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.target-item {
    background: rgba(15, 23, 42, 0.7);
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.target-item-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 2px;
}

.target-item-val {
    font-size: 13px;
    font-weight: 700;
    color: #F1F5F9;
    font-family: 'JetBrains Mono', monospace;
}

/* Primary Button Styling */
.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #059669 0%, #10B981 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: 0.3px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4) !important;
    transition: all 0.25s ease !important;
}

.stButton>button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6) !important;
    transform: translateY(-1px) !important;
}

/* Tabs Styling */
.stTabs [data-baseweb="tab-list"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    background-color: rgba(15, 23, 42, 0.6);
    padding: 6px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 14px;
    color: #94A3B8;
    font-weight: 600;
    font-size: 13px;
    border: none !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #1E293B, #334155) !important;
    color: #38BDF8 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
}

/* Dataframe custom styling */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------

# -------------------------------------------------------------
# Active Trades & Risk Guardian Data Layer
# -------------------------------------------------------------
TRADES_FILE = "active_trades.json"

def load_active_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_active_trades(trades):
    try:
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2)
        return True
    except Exception:
        return False

def format_volume(vol):
    if pd.isna(vol) or vol == 0:
        return "0"
    if vol >= 10_000_000:
        return f"{vol / 10_000_000:.2f} Cr"
    elif vol >= 100_000:
        return f"{vol / 100_000:.2f} L"
    elif vol >= 1_000:
        return f"{vol / 1_000:.1f} K"
    return f"{vol:,.0f}"

def calculate_trade_levels(entry_price, stop_loss, is_short=False):
    if is_short:
        risk = stop_loss - entry_price if stop_loss > entry_price else entry_price * 0.015
        if risk <= 0 or risk > (entry_price * 0.12):
            risk = entry_price * 0.015
            stop_loss = entry_price + risk
        t1 = entry_price - (1.5 * risk)
        t2 = entry_price - (2.5 * risk)
        risk_pct = (risk / entry_price) * 100
        t1_pct = ((entry_price - t1) / entry_price) * 100
        t2_pct = ((entry_price - t2) / entry_price) * 100
    else:
        risk = entry_price - stop_loss
        if risk <= 0 or risk > (entry_price * 0.12):
            risk = entry_price * 0.015 # default 1.5% tight risk
            stop_loss = entry_price - risk
            
        t1 = entry_price + (1.5 * risk)
        t2 = entry_price + (2.5 * risk)
        risk_pct = (risk / entry_price) * 100
        t1_pct = ((t1 - entry_price) / entry_price) * 100
        t2_pct = ((t2 - entry_price) / entry_price) * 100
    
    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "risk_pct": risk_pct,
        "t1": t1,
        "t1_pct": t1_pct,
        "t2": t2,
        "t2_pct": t2_pct,
        "is_short": is_short
    }

@st.cache_data(ttl=120)
def get_nifty_sentiment():
    try:
        t = yf.Ticker("^NSEI")
        d = t.history(period="5d", interval="1d")
        if d.empty or len(d) < 2:
            return None
        c = d['Close'].iloc[-1]
        p = d['Close'].iloc[-2]
        chg = c - p
        pct = (chg / p) * 100
        return {"price": c, "change": chg, "pct": pct, "is_bullish": chg >= 0}
    except Exception:
        return None

# Watchlist Baskets
BASKETS = {
    "🚀 Top F&O Momentum Leaders (75 Stocks)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS",
        "HINDUNILVR.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
        "TITAN.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TATASTEEL.NS", "NTPC.NS",
        "POWERGRID.NS", "COALINDIA.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ONGC.NS",
        "M&M.NS", "BAJAJFINSV.NS", "ULTRACEMCO.NS", "BEL.NS", "HAL.NS",
        "BHEL.NS", "ZYDUSLIFE.NS", "ADANIPOWER.NS", "VEDL.NS", "SUZLON.NS",
        "TRENT.NS", "DIXON.NS", "POLYCAB.NS", "PERSISTENT.NS", "COFORGE.NS",
        "HAVELLS.NS", "WIPRO.NS", "TECHM.NS", "HCLTECH.NS", "DLF.NS",
        "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS", "RECLTD.NS", "PFC.NS",
        "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS",
        "INDUSINDBK.NS", "AUBANK.NS", "SIEMENS.NS", "ABB.NS", "CUMMINSIND.NS",
        "TVSMOTOR.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "ASHOKLEY.NS", "BHARATFORG.NS",
        "CIPLA.NS", "DRREDDY.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS",
        "AMBUJACEM.NS", "ACC.NS", "GAIL.NS", "BPCL.NS", "IOC.NS"
    ],
    "🏛️ Nifty 50 (બધા 50 બ્લુચિપ સ્ટોક્સ)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
        "INFY.NS", "ITC.NS", "SBIN.NS", "LT.NS", "HINDUNILVR.NS",
        "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "ADANIENT.NS",
        "SHRIRAMFIN.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "NTPC.NS",
        "AXISBANK.NS", "ADANIPORTS.NS", "POWERGRID.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
        "M&M.NS", "TATASTEEL.NS", "ULTRACEMCO.NS", "ASIANPAINT.NS", "JSWSTEEL.NS",
        "GRASIM.NS", "BEL.NS", "TRENT.NS", "TECHM.NS", "SHREECEM.NS",
        "CIPLA.NS", "INDUSINDBK.NS", "HINDALCO.NS", "BPCL.NS", "DRREDDY.NS",
        "TATACONSUM.NS", "NESTLEIND.NS", "EICHERMOT.NS", "APOLLOHOSP.NS", "WIPRO.NS",
        "SBILIFE.NS", "BRITANNIA.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "HEROMOTOCO.NS"
    ],
    "📈 Nifty 100 (ટોપ 100 લાર્જકેપ સ્ટોક્સ)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
        "INFY.NS", "ITC.NS", "SBIN.NS", "LT.NS", "HINDUNILVR.NS",
        "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "ADANIENT.NS",
        "SHRIRAMFIN.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "NTPC.NS",
        "AXISBANK.NS", "ADANIPORTS.NS", "POWERGRID.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
        "M&M.NS", "TATASTEEL.NS", "ULTRACEMCO.NS", "ASIANPAINT.NS", "JSWSTEEL.NS",
        "GRASIM.NS", "BEL.NS", "TRENT.NS", "TECHM.NS", "SHREECEM.NS",
        "CIPLA.NS", "INDUSINDBK.NS", "HINDALCO.NS", "BPCL.NS", "DRREDDY.NS",
        "TATACONSUM.NS", "NESTLEIND.NS", "EICHERMOT.NS", "APOLLOHOSP.NS", "WIPRO.NS",
        "SBILIFE.NS", "BRITANNIA.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "HEROMOTOCO.NS",
        "ZOMATO.NS", "JIOFIN.NS", "HAL.NS", "VEDL.NS", "DLF.NS",
        "CHOLAFIN.NS", "SIEMENS.NS", "ABB.NS", "TVSMOTOR.NS", "AMBUJACEM.NS",
        "GAIL.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS",
        "IOC.NS", "RECLTD.NS", "PFC.NS", "IRFC.NS", "RVNL.NS",
        "MAZDOCK.NS", "BHEL.NS", "ZYDUSLIFE.NS", "ADANIPOWER.NS", "ADANIGREEN.NS",
        "ATGL.NS", "HAVELLS.NS", "POLYCAB.NS", "CGPOWER.NS", "GODREJCP.NS",
        "PIDILITIND.NS", "DABUR.NS", "MARICO.NS", "BERGEPAINT.NS", "SRF.NS",
        "MOTHERSON.NS", "BOSCHLTD.NS", "CUMMINSIND.NS", "PERSISTENT.NS", "HAVELLS.NS",
        "COFORGE.NS", "MPHASIS.NS", "DIXON.NS", "TORNTPHARM.NS", "LUPIN.NS",
        "AUROPHARMA.NS", "ALKEM.NS", "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "ICICIGI.NS"
    ],
    "⚡ High-Beta Growth Midcaps": [
        "ZYDUSLIFE.NS", "BHEL.NS", "COALINDIA.NS", "ADANIPOWER.NS", "SUZLON.NS",
        "BEL.NS", "HAL.NS", "RVNL.NS", "IRFC.NS", "MAZDOCK.NS",
        "DIXON.NS", "POLYCAB.NS", "PERSISTENT.NS", "TRENT.NS", "IDFCFIRSTB.NS"
    ]
}

# -------------------------------------------------------------
# Indicators
# -------------------------------------------------------------
def calculate_hilega_milega(df, rsi_period=9, ema_period=3, wma_period=21):
    if len(df) < (rsi_period + wma_period):
        return df

    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)
    
    green_ema3 = rsi.ewm(span=ema_period, adjust=False).mean()
    weights = np.arange(1, wma_period + 1)
    wma21 = rsi.rolling(wma_period).apply(lambda s: np.dot(s, weights) / weights.sum(), raw=True)
    
    df['RSI_9'] = rsi
    df['Green_EMA3'] = green_ema3
    df['Red_WMA21'] = wma21
    df['Water_50'] = 50.0
    return df

def calculate_trend_craft_ict(df, default_period=45):
    if len(df) < 10:
        return df
    
    period = default_period if len(df) >= (default_period + 5) else max(8, len(df) // 2)
    df['TC_SMA_High'] = df['High'].rolling(period).mean()
    df['TC_SMA_Low'] = df['Low'].rolling(period).mean()
    df['TC_Period'] = period
    return df

def calculate_volume_analysis(df, sma_period=20):
    if 'Volume' not in df.columns or len(df) < 5:
        return df
        
    actual_period = sma_period if len(df) >= sma_period else max(3, len(df) // 2)
    df['Vol_SMA20'] = df['Volume'].rolling(actual_period).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
    
    if 'Open' in df.columns:
        df['Candle_Color'] = np.where(df['Close'] >= df['Open'], '#00E676', '#FF1744')
        df['Vol_Color'] = df['Candle_Color']
    else:
        df['Candle_Color'] = np.where(df['Close'] >= df['Close'].shift(1).fillna(df['Close']), '#00E676', '#FF1744')
        df['Vol_Color'] = df['Candle_Color']
        
    return df

def calculate_daily_pivot_points(df_d):
    """
    Standard Daily Pivot Points calculated from previous trading session's High, Low, Close.
    P = (H + L + C) / 3
    R1 = 2P - L, S1 = 2P - H
    R2 = P + (H - L), S2 = P - (H - L)
    R3 = H + 2*(P - L), S3 = L - 2*(H - P)
    """
    if len(df_d) < 2:
        return None
    prev = df_d.iloc[-2]
    h, l, c = float(prev['High']), float(prev['Low']), float(prev['Close'])
    p = (h + l + c) / 3.0
    r1 = (2.0 * p) - l
    s1 = (2.0 * p) - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    r3 = h + 2.0 * (p - l)
    s3 = l - 2.0 * (h - p)
    
    return {
        "p": round(p, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
        "prev_high": round(h, 2),
        "prev_low": round(l, 2),
        "prev_close": round(c, 2)
    }

# -------------------------------------------------------------
# Status Analysis
# -------------------------------------------------------------
def analyze_hm_timeframe(df, name="Timeframe"):
    if 'Red_WMA21' not in df.columns or df['Red_WMA21'].dropna().empty or len(df.dropna(subset=['Red_WMA21'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "bullish": False,
            "crossover": False, "crossover_bull": False, "crossover_bear": False, "above_water": False,
            "green": 50.0, "red": 50.0, "rsi": 50.0, "spread": 0.0,
            "prev_green": 50.0, "prev_red": 50.0,
            "green_slope": 0.0, "two_bar_green_slope": 0.0,
            "prev_spread": 0.0
        }
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3] if len(df) >= 3 else prev
    
    c_green = curr['Green_EMA3']
    p_green = prev['Green_EMA3']
    p2_green = prev2['Green_EMA3']
    c_red = curr['Red_WMA21']
    p_red = prev['Red_WMA21']
    c_rsi = curr['RSI_9']
    
    green_slope = c_green - p_green
    two_bar_green_slope = c_green - p2_green
    
    is_above_water = c_green >= 50.0 and c_red >= 50.0
    is_partly_above_water = c_green >= 50.0 or c_red >= 50.0
    is_green_above_red = c_green > c_red
    is_fresh_cross_bull = (p_green <= p_red) and (c_green > c_red)
    is_fresh_cross_bear = (p_green >= p_red) and (c_green < c_red)
    
    if is_fresh_cross_bull:
        status_text = "🟢 તાજો ગોલ્ડન ક્રોસઓવર (Fresh Buy Cross)"
        bullish = True
    elif is_fresh_cross_bear:
        status_text = "🔴 તાજો બેરિશ ક્રોસઓવર (Fresh Bear Cross)"
        bullish = False
    elif is_green_above_red and is_above_water:
        status_text = "🟢 સુપર તેજી (Bullish - પાણીની ઉપર)"
        bullish = True
    elif is_green_above_red and not is_above_water:
        status_text = "🟡 રિવર્સલ શરૂ (પાણીની નીચે ક્રોસ)"
        bullish = True
    elif not is_green_above_red and is_partly_above_water:
        status_text = "🟠 પ્રોફિટ બુકિંગ / પુલબેક (Pullback)"
        bullish = False
    else:
        status_text = "🔴 સંપૂર્ણ મંદી (Bearish - પાણીની નીચે)"
        bullish = False
        
    return {
        "name": name, "status": status_text, "bullish": bullish,
        "crossover": is_fresh_cross_bull, "crossover_bull": is_fresh_cross_bull,
        "crossover_bear": is_fresh_cross_bear, "above_water": is_above_water,
        "green": c_green, "red": c_red, "rsi": c_rsi, "spread": round(c_green - c_red, 2),
        "prev_green": p_green, "prev_red": p_red,
        "green_slope": green_slope, "two_bar_green_slope": two_bar_green_slope,
        "prev_spread": round(p_green - p_red, 2)
    }

def analyze_trend_craft_timeframe(df, name="Timeframe"):
    if 'TC_SMA_High' not in df.columns or len(df.dropna(subset=['TC_SMA_High'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "trend": "NEUTRAL",
            "bullish": False, "color": "gray", "close": 0.0, "tc_high": 0.0, "tc_low": 0.0, "is_pullback": False
        }
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    c = curr['Close']
    h = curr['TC_SMA_High']
    l = curr['TC_SMA_Low']
    
    if c > h:
        trend = "BULLISH"
        color = "green"
        bullish = True
        is_pullback = curr['Low'] <= (h * 1.012) and c >= h
        status_text = "🟢 ગ્રીન ચેનલની ઉપર (Bullish Trend)"
    elif c < l:
        trend = "BEARISH"
        color = "red"
        bullish = False
        is_pullback = False
        status_text = "🔴 રેડ ચેનલની નીચે (Bearish Trend)"
    else:
        if prev['Close'] > prev['TC_SMA_High']:
            trend = "PULLBACK_SUPPORT"
            color = "orange"
            bullish = True
            is_pullback = True
            status_text = "🎯 પુલબેક સપોર્ટ ટેસ્ટ (Inside Band Support)"
        else:
            trend = "CONSOLIDATION"
            color = "gray"
            bullish = False
            is_pullback = False
            status_text = "⚪ રેન્જ બાઉન્ડ / બેન્ડની અંદર (Consolidation)"
            
    return {
        "name": name, "status": status_text, "trend": trend, "bullish": bullish,
        "color": color, "close": c, "tc_high": h, "tc_low": l, "is_pullback": is_pullback
    }

def analyze_volume_timeframe(df, name="Timeframe"):
    if 'Vol_SMA20' not in df.columns or len(df.dropna(subset=['Vol_SMA20'])) < 2:
        return {
            "name": name, "status": "ડેટા અપૂરતો છે", "curr_vol": 0, "vol_sma": 0,
            "ratio": 1.0, "is_spike": False, "is_healthy_dip": False, "verdict": "Neutral"
        }
        
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    v = curr['Volume']
    v_sma = curr['Vol_SMA20']
    ratio = curr['Vol_Ratio'] if pd.notna(curr['Vol_Ratio']) else 1.0
    price_up = curr['Close'] >= prev['Close']
    
    is_spike = ratio >= 1.5
    is_healthy_dip = (not price_up) and (ratio < 0.85)
    
    if price_up and is_spike:
        status_text = f"🔥 ભારે ઇન્સ્ટિટ્યૂશનલ ખરીદી ({ratio:.1f}x Avg Volume)"
        verdict = "High Volume Bullish"
    elif price_up and ratio >= 1.0:
        status_text = f"🟢 સરેરાશથી વધુ વૉલ્યુમ સાથે તેજી ({ratio:.1f}x)"
        verdict = "Healthy Bullish"
    elif price_up and ratio < 1.0:
        status_text = f"⚠️ લો-વૉલ્યુમ તેજી / ફેકઆઉટ જોખમ ({ratio:.1f}x Avg)"
        verdict = "Weak Volume Bullish"
    elif not price_up and is_healthy_dip:
        status_text = f"🎯 લો-વૉલ્યુમ હેલ્ધી પુલબેક ({ratio:.1f}x - કોઈ મોટો સેલર નથી)"
        verdict = "Healthy Low-Volume Dip"
    elif not price_up and is_spike:
        status_text = f"🔴 પેનિક સેલિંગ / ઇન્સ્ટિટ્યૂશનલ ડિસ્ટ્રિબ્યુશન ({ratio:.1f}x Avg)"
        verdict = "Heavy Volume Selling"
    else:
        status_text = f"🟠 સરેરાશ વૉલ્યુમ સાથે ઘટાડો ({ratio:.1f}x)"
        verdict = "Moderate Selling"
        
    return {
        "name": name, "status": status_text, "curr_vol": v, "vol_sma": v_sma,
        "ratio": ratio, "is_spike": is_spike, "is_healthy_dip": is_healthy_dip,
        "price_up": price_up, "verdict": verdict
    }

def calculate_master_confluence_vpa(m_hm, w_hm, d_hm, h1_hm, m_tc, w_tc, d_tc, h1_tc, m_vol, w_vol, d_vol, h1_vol):
    score = 0
    checks = []
    
    # 1. Monthly Mega Trend (15 pts)
    if m_hm['bullish'] and m_hm['above_water'] and m_tc['bullish']:
        score += 15
        checks.append("✅ Monthly: HM + Trend Craft બંને 100% તેજીમાં (+15)")
    elif m_hm['bullish'] or m_tc['bullish']:
        score += 10
        checks.append("🟡 Monthly: લાંબો ગાળો આંશિક તેજી (+10)")
    else:
        checks.append("❌ Monthly: મંદી / પાણીની અંદર (0)")

    # 2. Weekly Swing Trend (20 pts)
    if w_hm['bullish'] and w_hm['above_water'] and w_tc['bullish']:
        score += 20
        checks.append("✅ Weekly: HM + Trend Craft મજબૂત સ્વિંગ તેજીમાં (+20)")
    elif w_hm['bullish'] or w_tc['bullish']:
        score += 12
        checks.append("🟡 Weekly: સ્વિંગ ટ્રેન્ડ આંશિક તેજી (+12)")
    else:
        checks.append("❌ Weekly: સ્વિંગ મંદી (0)")

    # 3. Daily Structure & Support (20 pts)
    if d_hm['bullish'] and d_tc['bullish']:
        score += 20
        checks.append("✅ Daily: ડેઇલી ચેનલ અને મોમેન્ટમ બંને બુલિશ (+20)")
    elif d_tc['is_pullback'] or d_tc['trend'] == "PULLBACK_SUPPORT":
        score += 18
        checks.append("🎯 Daily: ડેઇલી બેન્ડ સપોર્ટ પાસે પુલબેક (+18)")
    elif d_hm['bullish'] or d_tc['bullish']:
        score += 12
        checks.append("🟡 Daily: ડેઇલી ટ્રેન્ડ સારો (+12)")
    else:
        checks.append("❌ Daily: ડેઇલી કરેક્શન / મંદી (0)")

    # 4. 1-Hour Sniper Trigger (20 pts)
    if h1_hm['crossover'] and (h1_tc['trend'] in ["BULLISH", "PULLBACK_SUPPORT"]):
        score += 20
        checks.append("🚀 1-Hour: તાજો સ્નાઈપર ગોલ્ડન ક્રોસ + ગ્રીન બેન્ડ સપોર્ટ! (+20)")
    elif h1_hm['bullish'] and h1_tc['bullish']:
        score += 16
        checks.append("✅ 1-Hour: મોમેન્ટમ અને પ્રાઈસ બંને તેજીમાં (+16)")
    elif h1_tc['is_pullback']:
        score += 14
        checks.append("🎯 1-Hour: 1-Hour બેન્ડ સપોર્ટ પર બાઉન્સ (+14)")
    elif h1_hm['bullish']:
        score += 10
        checks.append("🟡 1-Hour: મોમેન્ટમ તેજી તરફી (+10)")
    else:
        checks.append("❌ 1-Hour: શોર્ટ-ટર્મ કરેક્શન / મંદી (0)")

    # 5. Volume (VPA) Confirmation (25 pts)
    vol_pts = 0
    if h1_vol['price_up'] and h1_vol['is_spike']:
        vol_pts += 15
        checks.append(f"🔥 1-Hour Volume: ઇન્સ્ટિટ્યૂશનલ સ્નાઈપર વૉલ્યુમ સ્પાઇક ({h1_vol['ratio']:.1f}x Avg) (+15)")
    elif h1_vol['is_healthy_dip']:
        vol_pts += 15
        checks.append(f"🎯 1-Hour Volume: પરફેક્ટ લો-વૉલ્યુમ ડીપ ({h1_vol['ratio']:.1f}x - કોઈ સેલર નથી) (+15)")
    elif h1_vol['price_up'] and h1_vol['ratio'] >= 1.0:
        vol_pts += 10
        checks.append(f"🟢 1-Hour Volume: એવરેજથી વધુ વૉલ્યુમ (+10)")
    elif h1_vol['price_up'] and h1_vol['ratio'] < 0.7:
        checks.append(f"⚠️ 1-Hour Volume: લો-વૉલ્યુમ ફેકઆઉટ જોખમ ({h1_vol['ratio']:.1f}x) (0)")
        
    if d_vol['price_up'] and d_vol['ratio'] >= 1.0:
        vol_pts += 10
        checks.append(f"✅ Daily Volume: ડેઇલી વૉલ્યુમ સપોર્ટેડ (+10)")
    elif d_vol['is_healthy_dip']:
        vol_pts += 10
        checks.append(f"🎯 Daily Volume: ડેઇલી લો-વૉલ્યુમ પુલબેક (+10)")
        
    score += min(vol_pts, 25)
    score = min(score, 100)

    # Daily HM & TC (Macro Trend Filter)
    d_hm_bull = (d_hm['green'] > d_hm['red']) and (d_hm['green'] >= 50.0)
    d_hm_bear = (d_hm['green'] < d_hm['red']) and (d_hm['green'] <= 50.0)
    d_bull_gap = d_hm['green'] - d_hm['red']
    d_bear_gap = d_hm['red'] - d_hm['green']
    d_is_positive = d_hm_bull and (d_bull_gap >= 2.5) and d_tc['bullish']
    d_is_negative = d_hm_bear and (d_bear_gap >= 2.5) and (not d_tc['bullish'])
    
    # 1-Hour Rocket / Avalanche Trigger (Strict Confluence)
    h1_green_slope = h1_hm.get('green_slope', h1_hm['green'] - h1_hm.get('prev_green', h1_hm['green']))
    h1_two_bar_green_slope = h1_hm.get('two_bar_green_slope', h1_green_slope)
    h1_bull_gap = h1_hm['green'] - h1_hm['red']
    h1_prev_bull_gap = h1_hm.get('prev_green', h1_hm['green']) - h1_hm.get('prev_red', h1_hm['red'])
    h1_bear_gap = h1_hm['red'] - h1_hm['green']
    h1_prev_bear_gap = h1_hm.get('prev_red', h1_hm['red']) - h1_hm.get('prev_green', h1_hm['green'])
    
    h1_vol_ratio = h1_vol.get('ratio', 1.0)
    h1_vol_confirmed = h1_vol_ratio >= 1.2
    
    # Image 5: Bullish Rocket Confluence (Daily Positive + 1H Vertical, Gap Expanding, Above Water 50, Vol >= 1.2x)
    h1_is_vertical_up = (h1_green_slope >= 1.8) or (h1_two_bar_green_slope >= 3.0)
    h1_gap_expanding_up = (h1_bull_gap >= 2.5) and (h1_bull_gap >= h1_prev_bull_gap)
    h1_above_water = (h1_hm['rsi'] >= 51.5) and (h1_hm['green'] >= 50.0)
    h1_hierarchy_bull = (h1_hm['rsi'] >= h1_hm['green'] - 1.5) and (h1_hm['green'] > h1_hm['red'])
    h1_tc_confirmed_bull = h1_tc.get('bullish', False)
    
    is_sniper_buy = (
        d_is_positive and
        h1_is_vertical_up and
        h1_hierarchy_bull and
        h1_gap_expanding_up and
        h1_above_water and
        h1_tc_confirmed_bull and
        h1_vol_confirmed
    )
    
    # Image 4: Bearish Avalanche Confluence (Daily Negative + 1H Vertical, Gap Expanding, Below Water 50, Vol >= 1.2x)
    h1_is_vertical_down = (h1_green_slope <= -1.8) or (h1_two_bar_green_slope <= -3.0)
    h1_gap_expanding_down = (h1_bear_gap >= 2.5) and (h1_gap_expanding_down := (h1_bear_gap >= h1_prev_bear_gap))
    h1_below_water = (h1_hm['rsi'] <= 48.5) and (h1_hm['green'] <= 50.0)
    h1_hierarchy_bear = (h1_hm['rsi'] <= h1_hm['green'] + 1.5) and (h1_hm['green'] < h1_hm['red'])
    h1_tc_confirmed_bear = not h1_tc.get('bullish', True)
    
    is_sniper_short = (
        d_is_negative and
        h1_is_vertical_down and
        h1_hierarchy_bear and
        h1_gap_expanding_down and
        h1_below_water and
        h1_tc_confirmed_bear and
        h1_vol_confirmed
    )
    
    is_buy_pullback = d_is_positive and not is_sniper_buy
    is_relief_bounce = d_is_negative and not is_sniper_short
    
    is_1h_confirmed_bullish = h1_is_vertical_up and h1_gap_expanding_up and h1_above_water and h1_tc_confirmed_bull
    is_inside_tc = (d_tc['close'] >= d_tc['tc_low'] * 0.985) and (d_tc['close'] <= d_tc['tc_high'] * 1.015)
    is_range_bound = is_inside_tc and (36 <= score <= 64) and (36 <= d_hm['rsi'] <= 64)

    if is_sniper_buy:
        verdict = "🎯 SNIPER DIP BUY (તાત્કાલિક ખરીદી સેટઅપ)"
        verdict_type = "success"
        pill_class = "pill-sniper-buy"
        explanation = (
            "Daily ચાર્ટ પર ટ્રેન્ડ સુપર પોઝિટિવ છે (Green > Red + Gap Expanding). "
            "1-Hour ચાર્ટ પર Black (RSI) અને Green (EMA) બંને Red લાઈનથી એકદમ વર્ટિકલ ઉપર છૂટી પડ્યા છે (Rocket Launch) "
            "અને સંસ્થાકીય વોલ્યુમ (>=1.2x) સાથે પાણી (50) ની ઉપર સંપૂર્ણ કન્ફર્મ થઈ ગયા છે!"
        )
        stars = "⭐⭐⭐⭐⭐"
    elif is_buy_pullback:
        verdict = "⏳ BUY ON DIPS (પુલબેક ચાલુ • 1H ક્રોસની રાહ જુઓ)"
        verdict_type = "info"
        pill_class = "pill-buy-dips"
        explanation = (
            "Daily ચાર્ટ પર મોટો ટ્રેન્ડ મજબૂત તેજીમાં છે (Positive Trend), પરંતુ 1-Hour ચાર્ટ પર હજુ સુધી સ્નાઈપર રોકેટ ટ્રિગર નથી થયું. "
            "પડતી કેન્ડલમાં ઉતાવળે ખરીદવાને બદલે 1-Hour માં Green અને Black લાઇન Red થી વર્ટિકલ છૂટી પડે અને વોલ્યુમ આવે ત્યારે જ એન્ટ્રી કરવી!"
        )
        stars = "⭐⭐⭐⭐"
    elif is_sniper_short:
        verdict = "🩸 SNIPER SHORT SELL (ઉછાળે વેચો / શોર્ટ એન્ટ્રી)"
        verdict_type = "error"
        pill_class = "pill-sniper-short"
        explanation = (
            "Daily ચાર્ટ પર ટ્રેન્ડ નેગેટિવ છે (Green < Red + Bear Gap Expanding). "
            "1-Hour ચાર્ટ પર Black (RSI) અને Green (EMA) બંને Red લાઈનથી વર્ટિકલ નીચે ડૂબી ગયા છે (Avalanche Dump) "
            "અને ભારે સેલિંગ વોલ્યુમ (>=1.2x) સાથે પાણી (50) ની નીચે સંપૂર્ણ કન્ફર્મ થઈ ગયા છે!"
        )
        stars = "⭐⭐⭐⭐⭐"
    elif is_relief_bounce:
        verdict = "⚠️ SHORT ON BOUNCE (ઉછાળો પૂરો થવાની રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-sell"
        explanation = (
            "Daily મોટા ટ્રેન્ડમાં મંદી છે, પરંતુ 1-Hour ચાર્ટ પર હજુ શોર્ટ માટે સંપૂર્ણ કન્ફર્મેશન નથી મળ્યું. "
            "તળિયે વેચવાને બદલે 1-Hour માં વર્ટિકલ ડાઉનવર્ડ સ્લોપ અને વોલ્યુમ સાથે એન્ટ્રી મળશે!"
        )
        stars = "⭐⭐⭐⭐"
    elif score >= 80 and is_1h_confirmed_bullish and h1_vol_confirmed:
        verdict = "🚀 PERFECT STRONG BUY (તાત્કાલિક એન્ટ્રી સેટઅપ)"
        verdict_type = "success"
        pill_class = "pill-strong-buy"
        explanation = (
            "Monthly, Weekly, Daily અને 1-Hour ચારેય ટાઇમફ્રેમ્સ પર સંપૂર્ણ કન્ફર્મ તેજી છે અને 1-Hour માં પણ બાય ટ્રિગર થઈ ગયું છે! "
            "મોટું ઇન્સ્ટિટ્યૂશનલ વૉલ્યુમ અને પ્રાઈસ બ્રેકઆઉટ સાથે આ સુપર હાઈ-પ્રોબેબિલિટી બાય સેટઅપ છે."
        )
        stars = "⭐⭐⭐⭐⭐"
    elif score >= 65:
        if not is_1h_confirmed_bullish or h1_vol['is_healthy_dip'] or d_tc['is_pullback']:
            verdict = "⏳ BUY ON DIPS (પુલબેક ચાલુ • 1H ક્રોસની રાહ જુઓ)"
            verdict_type = "info"
            pill_class = "pill-buy-dips"
            explanation = (
                "Monthly, Weekly અને Daily મોટા ટ્રેન્ડ ખૂબ મજબૂત છે, પરંતુ 1-Hour ચાર્ટ પર હાલમાં કરેક્શન/પુલબેક (Dip) ચાલે છે. "
                "પડતી કેન્ડલમાં ખરીદવાને બદલે 1-Hour માં ગ્રીન લાઇન રેડ લાઇનને ક્રોસ કરીને ઉપર વળે ત્યારે સૌથી ઓછા રિસ્કે ઉત્તમ એન્ટ્રી મળશે!"
            )
            stars = "⭐⭐⭐⭐"
        else:
            verdict = "🟢 MODERATE BULLISH (સ્વિંગ બાય સેટઅપ)"
            verdict_type = "success"
            pill_class = "pill-bullish"
            explanation = "મોટાભાગના ટાઇમફ્રેમ્સ તેજીમાં છે. સ્ટોપ-લોસ સાથે પોઝિશન રાખી શકાય છે."
            stars = "⭐⭐⭐"
    elif is_range_bound:
        verdict = "⚖️ RANGE-BOUND / OPTION SELLING (ઓપ્શન સેલિંગ)"
        verdict_type = "info"
        pill_class = "pill-option-sell"
        explanation = (
            f"સ્ટોક Daily Trend Craft ચેનલમાં ₹{d_tc['tc_low']:.1f} થી ₹{d_tc['tc_high']:.1f} વચ્ચે સજ્જડ રેન્જ-બાઉન્ડ કન્સોલિડેટ થાય છે. "
            f"મોટા ડાયરેક્શનલ ટ્રેન્ડના અભાવે બંને બાજુ OTM Call (>{d_tc['tc_high']:.1f}) અને OTM Put (<{d_tc['tc_low']:.1f}) વેચીને થીટા ડીકે (Theta Decay) "
            f"કમાવા માટે આ આદર્શ સેટઅપ છે (Short Strangle / Iron Condor)."
        )
        stars = "⭐⭐⭐"
    elif is_relief_bounce and score <= 45:
        verdict = "⚠️ SHORT ON BOUNCE (ઉછાળો પૂરો થવાની રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-sell"
        explanation = (
            "Daily મોટા ટ્રેન્ડમાં ભારે મંદી છે, પરંતુ 1-Hour ચાર્ટ પર હાલમાં ટેમ્પરરી ઉછાળો (Relief Bounce) ચાલે છે. "
            "તળિયે વેચવાને બદલે 1-Hour માં Green લાઇન Red લાઇન નીચે ક્રોસ થાય (Bear Cross) ત્યારે શ્રેષ્ઠ સ્નાઈપર શોર્ટ એન્ટ્રી મળશે!"
        )
        stars = "⭐⭐⭐⭐"
    elif score >= 40:
        verdict = "⏳ WAIT FOR CONFIRMATION (રાહ જુઓ)"
        verdict_type = "warning"
        pill_class = "pill-neutral"
        explanation = "સિગ્નલો મિશ્ર છે અથવા વૉલ્યુમ સપોર્ટ નથી. 1-Hour અથવા Daily માં વૉલ્યુમ સાથે સ્પષ્ટ ક્રોસઓવર થાય ત્યાં સુધી રાહ જુઓ."
        stars = "⭐⭐"
    else:
        verdict = "🔴 STRONG AVOID / BEARISH (સંપૂર્ણ મંદી - ખરીદી ટાળો)"
        verdict_type = "error"
        pill_class = "pill-sell"
        explanation = "સ્ટોક તમામ ટાઈમફ્રેમ્સમાં મંદીમાં છે અને વૉલ્યુમ સાથે સેલિંગ પ્રેશર દેખાય છે. અત્યારે આ સ્ટોકમાં ખરીદી કરવી જોખમી છે."
        stars = "⭐"

    stoploss_1h = h1_tc['tc_low'] if h1_tc['tc_low'] > 0 else d_tc['tc_low']
    stoploss_1h_short = h1_tc['tc_high'] if h1_tc['tc_high'] > 0 else d_tc['tc_high']

    return {
        "score": score,
        "stars": stars,
        "verdict": verdict,
        "verdict_type": verdict_type,
        "pill_class": pill_class,
        "explanation": explanation,
        "checks": checks,
        "stoploss_1h": stoploss_1h,
        "stoploss_1h_short": stoploss_1h_short,
        "stoploss_daily": d_tc['tc_low'],
        "stoploss_daily_short": d_tc['tc_high'],
        "is_1h_confirmed": is_1h_confirmed_bullish,
        "is_sniper_buy": is_sniper_buy,
        "is_buy_pullback": is_buy_pullback,
        "is_sniper_short": is_sniper_short,
        "is_relief_bounce": is_relief_bounce,
        "d_bull_gap": d_bull_gap,
        "d_bear_gap": d_bear_gap
    }

# -------------------------------------------------------------
# 3-Panel Synchronized Candlestick Chart (Dark Terminal Themed)
# -------------------------------------------------------------
def plot_candlestick_triple_chart(df, title_prefix="Daily", lookback=100, is_hourly=False):
    plot_df = df.dropna(subset=['Red_WMA21', 'TC_SMA_High', 'Vol_SMA20', 'Open', 'High', 'Low', 'Close']).tail(lookback).copy().reset_index()
    
    if 'Datetime' in plot_df.columns:
        date_col = 'Datetime'
    elif 'Date' in plot_df.columns:
        date_col = 'Date'
    else:
        date_col = plot_df.columns[0]
        
    date_axis_format = '%d %b %H:%M' if is_hourly else '%d %b %Y'
    bar_width = 5 if is_hourly else 6
    
    base = alt.Chart(plot_df).encode(x=alt.X(f'{date_col}:T', title=''))
    
    # PANEL 1: Candlestick + Trend Craft Envelopes
    band = base.mark_area(opacity=0.18, color='#00E676').encode(
        y=alt.Y('TC_SMA_High:Q', title='Price (₹)', scale=alt.Scale(zero=False)),
        y2='TC_SMA_Low:Q'
    )
    line_high = base.mark_line(color='#00E676', strokeWidth=1.8).encode(y='TC_SMA_High:Q')
    line_low = base.mark_line(color='#FF5252', strokeWidth=1.8).encode(y='TC_SMA_Low:Q')
    
    wicks = base.mark_rule(strokeWidth=1.2).encode(
        y=alt.Y('Low:Q', scale=alt.Scale(zero=False)),
        y2='High:Q',
        color=alt.Color('Candle_Color:N', scale=None)
    )
    
    bodies = base.mark_bar(size=bar_width).encode(
        y='Open:Q',
        y2='Close:Q',
        color=alt.Color('Candle_Color:N', scale=None),
        tooltip=[
            alt.Tooltip(f'{date_col}:T', title='Date/Time'),
            alt.Tooltip('Open:Q', title='Open (₹)', format='.2f'),
            alt.Tooltip('High:Q', title='High (₹)', format='.2f'),
            alt.Tooltip('Low:Q', title='Low (₹)', format='.2f'),
            alt.Tooltip('Close:Q', title='Close (₹)', format='.2f'),
            alt.Tooltip('TC_SMA_High:Q', title='TC High Band', format='.2f'),
            alt.Tooltip('TC_SMA_Low:Q', title='TC Low Band', format='.2f')
        ]
    )
    
    chart_candlestick = (band + line_high + line_low + wicks + bodies).properties(
        title=f"🕯️ {title_prefix} • Candlestick & Trend Craft ICT Channel (🟢 High Band | 🔴 Low Band)",
        height=270
    )
    
    # PANEL 2: Institutional Volume & 20 SMA
    vol_bars = base.mark_bar(opacity=0.8, size=bar_width).encode(
        y=alt.Y('Volume:Q', title='Volume', axis=alt.Axis(format='~s')),
        color=alt.Color('Vol_Color:N', scale=None),
        tooltip=[
            alt.Tooltip(f'{date_col}:T', title='Date/Time'),
            alt.Tooltip('Volume:Q', title='Volume', format=',.0f'),
            alt.Tooltip('Vol_SMA20:Q', title='20 SMA Vol', format=',.0f'),
            alt.Tooltip('Vol_Ratio:Q', title='Vol Ratio', format='.2f')
        ]
    )
    vol_line = base.mark_line(color='#FBBF24', strokeWidth=2).encode(y='Vol_SMA20:Q')
    chart_vol = (vol_bars + vol_line).properties(
        title=f"📊 {title_prefix} • Volume & 20 SMA (🟢 Bullish / 🔴 Bearish | 🟡 20-SMA)",
        height=110
    )
    
    # PANEL 3: NK Sir Hilega Milega
    water_rule = alt.Chart(pd.DataFrame({'y': [50.0]})).mark_rule(
        color='#38BDF8', strokeDash=[6, 4], strokeWidth=1.8, opacity=0.8
    ).encode(y='y:Q')
    
    melt_df = plot_df.melt(
        id_vars=[date_col, 'Close'],
        value_vars=['Green_EMA3', 'Red_WMA21', 'RSI_9'],
        var_name='Indicator',
        value_name='Value'
    )
    name_map = {
        'Green_EMA3': '🟢 Green (3 EMA - Price)',
        'Red_WMA21': '🔴 Red (21 WMA - Strength)',
        'RSI_9': '🟡 Yellow (RSI 9 - Momentum)'
    }
    melt_df['Indicator'] = melt_df['Indicator'].map(name_map)
    
    lines_hm = alt.Chart(melt_df).mark_line(strokeWidth=2.2).encode(
        x=alt.X(f'{date_col}:T', title='', axis=alt.Axis(format=date_axis_format, labelAngle=-30)),
        y=alt.Y('Value:Q', scale=alt.Scale(domain=[10, 95]), title='Hilega Milega'),
        color=alt.Color('Indicator:N', scale=alt.Scale(
            domain=[
                '🟢 Green (3 EMA - Price)',
                '🔴 Red (21 WMA - Strength)',
                '🟡 Yellow (RSI 9 - Momentum)'
            ],
            range=['#00E676', '#FF1744', '#FFD600']
        ), legend=alt.Legend(
            title="", orient="top", titleFontSize=11, labelFontSize=11, symbolStrokeWidth=3, symbolSize=80
        )),
        tooltip=[
            alt.Tooltip(f'{date_col}:T', title='Date/Time'),
            alt.Tooltip('Close:Q', title='Price (₹)', format='.2f'),
            alt.Tooltip('Indicator:N', title='Line'),
            alt.Tooltip('Value:Q', title='Value', format='.2f')
        ]
    )
    chart_hm = (water_rule + lines_hm).properties(
        title=f"🎯 {title_prefix} • NK Sir Hilega Milega (🟢 3 EMA | 🔴 21 WMA | 🟡 RSI 9 | 🌊 50 Water)",
        height=180
    )
    
    combined = alt.vconcat(chart_candlestick, chart_vol, chart_hm).resolve_scale(x='shared')
    return combined.configure(
        background='transparent',
        view=alt.ViewConfig(strokeWidth=0),
        title=alt.TitleConfig(color='#F1F5F9', fontSize=13, fontWeight=600, anchor='start'),
        axis=alt.AxisConfig(
            domainColor='#334155',
            gridColor='rgba(255, 255, 255, 0.05)',
            labelColor='#94A3B8',
            tickColor='#334155',
            titleColor='#CBD5E1',
            labelFontSize=11,
            titleFontSize=11
        ),
        legend=alt.LegendConfig(
            labelColor='#CBD5E1',
            titleColor='#F1F5F9',
            labelFontSize=11
        )
    )

# -------------------------------------------------------------
# Function: Scan a Single Stock for Screener
# -------------------------------------------------------------
def scan_stock(sym):
    try:
        clean_sym = sym.strip().upper()
        if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO") and not clean_sym.startswith("^"):
            ticker_sym = f"{clean_sym}.NS"
        else:
            ticker_sym = clean_sym
            
        ticker = yf.Ticker(ticker_sym)
        df_d = ticker.history(period="1y", interval="1d").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_w = ticker.history(period="3y", interval="1wk").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_m = ticker.history(period="5y", interval="1mo").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df_1h = ticker.history(period="1mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume'])
        
        if df_d.empty or len(df_d) < 30 or df_1h.empty:
            return None
            
        df_m = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_m), 24))
        df_w = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_w), 30))
        df_d = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_d), 45))
        df_1h = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_1h), 45))
        
        m_hm = analyze_hm_timeframe(df_m, "Monthly")
        w_hm = analyze_hm_timeframe(df_w, "Weekly")
        d_hm = analyze_hm_timeframe(df_d, "Daily")
        h1_hm = analyze_hm_timeframe(df_1h, "1-Hour")
        
        m_tc = analyze_trend_craft_timeframe(df_m, "Monthly")
        w_tc = analyze_trend_craft_timeframe(df_w, "Weekly")
        d_tc = analyze_trend_craft_timeframe(df_d, "Daily")
        h1_tc = analyze_trend_craft_timeframe(df_1h, "1-Hour")
        
        m_vol = analyze_volume_timeframe(df_m, "Monthly")
        w_vol = analyze_volume_timeframe(df_w, "Weekly")
        d_vol = analyze_volume_timeframe(df_d, "Daily")
        h1_vol = analyze_volume_timeframe(df_1h, "1-Hour")
        
        conf = calculate_master_confluence_vpa(
            m_hm, w_hm, d_hm, h1_hm,
            m_tc, w_tc, d_tc, h1_tc,
            m_vol, w_vol, d_vol, h1_vol
        )
        
        curr_p = df_d['Close'].iloc[-1]
        prev_p = df_d['Close'].iloc[-2]
        pct_chg = ((curr_p - prev_p) / prev_p) * 100
        
        levels = calculate_trade_levels(curr_p, conf['stoploss_1h'])
        is_1h_bull = h1_hm['crossover'] or (h1_hm['bullish'] and h1_tc['bullish'])
        
        # Check consolidation for Option Selling (Short Strangle / Iron Condor)
        h20 = df_d['High'].tail(20).max() if len(df_d) >= 20 else curr_p * 1.05
        l20 = df_d['Low'].tail(20).min() if len(df_d) >= 20 else curr_p * 0.95
        span_20d = ((h20 - l20) / curr_p) * 100
        is_in_band = (curr_p >= d_tc['tc_low'] * 0.97) and (curr_p <= d_tc['tc_high'] * 1.03)
        d_rsi = df_d['RSI_9'].iloc[-1] if 'RSI_9' in df_d.columns else 50.0
        
        is_option_selling = (
            is_in_band and 
            (span_20d <= 11.5) and 
            (36 <= d_rsi <= 64) and 
            (conf['score'] < 75)
        )
        
        is_sniper_buy = conf.get('is_sniper_buy', False)
        is_buy_pullback = conf.get('is_buy_pullback', False)
        is_sniper_short = conf.get('is_sniper_short', False)
        is_relief_bounce = conf.get('is_relief_bounce', False)
        
        strike_step = 20 if curr_p < 500 else (50 if curr_p < 2500 else 100)
        
        # Calculate Daily Pivot Points & R3 Option Radar
        pivots = calculate_daily_pivot_points(df_d)
        is_r3_radar = False
        otm_call_strike = round(curr_p * 1.015 / strike_step) * strike_step
        if otm_call_strike <= curr_p:
            otm_call_strike = (int(curr_p / strike_step) + 1) * strike_step
        pivot_status = "P Neutral"
        r1_val = 0.0
        r2_val = 0.0
        r3_val = 0.0
        p_val = 0.0
        
        if pivots:
            p_val = pivots['p']
            r1_val = pivots['r1']
            r2_val = pivots['r2']
            r3_val = pivots['r3']
            s1_val = pivots['s1']
            s2_val = pivots['s2']
            s3_val = pivots['s3']
            
            if curr_p >= r3_val:
                pivot_status = f"🚀 Above R3 (₹{r3_val:.1f})"
            elif curr_p >= r2_val:
                pivot_status = f"🔥 Above R2 (₹{r2_val:.1f})"
            elif curr_p >= r1_val:
                pivot_status = f"⚡ Above R1 (₹{r1_val:.1f})"
            elif curr_p >= p_val:
                pivot_status = f"🟢 Above P (₹{p_val:.1f})"
            elif curr_p <= s3_val:
                pivot_status = f"🩸 Below S3 (₹{s3_val:.1f})"
            elif curr_p <= s2_val:
                pivot_status = f"🔴 Below S2 (₹{s2_val:.1f})"
            elif curr_p <= s1_val:
                pivot_status = f"⚠️ Below S1 (₹{s1_val:.1f})"
            else:
                pivot_status = f"🟡 Below P (₹{p_val:.1f})"
                
            otm_call_strike = int((int(curr_p / strike_step) + 1) * strike_step)
            is_r3_radar = bool(
                (pct_chg >= 1.5 or curr_p >= r2_val) and
                (curr_p >= r1_val) and
                (d_hm.get('bullish', False) or pct_chg >= 2.0)
            )

        # Guarantee strictly Out-Of-The-Money (OTM) strikes for Option Selling
        ce_sell_strike = max(d_tc['tc_high'], curr_p * 1.015)
        pe_sell_strike = min(d_tc['tc_low'], curr_p * 0.985)
        
        if is_sniper_buy:
            signal_cat = "🎯 Sniper Dip Buy"
            pill_class = "pill-sniper-buy"
        elif is_sniper_short:
            signal_cat = "🩸 Sniper Short Sell"
            pill_class = "pill-sniper-short"
        elif is_buy_pullback or (conf['score'] >= 65 and not is_1h_bull):
            signal_cat = "⏳ Buy on Dips"
            pill_class = "pill-buy-dips"
        elif is_relief_bounce:
            signal_cat = "⚠️ Short on Bounce"
            pill_class = "pill-sell"
        elif conf['score'] >= 80 and is_1h_bull:
            signal_cat = "🚀 Strong Buy"
            pill_class = "pill-strong-buy"
        elif conf['score'] >= 60 and is_1h_bull:
            signal_cat = "🟢 Bullish"
            pill_class = "pill-bullish"
        elif is_option_selling:
            signal_cat = "⚖️ Option Selling (Range)"
            pill_class = "pill-option-sell"
        elif conf['score'] <= 35:
            signal_cat = "🔴 Strong Sell"
            pill_class = "pill-sell"
        elif conf['score'] < 50:
            signal_cat = "🟠 Weak / Bearish"
            pill_class = "pill-sell"
        else:
            signal_cat = "⏳ Neutral"
            pill_class = "pill-neutral"
            
        if is_sniper_buy:
            levels_buy = calculate_trade_levels(curr_p, conf['stoploss_1h'], is_short=False)
            t1_display = f"₹{levels_buy['t1']:.1f} (+{levels_buy['t1_pct']:.1f}%)"
            t2_display = f"₹{levels_buy['t2']:.1f} (+{levels_buy['t2_pct']:.1f}%)"
            sl_display = f"₹{levels_buy['stop_loss']:.1f} (-{levels_buy['risk_pct']:.1f}%)"
            ce_strike = round(curr_p * 1.005 / strike_step) * strike_step
            pe_strike = round(min(d_tc['tc_low'], curr_p * 0.98) / strike_step) * strike_step
        elif is_sniper_short:
            levels_short = calculate_trade_levels(curr_p, conf['stoploss_1h_short'], is_short=True)
            t1_display = f"₹{levels_short['t1']:.1f} (-{levels_short['t1_pct']:.1f}%)"
            t2_display = f"₹{levels_short['t2']:.1f} (-{levels_short['t2_pct']:.1f}%)"
            sl_display = f"₹{levels_short['stop_loss']:.1f} (+{levels_short['risk_pct']:.1f}%)"
            pe_strike = round(curr_p * 0.995 / strike_step) * strike_step
            ce_strike = round(max(d_tc['tc_high'], curr_p * 1.025) / strike_step) * strike_step
        elif "Option Selling" in signal_cat:
            t1_display = f"CE Sell: >₹{ce_sell_strike:.1f}"
            t2_display = f"PE Sell: <₹{pe_sell_strike:.1f}"
            sl_display = f"Band: ₹{pe_sell_strike:.0f}-₹{ce_sell_strike:.0f}"
            pe_strike = pe_sell_strike
            ce_strike = ce_sell_strike
        elif "Short on Bounce" in signal_cat:
            t1_display = "ઉછાળો ટેસ્ટિંગ"
            t2_display = "1H ક્રોસ પર એન્ટ્રી"
            sl_display = f"₹{conf['stoploss_1h_short']:.1f}"
            pe_strike = None
            ce_strike = None
        elif ("Sell" in signal_cat or "Bearish" in signal_cat):
            t1_display = "-"
            t2_display = "-"
            sl_display = f"₹{levels['stop_loss']:.1f}"
            pe_strike = None
            ce_strike = None
        else:
            t1_display = f"₹{levels['t1']:.1f} (+{levels['t1_pct']:.1f}%)"
            t2_display = f"₹{levels['t2']:.1f} (+{levels['t2_pct']:.1f}%)"
            sl_display = f"₹{levels['stop_loss']:.1f} (-{levels['risk_pct']:.1f}%)"
            ce_strike = round(curr_p * 1.005 / strike_step) * strike_step
            pe_strike = round(min(d_tc['tc_low'], curr_p * 0.98) / strike_step) * strike_step
            
        # 1-Hour Trigger indicator
        if h1_hm.get('crossover_bull', False):
            h1_trigger_display = "🚀 Bull Cross ⬆️"
        elif h1_hm.get('crossover_bear', False):
            h1_trigger_display = "🩸 Bear Cross ⬇️"
        elif is_sniper_buy:
            h1_trigger_display = "🟢 Reversal Trigger"
        elif is_sniper_short:
            h1_trigger_display = "🔴 Rejection Trigger"
        elif h1_hm['bullish']:
            h1_trigger_display = "🟢 Bullish"
        else:
            h1_trigger_display = "🟡 Dip Pullback ⏳"
            
        # Daily HM indicator
        d_bull_gap = d_hm['green'] - d_hm['red']
        d_bear_gap = d_hm['red'] - d_hm['green']
        if d_bull_gap >= 3.0:
            daily_hm_display = f"🟢 Rocket (+{d_bull_gap:.1f})"
        elif d_bull_gap > 0:
            daily_hm_display = f"🟢 Bull (+{d_bull_gap:.1f})"
        elif d_bear_gap >= 3.0:
            daily_hm_display = f"🔴 Avalanche (-{d_bear_gap:.1f})"
        else:
            daily_hm_display = f"🔴 Bear (-{d_bear_gap:.1f})"
            
        return {
            "Symbol": clean_sym.replace(".NS", ""),
            "FullSymbol": ticker_sym,
            "Price (₹)": round(curr_p, 2),
            "Change (%)": round(pct_chg, 2),
            "Signal": signal_cat,
            "PillClass": pill_class,
            "Score": conf['score'],
            "Target 1 (₹)": t1_display,
            "Target 2 (₹)": t2_display,
            "Stop Loss (1H)": sl_display,
            "Daily HM": daily_hm_display,
            "1H Trigger": h1_trigger_display,
            "1H Vol Ratio": f"{h1_vol['ratio']:.1f}x" + (" 🔥" if h1_vol['is_spike'] else ""),
            "Daily TC Band": "Green Band" if d_tc['trend'] == "BULLISH" else ("Pullback 🎯" if d_tc['trend'] == "PULLBACK_SUPPORT" else ("Range ⚖️" if is_option_selling else "Red Band 🔴")),
            "tc_high": round(ce_sell_strike, 1),
            "tc_low": round(pe_sell_strike, 1),
            "is_sniper_buy": is_sniper_buy,
            "is_sniper_short": is_sniper_short,
            "pe_strike": pe_strike,
            "ce_strike": ce_strike,
            "is_r3_radar": is_r3_radar,
            "otm_call_strike": otm_call_strike,
            "pivot_status": pivot_status,
            "r1": r1_val,
            "r2": r2_val,
            "r3": r3_val,
            "pivot_p": p_val
        }
    except Exception:
        return None

# =============================================================
# TOP HEADER & LIVE TICKER RIBBON
# =============================================================
nifty_data = get_nifty_sentiment()
if nifty_data:
    n_chg_sign = "+" if nifty_data['change'] >= 0 else ""
    n_chip_class = "ticker-chip-bull" if nifty_data['is_bullish'] else "ticker-chip-bear"
    n_arrow = "▲" if nifty_data['is_bullish'] else "▼"
    n_trend = "BULLISH 🟢" if nifty_data['is_bullish'] else "BEARISH 🔴"
    nifty_html = f'<div class="ticker-chip {n_chip_class}"><span>🏛️ <b>NIFTY 50:</b> ₹{nifty_data["price"]:,.2f}</span><span>{n_arrow} {n_chg_sign}{nifty_data["change"]:.2f} ({n_chg_sign}{nifty_data["pct"]:.2f}%)</span><span style="opacity: 0.5">•</span><span>{n_trend}</span></div>'
else:
    nifty_html = '<div class="ticker-chip"><span>🏛️ <b>NIFTY 50:</b> Connecting...</span></div>'

telegram_html = '<div class="ticker-chip ticker-chip-bot"><div class="pulse-dot"></div><span><b>TELEGRAM BOT:</b> @patel_stock_bot</span><span style="opacity: 0.5">•</span><span>⚡ 5-Min Auto-Scanner Active</span></div>'

header_html = f'<div class="brand-container"><div><div style="display: flex; align-items: center; gap: 12px;"><span class="brand-title">🎯 CONFLUENCE PRO</span><span class="brand-badge">INSTITUTIONAL v2.5</span></div><div class="brand-subtitle">Candlestick Price Channels • Hilega-Milega • Institutional Volume VPA • Precision Targets & Stop-Loss</div></div></div><div class="ticker-bar">{nifty_html}{telegram_html}</div>'
st.html(header_html)

# Navigation Tabs
nav_tab_screener, nav_tab_single, nav_tab_guardian, nav_tab_melting = st.tabs([
    "📊 Market Screener (ઓટોમેટિક સ્કેનર)",
    "🕯️ Single Stock (ડીપ કેન્ડલસ્ટિક ચાર્ટ્સ)",
    "🛡️ Risk Guardian (લાઈવ પોઝિશન & મોનિટર)",
    "🎯 Melting Straddles (ડૉ. ગાંગુલી 0DTE)"
])

# =============================================================
# TAB 1: LIVE MULTI-TIMEFRAME STOCK SCREENER
# =============================================================
with nav_tab_screener:
    with st.container():
        col_b1, col_b2, col_b3 = st.columns([2.4, 1.2, 1.6])
        with col_b1:
            selected_basket = st.selectbox(
                "સ્કેન કરવા માટે સ્ટોક બાસ્કેટ પસંદ કરો:",
                options=list(BASKETS.keys()) + ["✍️ Custom Watchlist (પોતાની લિસ્ટ નાખો)"],
                label_visibility="visible",
                key="screener_basket_select"
            )
        
        custom_symbols_text = ""
        if "Custom Watchlist" in selected_basket:
            custom_symbols_text = st.text_area(
                "તમારી પસંદના સ્ટોક નામો લખો (અલ્પવિરામ / Comma વડે અલગ કરો):",
                value="BHEL, ZYDUSLIFE, COALINDIA, RELIANCE, ADANIPOWER, TCS, BEL, SUZLON"
            )
        
        with col_b2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            start_scan = st.button("🚀 Scan Market Now", type="primary", use_container_width=True)

        with col_b3:
            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            auto_col1, auto_col2 = st.columns([1.05, 1.35])
            with auto_col1:
                auto_update_enabled = st.toggle("🔄 Auto-Update", value=True, help="ઓટોમેટિક લાઈવ ડેટા અપડેટ ચાલુ/બંધ કરો")
            with auto_col2:
                freq_choice = st.selectbox(
                    "આવર્તન",
                    options=["⚡ 1 Min (60s)", "⏱️ 2 Min (120s)", "⏳ 5 Min (300s)"],
                    index=0,
                    label_visibility="collapsed",
                    disabled=not auto_update_enabled
                )

    freq_seconds_map = {
        "⚡ 1 Min (60s)": 60,
        "⏱️ 2 Min (120s)": 120,
        "⏳ 5 Min (300s)": 300
    }
    interval_sec = freq_seconds_map.get(freq_choice, 60)
    interval_ms = interval_sec * 1000

    # Auto-load cached scan results on startup
    if "screener_results" not in st.session_state or st.session_state.screener_results is None:
        st.session_state.screener_results = None
        st.session_state.screener_last_updated = None
        st.session_state.screener_last_scan_ts = 0.0
        if os.path.exists("screener_cache.json"):
            try:
                with open("screener_cache.json", "r", encoding="utf-8") as f:
                    cache_obj = json.load(f)
                    if "data" in cache_obj and len(cache_obj["data"]) > 0:
                        df_cached = pd.DataFrame(cache_obj["data"])
                        df_cached = df_cached.sort_values(by=["Score", "Change (%)"], ascending=[False, False])
                        st.session_state.screener_results = df_cached
                        st.session_state.screener_last_updated = cache_obj.get("timestamp", datetime.datetime.now().strftime("%I:%M:%S %p"))
                        st.session_state.screener_last_scan_ts = time.time()
            except Exception:
                pass

    # Mount Auto-Refresh trigger
    if auto_update_enabled and st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key="screener_autorefresh_trigger")

    now_ts = time.time()
    last_scan_ts = st.session_state.get("screener_last_scan_ts", 0.0)
    time_since_last_scan = now_ts - last_scan_ts

    # Check if basket changed
    basket_changed = False
    if "screener_prev_basket" in st.session_state and st.session_state.screener_prev_basket != selected_basket:
        basket_changed = True
    st.session_state.screener_prev_basket = selected_basket

    # Determine if scan should run
    should_scan = False
    is_auto_scan = False

    if start_scan or basket_changed:
        should_scan = True
        is_auto_scan = False
    elif st.session_state.screener_results is None:
        should_scan = True
        is_auto_scan = False
    elif auto_update_enabled and (time_since_last_scan >= (interval_sec - 2)):
        should_scan = True
        is_auto_scan = True

    if should_scan:
        if "Custom Watchlist" in selected_basket:
            tickers_to_scan = [s.strip() for s in custom_symbols_text.split(",") if s.strip()]
        else:
            tickers_to_scan = BASKETS.get(selected_basket, [])
            
        total = len(tickers_to_scan)
        results = []
        
        if is_auto_scan:
            with st.spinner(f"🔄 લાઈવ માર્કેટ સ્કેનર ઓટો-અપડેટ થઈ રહ્યું છે ({total} શેરો)..."):
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_stock = {executor.submit(scan_stock, sym): sym for sym in tickers_to_scan}
                    for future in as_completed(future_to_stock):
                        try:
                            res = future.result()
                            if res:
                                results.append(res)
                        except Exception:
                            pass
        else:
            progress_bar = st.progress(0, text="સ્કેનિંગ શરૂ થઈ રહ્યું છે...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_stock = {executor.submit(scan_stock, sym): sym for sym in tickers_to_scan}
                completed = 0
                for future in as_completed(future_to_stock):
                    completed += 1
                    progress_bar.progress(completed / total, text=f"સ્કેનિંગ પ્રગતિમાં છે... ({completed}/{total} શેરો પૂરા થયા)")
                    try:
                        res = future.result()
                        if res:
                            results.append(res)
                    except Exception:
                        pass
            progress_bar.empty()
            
        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res.sort_values(by=["Score", "Change (%)"], ascending=[False, False])
            st.session_state.screener_results = df_res
            now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
            st.session_state.screener_last_updated = now_str
            st.session_state.screener_last_scan_ts = time.time()

            # Save to screener_cache.json
            try:
                cache_obj = {
                    "timestamp": now_str,
                    "basket": selected_basket,
                    "data": results
                }
                with open("screener_cache.json", "w", encoding="utf-8") as f:
                    json.dump(cache_obj, f, indent=2, ensure_ascii=False, default=serialize_screener_data)
            except Exception:
                pass

            if is_auto_scan:
                st.toast(f"🔄 લાઈવ માર્કેટ સ્કેનર આપમેળે અપડેટ થયું! ({now_str})", icon="✅")
            else:
                st.toast(f"✅ સફળતાપૂર્વક {len(results)} સ્ટોક્સનું મલ્ટી-ટાઇમફ્રેમ સ્કેનિંગ પૂરું થયું!", icon="🚀")
        else:
            if not is_auto_scan:
                st.error("કોઈ સ્ટોકનો ડેટા મળ્યો નથી. કૃપા કરીને સિમ્બોલ ચકાસો.")

    last_updated_str = st.session_state.get("screener_last_updated") or "તાજેતરનો ડેટા"
    if auto_update_enabled:
        st.markdown(
            f'<div style="display: flex; align-items: center; justify-content: space-between; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); padding: 8px 16px; border-radius: 10px; margin-top: 10px; margin-bottom: 16px;">'
            f'<div style="display: flex; align-items: center; gap: 10px;">'
            f'<span style="display: inline-block; width: 10px; height: 10px; background: #10B981; border-radius: 50%; box-shadow: 0 0 10px #10B981;"></span>'
            f'<span style="color: #34D399; font-weight: 700; font-size: 13.5px;">🟢 LIVE AUTO-UPDATE સક્રિય ({freq_choice})</span>'
            f'<span style="color: #9CA3AF; font-size: 13px;">| બજારનો તાજો ડેટા આપમેળે રિફ્રેશ થઈ રહ્યો છે</span>'
            f'</div>'
            f'<div style="color: #E5E7EB; font-size: 13px; font-weight: 600;">છેલ્લું અપડેટ: <span style="color: #38BDF8; font-family: monospace; font-size: 14px;">{last_updated_str}</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div style="display: flex; align-items: center; justify-content: space-between; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); padding: 8px 16px; border-radius: 10px; margin-top: 10px; margin-bottom: 16px;">'
            f'<div style="display: flex; align-items: center; gap: 10px;">'
            f'<span style="display: inline-block; width: 10px; height: 10px; background: #EF4444; border-radius: 50%;"></span>'
            f'<span style="color: #F87171; font-weight: 700; font-size: 13.5px;">⏸️ ઓટો-અપડેટ બંધ છે (મેન્યુઅલ મોડ)</span>'
            f'<span style="color: #9CA3AF; font-size: 13px;">| નવો ડેટા મેળવવા "🚀 Scan Market Now" બટન દબાવો</span>'
            f'</div>'
            f'<div style="color: #E5E7EB; font-size: 13px; font-weight: 600;">છેલ્લું અપડેટ: <span style="color: #9CA3AF; font-family: monospace; font-size: 14px;">{last_updated_str}</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )

    if st.session_state.screener_results is not None:
        df_res = st.session_state.screener_results
        
        count_sniper_buy = len(df_res[df_res["Signal"].str.contains("Sniper Dip Buy", na=False)])
        count_buy_dips = len(df_res[df_res["Signal"].str.contains("Buy on Dips", na=False)])
        count_r3_radar = len(df_res[df_res["is_r3_radar"] == True]) if "is_r3_radar" in df_res.columns else 0
        count_sniper_short = len(df_res[df_res["Signal"].str.contains("Sniper Short", na=False)])
        count_option_sell = len(df_res[df_res["Signal"].str.contains("Option Selling", na=False)])
        count_sell = len(df_res[df_res["Signal"].isin(["🔴 Strong Sell", "🟠 Weak / Bearish", "⚠️ Short on Bounce"])])
        
        # Interactive Clickable KPI Cards (Top Row - 6 Strategy Cards)
        if "screener_filter" not in st.session_state:
            st.session_state.screener_filter = "ALL"
            
        kpi_cols = st.columns(6)
        
        is_active_sniper_buy = (st.session_state.screener_filter == "SNIPER_BUY")
        is_active_buy_dips = (st.session_state.screener_filter == "BUY_DIPS")
        is_active_r3_radar = (st.session_state.screener_filter == "R3_RADAR")
        is_active_sniper_short = (st.session_state.screener_filter == "SNIPER_SHORT")
        is_active_option_sell = (st.session_state.screener_filter == "OPTION_SELL")
        is_active_sell = (st.session_state.screener_filter == "SELL")
        
        with kpi_cols[0]:
            if st.button(
                f"🎯 SNIPER DIP BUY  \n**{count_sniper_buy}**  \n*1H Reversal Triggered*",
                key="btn_kpi_sniper_buy",
                type="primary" if is_active_sniper_buy else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_sniper_buy else "SNIPER_BUY"
                st.rerun()

        with kpi_cols[1]:
            if st.button(
                f"⏳ BUY ON DIPS  \n**{count_buy_dips}**  \n*Wait for 1H Bull Cross*",
                key="btn_kpi_buy_dips",
                type="primary" if is_active_buy_dips else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_buy_dips else "BUY_DIPS"
                st.rerun()

        with kpi_cols[2]:
            if st.button(
                f"⚡ R3 OPTION RADAR  \n**{count_r3_radar}**  \n*Option Rocket Setup*",
                key="btn_kpi_r3_radar",
                type="primary" if is_active_r3_radar else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_r3_radar else "R3_RADAR"
                st.rerun()

        with kpi_cols[3]:
            if st.button(
                f"🩸 SNIPER SHORT  \n**{count_sniper_short}**  \n*Bounce Rejection Cross*",
                key="btn_kpi_sniper_short",
                type="primary" if is_active_sniper_short else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_sniper_short else "SNIPER_SHORT"
                st.rerun()

        with kpi_cols[4]:
            if st.button(
                f"⚖️ OPTION SELLING  \n**{count_option_sell}**  \n*Both-Side Theta Decay*",
                key="btn_kpi_option_sell",
                type="primary" if is_active_option_sell else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_option_sell else "OPTION_SELL"
                st.rerun()

        with kpi_cols[5]:
            if st.button(
                f"🔴 SELL / CAUTION  \n**{count_sell}**  \n*Downside Pressure*",
                key="btn_kpi_sell_caution",
                type="primary" if is_active_sell else "secondary",
                use_container_width=True
            ):
                st.session_state.screener_filter = "ALL" if is_active_sell else "SELL"
                st.rerun()
        
        # Filter & View Controls
        filter_map = {
            "ALL": "બધા જ સ્ટોક્સ (All)",
            "SNIPER_BUY": "🎯 સ્નાઈપર બાય (Sniper Dip Buy)",
            "BUY_DIPS": "⏳ પુલબેક તેજી (Buy on Dips - Wait 1H)",
            "R3_RADAR": "⚡ R3 ઓપ્શન રોકેટ (R3 Option Radar)",
            "SNIPER_SHORT": "🩸 સ્નાઈપર શોર્ટ (Sniper Short Sell)",
            "OPTION_SELL": "⚖️ માત્ર ઓપ્શન સેલિંગ (Range-Bound / Neutral)",
            "SELL": "🔴 માત્ર વેચાણ સિગ્નલ (Sell / Avoid)"
        }
        reverse_filter_map = {v: k for k, v in filter_map.items()}

        ctrl_col1, ctrl_col2 = st.columns([3, 2])
        with ctrl_col1:
            current_pill = filter_map.get(st.session_state.screener_filter, "બધા જ સ્ટોક્સ (All)")
            filter_opt = st.pills(
                "સિગ્નલ ફિલ્ટર કરો:",
                options=list(filter_map.values()),
                default=current_pill,
                key=f"pill_filter_widget_{st.session_state.screener_filter}"
            )
            if filter_opt and reverse_filter_map.get(filter_opt) != st.session_state.screener_filter:
                st.session_state.screener_filter = reverse_filter_map.get(filter_opt, "ALL")
                st.rerun()
                
        with ctrl_col2:
            view_mode = st.segmented_control(
                "ડિસ્પ્લે ફોર્મેટ:",
                options=["🎴 Visual Trading Cards", "📋 Pro Data Table"],
                default="🎴 Visual Trading Cards",
                key="screener_view_mode_select"
            )
            
        filtered_df = df_res.copy()
        if st.session_state.screener_filter == "SNIPER_BUY":
            filtered_df = filtered_df[filtered_df["Signal"].str.contains("Sniper Dip Buy", na=False)]
        elif st.session_state.screener_filter == "BUY_DIPS":
            filtered_df = filtered_df[filtered_df["Signal"].str.contains("Buy on Dips", na=False)]
        elif st.session_state.screener_filter == "R3_RADAR":
            filtered_df = filtered_df[filtered_df["is_r3_radar"] == True]
        elif st.session_state.screener_filter == "SNIPER_SHORT":
            filtered_df = filtered_df[filtered_df["Signal"].str.contains("Sniper Short", na=False)]
        elif st.session_state.screener_filter == "OPTION_SELL":
            filtered_df = filtered_df[filtered_df["Signal"].str.contains("Option Selling", na=False)]
        elif st.session_state.screener_filter == "SELL":
            filtered_df = filtered_df[filtered_df["Signal"].isin(["🔴 Strong Sell", "🟠 Weak / Bearish", "⚠️ Short on Bounce"])]
            
        if st.session_state.screener_filter != "ALL":
            active_name = filter_map.get(st.session_state.screener_filter, "")
            st.info(f"🔍 **સક્રિય કેટેગરી:** {active_name} • દર્શાવેલ સ્ટોક્સ: **{len(filtered_df)}** / {len(df_res)} (ફિલ્ટર હટાવવા કાર્ડ પર ફરી ક્લિક કરો)")
            
        if filtered_df.empty:
            st.info("પસંદ કરેલા ફિલ્ટરમાં કોઈ સ્ટોક મળ્યો નથી.")
        else:
            # OPTION A: Visual Trading Cards Grid
            if view_mode == "🎴 Visual Trading Cards":
                num_cols = 2
                cols = st.columns(num_cols)
                
                for idx, (_, row) in enumerate(filtered_df.iterrows()):
                    col_idx = idx % num_cols
                    chg = row['Change (%)']
                    chg_color = "#34D399" if chg >= 0 else "#F87171"
                    chg_bg = "rgba(16, 185, 129, 0.15)" if chg >= 0 else "rgba(239, 68, 68, 0.15)"
                    chg_arrow = "▲" if chg >= 0 else "▼"
                    pill_cls = row.get('PillClass', 'pill-neutral')
                    
                    if "Sniper Dip Buy" in row["Signal"]:
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #10B981; grid-column: span 3; background: rgba(16, 185, 129, 0.08);">'
                            f'<div class="target-item-title" style="color: #34D399;">🎯 SNIPER DIP BUY SETUP • રિવર્સલ કન્ફર્મ ખરીદી</div>'
                            f'<div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;">💡 CE Buy: <b>₹{row.get("ce_strike", "-")}</b> | PE Sell: <b>&lt; ₹{row.get("pe_strike", "-")}</b> • 1H Bull Cross સાથે તાત્કાલિક એન્ટ્રી!</div>'
                            f'</div>'
                            f'<div class="target-item" style="border-left: 3px solid #10B981;"><div class="target-item-title" style="color: #34D399;">Target 1 (1:1.5)</div><div class="target-item-val" style="color: #34D399;">{row["Target 1 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #06B6D4;"><div class="target-item-title" style="color: #38BDF8;">Target 2 (1:2.5)</div><div class="target-item-val" style="color: #38BDF8;">{row["Target 2 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444;"><div class="target-item-title" style="color: #F87171;">Stop Loss (1H Low)</div><div class="target-item-val" style="color: #F87171;">{row["Stop Loss (1H)"]}</div></div>'
                            f'</div>'
                        )
                    elif "Buy on Dips" in row["Signal"]:
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #06B6D4; grid-column: span 3; background: rgba(6, 182, 212, 0.08);">'
                            f'<div class="target-item-title" style="color: #38BDF8;">⏳ PULLBACK IN PROGRESS • ૧ કલાકમાં પુલબેક ચાલુ છે</div>'
                            f'<div style="font-size: 11px; color: #E2E8F0; margin-top: 2px;">🛑 <b>ઉતાવળે ખરીદી ના કરો!</b> Daily મજબૂત તેજીમાં છે, પણ 1-Hour માં હજુ Dip ચાલે છે. <b>1-Hour માં Green લાઈન Red લાઈન ઉપર ક્રોસ (Bull Cross ⬆️) કરે ત્યારે જ સ્નાઈપર બાય એન્ટ્રી કરવી!</b></div>'
                            f'</div>'
                            f'<div class="target-item" style="border-left: 3px solid #10B981;"><div class="target-item-title" style="color: #34D399;">Potential Target 1</div><div class="target-item-val" style="color: #34D399;">{row["Target 1 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #06B6D4;"><div class="target-item-title" style="color: #38BDF8;">Potential Target 2</div><div class="target-item-val" style="color: #38BDF8;">{row["Target 2 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444;"><div class="target-item-title" style="color: #F87171;">Stop Loss (1H Low)</div><div class="target-item-val" style="color: #F87171;">{row["Stop Loss (1H)"]}</div></div>'
                            f'</div>'
                        )
                    elif "Sniper Short" in row["Signal"]:
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444; grid-column: span 3; background: rgba(239, 68, 68, 0.08);">'
                            f'<div class="target-item-title" style="color: #F87171;">🩸 SNIPER SHORT SETUP • ઉછાળે શોર્ટ સેટઅપ</div>'
                            f'<div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;">💡 Put Buy (PE): <b>₹{row.get("pe_strike", "-")}</b> | Call Sell (CE): <b>&gt; ₹{row.get("ce_strike", "-")}</b> • 1H Rejection સાથે શોર્ટ એન્ટ્રી!</div>'
                            f'</div>'
                            f'<div class="target-item" style="border-left: 3px solid #F87171;"><div class="target-item-title" style="color: #FCA5A5;">Target 1 (1:1.5)</div><div class="target-item-val" style="color: #F87171;">{row["Target 1 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444;"><div class="target-item-title" style="color: #F87171;">Target 2 (1:2.5)</div><div class="target-item-val" style="color: #EF4444;">{row["Target 2 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #F59E0B;"><div class="target-item-title" style="color: #FCD34D;">Stop Loss (1H)</div><div class="target-item-val" style="color: #FCD34D;">{row["Stop Loss (1H)"]}</div></div>'
                            f'</div>'
                        )
                    elif "Option Selling" in row["Signal"]:
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #A855F7; grid-column: span 3; background: rgba(168, 85, 247, 0.08);">'
                            f'<div class="target-item-title" style="color: #C084FC;">⚖️ OPTION SELLING SETUP (SHORT STRANGLE / RANGE-BOUND)</div>'
                            f'<div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;">💡 બંને બાજુ CE & PE વેચીને <b>થીટા ડીકે (Theta Decay)</b> નફો મેળવી શકાય.</div>'
                            f'</div>'
                            f'<div class="target-item" style="border-left: 3px solid #EC4899;"><div class="target-item-title" style="color: #F472B6;">Call Sell (CE Resist)</div><div class="target-item-val" style="color: #F472B6;">&gt; ₹{row["tc_high"]:.1f}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #38BDF8;"><div class="target-item-title" style="color: #38BDF8;">Put Sell (PE Support)</div><div class="target-item-val" style="color: #38BDF8;">&lt; ₹{row["tc_low"]:.1f}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #A855F7;"><div class="target-item-title" style="color: #C084FC;">Safe Expiry Range</div><div class="target-item-val" style="color: #DDD6FE;">₹{row["tc_low"]:.0f} - ₹{row["tc_high"]:.0f}</div></div>'
                            f'</div>'
                        )
                    elif ("Sell" in row["Signal"] or "Bearish" in row["Signal"] or "Short on Bounce" in row["Signal"]):
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444; grid-column: span 3; background: rgba(239, 68, 68, 0.08);">'
                            f'<div class="target-item-title" style="color: #F87171;">⚠️ ટ્રેડિંગ નિર્ણય (Trading Verdict)</div>'
                            f'<div style="font-size: 13px; color: #FCA5A5; font-weight: 600; margin-top: 2px;">🛑 મંદીનું દબાણ છે • નવી ખરીદી બિલકુલ ટાળવી • 1H રીજેક્શનની રાહ જુઓ</div>'
                            f'</div>'
                            f'</div>'
                        )
                    else:
                        targets_snippet = (
                            f'<div class="targets-row">'
                            f'<div class="target-item" style="border-left: 3px solid #10B981;"><div class="target-item-title" style="color: #34D399;">Target 1</div><div class="target-item-val" style="color: #34D399;">{row["Target 1 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #06B6D4;"><div class="target-item-title" style="color: #38BDF8;">Target 2</div><div class="target-item-val" style="color: #38BDF8;">{row["Target 2 (₹)"]}</div></div>'
                            f'<div class="target-item" style="border-left: 3px solid #EF4444;"><div class="target-item-title" style="color: #F87171;">Stop Loss</div><div class="target-item-val" style="color: #F87171;">{row["Stop Loss (1H)"]}</div></div>'
                            f'</div>'
                        )
                    
                    r3_banner = ""
                    if row.get("is_r3_radar"):
                        otm_ce = row.get("otm_call_strike", "-")
                        r1_v = row.get("r1", 0)
                        r2_v = row.get("r2", 0)
                        r3_v = row.get("r3", 0)
                        p_v = row.get("pivot_p", 0)
                        is_confirmed_buy = row.get("is_sniper_buy", False) or ("Sniper Dip Buy" in str(row.get("Signal", "")))
                        
                        badge_text = "🚀 100% CONFIRMED BUY" if is_confirmed_buy else "OPTION LEADS FUTURE"
                        badge_bg = "#10B981" if is_confirmed_buy else "#D97706"
                        border_color = "#10B981" if is_confirmed_buy else "#F59E0B"
                        title_text = "⚡ R3 OPTION ROCKET (૧૦૦% કન્ફર્મ ખરીદી સેટઅપ)" if is_confirmed_buy else "⚡ R3 OPTION ROCKET SETUP"
                        
                        confirm_line = ""
                        if is_confirmed_buy:
                            confirm_line = f'<div style="color: #34D399; font-weight: 700; margin-bottom: 4px;">✅ <b>૧૦૦% કન્ફર્મ એન્ટ્રી:</b> ૧ કલાકમાં Bull Cross થઈ ગયું છે. <b>₹{otm_ce} CE</b> અથવા સ્ટોકમાં તાત્કાલિક એન્ટ્રી લેવી!</div>'
                            
                        r3_banner = (
                            f'<div style="margin-top: 10px; background: linear-gradient(135deg, rgba(245, 158, 11, 0.14) 0%, rgba(217, 119, 6, 0.2) 100%); border: 1.5px solid {border_color}; border-radius: 10px; padding: 11px 13px; box-shadow: 0 4px 16px rgba(245, 158, 11, 0.22);">'
                            f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                            f'<span style="font-size: 12px; font-weight: 800; color: #FCD34D; letter-spacing: 0.5px;">{title_text}</span>'
                            f'<span style="font-size: 10px; font-weight: 700; color: #FFFFFF; background: {badge_bg}; padding: 2px 7px; border-radius: 4px;">{badge_text}</span>'
                            f'</div>'
                            f'<div style="font-size: 11px; color: #FEF3C7; margin-top: 6px; line-height: 1.45;">'
                            f'{confirm_line}'
                            f'🚀 <b>વોચલિસ્ટ કોલ:</b> <b style="color: #38BDF8; font-size: 13px;">₹{otm_ce} CE</b> • <b>રૂલ:</b> જ્યારે આ OTM CE તેના પોતાના <b>Daily R3</b> ને ક્રોસ કરે ત્યારે એન્ટ્રી!<br>'
                            f'🛡️ <b>SL:</b> ઓપ્શન કેન્ડલ Low | 🎯 <b>Target:</b> 100% થી 200%+ (Double/Multibagger)<br>'
                            f'📊 <b>Spot Pivot Levels:</b> P: ₹{p_v:.1f} • R1: ₹{r1_v:.1f} • R2: ₹{r2_v:.1f} • R3: ₹{r3_v:.1f}'
                            f'</div>'
                            f'</div>'
                        )
                    
                    card_html = (
                        f'<div class="stock-card">'
                        f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
                        f'<div><div style="font-size: 22px; font-weight: 800; color: #FFFFFF; font-family: monospace; letter-spacing: -0.5px;">{row["Symbol"]}</div><div style="font-size: 11px; color: #94A3B8; font-weight: 500;">NSE • Equity Segment</div></div>'
                        f'<div style="text-align: right;"><div style="font-size: 20px; font-weight: 800; color: #F8FAFC; font-family: monospace;">₹{row["Price (₹)"]:.2f}</div><span style="font-size: 12px; font-weight: 700; color: {chg_color}; background: {chg_bg}; padding: 2px 8px; border-radius: 6px;">{chg_arrow} {chg:+.2f}%</span></div>'
                        f'</div>'
                        f'<div style="margin: 12px 0 10px 0; display: flex; justify-content: space-between; align-items: center;"><span class="signal-pill {pill_cls}">{row["Signal"]}</span><span style="font-size: 12px; font-weight: 700; color: #E2E8F0; background: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);">Confluence: <span style="color: #38BDF8;">{row["Score"]}%</span></span></div>'
                        f'<div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: #94A3B8; margin-bottom: 8px;">'
                        f'<span style="background: rgba(15,23,42,0.8); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">🚀 Daily HM: <b style="color: #F1F5F9;">{row.get("Daily HM", "-")}</b></span>'
                        f'<span style="background: rgba(15,23,42,0.8); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">⚡ 1H Trigger: <b style="color: #F1F5F9;">{row["1H Trigger"]}</b></span>'
                        f'<span style="background: rgba(15,23,42,0.8); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">📊 1H Vol: <b style="color: #F1F5F9;">{row["1H Vol Ratio"]}</b></span>'
                        f'<span style="background: rgba(15,23,42,0.8); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">🎯 Pivot: <b style="color: #FCD34D;">{row.get("pivot_status", "-")}</b></span>'
                        f'</div>'
                        f'{targets_snippet}'
                        f'{r3_banner}'
                        f'</div>'
                    )
                    with cols[col_idx]:
                        st.html(card_html)
            else:
                # OPTION B: Pro Data Table
                table_cols = [
                    "Symbol", "Price (₹)", "Change (%)", "Signal", "Score",
                    "Daily HM", "1H Trigger", "pivot_status", "otm_call_strike",
                    "Target 1 (₹)", "Target 2 (₹)", "Stop Loss (1H)",
                    "1H Vol Ratio", "Daily TC Band"
                ]
                existing_cols = [c for c in table_cols if c in filtered_df.columns]
                st.dataframe(
                    filtered_df[existing_cols],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Score": st.column_config.NumberColumn(
                            "Score (%)",
                            format="%d%%"
                        ),
                        "Change (%)": st.column_config.NumberColumn(
                            "Change (%)",
                            format="%+.2f%%"
                        ),
                        "Price (₹)": st.column_config.NumberColumn(
                            "Price (₹)",
                            format="₹%.2f"
                        ),
                        "pivot_status": st.column_config.TextColumn(
                            "Daily Pivot Level"
                        ),
                        "otm_call_strike": st.column_config.NumberColumn(
                            "R3 Watch CE",
                            format="₹%d CE"
                        )
                    }
                )
        
        # Candlestick Inspector
        st.divider()
        st.subheader("🔍 સ્કેન કરેલા સ્ટોકનો લાઈવ કેન્ડલસ્ટિક ચાર્ટ જુઓ:")
        available_syms = df_res["FullSymbol"].tolist()
        inspect_sym = st.selectbox("ચાર્ટ જોવા માટે સ્ટોક પસંદ કરો:", options=available_syms, index=0)
        
        if inspect_sym:
            with st.spinner(f"{inspect_sym} માટે કેન્ડલસ્ટિક ચાર્ટ લોડ થઈ રહ્યો છે..."):
                t = yf.Ticker(inspect_sym)
                q_df_1h = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(t.history(period="1mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume']))))
                q_df_d = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(t.history(period="1y", interval="1d").dropna(subset=['Close', 'High', 'Low', 'Volume']))))
                
                chart_col1, chart_col2 = st.tabs(["⚡ 1-Hour Candlestick Chart", "⏰ Daily Candlestick Chart"])
                with chart_col1:
                    if not q_df_1h.empty:
                        c_1h = plot_candlestick_triple_chart(q_df_1h, title_prefix=f"{inspect_sym} 1-Hour", lookback=80, is_hourly=True)
                        st.altair_chart(c_1h, width="stretch")
                with chart_col2:
                    if not q_df_d.empty:
                        c_d = plot_candlestick_triple_chart(q_df_d, title_prefix=f"{inspect_sym} Daily", lookback=100, is_hourly=False)
                        st.altair_chart(c_d, width="stretch")

# =============================================================
# TAB 2: SINGLE STOCK DEEP CANDLESTICK ANALYSIS
# =============================================================
with nav_tab_single:
    st.subheader("🕯️ સિંગલ સ્ટોક ડીપ કેન્ડલસ્ટિક એનાલિસિસ (Cockpit View)")
    col_in, col_btn = st.columns([3, 1])
    with col_in:
        stock_symbol = st.text_input(
            "Stock Symbol દાખલ કરો:",
            value="BHEL.NS",
            placeholder="e.g. BHEL, ZYDUSLIFE, RELIANCE, COALINDIA, ADANIPOWER",
            key="single_stock_input"
        )
    with col_btn:
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 Analyze This Stock", type="primary", width="stretch", key="single_stock_btn")

    if analyze_btn or stock_symbol:
        raw_sym = stock_symbol.strip().upper()
        if raw_sym:
            if "." not in raw_sym and not raw_sym.startswith("^"):
                sym = f"{raw_sym}.NS"
            else:
                sym = raw_sym
                
            with st.spinner(f"⏳ {sym} માટે સંપૂર્ણ કેન્ડલસ્ટિક અને મલ્ટી-ટાઇમફ્રેમ ડેટા પ્રોસેસ થઈ રહ્યો છે..."):
                try:
                    ticker = yf.Ticker(sym)
                    df_monthly = ticker.history(period="10y", interval="1mo").dropna(subset=['Close', 'High', 'Low', 'Volume'])
                    df_weekly = ticker.history(period="5y", interval="1wk").dropna(subset=['Close', 'High', 'Low', 'Volume'])
                    df_daily = ticker.history(period="1y", interval="1d").dropna(subset=['Close', 'High', 'Low', 'Volume'])
                    df_1h = ticker.history(period="3mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume'])
                    
                    if df_daily.empty or len(df_daily) < 30:
                        st.error(f"❌ {sym} માટે પૂરતો ડેટા મળ્યો નથી. કૃપા કરીને સાચો સિમ્બોલ લખો.")
                    else:
                        # Indicators
                        df_monthly = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_monthly), default_period=24), sma_period=20)
                        df_weekly = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_weekly), default_period=30), sma_period=20)
                        df_daily = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_daily), default_period=45), sma_period=20)
                        df_1h = calculate_volume_analysis(calculate_trend_craft_ict(calculate_hilega_milega(df_1h), default_period=45), sma_period=20)
                        
                        m_hm = analyze_hm_timeframe(df_monthly, "Monthly")
                        w_hm = analyze_hm_timeframe(df_weekly, "Weekly")
                        d_hm = analyze_hm_timeframe(df_daily, "Daily")
                        h1_hm = analyze_hm_timeframe(df_1h, "1-Hour")
                        
                        m_tc = analyze_trend_craft_timeframe(df_monthly, "Monthly")
                        w_tc = analyze_trend_craft_timeframe(df_weekly, "Weekly")
                        d_tc = analyze_trend_craft_timeframe(df_daily, "Daily")
                        h1_tc = analyze_trend_craft_timeframe(df_1h, "1-Hour")
                        
                        m_vol = analyze_volume_timeframe(df_monthly, "Monthly")
                        w_vol = analyze_volume_timeframe(df_weekly, "Weekly")
                        d_vol = analyze_volume_timeframe(df_daily, "Daily")
                        h1_vol = analyze_volume_timeframe(df_1h, "1-Hour")
                        
                        conf = calculate_master_confluence_vpa(m_hm, w_hm, d_hm, h1_hm, m_tc, w_tc, d_tc, h1_tc, m_vol, w_vol, d_vol, h1_vol)
                        
                        curr_p = df_daily['Close'].iloc[-1]
                        prev_p = df_daily['Close'].iloc[-2]
                        chg = curr_p - prev_p
                        pct_chg = (chg / prev_p) * 100
                        
                        levels = calculate_trade_levels(curr_p, conf['stoploss_1h'])
                        
                        # Top Cockpit Executive Card
                        chg_color = "#34D399" if chg >= 0 else "#F87171"
                        chg_bg = "rgba(16, 185, 129, 0.15)" if chg >= 0 else "rgba(239, 68, 68, 0.15)"
                        chg_arrow = "▲" if chg >= 0 else "▼"
                        score_color = "#34D399" if conf['score'] >= 75 else ("#38BDF8" if conf['score'] >= 60 else "#F87171")
                        
                        cockpit_html = f'<div style="background: linear-gradient(135deg, rgba(22, 31, 48, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 22px 26px; margin: 16px 0 20px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.35);"><div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;"><div><div style="display: flex; align-items: center; gap: 14px;"><h2 style="margin: 0; font-size: 32px; font-weight: 800; color: #FFFFFF; font-family: monospace;">{sym}</h2><span style="font-size: 22px; font-weight: 700; color: #F1F5F9; font-family: monospace;">₹{curr_p:.2f}</span><span style="font-size: 13px; font-weight: 700; color: {chg_color}; background: {chg_bg}; padding: 3px 10px; border-radius: 6px;">{chg_arrow} {chg:+.2f} ({pct_chg:+.2f}%)</span></div><div style="margin-top: 10px; display: flex; align-items: center; gap: 10px;"><span class="signal-pill {conf["pill_class"]}">{conf["verdict"]}</span><span style="font-size: 15px; color: #FBBF24;">{conf["stars"]}</span></div></div><div style="text-align: right; background: rgba(15, 23, 42, 0.7); padding: 12px 22px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.06);"><div style="font-size: 11px; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px;">Confluence Score</div><div style="font-size: 34px; font-weight: 800; color: {score_color}; font-family: monospace; line-height: 1.1;">{conf["score"]}%</div><div style="font-size: 11px; color: #64748B;">4-Timeframe & VPA</div></div></div><div style="margin-top: 14px; color: #CBD5E1; font-size: 13px; line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px;">{conf["explanation"]}</div></div>'
                        st.html(cockpit_html)
                        
                        # 4 Target & Risk Matrix Cards (Adapts to Option Selling vs Short vs Directional Buy)
                        ce_sell_strike = max(d_tc['tc_high'], curr_p * 1.015)
                        pe_sell_strike = min(d_tc['tc_low'], curr_p * 0.985)
                        is_short_verdict = ("SHORT" in conf["verdict"] or "BEARISH" in conf["verdict"] or "AVOID" in conf["verdict"])
                        levels_short = calculate_trade_levels(curr_p, conf['stoploss_1h_short'], is_short=True)
                        
                        is_sniper_buy_verdict = ("SNIPER DIP BUY" in conf["verdict"])
                        is_buy_dips_verdict = ("BUY ON DIPS" in conf["verdict"])
                        
                        if "OPTION SELLING" in conf["verdict"]:
                            targets_matrix_html = (
                                f'<div class="kpi-grid">'
                                f'<div class="kpi-card" style="border-top: 3px solid #EC4899; background: rgba(236, 72, 153, 0.06);"><div class="kpi-title" style="color: #F472B6;">📉 CALL SELL STRIKE (CE)</div><div class="kpi-value" style="color: #F472B6;">&gt; ₹{ce_sell_strike:.1f}</div><div class="kpi-subtitle" style="color: #EC4899; font-weight: 600;">આ લેવલથી ઉપરનો કૉલ વેચવો</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #38BDF8; background: rgba(56, 189, 248, 0.06);"><div class="kpi-title" style="color: #38BDF8;">📈 PUT SELL STRIKE (PE)</div><div class="kpi-value" style="color: #38BDF8;">&lt; ₹{pe_sell_strike:.1f}</div><div class="kpi-subtitle" style="color: #0284C7; font-weight: 600;">આ લેવલથી નીચેનો પુટ વેચવો</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #A855F7; background: rgba(168, 85, 247, 0.06);"><div class="kpi-title" style="color: #C084FC;">🛡️ SAFE EXPIRY RANGE</div><div class="kpi-value" style="color: #C084FC;">₹{pe_sell_strike:.0f} - ₹{ce_sell_strike:.0f}</div><div class="kpi-subtitle" style="color: #A855F7; font-weight: 600;">આ રેન્જમાં એક્સપાયરી પર 100% નફો</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #10B981; background: rgba(168, 85, 247, 0.06);"><div class="kpi-title" style="color: #34D399;">⚖️ STRATEGY TYPE</div><div class="kpi-value" style="color: #34D399; font-size: 20px;">SHORT STRANGLE</div><div class="kpi-subtitle" style="color: #10B981; font-weight: 600;">Theta Decay (પ્રીમિયમ ઈનકમ)</div></div>'
                                f'</div>'
                            )
                        elif is_short_verdict:
                            targets_matrix_html = (
                                f'<div class="kpi-grid">'
                                f'<div class="kpi-card" style="border-top: 3px solid #F87171; background: rgba(239, 68, 68, 0.06);"><div class="kpi-title" style="color: #FCA5A5;">🎯 SHORT TARGET 1 (1:1.5)</div><div class="kpi-value" style="color: #F87171;">₹{levels_short["t1"]:.2f}</div><div class="kpi-subtitle" style="color: #F87171; font-weight: 600;">-{levels_short["t1_pct"]:.2f}% (પ્રથમ શોર્ટ લક્ષ્ય)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #EF4444; background: rgba(239, 68, 68, 0.08);"><div class="kpi-title" style="color: #F87171;">🚀 SHORT TARGET 2 (1:2.5)</div><div class="kpi-value" style="color: #EF4444;">₹{levels_short["t2"]:.2f}</div><div class="kpi-subtitle" style="color: #EF4444; font-weight: 600;">-{levels_short["t2_pct"]:.2f}% (મહત્તમ શોર્ટ લક્ષ્ય)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #F59E0B; background: rgba(245, 158, 11, 0.06);"><div class="kpi-title" style="color: #FCD34D;">🛡️ SNIPER STOP-LOSS</div><div class="kpi-value" style="color: #FCD34D;">₹{levels_short["stop_loss"]:.2f}</div><div class="kpi-subtitle" style="color: #F59E0B; font-weight: 600;">+{levels_short["risk_pct"]:.2f}% (જોખમ સપાટી)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #EC4899; background: rgba(236, 72, 153, 0.06);"><div class="kpi-title" style="color: #F472B6;">💡 OPTIONS ACTION</div><div class="kpi-value" style="color: #F472B6; font-size: 19px;">BUY PUT / SELL CALL</div><div class="kpi-subtitle" style="color: #EC4899; font-weight: 600;">Bearish Strategy</div></div>'
                                f'</div>'
                            )
                        elif is_sniper_buy_verdict:
                            targets_matrix_html = (
                                f'<div class="kpi-grid">'
                                f'<div class="kpi-card" style="border-top: 3px solid #10B981; background: rgba(16, 185, 129, 0.06);"><div class="kpi-title" style="color: #34D399;">🎯 BUY TARGET 1 (1:1.5)</div><div class="kpi-value" style="color: #34D399;">₹{levels["t1"]:.2f}</div><div class="kpi-subtitle" style="color: #10B981; font-weight: 600;">+{levels["t1_pct"]:.2f}% (પ્રથમ લક્ષ્ય)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #06B6D4; background: rgba(6, 182, 212, 0.06);"><div class="kpi-title" style="color: #38BDF8;">🚀 BUY TARGET 2 (1:2.5)</div><div class="kpi-value" style="color: #38BDF8;">₹{levels["t2"]:.2f}</div><div class="kpi-subtitle" style="color: #06B6D4; font-weight: 600;">+{levels["t2_pct"]:.2f}% (મહત્તમ લક્ષ્ય)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #EF4444; background: rgba(239, 68, 68, 0.06);"><div class="kpi-title" style="color: #F87171;">🛡️ SNIPER STOP-LOSS</div><div class="kpi-value" style="color: #F87171;">₹{levels["stop_loss"]:.2f}</div><div class="kpi-subtitle" style="color: #EF4444; font-weight: 600;">-{levels["risk_pct"]:.2f}% (જોખમ)</div></div>'
                                f'<div class="kpi-card" style="border-top: 3px solid #10B981; background: rgba(16, 185, 129, 0.06);"><div class="kpi-title" style="color: #34D399;">💡 OPTIONS ACTION</div><div class="kpi-value" style="color: #34D399; font-size: 19px;">BUY CALL / SELL PUT</div><div class="kpi-subtitle" style="color: #10B981; font-weight: 600;">Bullish Strategy</div></div>'
                                f'</div>'
                            )
                        else:
                            targets_matrix_html = f'<div class="kpi-grid"><div class="kpi-card" style="border-top: 3px solid #10B981; background: rgba(16, 185, 129, 0.06);"><div class="kpi-title" style="color: #34D399;">🎯 TARGET 1 (1:1.5 R:R)</div><div class="kpi-value" style="color: #34D399;">₹{levels["t1"]:.2f}</div><div class="kpi-subtitle" style="color: #10B981; font-weight: 600;">+{levels["t1_pct"]:.2f}% (પ્રથમ લક્ષ્ય)</div></div><div class="kpi-card" style="border-top: 3px solid #06B6D4; background: rgba(6, 182, 212, 0.06);"><div class="kpi-title" style="color: #38BDF8;">🚀 TARGET 2 (1:2.5 R:R)</div><div class="kpi-value" style="color: #38BDF8;">₹{levels["t2"]:.2f}</div><div class="kpi-subtitle" style="color: #06B6D4; font-weight: 600;">+{levels["t2_pct"]:.2f}% (મહત્તમ લક્ષ્ય)</div></div><div class="kpi-card" style="border-top: 3px solid #EF4444; background: rgba(239, 68, 68, 0.06);"><div class="kpi-title" style="color: #F87171;">🛡️ SNIPER STOP-LOSS</div><div class="kpi-value" style="color: #F87171;">₹{levels["stop_loss"]:.2f}</div><div class="kpi-subtitle" style="color: #EF4444; font-weight: 600;">-{levels["risk_pct"]:.2f}% (જોખમ)</div></div><div class="kpi-card" style="border-top: 3px solid #8B5CF6; background: rgba(139, 92, 246, 0.06);"><div class="kpi-title" style="color: #A78BFA;">⚖️ RISK : REWARD</div><div class="kpi-value" style="color: #DDD6FE;">1 : 2.5</div><div class="kpi-subtitle" style="color: #A78BFA; font-weight: 600;">High Probability Setup</div></div></div>'
                        st.html(targets_matrix_html)
                        
                        # Checklist & Levels
                        r1, r2 = st.columns([2, 1])
                        with r1:
                            st.write("**🔍 Confluence Checklist:**")
                            for chk in conf['checks']:
                                st.write(f"- {chk}")
                        with r2:
                            with st.container(border=True):
                                if "OPTION SELLING" in conf["verdict"]:
                                    st.markdown("#### ⚖️ ઓપ્શન સેલિંગ લેવલ્સ")
                                    st.write(f"**હાલનો ભાવ:** ₹{curr_p:.2f}")
                                    st.write(f"**Call Sell Strike (CE):** &gt; ₹{ce_sell_strike:.1f}")
                                    st.write(f"**Put Sell Strike (PE):** &lt; ₹{pe_sell_strike:.1f}")
                                    st.write(f"**રેન્જ કન્સોલિડેશન:** ₹{pe_sell_strike:.1f} થી ₹{ce_sell_strike:.1f}")
                                    st.write(f"**રિસ્ક એક્ઝિટ:** ₹{pe_sell_strike*0.98:.1f} અથવા ₹{ce_sell_strike*1.02:.1f} ની બહાર નીકળે ત્યારે")
                                elif is_short_verdict:
                                    st.markdown("#### 🩸 શોર્ટ સેલ કી-લેવલ્સ")
                                    st.write(f"**શોર્ટ એન્ટ્રી ભાવ:** ₹{curr_p:.2f}")
                                    st.write(f"**શોર્ટ ટાર્ગેટ ૧:** ₹{levels_short['t1']:.2f} (-{levels_short['t1_pct']:.1f}%)")
                                    st.write(f"**શોર્ટ ટાર્ગેટ ૨:** ₹{levels_short['t2']:.2f} (-{levels_short['t2_pct']:.1f}%)")
                                    st.write(f"**ચુસ્ત સ્ટોપલોસ:** ₹{levels_short['stop_loss']:.2f} (+{levels_short['risk_pct']:.1f}%)")
                                    st.write(f"💡 **Put Buy Strike:** ₹{curr_p*0.995:.0f} PE")
                                    st.write(f"💡 **Call Sell Strike:** &gt; ₹{ce_sell_strike:.0f} CE")
                                elif is_sniper_buy_verdict:
                                    st.markdown("#### 🎯 સ્નાઈપર બાય કી-લેવલ્સ")
                                    st.write(f"**એન્ટ્રી ભાવ:** ₹{curr_p:.2f}")
                                    st.write(f"**ટાર્ગેટ ૧:** ₹{levels['t1']:.2f} (+{levels['t1_pct']:.1f}%)")
                                    st.write(f"**ટાર્ગેટ ૨:** ₹{levels['t2']:.2f} (+{levels['t2_pct']:.1f}%)")
                                    st.write(f"**ચુસ્ત સ્ટોપલોસ (1H Low):** ₹{levels['stop_loss']:.2f} (-{levels['risk_pct']:.1f}%)")
                                    st.write(f"💡 **Call Buy Strike (CE):** ₹{curr_p*1.005:.0f} CE")
                                    st.write(f"💡 **Put Sell Strike (PE):** &lt; ₹{pe_sell_strike:.0f} PE")
                                elif is_buy_dips_verdict:
                                    st.markdown("#### ⏳ પુલબેક મોનિટરિંગ")
                                    st.write(f"**હાલનો ભાવ:** ₹{curr_p:.2f}")
                                    st.warning("🛑 **૧ કલાકમાં કરેક્શન/પુલબેક ચાલુ છે.** ઉતાવળે ખરીદી ના કરો! 1-Hour માં Green લાઈન Red લાઈન ઉપર ક્રોસ (Bull Cross ⬆️) કરે ત્યારે જ સ્નાઈપર બાય એન્ટ્રી કરવી.")
                                    st.write(f"**સંભવિત ટાર્ગેટ ૧:** ₹{levels['t1']:.2f}")
                                    st.write(f"**સંભવિત ટાર્ગેટ ૨:** ₹{levels['t2']:.2f}")
                                    st.write(f"**કી સપોર્ટ / સ્ટોપલોસ:** ₹{levels['stop_loss']:.2f}")
                                else:
                                    st.markdown("#### 🎯 કી-લેવલ્સ સારાંશ")
                                    st.write(f"**એન્ટ્રી ભાવ:** ₹{curr_p:.2f}")
                                    st.write(f"**ટાર્ગેટ ૧:** ₹{levels['t1']:.2f} (+{levels['t1_pct']:.1f}%)")
                                    st.write(f"**ટાર્ગેટ ૨:** ₹{levels['t2']:.2f} (+{levels['t2_pct']:.1f}%)")
                                    st.write(f"**ચુસ્ત સ્ટોપલોસ:** ₹{levels['stop_loss']:.2f}")
                        
                        # 4-Timeframe Breakdown Columns
                        st.divider()
                        st.subheader("🧭 4-Timeframe Breakdown:")
                        b1, b2, b3, b4 = st.columns(4)
                        with b1:
                            with st.container(border=True):
                                st.markdown("### 📅 Monthly")
                                st.write(f"**HM:** {m_hm['status']}")
                                st.write(f"**TC:** {m_tc['status']}")
                                st.write(f"**Vol:** {m_vol['status']}")
                        with b2:
                            with st.container(border=True):
                                st.markdown("### 📆 Weekly")
                                st.write(f"**HM:** {w_hm['status']}")
                                st.write(f"**TC:** {w_tc['status']}")
                                st.write(f"**Vol:** {w_vol['status']}")
                        with b3:
                            with st.container(border=True):
                                st.markdown("### ⏰ Daily")
                                st.write(f"**HM:** {d_hm['status']}")
                                st.write(f"**TC:** {d_tc['status']}")
                                st.write(f"**Vol:** {d_vol['status']}")
                        with b4:
                            with st.container(border=True):
                                st.markdown("### ⚡ 1-Hour")
                                st.write(f"**HM:** {h1_hm['status']}")
                                st.write(f"**TC:** {h1_tc['status']}")
                                st.write(f"**Vol:** {h1_vol['status']}")
                        
                        # Institutional Daily Pivot Points Matrix & R3 Option Rocket Radar
                        pivots_single = calculate_daily_pivot_points(df_daily)
                        if pivots_single:
                            st.divider()
                            st.subheader("🎯 Institutional Daily Pivot Points Matrix (સ્ટાન્ડર્ડ પિવટ લેવલ્સ):")
                            
                            p_v = pivots_single['p']
                            r1_v = pivots_single['r1']
                            r2_v = pivots_single['r2']
                            r3_v = pivots_single['r3']
                            s1_v = pivots_single['s1']
                            s2_v = pivots_single['s2']
                            s3_v = pivots_single['s3']
                            
                            # Determine level highlights
                            is_r3_cross = curr_p >= r3_v
                            is_r2_cross = curr_p >= r2_v
                            is_r1_cross = curr_p >= r1_v
                            
                            strike_step_single = 20 if curr_p < 500 else (50 if curr_p < 2500 else 100)
                            otm_ce_single = int((int(curr_p / strike_step_single) + 1) * strike_step_single)
                            is_r3_radar_single = (pct_chg >= 1.5 or curr_p >= r2_v) and (curr_p >= r1_v) and (d_hm.get('bullish', False) or pct_chg >= 2.0)
                            
                            # 7 columns for S3, S2, S1, P, R1, R2, R3
                            p_cols = st.columns(7)
                            with p_cols[0]:
                                st.markdown(f'<div style="background: rgba(239, 68, 68, 0.08); border-top: 3px solid #EF4444; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: #FCA5A5; font-weight: 700;">SUPPORT S3</div><div style="font-size: 16px; font-weight: 800; color: #EF4444; font-family: monospace;">₹{s3_v:.1f}</div></div>', unsafe_allow_html=True)
                            with p_cols[1]:
                                st.markdown(f'<div style="background: rgba(239, 68, 68, 0.06); border-top: 3px solid #F87171; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: #FCA5A5; font-weight: 700;">SUPPORT S2</div><div style="font-size: 16px; font-weight: 800; color: #F87171; font-family: monospace;">₹{s2_v:.1f}</div></div>', unsafe_allow_html=True)
                            with p_cols[2]:
                                st.markdown(f'<div style="background: rgba(245, 158, 11, 0.08); border-top: 3px solid #F59E0B; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: #FCD34D; font-weight: 700;">SUPPORT S1</div><div style="font-size: 16px; font-weight: 800; color: #F59E0B; font-family: monospace;">₹{s1_v:.1f}</div></div>', unsafe_allow_html=True)
                            with p_cols[3]:
                                st.markdown(f'<div style="background: rgba(56, 189, 248, 0.1); border-top: 3px solid #38BDF8; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: #7DD3FC; font-weight: 700;">PIVOT (P)</div><div style="font-size: 16px; font-weight: 800; color: #38BDF8; font-family: monospace;">₹{p_v:.1f}</div></div>', unsafe_allow_html=True)
                            with p_cols[4]:
                                border_r1 = "#10B981" if is_r1_cross else "#64748B"
                                bg_r1 = "rgba(16, 185, 129, 0.12)" if is_r1_cross else "rgba(100, 116, 139, 0.06)"
                                col_r1 = "#34D399" if is_r1_cross else "#94A3B8"
                                st.markdown(f'<div style="background: {bg_r1}; border-top: 3px solid {border_r1}; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: {col_r1}; font-weight: 700;">RESIST R1</div><div style="font-size: 16px; font-weight: 800; color: {col_r1}; font-family: monospace;">₹{r1_v:.1f}</div>{"<div style=\'font-size:9px;color:#34D399;font-weight:700;\'>CROSS ✓</div>" if is_r1_cross else ""}</div>', unsafe_allow_html=True)
                            with p_cols[5]:
                                border_r2 = "#F59E0B" if is_r2_cross else "#64748B"
                                bg_r2 = "rgba(245, 158, 11, 0.15)" if is_r2_cross else "rgba(100, 116, 139, 0.06)"
                                col_r2 = "#FBBF24" if is_r2_cross else "#94A3B8"
                                st.markdown(f'<div style="background: {bg_r2}; border-top: 3px solid {border_r2}; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: {col_r2}; font-weight: 700;">RESIST R2</div><div style="font-size: 16px; font-weight: 800; color: {col_r2}; font-family: monospace;">₹{r2_v:.1f}</div>{"<div style=\'font-size:9px;color:#FBBF24;font-weight:700;\'>CROSS ✓</div>" if is_r2_cross else ""}</div>', unsafe_allow_html=True)
                            with p_cols[6]:
                                border_r3 = "#EC4899" if is_r3_cross else "#64748B"
                                bg_r3 = "rgba(236, 72, 153, 0.18)" if is_r3_cross else "rgba(100, 116, 139, 0.06)"
                                col_r3 = "#F472B6" if is_r3_cross else "#94A3B8"
                                st.markdown(f'<div style="background: {bg_r3}; border-top: 3px solid {border_r3}; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 11px; color: {col_r3}; font-weight: 700;">RESIST R3 🚀</div><div style="font-size: 16px; font-weight: 800; color: {col_r3}; font-family: monospace;">₹{r3_v:.1f}</div>{"<div style=\'font-size:9px;color:#F472B6;font-weight:700;\'>BOOM 🚀</div>" if is_r3_cross else ""}</div>', unsafe_allow_html=True)

                            if is_r3_radar_single:
                                st.markdown(
                                    f'<div style="margin-top: 14px; background: linear-gradient(135deg, rgba(245, 158, 11, 0.18) 0%, rgba(217, 119, 6, 0.25) 100%); border: 1.5px solid #F59E0B; border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 20px rgba(245, 158, 11, 0.25);">'
                                    f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                                    f'<span style="font-size: 14px; font-weight: 800; color: #FCD34D;">⚡ R3 OPTION ROCKET SETUP ACTIVATED</span>'
                                    f'<span style="font-size: 11px; font-weight: 700; color: #FFFFFF; background: #D97706; padding: 3px 10px; border-radius: 6px;">OPTION LEADS FUTURE</span>'
                                    f'</div>'
                                    f'<div style="font-size: 13px; color: #FEF3C7; margin-top: 8px; line-height: 1.6;">'
                                    f'• <b>વોચલિસ્ટ OTM Call Strike:</b> <b style="color: #38BDF8; font-size: 15px;">₹{otm_ce_single} CE</b><br>'
                                    f'• <b>સુવર્ણ નિયમ (Golden Rule):</b> જ્યારે આ OTM CE તેના પોતાના <b>Daily R3</b> લેવલને ક્રોસ કરે ત્યારે જ બાય એન્ટ્રી કરવી!<br>'
                                    f'• <b>સ્ટોપલોસ (SL):</b> ઓપ્શનની 5m/15m બ્રેકઆઉટ કેન્ડલનો લો (Low)<br>'
                                    f'• <b>ટાર્ગેટ (Target):</b> 100% થી 200%+ (ડબલ / મલ્ટિબેગર કેપિટલ ગેઇન)'
                                    f'</div>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )

                        # Interactive 3-Panel Candlestick Charts
                        st.divider()
                        st.subheader("🕯️ ઇન્ટરેક્ટિવ કેન્ડલસ્ટિક ચાર્ટ્સ (3 Panels Synchronized):")
                        t1, t2, t3, t4 = st.tabs([
                            "⚡ 1-Hour Candlestick View",
                            "⏰ Daily Candlestick View",
                            "📆 Weekly Candlestick View",
                            "📅 Monthly Candlestick View"
                        ])
                        with t1:
                            chart_1h = plot_candlestick_triple_chart(df_1h, title_prefix="1-Hour", lookback=100, is_hourly=True)
                            st.altair_chart(chart_1h, width="stretch")
                        with t2:
                            chart_d = plot_candlestick_triple_chart(df_daily, title_prefix="Daily", lookback=120, is_hourly=False)
                            st.altair_chart(chart_d, width="stretch")
                        with t3:
                            chart_w = plot_candlestick_triple_chart(df_weekly, title_prefix="Weekly", lookback=80, is_hourly=False)
                            st.altair_chart(chart_w, width="stretch")
                        with t4:
                            chart_m = plot_candlestick_triple_chart(df_monthly, title_prefix="Monthly", lookback=60, is_hourly=False)
                            st.altair_chart(chart_m, width="stretch")
                except Exception as e:
                    st.error(f"ક્ષતિ આવી: {e}")


# =============================================================
# TAB 3: MY ACTIVE TRADES & RISK GUARDIAN (AUTO-EXIT WATCHDOG)
# =============================================================
with nav_tab_guardian:
    guardian_header_html = (
        '<div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%); '
        'border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 20px 24px; margin-bottom: 22px; '
        'box-shadow: 0 8px 25px rgba(0,0,0,0.3);">'
        '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">'
        '<div>'
        '<div style="font-size: 22px; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 10px;">'
        '🛡️ MY ACTIVE TRADES & RISK GUARDIAN'
        '<span style="font-size: 11px; font-weight: 700; background: rgba(16, 185, 129, 0.2); color: #34D399; '
        'border: 1px solid #10B981; padding: 3px 10px; border-radius: 9999px;">24x7 WATCHDOG ACTIVE</span>'
        '</div>'
        '<div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">'
        'તમે લીધેલા <b>Buy</b> અથવા <b>Option Selling</b> ટ્રેડ્સ અહીં એડ કરો. જો ભાવ ધારણાથી વિરુદ્ધ જશે તો સિસ્ટમ તાત્કાલિક ટેલિગ્રામ પર <b>EXIT સાયરન</b> વગાડશે!'
        '</div>'
        '</div>'
        '<div style="text-align: right;">'
        '<span style="font-size: 12px; font-weight: 700; color: #38BDF8; background: rgba(56, 189, 248, 0.12); '
        'border: 1px solid rgba(56, 189, 248, 0.3); padding: 6px 14px; border-radius: 10px;">'
        '⚡ Instant Mobile Telegram Alerts'
        '</span>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.html(guardian_header_html)
    
    # Section A: Add New Trade Form
    with st.expander("➕ નવો ટ્રેડ મોનિટરિંગમાં ઉમેરો (Add New Position to Watchdog)", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            t_type_selected = st.radio(
                "ટ્રેડનો પ્રકાર (Trade Type):",
                options=["📈 BUY Trade (ખરીદી પોઝિશન)", "📉 SHORT Trade (વેચાણ પોઝિશન)", "⚖️ Option Selling (રેન્જ સેલિંગ)"],
                horizontal=True,
                key="trd_type_radio"
            )
            t_sym_input = st.text_input(
                "સ્ટોક સિમ્બોલ (Stock Symbol):",
                value="TATASTEEL",
                placeholder="દા.ત. TATASTEEL, ITC, BHEL, HEROMOTOCO, RELIANCE",
                key="trd_sym_input"
            ).strip().upper()
            t_entry_p = st.number_input(
                "તમારો એન્ટ્રી ભાવ (Entry Price ₹):",
                min_value=0.1,
                value=185.0,
                step=0.5,
                key="trd_entry_price"
            )
            t_qty = st.number_input(
                "શેર / લોટ ક્વોન્ટિટી (Quantity):",
                min_value=1,
                value=100,
                step=1,
                key="trd_qty"
            )
            
        with col_f2:
            if "BUY" in t_type_selected:
                auto_sl = round(t_entry_p * 0.985, 2)
                auto_t1 = round(t_entry_p * 1.03, 2)
                auto_t2 = round(t_entry_p * 1.06, 2)
                
                t_sl = st.number_input(
                    "સ્ટોપ-લોસ લેવલ (Stop-Loss ₹):",
                    min_value=0.1,
                    value=auto_sl,
                    step=0.5,
                    help="આ લેવલથી નીચે ભાવ જતાં જ તમને તાત્કાલિક EXIT એલર્ટ મળશે!",
                    key="trd_sl"
                )
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    t_t1 = st.number_input("Target 1 (₹):", min_value=0.1, value=auto_t1, step=0.5, key="trd_t1")
                with sub_col2:
                    t_t2 = st.number_input("Target 2 (₹):", min_value=0.1, value=auto_t2, step=0.5, key="trd_t2")
                t_ce_strike = None
                t_pe_strike = None
            elif "SHORT" in t_type_selected:
                auto_sl = round(t_entry_p * 1.015, 2)
                auto_t1 = round(t_entry_p * 0.97, 2)
                auto_t2 = round(t_entry_p * 0.94, 2)
                
                t_sl = st.number_input(
                    "શોર્ટ સ્ટોપ-લોસ લેવલ (Short Stop-Loss ₹):",
                    min_value=0.1,
                    value=auto_sl,
                    step=0.5,
                    help="આ ભાવથી ઉપર નીકળે તો શોર્ટ પોઝિશનમાંથી તાત્કાલિક EXIT એલર્ટ મળશે!",
                    key="trd_sl"
                )
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    t_t1 = st.number_input("Short Target 1 (₹):", min_value=0.1, value=auto_t1, step=0.5, key="trd_t1")
                with sub_col2:
                    t_t2 = st.number_input("Short Target 2 (₹):", min_value=0.1, value=auto_t2, step=0.5, key="trd_t2")
                t_ce_strike = None
                t_pe_strike = None
            else:
                auto_ce = round(t_entry_p * 1.025, 2)
                auto_pe = round(t_entry_p * 0.975, 2)
                c_c1, c_c2 = st.columns(2)
                with c_c1:
                    t_ce_strike = st.number_input(
                        "Call Sell Strike (CE Resistance ₹):",
                        min_value=0.1,
                        value=auto_ce,
                        step=0.5,
                        help="આ ભાવથી ઉપર નીકળે તો કૉલમાંથી એક્ઝિટ સાયરન વાગશે.",
                        key="trd_ce"
                    )
                with c_c2:
                    t_pe_strike = st.number_input(
                        "Put Sell Strike (PE Support ₹):",
                        min_value=0.1,
                        value=auto_pe,
                        step=0.5,
                        help="આ ભાવથી નીચે પડે તો પુટમાંથી એક્ઝિટ સાયરન વાગશે.",
                        key="trd_pe"
                    )
                t_sl = None
                t_t1 = None
                t_t2 = None
                
            t_notes = st.text_input(
                "ટ્રેડ નોંધ / વ્યૂહરચના (Notes):",
                value="Sniper Alignment Strategy",
                key="trd_notes"
            )
            
        add_btn = st.button("🚀 Add Trade to Risk Guardian", type="primary", use_container_width=True)
        if add_btn and t_sym_input:
            clean_s = t_sym_input.replace(".NS", "").replace(".BO", "").strip()
            full_s = f"{clean_s}.NS"
            actual_type = "BUY" if "BUY" in t_type_selected else ("SHORT" if "SHORT" in t_type_selected else "OPTION_SELLING")
            new_trd = {
                "id": f"TRD_{int(time.time())}",
                "symbol": clean_s,
                "full_symbol": full_s,
                "trade_type": actual_type,
                "entry_price": float(t_entry_p),
                "qty": int(t_qty),
                "entry_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "stop_loss": float(t_sl) if t_sl else None,
                "target_1": float(t_t1) if t_t1 else None,
                "target_2": float(t_t2) if t_t2 else None,
                "ce_strike": float(t_ce_strike) if t_ce_strike else None,
                "pe_strike": float(t_pe_strike) if t_pe_strike else None,
                "status": "ACTIVE",
                "notes": t_notes
            }
            all_trades = load_active_trades()
            all_trades.append(new_trd)
            save_active_trades(all_trades)
            st.toast(f"✅ {clean_s} સફળતાપૂર્વક Risk Guardian મોનિટરિંગમાં એડ થઈ ગયો!", icon="🛡️")
            st.rerun()

    # Section B: Live Position Dashboard
    all_trades = load_active_trades()
    active_positions = [t for t in all_trades if t.get("status") == "ACTIVE"]
    closed_positions = [t for t in all_trades if t.get("status") == "CLOSED"]
    
    if not active_positions:
        st.info("💡 તમારી પાસે હાલમાં કોઈ સક્રિય ટ્રેડ મોનિટરિંગમાં નથી. ઉપરના ફોર્મમાંથી તમારો **Buy** અથવા **Option Selling** ટ્રેડ ઉમેરો.")
    else:
        # Fetch live prices for active positions in parallel
        unique_syms = list(set([t.get("full_symbol", f"{t['symbol']}.NS") for t in active_positions]))
        live_prices = {}
        
        def fetch_live_p(s):
            try:
                tkr = yf.Ticker(s)
                h = tkr.history(period="2d", interval="1d")
                df_1h = tkr.history(period="1mo", interval="1h").dropna(subset=['Close', 'High', 'Low', 'Volume'])
                hm_info = {"status": "સામાન્ય", "is_bear": False, "green": 50.0, "red": 50.0}
                if not df_1h.empty and len(df_1h) >= 25:
                    df_1h = calculate_hilega_milega(df_1h)
                    cg = float(df_1h['Green_EMA3'].iloc[-1])
                    cr = float(df_1h['Red_WMA21'].iloc[-1])
                    pg = float(df_1h['Green_EMA3'].iloc[-2])
                    pr = float(df_1h['Red_WMA21'].iloc[-2])
                    is_bear = (pg >= pr and cg < cr) or (cg < cr and cg < 50.0)
                    if pg >= pr and cg < cr:
                        st_txt = "🔴 તાજો બેરિશ ક્રોસ"
                    elif cg < cr and cg < 50:
                        st_txt = "🔴 મંદી (પાણી 50 નીચે)"
                    elif cg > cr and cg >= 50:
                        st_txt = "🟢 સુપર તેજી (પાણી ઉપર)"
                    else:
                        st_txt = "🟡 રિવર્સલ / પુલબેક"
                    hm_info = {"status": st_txt, "is_bear": is_bear, "green": cg, "red": cr}
                    
                if not h.empty:
                    c_p = float(h['Close'].iloc[-1])
                    p_p = float(h['Close'].iloc[-2]) if len(h) > 1 else c_p
                    return s, c_p, p_p, hm_info
            except Exception:
                pass
            return s, None, None, {"status": "અપૂરતો ડેટા", "is_bear": False, "green": 50, "red": 50}
            
        with ThreadPoolExecutor(max_workers=5) as executor:
            for s, c_price, p_price, hm_info in executor.map(lambda sym: fetch_live_p(sym), unique_syms):
                if c_price is not None:
                    live_prices[s] = {"curr": c_price, "prev": p_price, "hm": hm_info}

        # Calculate Portfolio Overview KPIs
        total_pnl = 0.0
        danger_count = 0
        target_count = 0
        safe_count = 0
        
        for trd in active_positions:
            s_full = trd.get("full_symbol", f"{trd['symbol']}.NS")
            p_data = live_prices.get(s_full, {"curr": trd["entry_price"], "prev": trd["entry_price"]})
            curr_p = p_data["curr"]
            entry_p = trd["entry_price"]
            qty = trd.get("qty", 1)
            t_type = trd["trade_type"]
            
            if t_type == "BUY":
                pnl = (curr_p - entry_p) * qty
                total_pnl += pnl
                sl = trd.get("stop_loss", entry_p * 0.98)
                t1 = trd.get("target_1", entry_p * 1.03)
                if curr_p <= sl or curr_p <= sl * 1.012:
                    danger_count += 1
                elif curr_p >= t1:
                    target_count += 1
                else:
                    safe_count += 1
            elif t_type == "SHORT":
                pnl = (entry_p - curr_p) * qty
                total_pnl += pnl
                sl = trd.get("stop_loss", entry_p * 1.02)
                t1 = trd.get("target_1", entry_p * 0.97)
                if curr_p >= sl or curr_p >= sl * 0.988:
                    danger_count += 1
                elif curr_p <= t1:
                    target_count += 1
                else:
                    safe_count += 1
            else: # OPTION_SELLING
                ce = trd.get("ce_strike", entry_p * 1.03)
                pe = trd.get("pe_strike", entry_p * 0.97)
                if curr_p >= ce or curr_p <= pe:
                    danger_count += 1
                elif curr_p >= ce * 0.99 or curr_p <= pe * 1.01:
                    danger_count += 1
                else:
                    safe_count += 1

        pnl_color = "#34D399" if total_pnl >= 0 else "#F87171"
        pnl_sign = "+" if total_pnl >= 0 else ""
        
        # Summary KPI Cards
        kpi_guard_html = (
            f'<div class="kpi-grid">'
            f'<div class="kpi-card" style="border-top: 3px solid #38BDF8;">'
            f'<div class="kpi-title" style="color: #38BDF8;">📊 ACTIVE TRADES</div>'
            f'<div class="kpi-value">{len(active_positions)}</div>'
            f'<div class="kpi-subtitle">સક્રિય પોઝિશન્સ</div>'
            f'</div>'
            f'<div class="kpi-card" style="border-top: 3px solid {pnl_color};">'
            f'<div class="kpi-title" style="color: {pnl_color};">💰 UNREALIZED P&L</div>'
            f'<div class="kpi-value" style="color: {pnl_color};">{pnl_sign}₹{total_pnl:,.2f}</div>'
            f'<div class="kpi-subtitle">લાઈવ નફો / નુકસાન</div>'
            f'</div>'
            f'<div class="kpi-card kpi-green">'
            f'<div class="kpi-title">🟢 ON TRACK (SAFE)</div>'
            f'<div class="kpi-value">{safe_count}</div>'
            f'<div class="kpi-subtitle">સુરક્ષિત રેન્જમાં</div>'
            f'</div>'
            f'<div class="kpi-card kpi-cyan">'
            f'<div class="kpi-title">🎯 TARGETS HIT</div>'
            f'<div class="kpi-value">{target_count}</div>'
            f'<div class="kpi-subtitle">પ્રોફિટ બુકિંગ ઝોન</div>'
            f'</div>'
            f'<div class="kpi-card kpi-red">'
            f'<div class="kpi-title">🚨 AT RISK / EXIT</div>'
            f'<div class="kpi-value">{danger_count}</div>'
            f'<div class="kpi-subtitle">સ્ટોપલોસ / રેન્જ જોખમ</div>'
            f'</div>'
            f'</div>'
        )
        st.html(kpi_guard_html)
        
        st.write("### 📌 સક્રિય ટ્રેડ્સ વિગતો (Live Position Watchlist):")
        
        # Display each trade in dedicated Risk Ticket
        for idx, trd in enumerate(active_positions):
            tid = trd["id"]
            sym = trd["symbol"]
            s_full = trd.get("full_symbol", f"{sym}.NS")
            p_data = live_prices.get(s_full, {"curr": trd["entry_price"], "prev": trd["entry_price"]})
            curr_p = p_data["curr"]
            prev_p = p_data["prev"]
            entry_p = trd["entry_price"]
            qty = trd.get("qty", 1)
            t_type = trd["trade_type"]
            entry_dt = trd.get("entry_date", "Today")
            
            day_chg = curr_p - prev_p
            day_pct = (day_chg / prev_p) * 100 if prev_p else 0
            day_color = "#34D399" if day_chg >= 0 else "#F87171"
            day_arrow = "▲" if day_chg >= 0 else "▼"
            
            with st.container(border=True):
                head_col1, head_col2, head_col3 = st.columns([3, 3, 2])
                with head_col1:
                    hm_meta = p_data.get("hm", {"status": "સામાન્ય", "is_bear": False, "green": 50, "red": 50})
                    hm_pill_color = "#F87171" if hm_meta.get("is_bear") else "#34D399"
                    hm_pill_bg = "rgba(239, 68, 68, 0.15)" if hm_meta.get("is_bear") else "rgba(16, 185, 129, 0.15)"
                    hm_badge_html = f'<span style="background: {hm_pill_bg}; color: {hm_pill_color}; border: 1px solid {hm_pill_color}; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">⚡ 1H HM: {hm_meta["status"]}</span>'
                    if t_type == "BUY":
                        type_pill = '<span style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">📈 BUY POSITION</span>'
                    elif t_type == "SHORT":
                        type_pill = '<span style="background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #EF4444; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">📉 SHORT POSITION</span>'
                    else:
                        type_pill = '<span style="background: rgba(168, 85, 247, 0.2); color: #C084FC; border: 1px solid #A855F7; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">⚖️ OPTION SELLING</span>'
                    st.html(f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;"><span style="font-size: 24px; font-weight: 800; font-family: monospace; color: #FFFFFF;">{sym}</span>{type_pill}{hm_badge_html}</div><div style="font-size: 11px; color: #94A3B8; margin-top: 2px;">એન્ટ્રી તારીખ: {entry_dt} • Qty: {qty}</div>')
                
                with head_col2:
                    st.html(f'<div><span style="font-size: 20px; font-weight: 800; font-family: monospace; color: #F8FAFC;">₹{curr_p:.2f}</span> <span style="font-size: 12px; font-weight: 700; color: {day_color};">{day_arrow} {day_chg:+.2f} ({day_pct:+.2f}%)</span></div><div style="font-size: 11px; color: #94A3B8;">એન્ટ્રી ભાવ: <b style="color: #F1F5F9;">₹{entry_p:.2f}</b></div>')
                    
                with head_col3:
                    if st.button("🛑 Close Trade", key=f"close_{tid}", use_container_width=True):
                        for item in all_trades:
                            if item["id"] == tid:
                                item["status"] = "CLOSED"
                                item["exit_price"] = curr_p
                                item["exit_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_active_trades(all_trades)
                        st.toast(f"✅ {sym} ટ્રેડ સફળતાપૂર્વક ક્લોઝ થઈ ગયો!", icon="🔒")
                        st.rerun()

                # Status Evaluation & Risk Matrix
                if t_type == "BUY":
                    pnl_val = (curr_p - entry_p) * qty
                    pnl_pct = ((curr_p - entry_p) / entry_p) * 100
                    pnl_color_cls = "#34D399" if pnl_val >= 0 else "#F87171"
                    pnl_sign_cls = "+" if pnl_val >= 0 else ""
                    
                    sl = float(trd.get("stop_loss", entry_p * 0.985))
                    t1 = float(trd.get("target_1", entry_p * 1.03))
                    t2 = float(trd.get("target_2", entry_p * 1.06))
                    
                    hm_info = p_data.get("hm", {})
                    is_hm_bear = hm_info.get("is_bear", False)
                    
                    if curr_p <= sl:
                        status_banner = f'<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #F87171; font-weight: 800;">🚨 EMERGENCY EXIT TRIGGERED:</span> <span style="color: #FCA5A5; font-size: 12px;">સ્ટોક તમારા સ્ટોપ-લોસ (₹{sl:.2f}) ની નીચે ગયો છે! મૂડી બચાવવા હમણાં જ EXIT કરો.</span></div>'
                    elif curr_p <= sl * 1.012:
                        status_banner = f'<div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #FBBF24; font-weight: 800;">⚠️ DANGER ZONE:</span> <span style="color: #FDE68A; font-size: 12px;">ભાવ સ્ટોપલોસથી માત્ર ₹{curr_p - sl:.2f} ઉપર છે. સાવચેત રહો.</span></div>'
                    elif curr_p >= t2:
                        status_banner = f'<div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #34D399; font-weight: 800;">🎉 TARGET 2 ACHIEVED:</span> <span style="color: #A7F3D0; font-size: 12px;">૧૦૦% પ્રોફિટ ટાર્ગેટ આવી ગયો છે. પૂરો પ્રોફિટ બુક કરો!</span></div>'
                    elif curr_p >= t1:
                        status_banner = f'<div style="background: rgba(6, 182, 212, 0.15); border: 1px solid #06B6D4; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #38BDF8; font-weight: 800;">🎯 TARGET 1 HIT:</span> <span style="color: #BAE6FD; font-size: 12px;">૫૦% પ્રોફિટ બુક કરો અને બાકીના સ્ટોપ-લોસને એન્ટ્રી ભાવે ટ્રેલ કરો.</span></div>'
                    elif is_hm_bear:
                        status_banner = f'<div style="background: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #FBBF24; font-weight: 800;">⚠️ EARLY EXIT ADVICE (HILEGA-MILEGA REVERSAL):</span> <span style="color: #FDE68A; font-size: 12px;">૧-Hour માં ગ્રીન લાઈન રેડ લાઈનની નીચે સરકી ગઈ છે અને મોમેન્ટમ ગુમાવી રહ્યું છે. પૂરો સ્ટોપલોસ હિટ થવાની રાહ જોવાને બદલે અત્યારે જ સેફ એક્ઝિટ લઈ શકાય!</span></div>'
                    else:
                        status_banner = f'<div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #34D399; font-weight: 700;">🟢 ON TRACK:</span> <span style="color: #CBD5E1; font-size: 12px;">પોઝિશન સામાન્ય અને સુરક્ષિત રીતે ચાલે છે.</span></div>'
                    
                    st.html(status_banner)
                    
                    # Levels Grid
                    m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                    with m_c1:
                        st.metric("P&L (નફો/નુકસાન)", f"{pnl_sign_cls}₹{pnl_val:,.2f}", f"{pnl_sign_cls}{pnl_pct:.2f}%")
                    with m_c2:
                        st.metric("🛡️ Stop Loss", f"₹{sl:.2f}", f"-{((entry_p - sl)/entry_p)*100:.1f}%")
                    with m_c3:
                        st.metric("🎯 Target 1", f"₹{t1:.2f}", f"+{((t1 - entry_p)/entry_p)*100:.1f}%")
                    with m_c4:
                        st.metric("🚀 Target 2", f"₹{t2:.2f}", f"+{((t2 - entry_p)/entry_p)*100:.1f}%")
                    with m_c5:
                        rr_ratio = (t2 - entry_p) / (entry_p - sl) if (entry_p - sl) > 0 else 2.5
                        st.metric("⚖️ Risk:Reward", f"1 : {rr_ratio:.1f}")
                elif t_type == "SHORT":
                    pnl_val = (entry_p - curr_p) * qty
                    pnl_pct = ((entry_p - curr_p) / entry_p) * 100
                    pnl_color_cls = "#34D399" if pnl_val >= 0 else "#F87171"
                    pnl_sign_cls = "+" if pnl_val >= 0 else ""
                    
                    sl = float(trd.get("stop_loss", entry_p * 1.015))
                    t1 = float(trd.get("target_1", entry_p * 0.97))
                    t2 = float(trd.get("target_2", entry_p * 0.94))
                    
                    hm_info = p_data.get("hm", {})
                    is_hm_bull = (hm_info.get("green", 50) > hm_info.get("red", 50)) and (hm_info.get("green", 50) >= 50.0)
                    
                    if curr_p >= sl:
                        status_banner = f'<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #F87171; font-weight: 800;">🚨 EMERGENCY EXIT TRIGGERED (SHORT SL HIT):</span> <span style="color: #FCA5A5; font-size: 12px;">ભાવ શોર્ટ સ્ટોપ-લોસ (₹{sl:.2f}) ની ઉપર નીકળી ગયો છે! નુકસાન અટકાવવા હમણાં જ EXIT કરો.</span></div>'
                    elif curr_p >= sl * 0.988:
                        status_banner = f'<div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #FBBF24; font-weight: 800;">⚠️ DANGER ZONE:</span> <span style="color: #FDE68A; font-size: 12px;">ભાવ સ્ટોપલોસથી માત્ર ₹{sl - curr_p:.2f} નીચે છે. સાવચેત રહો.</span></div>'
                    elif curr_p <= t2:
                        status_banner = f'<div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #34D399; font-weight: 800;">🎉 TARGET 2 ACHIEVED (MAX SHORT PROFIT):</span> <span style="color: #A7F3D0; font-size: 12px;">૧૦૦% શોર્ટ નફા લક્ષ્ય આવી ગયું છે. પૂરો નફો બુક કરો!</span></div>'
                    elif curr_p <= t1:
                        status_banner = f'<div style="background: rgba(6, 182, 212, 0.15); border: 1px solid #06B6D4; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #38BDF8; font-weight: 800;">🎯 TARGET 1 HIT:</span> <span style="color: #BAE6FD; font-size: 12px;">૫૦% શોર્ટ નફો બુક કરો અને બાકીના સ્ટોપ-લોસને એન્ટ્રી ભાવે ટ્રેલ કરો.</span></div>'
                    elif is_hm_bull:
                        status_banner = f'<div style="background: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #FBBF24; font-weight: 800;">⚠️ EARLY EXIT ADVICE (HILEGA-MILEGA BULLISH REVERSAL):</span> <span style="color: #FDE68A; font-size: 12px;">૧-Hour માં ગ્રીન લાઈન રેડ લાઈન ઉપર નીકળી ગઈ છે. શોર્ટ પોઝિશનમાંથી સેફ એક્ઝિટ લઈ શકાય!</span></div>'
                    else:
                        status_banner = f'<div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #34D399; font-weight: 700;">🟢 ON TRACK:</span> <span style="color: #CBD5E1; font-size: 12px;">શોર્ટ પોઝિશન સામાન્ય અને સુરક્ષિત રીતે ચાલે છે.</span></div>'
                    
                    st.html(status_banner)
                    
                    # Levels Grid for Short
                    m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                    with m_c1:
                        st.metric("P&L (નફો/નુકસાન)", f"{pnl_sign_cls}₹{pnl_val:,.2f}", f"{pnl_sign_cls}{pnl_pct:.2f}%")
                    with m_c2:
                        st.metric("🛡️ Short SL", f"₹{sl:.2f}", f"+{((sl - entry_p)/entry_p)*100:.1f}%")
                    with m_c3:
                        st.metric("🎯 Short Target 1", f"₹{t1:.2f}", f"-{((entry_p - t1)/entry_p)*100:.1f}%")
                    with m_c4:
                        st.metric("🚀 Short Target 2", f"₹{t2:.2f}", f"-{((entry_p - t2)/entry_p)*100:.1f}%")
                    with m_c5:
                        rr_ratio = (entry_p - t2) / (sl - entry_p) if (sl - entry_p) > 0 else 2.5
                        st.metric("⚖️ Risk:Reward", f"1 : {rr_ratio:.1f}")
                else: # OPTION SELLING
                    ce = float(trd.get("ce_strike", entry_p * 1.025))
                    pe = float(trd.get("pe_strike", entry_p * 0.975))
                    
                    if curr_p >= ce:
                        status_banner = f'<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #F87171; font-weight: 800;">🚨 CALL BREACH ALERT:</span> <span style="color: #FCA5A5; font-size: 12px;">ભાવ Call Strike (₹{ce:.1f}) થી ઉપર નીકળી ગયો છે! શોર્ટ કૉલમાંથી EXIT કરો અથવા હેજ કરો.</span></div>'
                    elif curr_p <= pe:
                        status_banner = f'<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #F87171; font-weight: 800;">🚨 PUT BREACH ALERT:</span> <span style="color: #FCA5A5; font-size: 12px;">ભાવ Put Strike (₹{pe:.1f}) થી નીચે ઉતરી ગયો છે! શોર્ટ પુટમાંથી EXIT કરો અથવા હેજ કરો.</span></div>'
                    elif (ce - curr_p) <= (ce * 0.008) or (curr_p - pe) <= (pe * 0.008):
                        status_banner = f'<div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #FBBF24; font-weight: 800;">⚠️ NEAR RANGE BOUNDARY:</span> <span style="color: #FDE68A; font-size: 12px;">ભાવ રેન્જની કિનારી પર આવી ગયો છે. સતર્ક રહો.</span></div>'
                    else:
                        status_banner = f'<div style="background: rgba(168, 85, 247, 0.1); border: 1px solid #A855F7; border-radius: 8px; padding: 8px 12px; margin: 10px 0;"><span style="color: #C084FC; font-weight: 800;">🟢 SAFE THETA DECAY:</span> <span style="color: #E2E8F0; font-size: 12px;">સ્ટોક ₹{pe:.1f} થી ₹{ce:.1f} ની સેફ રેન્જમાં શાંતિથી ફરી રહ્યો છે. બંને બાજુ પ્રીમિયમ ગળી રહ્યું છે!</span></div>'
                    
                    st.html(status_banner)
                    
                    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                    with m_c1:
                        st.metric("📉 Call Strike (CE Sell)", f"> ₹{ce:.1f}", f"+{((ce - curr_p)/curr_p)*100:.1f}% Buffer")
                    with m_c2:
                        st.metric("📈 Put Strike (PE Sell)", f"< ₹{pe:.1f}", f"-{((curr_p - pe)/curr_p)*100:.1f}% Buffer")
                    with m_c3:
                        st.metric("🛡️ Safe Expiry Range", f"₹{pe:.0f} - ₹{ce:.0f}", "100% Profit Band")
                    with m_c4:
                        st.metric("⚖️ Strategy", "SHORT STRANGLE", "Theta Decay")

    # Section C: Closed Trades History
    if closed_positions:
        with st.expander(f"📜 બંધ કરેલા જૂના ટ્રેડ્સ (Closed History - {len(closed_positions)} Trades)", expanded=False):
            st.dataframe(
                pd.DataFrame([
                    {
                        "Symbol": t["symbol"],
                        "Type": t["trade_type"],
                        "Entry Price": f"₹{t['entry_price']:.2f}",
                        "Exit Price": f"₹{t.get('exit_price', 0):.2f}",
                        "Entry Date": t.get("entry_date", "-"),
                        "Exit Date": t.get("exit_date", "-"),
                        "Notes": t.get("notes", "-")
                    } for t in closed_positions
                ]),
                use_container_width=True,
                hide_index=True
            )

# =============================================================
# TAB 4: DR. SHUBHENDU GANGULY'S MELTING STRADDLES COCKPIT
# =============================================================
def calculate_camarilla_levels(df_d):
    """
    Camarilla Pivot Points calculation:
    Range = High - Low
    H4 = Close + Range * 1.1 / 2
    H3 = Close + Range * 1.1 / 4
    L3 = Close - Range * 1.1 / 4
    L4 = Close - Range * 1.1 / 2
    H5 = (High / Low) * Close
    L5 = Close - (H5 - Close)
    """
    if df_d is None or df_d.empty or len(df_d) < 2:
        return None
    prev = df_d.iloc[-2]
    h, l, c = float(prev['High']), float(prev['Low']), float(prev['Close'])
    rng = h - l
    h4 = c + (rng * 1.1 / 2.0)
    h3 = c + (rng * 1.1 / 4.0)
    h2 = c + (rng * 1.1 / 6.0)
    h1 = c + (rng * 1.1 / 12.0)
    l1 = c - (rng * 1.1 / 12.0)
    l2 = c - (rng * 1.1 / 6.0)
    l3 = c - (rng * 1.1 / 4.0)
    l4 = c - (rng * 1.1 / 2.0)
    h5 = (h / l) * c if l > 0 else h4 * 1.01
    l5 = c - (h5 - c)
    return {
        "prev_h": h, "prev_l": l, "prev_c": c, "range": rng,
        "h5": h5, "h4": h4, "h3": h3, "h2": h2, "h1": h1,
        "l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5": l5
    }

@st.cache_data(ttl=60)
def fetch_index_data_for_melting(symbol):
    try:
        t = yf.Ticker(symbol)
        df_d = t.history(period="10d", interval="1d").dropna(subset=['Close', 'High', 'Low'])
        df_5m = t.history(period="2d", interval="5m").dropna(subset=['Close', 'High', 'Low'])
        return df_d, df_5m
    except Exception:
        return None, None

with nav_tab_melting:
    melting_header_html = (
        '<div style="background: linear-gradient(135deg, rgba(20, 30, 48, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%); '
        'border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 22px 26px; margin-bottom: 20px; '
        'box-shadow: 0 10px 30px rgba(0,0,0,0.35);">'
        '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">'
        '<div>'
        '<div style="font-size: 24px; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 12px;">'
        '🎯 MELTING STRADDLES COCKPIT'
        '<span style="font-size: 11px; font-weight: 700; background: linear-gradient(135deg, #10B981, #059669); '
        'color: #FFFFFF; padding: 4px 12px; border-radius: 9999px; box-shadow: 0 0 14px rgba(16, 185, 129, 0.4);">'
        'DR. GANGULY 0DTE STRATEGY</span>'
        '</div>'
        '<div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">'
        'ઇન્ટ્રાડે ATM કમ્બાઈન્ડ સ્ટ્રેડલ ડીકે • દૈનિક <b>૧૦-પોઇન્ટ્સ નિયમ</b> • <b>Camarilla S3/R3</b> બાઉન્ડ્રી ફિલ્ટર • <b>3-Straddle</b> કોકપિટ રડાર'
        '</div>'
        '</div>'
        '<div style="text-align: right;">'
        '<span style="font-size: 12px; font-weight: 700; color: #38BDF8; background: rgba(56, 189, 248, 0.12); '
        'border: 1px solid rgba(56, 189, 248, 0.3); padding: 6px 14px; border-radius: 10px;">'
        '⚡ Mathematical Theta Decay'
        '</span>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.html(melting_header_html)

    # 1. Day Detection & Auto-Selector
    now_dt = datetime.datetime.now()
    cur_weekday = now_dt.weekday()
    day_labels = ["સોમવાર (Monday)", "મંગળવાર (Tuesday)", "બુધવાર (Wednesday)", "ગુરુવાર (Thursday)", "શુક્રવાર (Friday)", "શનિવાર (Saturday)", "રવિવાર (Sunday)"]
    today_label = day_labels[cur_weekday]

    if cur_weekday in [4, 0, 1]:  # Fri, Mon, Tue -> Nifty
        default_index_pos = 0
        rule_info = f"💡 <b>આજનો વાર {today_label}:</b> ડૉ. ગાંગુલીના નિયમ મુજબ શુક્રવાર, સોમવાર અને મંગળવારે <b>NIFTY 50</b> પર ટ્રેડ કરવું (મંગળવાર એક્સપાયરી ડીકે સાયકલ)."
    elif cur_weekday in [2, 3]:  # Wed, Thu -> Sensex
        default_index_pos = 1
        rule_info = f"💡 <b>આજનો વાર {today_label}:</b> ડૉ. ગાંગુલીના નિયમ મુજબ બુધવાર અને ગુરુવારે <b>SENSEX</b> પર ટ્રેડ કરવું (ગુરુવાર એક્સપાયરી ડીકે સાયકલ)."
    else:
        default_index_pos = 0
        rule_info = f"⏸️ <b>આજનો વાર {today_label} (વીકેન્ડ):</b> હાલ બજાર બંધ છે. તમે Nifty અથવા Sensex પર બેકટેસ્ટ અને સ્ટ્રેટેજી સમજી શકો છો."

    st.markdown(f'<div style="background: rgba(30, 41, 59, 0.7); border-left: 4px solid #38BDF8; border-radius: 8px; padding: 10px 16px; margin-bottom: 16px; font-size: 13px; color: #E2E8F0;">{rule_info}</div>', unsafe_allow_html=True)

    c_inst1, c_inst2 = st.columns([2.5, 1.5])
    with c_inst1:
        selected_inst = st.radio(
            "ટ્રેડિંગ ઇન્ડેક્સ પસંદ કરો:",
            options=["🏛️ NIFTY 50 (^NSEI) [શુક્ર, સોમ, મંગળ]", "📈 BSE SENSEX (^BSESN) [બુધ, ગુરુ]"],
            index=default_index_pos,
            horizontal=True,
            key="melting_inst_selector"
        )
    with c_inst2:
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        refresh_melting = st.button("🔄 Refresh Index Data", key="refresh_melting_btn", use_container_width=True)

    is_nifty = "NIFTY" in selected_inst
    inst_sym = "^NSEI" if is_nifty else "^BSESN"
    inst_title = "NIFTY 50" if is_nifty else "BSE SENSEX"
    strike_round = 100 if is_nifty else 500
    straddle_delta = 200 if is_nifty else 500
    lot_size_default = 25 if is_nifty else 10

    # Fetch Data
    df_d_m, df_5m_m = fetch_index_data_for_melting(inst_sym)

    if df_d_m is None or df_d_m.empty or len(df_d_m) < 2:
        st.error(f"❌ {inst_title} નો ડેટા લોડ થઈ શક્યો નથી. થોડીવાર પછી ફરી પ્રયાસ કરો.")
    else:
        curr_p = float(df_d_m['Close'].iloc[-1])
        prev_p = float(df_d_m['Close'].iloc[-2])
        p_chg = curr_p - prev_p
        p_pct = (p_chg / prev_p) * 100
        cam = calculate_camarilla_levels(df_d_m)

        # 3 Straddle Strikes
        atm_strike = int(round(curr_p / float(strike_round)) * strike_round)
        lower_strike = atm_strike - straddle_delta
        higher_strike = atm_strike + straddle_delta

        # Camarilla Regime Check
        h3 = cam['h3']
        l3 = cam['l3']
        h4 = cam['h4']
        l4 = cam['l4']

        is_neutral_zone = (curr_p >= l3 and curr_p <= h3)
        is_bull_expansion = (curr_p > h3)
        is_bear_expansion = (curr_p < l3)

        # Regime Banner
        if is_neutral_zone:
            regime_class = "border: 1.5px solid #10B981; background: rgba(16, 185, 129, 0.12);"
            regime_badge = '<span style="background: #10B981; color: #FFFFFF; font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;">🟢 NEUTRAL S3 - R3 ZONE (100% ATM STRADDLE DAY)</span>'
            regime_text = (
                f"<b>સુવર્ણ તક:</b> ભાવ <b>S3 (₹{l3:.1f})</b> અને <b>R3 (₹{h3:.1f})</b> ની વચ્ચે સંપૂર્ણ રેન્જબાઉન્ડ છે! "
                f"ડૉ. ગાંગુલીના નિયમ મુજબ આજે <b>માત્ર ATM Straddle (₹{atm_strike} CE+PE)</b> જ સેલ કરવો. "
                f"બંને બાજુ પ્રીમિયમ ઝડપથી ઓગળશે (Theta Melt). ઓપ્શન ખરીદનારાઓ માટે જોખમી દિવસ!"
            )
        elif is_bull_expansion:
            regime_class = "border: 1.5px solid #38BDF8; background: rgba(56, 189, 248, 0.12);"
            regime_badge = '<span style="background: #0284C7; color: #FFFFFF; font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;">🚀 BULLISH EXPANSION (Above R3)</span>'
            regime_text = (
                f"<b>ટ્રેન્ડિંગ તેજી:</b> ભાવ R3 (₹{h3:.1f}) ની ઉપર નીકળી ગયો છે! "
                f"ATM Straddle છોડીને <b>HIGHER STRADDLE (₹{higher_strike} CE+PE)</b> પર શિફ્ટ થાઓ. "
                f"પુટ ઇન-ધ-મની (ITM) હોવાથી હાયર સ્ટ્રેડલ ઝડપથી ઓગળીને નફો આપશે."
            )
        else:
            regime_class = "border: 1.5px solid #EF4444; background: rgba(239, 68, 68, 0.12);"
            regime_badge = '<span style="background: #DC2626; color: #FFFFFF; font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;">🩸 BEARISH EXPANSION (Below S3)</span>'
            regime_text = (
                f"<b>ટ્રેન્ડિંગ મંદી:</b> ભાવ S3 (₹{l3:.1f}) ની નીચે ઉતરી ગયો છે! "
                f"ATM Straddle છોડીને <b>LOWER STRADDLE (₹{lower_strike} CE+PE)</b> પર શિફ્ટ થાઓ. "
                f"કૉલ ઇન-ધ-મની (ITM) હોવાથી લોઅર સ્ટ્રેડલ ઝડપથી ડીકે થશે."
            )

        regime_card_html = (
            f'<div style="{regime_class} border-radius: 14px; padding: 18px 22px; margin-bottom: 22px;">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">'
            f'<div style="display: flex; align-items: center; gap: 12px;">'
            f'<span style="font-size: 20px; font-weight: 800; color: #FFFFFF; font-family: monospace;">{inst_title}: ₹{curr_p:,.1f}</span>'
            f'<span style="font-size: 12px; font-weight: 700; color: {"#34D399" if p_chg >= 0 else "#F87171"}; '
            f'background: {"rgba(16, 185, 129, 0.15)" if p_chg >= 0 else "rgba(239, 68, 68, 0.15)"}; padding: 3px 8px; border-radius: 6px;">'
            f'{"▲" if p_chg >= 0 else "▼"} {p_chg:+.1f} ({p_pct:+.2f}%)</span>'
            f'</div>'
            f'<div>{regime_badge}</div>'
            f'</div>'
            f'<div style="margin-top: 10px; color: #E2E8F0; font-size: 13px; line-height: 1.6;">{regime_text}</div>'
            f'</div>'
        )
        st.html(regime_card_html)

        # 2. 3-Straddle Cockpit Radar (Visual KPI Cards)
        st.markdown("### 🎛️ 3-Straddle Cockpit Setup (ડૉ. ગાંગુલીના ૩ સ્ટ્રેડલ્સ)")
        sc1, sc2, sc3 = st.columns(3)

        with sc1:
            lower_active = "border: 2px solid #EF4444;" if is_bear_expansion else "border: 1px solid rgba(255,255,255,0.08);"
            lower_badge = "🔥 ACTIVE SHORT TARGET" if is_bear_expansion else "Cushion / Trend Buffer"
            lower_html = (
                f'<div style="background: rgba(22, 31, 48, 0.95); {lower_active} border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<span style="font-size: 11px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">📉 LOWER STRADDLE (-{straddle_delta} pts)</span>'
                f'<span style="font-size: 10px; font-weight: 700; color: #FCA5A5; background: rgba(239, 68, 68, 0.2); padding: 2px 7px; border-radius: 4px;">{lower_badge}</span>'
                f'</div>'
                f'<div style="font-size: 26px; font-weight: 800; color: #FFFFFF; font-family: monospace; margin: 8px 0 4px 0;">₹{lower_strike} CE+PE</div>'
                f'<div style="font-size: 12px; color: #CBD5E1;">જ્યારે બજાર S3 તોડીને નીચે જાય ત્યારે આ સ્ટ્રેડલ શોર્ટ કરવો.</div>'
                f'<div style="font-size: 11px; color: #64748B; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">Distance: -{curr_p - lower_strike:.0f} pts from Spot</div>'
                f'</div>'
            )
            st.html(lower_html)

        with sc2:
            atm_active = "border: 2px solid #10B981; box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);" if is_neutral_zone else "border: 1px solid rgba(255,255,255,0.08);"
            atm_badge = "🎯 100% FOCUS STRADDLE" if is_neutral_zone else "Hold / Neutral"
            atm_html = (
                f'<div style="background: rgba(22, 31, 48, 0.95); {atm_active} border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<span style="font-size: 11px; font-weight: 700; color: #34D399; text-transform: uppercase;">🟢 ATM STRADDLE (PRIMARY)</span>'
                f'<span style="font-size: 10px; font-weight: 700; color: #FFFFFF; background: #10B981; padding: 2px 7px; border-radius: 4px;">{atm_badge}</span>'
                f'</div>'
                f'<div style="font-size: 26px; font-weight: 800; color: #34D399; font-family: monospace; margin: 8px 0 4px 0;">₹{atm_strike} CE+PE</div>'
                f'<div style="font-size: 12px; color: #CBD5E1;">બજાર S3 અને R3 વચ્ચે હોય ત્યાં સુધી માત્ર આ સ્ટ્રેડલ મેલ્ટ થશે.</div>'
                f'<div style="font-size: 11px; color: #64748B; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">Distance: {abs(curr_p - atm_strike):.0f} pts from Spot (At The Money)</div>'
                f'</div>'
            )
            st.html(atm_html)

        with sc3:
            higher_active = "border: 2px solid #38BDF8;" if is_bull_expansion else "border: 1px solid rgba(255,255,255,0.08);"
            higher_badge = "🔥 ACTIVE SHORT TARGET" if is_bull_expansion else "Cushion / Trend Buffer"
            higher_html = (
                f'<div style="background: rgba(22, 31, 48, 0.95); {higher_active} border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<span style="font-size: 11px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">📈 HIGHER STRADDLE (+{straddle_delta} pts)</span>'
                f'<span style="font-size: 10px; font-weight: 700; color: #38BDF8; background: rgba(56, 189, 248, 0.2); padding: 2px 7px; border-radius: 4px;">{higher_badge}</span>'
                f'</div>'
                f'<div style="font-size: 26px; font-weight: 800; color: #FFFFFF; font-family: monospace; margin: 8px 0 4px 0;">₹{higher_strike} CE+PE</div>'
                f'<div style="font-size: 12px; color: #CBD5E1;">જ્યારે બજાર R3 તોડીને ઉપર જાય ત્યારે આ સ્ટ્રેડલ શોર્ટ કરવો.</div>'
                f'<div style="font-size: 11px; color: #64748B; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">Distance: +{higher_strike - curr_p:.0f} pts from Spot</div>'
                f'</div>'
            )
            st.html(higher_html)

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        # 3. Camarilla Pivot Levels Matrix
        with st.expander(f"📊 {inst_title} Daily Camarilla Levels Breakdown (H5 to L5)", expanded=True):
            cam_cols = st.columns(6)
            with cam_cols[0]:
                st.metric("H5 (Extreme High)", f"₹{cam['h5']:.1f}", "Target Above")
            with cam_cols[1]:
                st.metric("H4 (Breakout Buy)", f"₹{cam['h4']:.1f}", "Bull Extension")
            with cam_cols[2]:
                st.metric("H3 (Range Top / R3)", f"₹{cam['h3']:.1f}", "ATM Upper Limit")
            with cam_cols[3]:
                st.metric("L3 (Range Bottom / S3)", f"₹{cam['l3']:.1f}", "ATM Lower Limit")
            with cam_cols[4]:
                st.metric("L4 (Breakdown Sell)", f"₹{cam['l4']:.1f}", "Bear Extension")
            with cam_cols[5]:
                st.metric("L5 (Extreme Low)", f"₹{cam['l5']:.1f}", "Target Below")

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # 4. The 10-Point Mechanical Profit & SL Calculator
        st.markdown("### 🧮 ૧૦-પોઇન્ટ્સ રૂલ કેલ્ક્યુલેટર (The 10-Point Mechanical Engine)")
        st.caption("ડૉ. ગાંગુલીનો સુવર્ણ નિયમ: દરરોજ માત્ર ૧૦ પોઇન્ટ્સ કમ્બાઈન્ડ પ્રીમિયમ મેળવો, લોભ ન કરો. આ કેલ્ક્યુલેટર તમારા લેવલ્સ ગણી આપશે:")

        calc_col1, calc_col2 = st.columns([1.2, 1.8])
        with calc_col1:
            user_entry_prem = st.number_input(
                "તમારી કમ્બાઈન્ડ Straddle એન્ટ્રી કિંમત (CE+PE Combined ₹):",
                min_value=5.0,
                max_value=2000.0,
                value=160.0,
                step=5.0,
                key="melting_entry_price_input"
            )
            user_lots = st.number_input(
                "લોટ્સ સંખ્યા (Number of Lots):",
                min_value=1,
                max_value=100,
                value=4,
                step=1,
                key="melting_lots_input"
            )
            user_lot_size = st.number_input(
                "લોટ સાઈઝ (Lot Size):",
                min_value=1,
                max_value=500,
                value=lot_size_default,
                step=1,
                key="melting_lot_size_input"
            )

        total_qty = user_lots * user_lot_size
        calc_sl = user_entry_prem + 10.0
        calc_t1 = user_entry_prem - 10.0
        calc_t2 = user_entry_prem - 20.0
        calc_t3 = user_entry_prem - 30.0

        pnl_10 = 10.0 * total_qty
        pnl_20 = 20.0 * total_qty
        pnl_sl = -10.0 * total_qty

        with calc_col2:
            calc_matrix_html = (
                f'<div class="kpi-grid">'
                f'<div class="kpi-card" style="border-top: 3px solid #EF4444; background: rgba(239, 68, 68, 0.08);">'
                f'<div class="kpi-title" style="color: #F87171;">🛡️ STRICT STOP-LOSS (+10 pts)</div>'
                f'<div class="kpi-value" style="color: #F87171;">₹{calc_sl:.1f}</div>'
                f'<div class="kpi-subtitle" style="color: #EF4444; font-weight: 700;">Loss: -₹{abs(pnl_sl):,.0f} (Above VWAP Exit)</div>'
                f'</div>'
                f'<div class="kpi-card" style="border-top: 3px solid #10B981; background: rgba(16, 185, 129, 0.08);">'
                f'<div class="kpi-title" style="color: #34D399;">🎯 TARGET 1 (-10 pts)</div>'
                f'<div class="kpi-value" style="color: #34D399;">₹{calc_t1:.1f}</div>'
                f'<div class="kpi-subtitle" style="color: #10B981; font-weight: 700;">Profit: +₹{pnl_10:,.0f} (Book Lot 1 & Move SL to Cost)</div>'
                f'</div>'
                f'<div class="kpi-card" style="border-top: 3px solid #06B6D4; background: rgba(6, 182, 212, 0.08);">'
                f'<div class="kpi-title" style="color: #38BDF8;">🚀 TARGET 2 (-20 pts)</div>'
                f'<div class="kpi-value" style="color: #38BDF8;">₹{calc_t2:.1f}</div>'
                f'<div class="kpi-subtitle" style="color: #06B6D4; font-weight: 700;">Profit: +₹{pnl_20:,.0f} (Book Lot 2)</div>'
                f'</div>'
                f'<div class="kpi-card" style="border-top: 3px solid #8B5CF6; background: rgba(139, 92, 246, 0.08);">'
                f'<div class="kpi-title" style="color: #A78BFA;">💰 WEEKLY POTENTIAL</div>'
                f'<div class="kpi-value" style="color: #C084FC;">50 Points</div>'
                f'<div class="kpi-subtitle" style="color: #A78BFA; font-weight: 700;">2,600 Points / Year (No Greed)</div>'
                f'</div>'
                f'</div>'
            )
            st.html(calc_matrix_html)

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        # 4.1 Definedge P&F (Point & Figure) 0.5% Straddle Execution Engine
        st.markdown("### 📐 P&F (Point & Figure) 0.5% ચાર્ટ એક્ઝિક્યુશન ગાઈડ")
        st.caption("કેન્ડલસ્ટિકના અવાજ (Noise) વગર શુદ્ધ ભાવ નક્કી કરવા Definedge TradePoint પર કમ્બાઈન્ડ પ્રીમિયમનો 0.5% P&F ચાર્ટ વાપરવામાં આવે છે:")

        pnf_c1, pnf_c2 = st.columns([1.6, 1.4])
        with pnf_c1:
            pnf_box_html = (
                '<div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px 20px;">'
                '<div style="font-size: 15px; font-weight: 800; color: #FCD34D; margin-bottom: 10px;">🛠️ Definedge TradePoint P&F સેટિંગ્સ:</div>'
                '<ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #E2E8F0; line-height: 1.8;">'
                '<li><b>ચાર્ટ પ્રકાર:</b> Point & Figure (P&F Chart)</li>'
                '<li><b>બોક્સ સાઈઝ (Box Size):</b> <b style="color: #38BDF8;">0.5% (Point Five Percent)</b></li>'
                '<li><b>રિવર્સલ (Reversal):</b> <b>3 Boxes</b> (લગભગ 2.5 થી 3 પોઇન્ટ્સ)</li>'
                '<li><b>ટાઇમફ્રેમ:</b> <b>1-Minute (૧ મિનિટ)</b></li>'
                '<li><b>ઇન્ડિકેટર:</b> <b>VWAP</b> (P&F કમ્બાઈન્ડ પ્રીમિયમ પર)</li>'
                '</ul>'
                '</div>'
            )
            st.html(pnf_box_html)

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            st.markdown("##### 🎯 P&F ના ૪ સુવર્ણ સેલ સિગ્નલ્સ (All Below VWAP):")
            st.markdown("""
            1. 📉 **Double Bottom Sell (DBS):** અગાઉના 'O' કૉલમનું તળિયું નવો 'O' કૉલમ તોડીને નીચે જાય ત્યારે સૌથી ક્લીન સેલ એન્ટ્રી.
            2. ⚓ **Anchor Follow-Through (AFT):** મોટો બેરિશ એન્કર કૉલમ બન્યા પછી વધારાનું સેલ કન્ફર્મેશન.
            3. 🗼 **High Pole Follow-Through (HPFT):** અચાનક 'X' કૉલમ ઉછળીને ૫૦% થી વધુ પાછો ઘટે અને સેલ સિગ્નલ આપે.
            4. 🐢 **Turtle Sell Breakdown:** મલ્ટી-કૉલમ / ૨૦-પીરિયડ લો તૂટે ત્યારે બ્રેકડાઉન સેલ.
            """)

        with pnf_c2:
            st.markdown("##### ✅ લાઈવ ટ્રેડ એક્ઝિક્યુશન ચેકલિસ્ટ:")
            chk1 = st.checkbox("1. શું કમ્બાઈન્ડ પ્રીમિયમ તેના VWAP ની નીચે ટ્રેડ કરી રહ્યું છે?", value=True, key="chk_pnf_vwap")
            chk2 = st.checkbox("2. શું P&F (0.5% x 3) પર Double Bottom Sell કે Follow-Through બન્યું છે?", value=True, key="chk_pnf_sig")
            chk3 = st.checkbox("3. શું સ્ટોપ-લોસ VWAP ની ઉપર (ચુસ્ત ૧૦ પોઇન્ટ્સ) સિસ્ટમમાં મૂકેલ છે?", value=True, key="chk_pnf_sl")
            chk4 = st.checkbox("4. શું કૉલમ રિવર્સલ (O -> X) અથવા VWAP ક્રોસ થતાં જ તાત્કાલિક એક્ઝિટ માટે તૈયાર છો?", value=True, key="chk_pnf_exit")

            if chk1 and chk2 and chk3 and chk4:
                st.success("🟢 બધા નિયમો પાળવામાં આવ્યા છે: તમે ડૉ. ગાંગુલીના 10-પોઇન્ટ્સ રૂલ મુજબ પરફેક્ટ ટ્રેડમાં છો!")
            else:
                st.warning("⚠️ ચેતવણી: તમામ નિયમો કન્ફર્મ ન થાય ત્યાં સુધી એન્ટ્રી ન કરો.")

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        # 5. Decay Statistics Table from Dr. Ganguly's 20-week study
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            with st.expander("📈 નિફ્ટી ઐતિહાસિક ડીકે સ્ટેટિસ્ટિક્સ (20-Week Average Data)", expanded=False):
                st.markdown("""
                | ટ્રેડિંગ દિવસ | સરેરાશ ઇન્ટ્રાડે ડીકે | અપેક્ષિત ડીકે % | નોંધ |
                |---|---|---|---|
                | **શુક્રવાર (Friday)** | ~27 Points | ~35% | ધીમો ડીકે શરૂ થાય છે |
                | **સોમવાર (Monday)** | ~56 Points | ~60% | વીકેન્ડ પછી ઝડપી મેલ્ટિંગ |
                | **મંગળવાર (Tuesday Expiry)** | ~133 Points | ~90% | એક્સપાયરી દિવસ - સુપ્રીમ ડીકે |
                | **કુલ ઉપલબ્ધ ડીકે:** | **~217 Points** | - | **તમારો ટાર્ગેટ માત્ર 50 પોઇન્ટ્સ છે!** |
                """)
        with col_t2:
            with st.expander("📈 સેન્સેક્સ ઐતિહાસિક ડીકે સ્ટેટિસ્ટિક્સ (20-Week Average Data)", expanded=False):
                st.markdown("""
                | ટ્રેડિંગ દિવસ | સરેરાશ ઇન્ટ્રાડે ડીકે | અપેક્ષિત ડીકે % | નોંધ |
                |---|---|---|---|
                | **બુધવાર (Wednesday)** | ~119 Points | ~65% | મધ્યમ ડીકે દિવસ |
                | **ગુરુવાર (Thursday Expiry)**| ~422 Points | ~95% | એક્સપાયરી દિવસ - એક્સ્ટ્રીમ મેલ્ટિંગ |
                | **કુલ ઉપલબ્ધ ડીકે:** | **~541 Points** | - | **નિફ્ટી સ્કેલમાં ~180 પોઇન્ટ્સ બરાબર** |
                """)

        # 6. The 7 Golden Commandments of Melting Straddles
        with st.expander("📜 ડૉ. શુભેન્દુ ગાંગુલીના ૭ સુવર્ણ નિયમો (The 7 Golden Rules)", expanded=False):
            st.markdown("""
            1. 🧠 **ગણિત સર્વોપરી છે (Mathematics > Prediction):** બજાર ક્યાં જશે તે કોઈ નથી જાણતું, પણ ગણિત ફિક્સ છે કે ATM Straddle એક્સપાયરી સુધીમાં શૂન્ય (0) થશે જ.
            2. 🎯 **રોજના માત્ર ૧૦ પોઇન્ટ્સ (No FOMO):** 200 પોઇન્ટ્સ ડીકેમાંથી આખો નફો લેવાની લાલચ ન કરવી. દરરોજ 10 પોઇન્ટ્સ લેશો તો પણ વર્ષે 2600 પોઇન્ટ્સ થશે.
            3. ⚖️ **કમ્બાઈન્ડ પ્રીમિયમ પર જ ટ્રેડ:** ક્યારેય સિંગલ લેગ (ફક્ત કૉલ કે ફક્ત પુટ) ન વેચવો. હંમેશા બંને લેગ કમ્બાઈન્ડ શોર્ટ કરવા.
            4. 📉 **VWAP નીચે જ એન્ટ્રી:** કમ્બાઈન્ડ પ્રીમિયમ જ્યારે તેના VWAP ની નીચે સેલ સિગ્નલ આપે ત્યારે જ શોર્ટ કરવો.
            5. 🛡️ **ચુસ્ત ૧૦-પોઇન્ટ્સનો SL:** જો પ્રીમિયમ VWAP ની ઉપર નીકળે તો કોઈ પણ હિચકિચાટ વગર તાત્કાલિક એક્ઝિટ કરવું.
            6. 🔄 **Shift Straddles Like Trains:** જો બજાર S3 કે R3 તોડે તો પાટા બદલો—ATM છોડીને Higher કે Lower Straddle પકડો.
            7. ⚡ **બાસ્કેટ ઓર્ડર્સ (Basket Orders):** સ્લિપેજ ઘટાડવા માટે એક જ ક્લિકમાં CE અને PE સેલ અને એક્ઝિટ માટે બાસ્કેટ ઓર્ડર વાપરવા.
            """)

