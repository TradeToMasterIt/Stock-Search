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
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    return (
        f"⚡ <b>R3 OPTION ROCKET BREAKOUT!</b> ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"🚀 <b>સેટઅપ:</b> Strong Morning Move + Breakout above Daily R1/R2\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>R3 Option Strategy (Option Leads, Future Follows):</b>\n"
        f"• <b>વોચલિસ્ટ કોલ:</b> <b>₹{res['otm_call_strike']} CE</b>\n"
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
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res['vol_ratio'] >= 1.2 else ""
    return (
        f"🚀 <b>૧૦૦% કન્ફર્મ બાય એલર્ટ! (100% CONFIRMED BUY)</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"🎯 <b>સેટઅપ:</b> R3 Option Rocket + 1-Hour Bull Cross કન્ફર્મ!\n"
        f"⚡ <b>Hilega-Milega 1H:</b> Green &gt; Red (પાણી 50 ની ઉપર - ૧૦૦% ખરીદી પાકી)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>ACTIONABLE TRADE ENTRY (તાત્કાલિક એન્ટ્રી):</b>\n"
        f"• <b>Call Option Buy (CE):</b> <b>₹{res['otm_call_strike']} CE</b> ખરીદો\n"
        f"• <b>Equity / Future Buy:</b> ₹{res['price']:.2f}\n"
        f"• <b>ચુસ્ત સ્ટોપલોસ:</b> ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"• <b>Target 1 (1:1.5):</b> ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"• <b>Target 2 (1:2.5):</b> ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"• <b>ઓપ્શન ટાર્ગેટ:</b> ૧૦૦% થી ૨૦૦%+ (ડબલ / મલ્ટિબેગર નફો)\n"
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
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res['vol_ratio'] >= 1.5 else ""
    return (
        f"🎯 <b>SNIPER DIP BUY CONFIRMED!</b> 🎯\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (LTP: ₹{res['price']:.2f})\n"
        f"📈 <b>સેટઅપ:</b> Daily Rocket + 1H Pullback Reversal\n"
        f"⚡ <b>Hilega-Milega:</b> Green &gt; Red (પાણી 50 ની ઉપર)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Trade Setup (Bullish):</b>\n"
        f"• Entry (Buy): ₹{res['price']:.2f}\n"
        f"• Stop Loss: ₹{res['stop_loss']:.2f} (-{res['risk_pct']:.1f}%)\n"
        f"• Target 1 (1:1.5): ₹{res['t1']:.2f} (+{res['t1_pct']:.1f}%)\n"
        f"• Target 2 (1:2.5): ₹{res['t2']:.2f} (+{res['t2_pct']:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Options Action:</b>\n"
        f"• Call Buyers: ₹{res['ce_strike']} CE બાય કરો\n"
        f"• Option Sellers: &lt; ₹{res['pe_strike']:.0f} PE સેલ કરો (સેફ OTM)\n"
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
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_exit_alert(res):
    s_name = res['symbol']
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    return (
        f"⚠️ <b>EXIT / BREAKDOWN ALERT!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>સ્ટોક:</b> {s_name}\n"
        f"💰 <b>ભાવ:</b> ₹{res['price']:.2f} ({res['change']:+.2f}%)\n"
        f"🚨 <b>સિગ્નલ:</b> 🔴 STRONG SELL / AVOID\n"
        f"🛑 <b>સલાહ:</b> સ્ટોકમાં મંદીનું દબાણ શરૂ થયું છે. જો તમારી પાસે સ્ટોક હોય તો એક્ઝિટ / પ્રોફિટ બુક કરો. <b>નવી ખરીદી બિલકુલ ટાળવી!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )
