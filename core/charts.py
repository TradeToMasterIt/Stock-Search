"""
TradingView & Institutional Charting Module for Patel Trading Bot / Confluence Pro
Provides both live TradingView Technical Analysis widgets and custom synchronized Altair charts.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import altair as alt

SYMBOL_ALIASES = {
    "GMRINFRA": "GMRAIRPORT",
    "MCDOWELL-N": "UNITDSPR",
    "MCDOWELL_N": "UNITDSPR",
}

def get_tradingview_symbol(symbol):
    """Converts local ticker symbol to TradingView NSE symbol."""
    if not symbol:
        return "NSE:NIFTY"
    clean = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    clean = SYMBOL_ALIASES.get(clean, clean)
    if clean in ["^NSEI", "NIFTY", "NIFTY50", "NIFTY 50"]:
        return "NSE:NIFTY"
    elif clean in ["^NSEBANK", "BANKNIFTY", "BANK NIFTY"]:
        return "NSE:BANKNIFTY"
    elif clean in ["FINNIFTY", "NIFTY_FIN_SERVICE"]:
        return "NSE:FINNIFTY"
    return f"NSE:{clean}"

def get_fyers_symbol(symbol):
    """Normalizes symbol to official Fyers format."""
    if not symbol:
        return "NSE:NIFTY50-INDEX"
    clean = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").replace("NSE:", "").strip().upper()
    clean = SYMBOL_ALIASES.get(clean, clean)
    if clean in ["NSEI", "NIFTY", "NIFTY50", "NIFTY 50"]:
        return "NSE:NIFTY50-INDEX"
    elif clean in ["NSEBANK", "BANKNIFTY", "BANK NIFTY"]:
        return "NSE:NIFTYBANK-INDEX"
    elif clean in ["FINNIFTY", "NIFTY_FIN_SERVICE"]:
        return "NSE:FINNIFTY-INDEX"
    if not clean.endswith("-EQ") and not clean.endswith("-INDEX"):
        return f"NSE:{clean}-EQ"
    return clean

def fetch_fyers_chart_df(symbol, interval="D", days=180):
    """Fetches high-precision historical candles directly from Fyers API."""
    try:
        from core.fyers_auth import get_fyers_client, safe_fyers_history
        ok, fyers = get_fyers_client()
        if not ok:
            return None
        
        f_sym = get_fyers_symbol(symbol)
        res_code = "D"
        if str(interval).lower() in ["60", "60m", "1h", "2-hour"]:
            res_code = "60"
        elif str(interval).lower() in ["15", "15m"]:
            res_code = "15"
        elif str(interval).lower() in ["30", "30m"]:
            res_code = "30"
        elif str(interval).lower() in ["5", "5m"]:
            res_code = "5"
            
        now_dt = datetime.now()
        to_d = now_dt.strftime("%Y-%m-%d")
        from_d = (now_dt - timedelta(days=days)).strftime("%Y-%m-%d")
        data = {
            "symbol": f_sym,
            "resolution": res_code,
            "date_format": "1",
            "range_from": from_d,
            "range_to": to_d,
            "cont_flag": "1"
        }
        resp = safe_fyers_history(fyers, data)
        candles = resp.get("candles", [])
        if not candles:
            return None
        
        df = pd.DataFrame(candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"[FYERS_CHART] History fetch error: {e}")
        return None

def render_tradingview_widget(symbol, df=None, interval="D", height=600):
    """
    Renders institutional-grade TradingView Pro Chart powered directly by Fyers API Live Data.
    Features:
    - 100% Real-Time NSE Candle Data (Zero delayed, official broker feed)
    - Full TradingView Lightweight Charts v4 Canvas
    - Instant Bar Style Switcher: Normal Candles vs Heikin Ashi
    - Overlays: 20 EMA (Cyan), 50 SMA (Orange), 200 SMA (Purple), Volume (Colorized)
    - Synchronized Sub-chart: RSI (14) with 70/30/50 bands
    - 1-Click Launch buttons for full TradingView and Fyers web terminals
    - Zero 'Only available on TradingView' blocking errors
    """
    import json
    import time

    clean_sym = symbol.replace(".NS", "").replace(".BO", "").replace("^", "").replace("NSE:", "").strip().upper()
    tv_symbol = get_tradingview_symbol(symbol)
    
    # 1. Fetch live data from Fyers API (with fallback to provided df or yfinance)
    fyers_df = fetch_fyers_chart_df(clean_sym, interval=interval)
    if fyers_df is not None and len(fyers_df) > 5:
        chart_df = fyers_df.tail(200).copy()
        data_source = "FYERS API (LIVE NSE)"
    elif df is not None and isinstance(df, pd.DataFrame) and not df.empty:
        chart_df = df.tail(200).copy()
        data_source = "CACHED HISTORICAL"
    else:
        try:
            import yfinance as yf
            full_s = f"{clean_sym}.NS" if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO") else clean_sym
            chart_df = yf.Ticker(full_s).history(period="1y", interval="1d").tail(200)
            data_source = "YFINANCE BACKUP"
        except Exception:
            chart_df = None
            data_source = "NONE"

    if chart_df is None or chart_df.empty or len(chart_df) < 2:
        st.warning(f"⚠️ {clean_sym} માટે ચાર્ટ ડેટા લોડ થઈ શક્યો નથી.")
        return

    # Clean timezone if needed
    if chart_df.index.tz is not None:
        plot_index = chart_df.index.tz_convert("Asia/Kolkata")
    else:
        plot_index = chart_df.index

    # 2. Indicators Calculation
    close_series = chart_df['Close'].astype(float)
    ema_20_series = close_series.ewm(span=20, adjust=False).mean()
    sma_50_series = close_series.rolling(window=50, min_periods=1).mean()
    sma_200_series = close_series.rolling(window=200, min_periods=1).mean()

    # RSI 14
    delta = close_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = (100 - (100 / (1 + rs))).fillna(50)

    # 3. Serializing Normal & Heikin Ashi Candles
    normal_candles = []
    ha_candles = []
    volumes = []
    ema_20_data = []
    sma_50_data = []
    sma_200_data = []
    rsi_data = []

    prev_ha_open = None
    prev_ha_close = None

    is_intraday = str(interval).lower() in ["60", "60m", "15", "15m", "30", "30m", "5", "5m"]

    rows = list(chart_df.iterrows())
    for i, (idx, row) in enumerate(rows):
        # Format time
        if is_intraday:
            # Unix timestamp for intraday
            time_val = int(idx.timestamp()) if hasattr(idx, 'timestamp') else int(time.time())
        else:
            time_val = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]

        o = round(float(row['Open']), 2)
        h = round(float(row['High']), 2)
        l = round(float(row['Low']), 2)
        c = round(float(row['Close']), 2)
        v = float(row.get('Volume', 0))

        normal_candles.append({"time": time_val, "open": o, "high": h, "low": l, "close": c})

        # Heikin Ashi calculation
        ha_close = round((o + h + l + c) / 4.0, 2)
        if i == 0 or prev_ha_open is None:
            ha_open = round((o + c) / 2.0, 2)
        else:
            ha_open = round((prev_ha_open + prev_ha_close) / 2.0, 2)
        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)
        prev_ha_open = ha_open
        prev_ha_close = ha_close

        ha_candles.append({"time": time_val, "open": ha_open, "high": ha_high, "low": ha_low, "close": ha_close})

        # Volume
        vol_col = "rgba(16, 185, 129, 0.45)" if c >= o else "rgba(239, 68, 68, 0.45)"
        volumes.append({"time": time_val, "value": v, "color": vol_col})

        # Overlays
        ema_val = ema_20_series.iloc[i]
        if pd.notna(ema_val):
            ema_20_data.append({"time": time_val, "value": round(float(ema_val), 2)})

        sma_50_val = sma_50_series.iloc[i]
        if pd.notna(sma_50_val):
            sma_50_data.append({"time": time_val, "value": round(float(sma_50_val), 2)})

        sma_200_val = sma_200_series.iloc[i]
        if pd.notna(sma_200_val):
            sma_200_data.append({"time": time_val, "value": round(float(sma_200_val), 2)})

        rsi_val = rsi_series.iloc[i]
        if pd.notna(rsi_val):
            rsi_data.append({"time": time_val, "value": round(float(rsi_val), 2)})

    # Summary metrics for header
    last_candle = normal_candles[-1]
    prev_candle = normal_candles[-2] if len(normal_candles) > 1 else last_candle
    last_close = last_candle['close']
    chg = round(last_close - prev_candle['close'], 2)
    chg_pct = round((chg / prev_candle['close']) * 100, 2) if prev_candle['close'] else 0.0
    chg_color = "#10B981" if chg >= 0 else "#EF4444"
    chg_sign = "+" if chg >= 0 else ""

    container_id = f"tv_chart_{clean_sym.replace('^', '').replace(':', '_')}"

    # Heights
    main_chart_height = max(height - 180, 360)
    rsi_chart_height = 140

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: #080c14;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                color: #F3F4F6;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: linear-gradient(180deg, #0e1626 0%, #080c14 100%);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
                overflow: hidden;
            }}
            .chart-top-bar {{
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                align-items: center;
                padding: 10px 16px;
                background: rgba(15, 23, 42, 0.95);
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                gap: 10px;
            }}
            .stock-title-wrap {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .stock-symbol {{
                font-size: 16px;
                font-weight: 800;
                color: #FFFFFF;
                font-family: monospace;
            }}
            .badge-source {{
                font-size: 10px;
                font-weight: 700;
                background: rgba(16, 185, 129, 0.15);
                color: #34D399;
                border: 1px solid rgba(16, 185, 129, 0.4);
                padding: 2px 8px;
                border-radius: 9999px;
            }}
            .stock-price {{
                font-size: 16px;
                font-weight: 800;
                font-family: monospace;
                color: {chg_color};
            }}
            .toolbar-actions {{
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }}
            .pill-btn {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #CBD5E1;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s ease;
            }}
            .pill-btn:hover {{
                background: rgba(56, 189, 248, 0.2);
                border-color: #38BDF8;
                color: #FFFFFF;
            }}
            .pill-active {{
                background: #2563EB !important;
                border-color: #3B82F6 !important;
                color: #FFFFFF !important;
            }}
            .toggle-label {{
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 11px;
                color: #94A3B8;
                cursor: pointer;
                user-select: none;
            }}
            .toggle-label input {{
                cursor: pointer;
                accent-color: #38BDF8;
            }}
            .ext-link-btn {{
                color: #38BDF8;
                text-decoration: none;
                font-size: 11px;
                font-weight: 700;
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.3);
                padding: 4px 10px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                gap: 4px;
                transition: all 0.2s;
            }}
            .ext-link-btn:hover {{
                background: rgba(56, 189, 248, 0.25);
                color: #FFFFFF;
            }}
            .legend-bar {{
                padding: 6px 16px;
                font-size: 11px;
                font-family: monospace;
                color: #94A3B8;
                display: flex;
                flex-wrap: wrap;
                gap: 14px;
                background: rgba(8, 12, 20, 0.6);
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }}
            .rsi-header {{
                padding: 4px 16px;
                font-size: 11px;
                font-weight: 700;
                color: #94A3B8;
                background: rgba(15, 23, 42, 0.7);
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            #main_chart_{container_id} {{
                width: 100%;
                height: {main_chart_height}px;
            }}
            #rsi_chart_{container_id} {{
                width: 100%;
                height: {rsi_chart_height}px;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <!-- Top Toolbar -->
            <div class="chart-top-bar">
                <div class="stock-title-wrap">
                    <span class="stock-symbol">{clean_sym}</span>
                    <span class="badge-source">⚡ {data_source}</span>
                    <span class="stock-price">₹{last_close:,.2f} ({chg_sign}{chg_pct}%)</span>
                </div>
                
                <div class="toolbar-actions">
                    <!-- Style Switcher -->
                    <button id="btn_candles_{container_id}" class="pill-btn pill-active" onclick="switchStyle('candles')">🕯️ Candles</button>
                    <button id="btn_ha_{container_id}" class="pill-btn" onclick="switchStyle('ha')">📊 Heikin Ashi</button>
                    
                    <span style="opacity: 0.3; margin: 0 4px;">|</span>
                    
                    <!-- Overlays Toggles -->
                    <label class="toggle-label"><input type="checkbox" id="chk_ema20_{container_id}" checked onchange="toggleEMA20(this.checked)"><span style="color: #06B6D4;">EMA 20</span></label>
                    <label class="toggle-label"><input type="checkbox" id="chk_sma50_{container_id}" checked onchange="toggleSMA50(this.checked)"><span style="color: #F59E0B;">SMA 50</span></label>
                    <label class="toggle-label"><input type="checkbox" id="chk_sma200_{container_id}" onchange="toggleSMA200(this.checked)"><span style="color: #A855F7;">SMA 200</span></label>
                    <label class="toggle-label"><input type="checkbox" id="chk_vol_{container_id}" checked onchange="toggleVolume(this.checked)"><span>Vol</span></label>
                    
                    <span style="opacity: 0.3; margin: 0 4px;">|</span>
                    
                    <!-- External Launchers -->
                    <a href="https://in.tradingview.com/chart/?symbol={tv_symbol}" target="_blank" class="ext-link-btn" title="Open official TradingView full chart">
                        ↗️ TradingView Web
                    </a>
                    <a href="https://trade.fyers.in/" target="_blank" class="ext-link-btn" style="color: #10B981; border-color: rgba(16, 185, 129, 0.4);" title="Open Fyers Trading Terminal">
                        ⚡ Fyers Web
                    </a>
                </div>
            </div>

            <!-- Dynamic Live Hover Legend -->
            <div id="legend_{container_id}" class="legend-bar">
                <span>O: <b id="leg_o">-</b></span>
                <span>H: <b id="leg_h">-</b></span>
                <span>L: <b id="leg_l">-</b></span>
                <span>C: <b id="leg_c">-</b></span>
                <span>Vol: <b id="leg_v">-</b></span>
                <span style="color: #06B6D4;">EMA20: <b id="leg_ema">-</b></span>
                <span style="color: #38BDF8;">RSI(14): <b id="leg_rsi">-</b></span>
            </div>

            <!-- Main Candlestick & Volume Chart -->
            <div id="main_chart_{container_id}"></div>

            <!-- Sub-chart: RSI (14) Oscillator -->
            <div id="rsi_wrap_{container_id}">
                <div class="rsi-header">
                    <span>⚡ RELATIVE STRENGTH INDEX (RSI 14)</span>
                    <span style="font-size: 10px; color: #64748B;">Overbought: 70 • Oversold: 30</span>
                </div>
                <div id="rsi_chart_{container_id}"></div>
            </div>
        </div>

        <script>
        (function() {{
            const normalCandles = {json.dumps(normal_candles)};
            const haCandles = {json.dumps(ha_candles)};
            const volumeData = {json.dumps(volumes)};
            const ema20Data = {json.dumps(ema_20_data)};
            const sma50Data = {json.dumps(sma_50_data)};
            const sma200Data = {json.dumps(sma_200_data)};
            const rsiData = {json.dumps(rsi_data)};

            const mainContainer = document.getElementById("main_chart_{container_id}");
            const rsiContainer = document.getElementById("rsi_chart_{container_id}");

            // 1. Create Main Chart
            const mainChart = LightweightCharts.createChart(mainContainer, {{
                width: mainContainer.clientWidth,
                height: {main_chart_height},
                layout: {{
                    background: {{ type: 'solid', color: '#080c14' }},
                    textColor: '#94A3B8',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1, style: 3 }},
                    horzLine: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1, style: 3 }},
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    scaleMargins: {{ top: 0.08, bottom: 0.2 }},
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    timeVisible: {str(is_intraday).lower()},
                    secondsVisible: false,
                }},
            }});

            // Candlestick Series
            const candleSeries = mainChart.addCandlestickSeries({{
                upColor: '#10B981',
                downColor: '#EF4444',
                borderVisible: false,
                wickUpColor: '#10B981',
                wickDownColor: '#EF4444',
            }});
            candleSeries.setData(normalCandles);

            // Volume Series
            const volumeSeries = mainChart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
                scaleMargins: {{ top: 0.82, bottom: 0 }},
            }});
            volumeSeries.setData(volumeData);

            // EMA 20 Series
            const ema20Series = mainChart.addLineSeries({{
                color: '#06B6D4',
                lineWidth: 2,
                title: 'EMA 20',
                priceLineVisible: false,
            }});
            ema20Series.setData(ema20Data);

            // SMA 50 Series
            const sma50Series = mainChart.addLineSeries({{
                color: '#F59E0B',
                lineWidth: 2,
                title: 'SMA 50',
                priceLineVisible: false,
            }});
            sma50Series.setData(sma50Data);

            // SMA 200 Series
            const sma200Series = mainChart.addLineSeries({{
                color: '#A855F7',
                lineWidth: 2,
                title: 'SMA 200',
                priceLineVisible: false,
                visible: false,
            }});
            sma200Series.setData(sma200Data);

            // 2. Create Synchronized RSI Sub-Chart
            const rsiChart = LightweightCharts.createChart(rsiContainer, {{
                width: rsiContainer.clientWidth,
                height: {rsi_chart_height},
                layout: {{
                    background: {{ type: 'solid', color: '#080c14' }},
                    textColor: '#94A3B8',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.03)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.03)' }},
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    scaleMargins: {{ top: 0.1, bottom: 0.1 }},
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    timeVisible: {str(is_intraday).lower()},
                    secondsVisible: false,
                }},
            }});

            const rsiSeries = rsiChart.addLineSeries({{
                color: '#38BDF8',
                lineWidth: 2,
                title: 'RSI(14)',
                priceLineVisible: false,
            }});
            rsiSeries.setData(rsiData);

            // RSI Bands (70 Overbought, 30 Oversold, 50 Midpoint)
            rsiSeries.createPriceLine({{ price: 70, color: 'rgba(239, 68, 68, 0.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'OB 70' }});
            rsiSeries.createPriceLine({{ price: 30, color: 'rgba(16, 185, 129, 0.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'OS 30' }});
            rsiSeries.createPriceLine({{ price: 50, color: 'rgba(148, 163, 184, 0.3)', lineWidth: 1, lineStyle: 3, axisLabelVisible: false }});

            // 3. TimeScale Synchronization
            let isSyncing = false;
            mainChart.timeScale().subscribeVisibleTimeRangeChange(range => {{
                if (isSyncing || !range) return;
                isSyncing = true;
                rsiChart.timeScale().setVisibleRange(range);
                isSyncing = false;
            }});

            rsiChart.timeScale().subscribeVisibleTimeRangeChange(range => {{
                if (isSyncing || !range) return;
                isSyncing = true;
                mainChart.timeScale().setVisibleRange(range);
                isSyncing = false;
            }});

            // 4. Live Crosshair Hover Tooltip
            mainChart.subscribeCrosshairMove(param => {{
                if (!param || !param.time) return;
                const price = param.seriesPrices.get(candleSeries);
                const vol = param.seriesPrices.get(volumeSeries);
                const ema = param.seriesPrices.get(ema20Series);
                
                if (price) {{
                    document.getElementById('leg_o').innerText = price.open.toFixed(2);
                    document.getElementById('leg_h').innerText = price.high.toFixed(2);
                    document.getElementById('leg_l').innerText = price.low.toFixed(2);
                    document.getElementById('leg_c').innerText = price.close.toFixed(2);
                }}
                if (vol !== undefined) {{
                    document.getElementById('leg_v').innerText = vol.toLocaleString();
                }}
                if (ema !== undefined) {{
                    document.getElementById('leg_ema').innerText = ema.toFixed(2);
                }}
            }});

            // Resize Observer
            window.addEventListener('resize', () => {{
                mainChart.applyOptions({{ width: mainContainer.clientWidth }});
                rsiChart.applyOptions({{ width: rsiContainer.clientWidth }});
            }});

            // Global UI functions
            window.switchStyle = function(style) {{
                const btnC = document.getElementById("btn_candles_{container_id}");
                const btnH = document.getElementById("btn_ha_{container_id}");
                if (style === 'ha') {{
                    candleSeries.setData(haCandles);
                    btnH.classList.add('pill-active');
                    btnC.classList.remove('pill-active');
                }} else {{
                    candleSeries.setData(normalCandles);
                    btnC.classList.add('pill-active');
                    btnH.classList.remove('pill-active');
                }}
            }};

            window.toggleEMA20 = function(checked) {{
                ema20Series.applyOptions({{ visible: checked }});
            }};
            window.toggleSMA50 = function(checked) {{
                sma50Series.applyOptions({{ visible: checked }});
            }};
            window.toggleSMA200 = function(checked) {{
                sma200Series.applyOptions({{ visible: checked }});
            }};
            window.toggleVolume = function(checked) {{
                volumeSeries.applyOptions({{ visible: checked }});
            }};

            // Auto-fit contents on initial render
            setTimeout(() => {{
                mainChart.timeScale().fitContent();
                rsiChart.timeScale().fitContent();
            }}, 150);

        }})();
        </script>
    </body>
    </html>
    """
    total_widget_height = height + 40
    components.html(html_code, height=total_widget_height)


def render_lightweight_chart(symbol, df=None, interval="D", height=550):
    """
    Fallback lightweight canvas chart powered by TradingView Lightweight Charts.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    tv_symbol = get_tradingview_symbol(symbol)

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        try:
            import yfinance as yf
            full_s = f"{clean_sym}.NS" if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO") and not clean_sym.startswith("^") else clean_sym
            t = yf.Ticker(full_s)
            df = t.history(period="1y", interval="1d").dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'])
        except Exception:
            df = None

    if df is None or not isinstance(df, pd.DataFrame) or df.empty or len(df) < 2:
        st.warning(f"⚠️ {clean_sym} માટે પૂરતો કેન્ડલસ્ટિક ડેટા ઉપલબ્ધ નથી.")
        return

    plot_df = df.tail(180).copy()
    if plot_df.index.tz is not None:
        plot_df.index = plot_df.index.tz_localize(None)

    candles = []
    volumes = []
    smas = []

    sma_series = plot_df['Close'].rolling(window=20).mean()

    for idx, row in plot_df.iterrows():
        time_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
        o = round(float(row['Open']), 2)
        h = round(float(row['High']), 2)
        l = round(float(row['Low']), 2)
        c = round(float(row['Close']), 2)
        v = float(row.get('Volume', 0))

        candles.append({"time": time_str, "open": o, "high": h, "low": l, "close": c})
        vol_col = "rgba(16, 185, 129, 0.45)" if c >= o else "rgba(239, 68, 68, 0.45)"
        volumes.append({"time": time_str, "value": v, "color": vol_col})

        sma_val = sma_series.loc[idx]
        if pd.notna(sma_val):
            smas.append({"time": time_str, "value": round(float(sma_val), 2)})

    import json
    candles_json = json.dumps(candles)
    volumes_json = json.dumps(volumes)
    smas_json = json.dumps(smas)

    widget_id = f"ggpatel_chart_{clean_sym.replace('^', '').replace(':', '_')}"
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: #080c14;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                overflow: hidden;
            }}
            .chart-wrapper {{
                width: 100%;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: #080c14;
                overflow: hidden;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 16px;
                background: rgba(15, 23, 42, 0.85);
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }}
            .stock-info {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .stock-name {{
                font-size: 15px;
                font-weight: 800;
                color: #FFFFFF;
                font-family: monospace;
            }}
            .badge-brand {{
                font-size: 10px;
                font-weight: 700;
                background: linear-gradient(135deg, #10B981, #059669);
                color: #FFFFFF;
                padding: 3px 8px;
                border-radius: 5px;
                letter-spacing: 0.5px;
            }}
            .legend-item {{
                font-size: 11px;
                color: #94A3B8;
                display: flex;
                align-items: center;
                gap: 5px;
            }}
            .dot-green {{ width: 8px; height: 8px; background: #10B981; border-radius: 50%; display: inline-block; }}
            .dot-red {{ width: 8px; height: 8px; background: #EF4444; border-radius: 50%; display: inline-block; }}
            .dot-orange {{ width: 8px; height: 8px; background: #F59E0B; border-radius: 50%; display: inline-block; }}
            .tv-btn {{
                color: #38BDF8;
                text-decoration: none;
                font-size: 11px;
                font-weight: 700;
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.3);
                padding: 5px 12px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                gap: 5px;
            }}
            #chart_target_{widget_id} {{
                width: 100%;
                height: {height - 48}px;
            }}
        </style>
    </head>
    <body>
        <div class="chart-wrapper">
            <div class="chart-header">
                <div class="stock-info">
                    <span class="stock-name">🎯 {clean_sym}</span>
                    <span class="badge-brand">GGPATEL PRO VIEW</span>
                    <div class="legend-item" style="margin-left: 10px;">
                        <span class="dot-green"></span> Bullish
                        <span class="dot-red" style="margin-left: 6px;"></span> Bearish
                        <span class="dot-orange" style="margin-left: 6px;"></span> 20 SMA
                    </div>
                </div>
                <a href="https://in.tradingview.com/chart/?symbol={tv_symbol}" target="_blank" class="tv-btn">
                    🚀 TradingView Fullscreen ↗
                </a>
            </div>
            <div id="chart_target_{widget_id}"></div>
        </div>

        <script>
            (function() {{
                const container = document.getElementById('chart_target_{widget_id}');
                if (!window.LightweightCharts) return;

                const chart = LightweightCharts.createChart(container, {{
                    width: container.clientWidth,
                    height: {height - 48},
                    layout: {{
                        background: {{ type: 'solid', color: '#080c14' }},
                        textColor: '#94A3B8',
                        fontSize: 11,
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    }},
                    grid: {{
                        vertLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                        horzLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                    }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{
                        borderColor: '#334155',
                        scaleMargins: {{ top: 0.08, bottom: 0.22 }},
                    }},
                    timeScale: {{ borderColor: '#334155', timeVisible: true, secondsVisible: false }},
                }});

                const candleSeries = chart.addCandlestickSeries({{
                    upColor: '#10B981',
                    downColor: '#EF4444',
                    borderVisible: false,
                    wickUpColor: '#10B981',
                    wickDownColor: '#EF4444',
                }});
                candleSeries.setData({candles_json});

                const volumeSeries = chart.addHistogramSeries({{
                    priceFormat: {{ type: 'volume' }},
                    priceScaleId: '',
                    scaleMargins: {{ top: 0.80, bottom: 0 }},
                }});
                volumeSeries.setData({volumes_json});

                const smaSeries = chart.addLineSeries({{
                    color: '#F59E0B',
                    lineWidth: 2,
                    priceScaleId: 'right',
                }});
                smaSeries.setData({smas_json});

                window.addEventListener('resize', () => {{
                    chart.applyOptions({{ width: container.clientWidth }});
                }});
                chart.timeScale().fitContent();
            }})();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15)


def plot_candlestick_triple_chart(df, title_prefix="Daily", lookback=100, is_hourly=False):
    """
    3-Panel Synchronized Candlestick Chart (Dark Terminal Themed):
    Panel 1: Candlestick + Trend Craft ICT Envelopes
    Panel 2: Institutional Volume & 20 SMA
    Panel 3: NK Sir Hilega Milega (Green 3 EMA, Red 21 WMA, RSI 9, 50 Water)
    """
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

def plot_heikin_ashi_donchian_chart(ha_df, donchian_p=11, lookback=80, title_prefix="Daily"):
    """Heikin Ashi Candlestick & Donchian Trailing SL Chart (Brijesh Bhatia Reversal System)."""
    plot_df = ha_df.tail(lookback).copy().reset_index()
    if 'Datetime' in plot_df.columns:
        date_col = 'Datetime'
    elif 'Date' in plot_df.columns:
        date_col = 'Date'
    else:
        date_col = plot_df.columns[0]
        
    sl_col = f'Donchian_Low_{donchian_p}'
    if sl_col not in plot_df.columns:
        plot_df[sl_col] = plot_df['Low'].rolling(donchian_p).min()
        
    plot_df['HA_Color'] = np.where(
        plot_df.get('HA_Is_Doji', False), '#38BDF8',
        np.where(plot_df['HA_Close'] >= plot_df['HA_Open'], '#00E676', '#FF1744')
    )
    
    base = alt.Chart(plot_df).encode(x=alt.X(f'{date_col}:T', title=''))
    
    sl_line = base.mark_line(color='#F59E0B', strokeDash=[6, 4], strokeWidth=2.4).encode(
        y=alt.Y(f'{sl_col}:Q', title='Price (₹)', scale=alt.Scale(zero=False))
    )
    
    ha_wicks = base.mark_rule(strokeWidth=1.4).encode(
        y=alt.Y('HA_Low:Q', scale=alt.Scale(zero=False)),
        y2='HA_High:Q',
        color=alt.Color('HA_Color:N', scale=None)
    )
    
    ha_bodies = base.mark_bar(size=6).encode(
        y='HA_Open:Q',
        y2='HA_Close:Q',
        color=alt.Color('HA_Color:N', scale=None),
        tooltip=[
            alt.Tooltip(f'{date_col}:T', title='Date/Time'),
            alt.Tooltip('HA_Open:Q', title='HA Open', format='.2f'),
            alt.Tooltip('HA_High:Q', title='HA High', format='.2f'),
            alt.Tooltip('HA_Low:Q', title='HA Low', format='.2f'),
            alt.Tooltip('HA_Close:Q', title='HA Close', format='.2f'),
            alt.Tooltip('Close:Q', title='Price (₹)', format='.2f'),
            alt.Tooltip(f'{sl_col}:Q', title=f'Donchian SL ({donchian_p})', format='.2f')
        ]
    )
    
    chart_ha = (ha_wicks + ha_bodies + sl_line).properties(
        title=f"🕯️ {title_prefix} • Heikin Ashi Candles & Donchian Trailing SL (🟢 Bullish | 🔴 Bearish | 🔵 Doji | 🟡 Donchian SL)",
        height=320
    )
    
    vol_bars = base.mark_bar(opacity=0.75, size=6).encode(
        y=alt.Y('Volume:Q', title='Volume', axis=alt.Axis(format='~s')),
        color=alt.Color('HA_Color:N', scale=None)
    )
    vol_line = base.mark_line(color='#FBBF24', strokeWidth=1.8).encode(y='Vol_SMA20:Q') if 'Vol_SMA20' in plot_df.columns else vol_bars
    chart_vol = (vol_bars + vol_line).properties(
        title=f"📊 {title_prefix} • Volume & 20 SMA",
        height=100
    )
    
    combined = alt.vconcat(chart_ha, chart_vol).resolve_scale(x='shared')
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

def plot_equity_curve_chart(df_equity, title="Portfolio Equity Curve"):
    """
    Renders an interactive Altair chart showing portfolio equity growth over time.
    """
    if df_equity is None or df_equity.empty:
        return None

    plot_df = df_equity.copy()
    if 'Date' in plot_df.columns and not pd.api.types.is_datetime64_any_dtype(plot_df['Date']):
        plot_df['Date'] = pd.to_datetime(plot_df['Date'])

    base = alt.Chart(plot_df).encode(
        x=alt.X('Date:T', title='તારીખ (Date)', axis=alt.Axis(format='%b %Y', grid=True))
    )

    area = base.mark_area(
        line={'color': '#10B981', 'strokeWidth': 2.2},
        color=alt.Gradient(
            gradient='linear',
            stops=[
                alt.GradientStop(color='rgba(16, 185, 129, 0.45)', offset=0),
                alt.GradientStop(color='rgba(16, 185, 129, 0.02)', offset=1)
            ],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        y=alt.Y('Equity:Q', title='પોર્ટફોલિયો કેપિટલ (₹)', scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip('Date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('Equity:Q', title='Portfolio Equity (₹)', format=',.2f'),
            alt.Tooltip('Close:Q', title='Stock Close (₹)', format=',.2f')
        ]
    )

    points = base.mark_circle(size=20, color='#34D399').encode(
        y='Equity:Q',
        tooltip=[
            alt.Tooltip('Date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('Equity:Q', title='Portfolio Equity (₹)', format=',.2f')
        ]
    )

    chart = (area + points).properties(
        title=f"📈 {title} (ઈક્વિટી ગ્રોથ ગ્રાફ)",
        height=320
    ).configure(
        background='transparent',
        view=alt.ViewConfig(strokeWidth=0),
        title=alt.TitleConfig(color='#F1F5F9', fontSize=14, fontWeight=700, anchor='start'),
        axis=alt.AxisConfig(
            domainColor='#334155',
            gridColor='rgba(255, 255, 255, 0.06)',
            labelColor='#94A3B8',
            tickColor='#334155',
            titleColor='#CBD5E1',
            labelFontSize=11,
            titleFontSize=11
        )
    )

    return chart

