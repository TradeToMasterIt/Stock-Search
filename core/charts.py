"""
TradingView & Institutional Charting Module for Patel Trading Bot / Confluence Pro
Provides both live TradingView Technical Analysis widgets and custom synchronized Altair charts.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt

def get_tradingview_symbol(symbol):
    """Converts local ticker symbol to TradingView NSE symbol."""
    if not symbol:
        return "NSE:NIFTY"
    clean = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    if clean in ["^NSEI", "NIFTY", "NIFTY50", "NIFTY 50"]:
        return "NSE:NIFTY"
    elif clean in ["^NSEBANK", "BANKNIFTY", "BANK NIFTY"]:
        return "NSE:BANKNIFTY"
    elif clean in ["FINNIFTY", "NIFTY_FIN_SERVICE"]:
        return "NSE:FINNIFTY"
    return f"NSE:{clean}"

def render_tradingview_widget(symbol, df=None, interval="D", height=550):
    """
    Renders high-performance interactive GGPATEL VIEW Chart powered by TradingView Lightweight Charts.
    Completely eliminates the annoying 'This symbol is only available on TradingView' notification modal
    by feeding actual candle and volume data directly to TradingView's open-source canvas engine.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    tv_symbol = get_tradingview_symbol(symbol)

    # If df not provided, fetch from yfinance
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

    # Prepare data for TradingView Lightweight Charts
    plot_df = df.tail(180).copy()
    if plot_df.index.tz is not None:
        plot_df.index = plot_df.index.tz_localize(None)

    candles = []
    volumes = []
    smas = []

    # Calculate 20 SMA if not present
    sma_series = plot_df['Close'].rolling(window=20).mean()

    for idx, row in plot_df.iterrows():
        if hasattr(idx, 'strftime'):
            time_str = idx.strftime('%Y-%m-%d')
        else:
            time_str = str(idx)[:10]

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
                transition: all 0.2s;
            }}
            .tv-btn:hover {{
                background: rgba(56, 189, 248, 0.25);
                color: #FFFFFF;
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
                if (!window.LightweightCharts) {{
                    container.innerHTML = '<div style="padding: 20px; color: #94A3B8; text-align: center;">ચાર્ટ લોડ થઈ રહ્યો છે...</div>';
                    return;
                }}

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
                    crosshair: {{
                        mode: LightweightCharts.CrosshairMode.Normal,
                    }},
                    rightPriceScale: {{
                        borderColor: '#334155',
                        scaleMargins: {{
                            top: 0.08,
                            bottom: 0.22,
                        }},
                    }},
                    timeScale: {{
                        borderColor: '#334155',
                        timeVisible: true,
                        secondsVisible: false,
                    }},
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
                    scaleMargins: {{
                        top: 0.80,
                        bottom: 0,
                    }},
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

