import requests
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_ist_now

def send_telegram_alert(msg):
    """
    Sends HTML-formatted alert to Telegram chat.
    Safe against empty bot token or chat ID.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram Alert Skipped] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in .env")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"Error sending telegram alert: {e}")
        return False

# -------------------------------------------------------------
# Alert Message Formatters (Gujarati HTML Format)
# -------------------------------------------------------------
def format_r3_radar_alert(res):
    s_name = res['symbol']
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    headline = f"⚡ <b>R3 {s_name.upper()} WEEKLY OPTION ROCKET!</b> ⚡" if is_idx else "⚡ <b>R3 OPTION ROCKET BREAKOUT!</b> ⚡"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    opt_strike_val = res.get('otm_call_strike', res.get('ce_strike', ''))
    strike_str = f"₹{int(opt_strike_val)} CE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} CE"
    contract_lbl = res.get('opt_contract_name', f"{strike_str}")
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{res['opt_fyers_symbol']}</code>\n" if res.get('opt_fyers_symbol') else ""
    rsi_15m_val = res.get('rsi_15m')
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    rsi_txt = (
        f"• <b>15m RSI Confluence:</b> <b>{rsi_15m_val:.1f}</b> (Golden Sweet Spot 58-74 ✅ - નો ફેકઆઉટ)\n"
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    ) if rsi_15m_val else f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    return (
        f"{headline}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"🚀 <b>સેટઅપ:</b> Strong Morning Move + Breakout above Daily R1/R2\n"
        f"{rsi_txt}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>R3 Option Strategy (Option Leads, Future Follows):</b>\n"
        f"• <b>વોચલિસ્ટ કોલ:</b> <b>{contract_lbl}</b> (Strike: {strike_str})\n"
        f"{fyers_lbl}"
        f"• <b>સુવર્ણ નિયમ (Golden Rule):</b> જ્યારે આ OTM CE તેના પોતાના <b>Daily R3</b> લેવલને ક્રોસ કરે ત્યારે જ બાય એન્ટ્રી કરવી!\n"
        f"• <b>સ્ટોપલોસ:</b> ઓપ્શનની 5m/15m બ્રેકઆઉટ કેન્ડલનો Low\n"
        f"• <b>ટાર્ગેટ:</b> 100% થી 200%+ (ડબલ / મલ્ટિબેગર કેપિટલ ગેઇન)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Spot Pivots:</b> P: ₹{res['pivot_p']:.1f} | R1: ₹{res['r1']:.1f} | R2: ₹{res['r2']:.1f} | R3: ₹{res['r3']:.1f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_100_confirmed_buy_alert(res):
    s_name = res['symbol']
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    is_gb = res.get('is_gamma_blast', False)
    if is_gb:
        headline = f"⚡🔥 <b>{s_name.upper()} 0DTE GAMMA BLAST ALERT! (HERO-ZERO ૧૦૦% કન્ફર્મ)</b> 🔥⚡"
    elif is_idx:
        headline = f"🚀 <b>૧૦૦% કન્ફર્મ {s_name.upper()} બાય એલર્ટ! (100% CONFIRMED BUY)</b> 🚀"
    else:
        headline = "🚀 <b>૧૦૦% કન્ફર્મ બાય એલર્ટ! (100% CONFIRMED BUY)</b> 🚀"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res.get('vol_ratio', 1.0) >= 1.2 else ""
    opt_strike_val = res.get('otm_call_strike', res.get('ce_strike', ''))
    strike_str = f"₹{int(opt_strike_val)} CE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} CE"
    contract_lbl = res.get('opt_contract_name', f"{strike_str}")
    opt_ltp_txt = f" (LTP: ₹{res['opt_ltp']:.2f})" if res.get('opt_ltp') else ""
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{res['opt_fyers_symbol']}</code>\n" if res.get('opt_fyers_symbol') else ""
    opt_r3_txt = f"• <b>Option R3:</b> ₹{res['opt_r3']:.2f} (ક્રોસ થયેલ ✅)\n" if res.get('opt_r3') else ""
    rsi_15m_val = res.get('rsi_15m', 62.0)
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    asset_action = "Index / Future Buy" if is_idx else "Equity / Future Buy"
    target_gain_txt = "૧૫૦% થી ૪૦૦%+ (ઝીરો-ટુ-હીરો સુપર જેકપોટ)" if is_gb else "૧૦૦% થી ૨૦૦%+ (ડબલ / મલ્ટિબેગર નફો)"
    rsi_badge = (
        f"• <b>15m RSI Confluence:</b> <b>{rsi_15m_val:.1f}</b> (Golden Sweet Spot 58-74 ✅ - મજબૂત તાજી તેજી)\n"
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    )
    return (
        f"{headline}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"🎯 <b>સેટઅપ:</b> Sniper Buy + OTM R3 Rocket + 15m RSI કન્ફર્મ!\n"
        f"⚡ <b>Hilega-Milega 1H:</b> Green &gt; Red (પાણી 50 ની ઉપર - ૧૦૦% ખરીદી પાકી)\n"
        f"{rsi_badge}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>ACTIONABLE TRADE ENTRY (તાત્કાલિક એન્ટ્રી):</b>\n"
        f"• <b>Call Option Buy (CE):</b> <b>{contract_lbl} ખરીદો{opt_ltp_txt}</b>\n"
        f"• <b>{strike_desc}:</b> <b>{strike_str}</b>\n"
        f"{fyers_lbl}"
        f"{opt_r3_txt}"
        f"• <b>{asset_action}:</b> ₹{res['price']:.2f}\n"
        f"• <b>ચુસ્ત સ્ટોપલોસ:</b> ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"• <b>Target 1 (1:1.5):</b> ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"• <b>Target 2 (1:2.5):</b> ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"• <b>ઓપ્શન ટાર્ગેટ:</b> {target_gain_txt}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Spot Pivots:</b> P: ₹{res['pivot_p']:.1f} | R1: ₹{res['r1']:.1f} | R2: ₹{res['r2']:.1f} | R3: ₹{res['r3']:.1f}\n"
        f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_ha_reversal_alert(res):
    s_name = res['symbol']
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    return (
        f"🚀 <b>BRIJESH BHATIA HEIKIN ASHI REVERSAL!</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"📉 <b>સેટઅપ:</b> {res['ha_red_count']} Red Candles ઘટાડા પછી તળિયેથી તાજું Reversal!\n"
        f"🟢 <b>Heikin Ashi:</b> પ્રથમ Flat Bottom Green Candle (No Lower Shadow - શુદ્ધ તેજી)\n"
        f"📈 <b>વીકલી ફિલ્ટર:</b> Weekly Macro Trend Bullish કન્ફર્મ\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Actionable Trade Setup (Pure Trend Following):</b>\n"
        f"• <b>Buy Entry:</b> ₹{res['price']:.2f}\n"
        f"• <b>🛡️ 11-Day Donchian Trailing SL:</b> ₹{res['ha_donchian_sl']:.2f} (-{res['ha_risk_pct']:.1f}%)\n"
        f"• <b>🎯 ટાર્ગેટ:</b> કોઈ ફિક્સ ટાર્ગેટ નથી! (૧:૧૦ થી ૧:૩૦+ Big Wave Ride)\n"
        f"• <b>💡 એક્ઝિટ નિયમ:</b> જ્યાં સુધી Daily Candle Donchian SL નીચે બંધ ન થાય ત્યાં સુધી નફો રાઇડ કરો!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_sniper_short_alert(res):
    s_name = res['symbol']
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    return (
        f"🩸 <b>SNIPER SHORT SELL CONFIRMED!</b> 🩸\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f})\n"
        f"📉 <b>સેટઅપ:</b> Daily Avalanche + 1H Relief Bounce Rejection\n"
        f"⚡ <b>Hilega-Milega:</b> Green &lt; Red (પાણી 50 ની નીચે)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Trade Setup (Bearish Short):</b>\n"
        f"• Entry (Short): ₹{res['price']:.2f}\n"
        f"• Stop Loss: ₹{res['stop_loss']:.2f} (+{res['risk_pct']:.1f}%)\n"
        f"• Target 1 (1:1.5): ₹{res['t1']:.2f} (-{res['t1_pct']:.1f}%)\n"
        f"• Target 2 (1:2.5): ₹{res['t2']:.2f} (-{res['t2_pct']:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Options Action:</b>\n"
        f"• Put Buyers: ₹{res['pe_strike']} PE બાય કરો\n"
        f"• Option Sellers: &gt; ₹{res['ce_strike']:.0f} CE સેલ કરો (સેફ OTM)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_sniper_buy_alert(res):
    s_name = res['symbol']
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res.get('vol_ratio', 1.0) >= 1.5 else ""
    opt_strike_val = res.get('otm_call_strike', res.get('ce_strike', ''))
    strike_str = f"₹{int(opt_strike_val)} CE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} CE"
    contract_lbl = res.get('opt_contract_name', f"{strike_str}")
    opt_ltp_txt = f" (LTP: ₹{res['opt_ltp']:.2f})" if res.get('opt_ltp') else ""
    opt_r3_txt = f"• <b>Option R3 લેવલ:</b> ₹{res['opt_r3']:.2f}\n" if res.get('opt_r3') else ""
    opt_status = " (✅ R3 ક્રોસ થયેલ - રોકેટ બ્રેકઆઉટ!)" if res.get('is_option_r3_crossed') else " (⚠️ R3 ક્રોસ થતાં જ એન્ટ્રી)"
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{res['opt_fyers_symbol']}</code>\n" if res.get('opt_fyers_symbol') else ""
    rsi_15m_val = res.get('rsi_15m')
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    asset_action = "Index / Future Buy" if is_idx else "Equity / Future Buy"
    rsi_txt = (
        f"• <b>15m RSI:</b> <b>{rsi_15m_val:.1f}</b> (Golden Sweet Spot 58-74 ✅)\n"
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    ) if rsi_15m_val else f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"

    return (
        f"🎯 <b>SNIPER DIP BUY CONFIRMED!</b> 🎯\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{res['price']:.2f})\n"
        f"📈 <b>સેટઅપ:</b> Daily Rocket + 1H Pullback Reversal\n"
        f"⚡ <b>Hilega-Milega:</b> Green &gt; Red (પાણી 50 ની ઉપર)\n"
        f"{rsi_txt}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Trade Setup (Bullish):</b>\n"
        f"• Entry (Buy): ₹{res['price']:.2f}\n"
        f"• Stop Loss: ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"• Target 1 (1:1.5): ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"• Target 2 (1:2.5): ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Options Action (સુવર્ણ નિયમ):</b>\n"
        f"• <b>Call Option Buy (CE):</b> <b>{contract_lbl}{opt_ltp_txt}</b>{opt_status}\n"
        f"• <b>{strike_desc}:</b> <b>{strike_str}</b>\n"
        f"{fyers_lbl}"
        f"{opt_r3_txt}"
        f"• <b>ઓપ્શન ટાર્ગેટ:</b> ૧૦૦% થી ૨૦૦%+ (મલ્ટિબેગર નફો)\n"
        f"• <b>Option Sellers:</b> &lt; ₹{res.get('pe_strike', res['price'] * 0.98):.0f} PE સેલ કરો (સેફ OTM)\n"
        f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_general_buy_alert(res):
    s_name = res['symbol']
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res['vol_ratio'] >= 1.5 else ""
    return (
        f"🚨 <b>{res['signal']} ALERT!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>સ્ટોક:</b> {s_name}\n"
        f"💰 <b>ભાવ:</b> ₹{res['price']:.2f} ({res['change']:+.2f}%)\n"
        f"🎯 <b>Target 1:</b> ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"🚀 <b>Target 2:</b> ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"🛡️ <b>Stop Loss:</b> ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"📊 <b>1-Hour Volume:</b> {res['vol_ratio']:.1f}x {vol_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Options Strategy:</b>\n"
        f"• Call Buyers: ₹{res['ce_strike']} CE બાય કરો\n"
        f"• Option Sellers: &lt; ₹{res['pe_strike']:.0f} PE સેલ કરો (સેફ OTM)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )


def format_exit_alert(res_or_trade, reason: str = "Exit Condition Met"):
    """Formats trade exit / stop-loss alert for Telegram."""
    sym = res_or_trade.get('symbol', 'N/A')
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    cmp_price = res_or_trade.get('price', res_or_trade.get('current_price', 0.0))
    entry = res_or_trade.get('entry_price', 0.0)
    return (
        f"🚨 <b>TRADE EXIT ALERT: {sym}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>કારણ:</b> {reason}\n"
        f"• <b>Entry Price:</b> ₹{entry:,.2f}\n"
        f"• <b>Current/Exit Price:</b> ₹{cmp_price:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )
