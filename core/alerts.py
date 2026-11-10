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

def format_rsi_confluence_badge(tf_lbl: str, rsi_val: float, is_bearish: bool = False) -> str:
    """Formats dynamic RSI badge showing Golden Sweet Spot or Overbought Warning based on actual RSI value."""
    if not rsi_val:
        return ""
    rsi_num = float(rsi_val)
    if not is_bearish:
        if 55.0 <= rsi_num <= 68.0:
            badge = f"<b>{rsi_num:.1f}</b> (Golden Sweet Spot 55-68 ✅ - પ્રારંભિક સ્નાઈપર એન્ટ્રી)"
        elif 68.0 < rsi_num <= 74.0:
            badge = f"<b>{rsi_num:.1f}</b> (બુલિશ મોમેન્ટમ 58-74 ✅ - સ્નાઈપર વેગ)"
        elif rsi_num > 74.0:
            badge = f"<b>{rsi_num:.1f}</b> (⚠️ Overbought RSI > 74 - પુલબેક સાવચેતી / 20 SMA ની રાહ જુઓ!)"
        elif 50.0 <= rsi_num < 55.0:
            badge = f"<b>{rsi_num:.1f}</b> (બુલિશ મોમેન્ટમ બિલ્ડઅપ ↗️)"
        else:
            badge = f"<b>{rsi_num:.1f}</b> (નબળો મોમેન્ટમ)"
    else:
        if 26.0 <= rsi_num <= 42.0:
            badge = f"<b>{rsi_num:.1f}</b> (Bearish Sweet Spot 26-42 ✅ - પેનિક બ્રેકડાઉન)"
        elif rsi_num < 26.0:
            badge = f"<b>{rsi_num:.1f}</b> (⚠️ Oversold RSI < 26 - બાઉન્સ સાવચેતી!)"
        elif 42.0 < rsi_num <= 50.0:
            badge = f"<b>{rsi_num:.1f}</b> (મંદી મોમેન્ટમ બિલ્ડઅપ ↘️)"
        else:
            badge = f"<b>{rsi_num:.1f}</b> (બુલિશ પ્રેશર)"
    return f"• <b>⚡ {tf_lbl} RSI Confluence:</b> {badge}\n"


def format_volume_ratio_badge(tf_lbl: str, vol_val: float) -> str:
    """Formats dynamic volume ratio with clear institutional label."""
    if not vol_val:
        return ""
    vol_num = float(vol_val)
    comment = "સંસ્થાકીય વોલ્યુમ કન્ફર્મ 🔥" if vol_num >= 1.2 else f"વોલ્યુમ: {vol_num:.1f}x"
    return f"• <b>📊 {tf_lbl} Volume Ratio:</b> <b>{vol_num:.1f}x</b> ({comment})\n"


def format_stage1_pre_breakout_alert(res):
    """
    Stage-1 Early Pre-Breakout Squeeze Alert (5 to 8 Minutes Early Notice).
    Triggers when stock breaks out of 3m Bollinger Squeeze with 3m RSI in 55-68 sweet spot,
    allowing traders to buy the Call Option at the cheaper base price (e.g. ₹4.50 instead of ₹5.44).
    """
    s_name = res.get('symbol', '')
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    
    spot_p = float(res.get('price', 0.0))
    spot_chg = float(res.get('change', 0.0))
    
    opt_strike_val = res.get('otm_call_strike', res.get('ce_strike', ''))
    strike_str = f"₹{int(opt_strike_val)} CE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} CE"
    contract_lbl = res.get('opt_contract_name', f"{strike_str}")
    fyers_code = res.get('opt_fyers_symbol', '')
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{fyers_code}</code>\n" if fyers_code else ""
    opt_p = float(res.get('opt_ltp', 0.0))
    opt_r3 = float(res.get('opt_r3', 0.0))
    
    tf_lbl = res.get('timeframe_used', '3m')
    rsi_val = float(res.get('rsi_3m', res.get('rsi_5m', 62.0)))
    vol_val = float(res.get('vol_5m', res.get('vol_ratio', 1.2)))
    
    # 50% Starter Entry targets
    sl_calc = round(opt_p * 0.80, 2) if opt_p > 0 else 0.0
    t1_calc = round(opt_p * 1.30, 2) if opt_p > 0 else 0.0
    t2_calc = round(opt_p * 1.60, 2) if opt_p > 0 else 0.0
    
    rsi_line = format_rsi_confluence_badge(tf_lbl, rsi_val, is_bearish=False)
    vol_line = format_volume_ratio_badge(tf_lbl, vol_val)
    
    return (
        f"⚡🎯 <b>STAGE-1 PRE-BREAKOUT SQUEEZE RADAR! (૫ થી ૮ મિનિટ વહેલું એલર્ટ)</b> 🎯⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{spot_p:.2f}, {spot_chg:+.2f}%)\n"
        f"📈 <b>સેટઅપ:</b> 3m Bollinger Squeeze Breakout + Fresh Trend Blast\n"
        f"{rsi_line}"
        f"{vol_line}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>ACTIONABLE EARLY ENTRY (સસ્તા ભાવે એન્ટ્રી):</b>\n"
        f"• <b>Call Option Strike:</b> <b>{contract_lbl}</b>\n"
        f"• <b>વર્તમાન સસ્તો ઓપ્શન ભાવ:</b> <b>₹{opt_p:.2f}</b>\n"
        f"{fyers_lbl}"
        f"• <b>Option R3 લેવલ:</b> ₹{opt_r3:.2f} (આગળનું મોટું બ્રેકઆઉટ લેવલ)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>વિશ્વ-કક્ષાની સ્માર્ટ રણનીતિ (World-Class Strategy):</b>\n"
        f"• <b>૫૦% ક્વોન્ટિટીથી Starter Entry:</b> ₹{opt_p:.2f} પર અડધી કોન્ટીટી લો (ચુસ્ત SL: ₹{sl_calc:.2f}).\n"
        f"• <b>બાકીની ૫૦% એડ કરો:</b> જ્યારે સ્ટોક R3 ક્રોસ કરીને રોકેટ કન્ફર્મ કરે ત્યારે બાકીની કોન્ટીટી ઉમેરો!\n"
        f"• <b>ફાયદો:</b> મોંઘી એન્ટ્રીથી બચી જશો અને એવરેજ પ્રાઈસ એકદમ સસ્તી રહેશે!\n"
        f"• <b>Target 1:</b> ₹{t1_calc:.2f} (+30%) | <b>Target 2:</b> ₹{t2_calc:.2f} (+60%+)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_pre_r3_radar_alert(res):
    """Stage 1: Pre-R3 Advance Radar Alert (2-3 Minutes advance notice before blast)."""
    s_name = res.get('symbol', '')
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    opt_strike_val = res.get('otm_call_strike', res.get('ce_strike', res.get('strike', '')))
    strike_str = f"₹{int(opt_strike_val)} CE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} CE"
    contract_lbl = res.get('opt_contract_name', res.get('contract_name', f"{strike_str}"))
    fyers_code = res.get('opt_fyers_symbol', res.get('fyers_symbol', ''))
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{fyers_code}</code>\n" if fyers_code else ""
    opt_p = float(res.get('opt_ltp', 0.0))
    opt_r3 = float(res.get('opt_r3', 0.0))
    tf_lbl = res.get('timeframe_used', '3m')
    vol_val = res.get('vol_5m', res.get('vol_ratio', 1.0))
    diff_val = max(0.05, opt_r3 - opt_p)
    spot_p = float(res.get('price', res.get('spot_price', 0.0)))
    spot_chg = float(res.get('change', res.get('spot_change', 0.0)))
    return (
        f"⚠️ <b>PRE-R3 ADVANCE SNIPER RADAR! (સજ્જ રહો - ૨ મિનિટ વહેલું એલર્ટ)</b> ⚠️\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{spot_p:.2f}, {spot_chg:+.2f}%)\n"
        f"🎯 <b>ઓપ્શન કોન્ટ્રાક્ટ:</b> <b>{contract_lbl}</b>\n"
        f"{fyers_lbl}"
        f"• <b>વર્તમાન ઓપ્શન ભાવ:</b> <b>₹{opt_p:.2f}</b>\n"
        f"• <b>લક્ષ્ય R3 બ્રેકઆઉટ લેવલ:</b> <b>₹{opt_r3:.2f}</b> (માત્ર ₹{diff_val:.2f} દૂર!)\n"
        f"• <b>📊 {tf_lbl} વોલ્યુમ સર્જ:</b> <b>{vol_val:.1f}x 🔥</b> (સંસ્થાકીય ખરીદી શરૂ)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>એક્શન પ્લાન (Action Plan):</b>\n"
        f"• ડિમેટ એકાઉન્ટ (Zerodha/Fyers) માં આ સ્ટ્રાઈક વોચલિસ્ટમાં એડ કરીને તૈયાર રાખો.\n"
        f"• અથવા ₹{opt_p:.2f} પર સસ્તા ભાવે ૫૦% એન્ટ્રી લઈ શકાય (SL: {tf_lbl} કેન્ડલ લો).\n"
        f"• જેવો ₹{opt_r3:.2f} ક્રોસ થશે એટલે રોકેટ બ્લાસ્ટ કન્ફર્મ થશે!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_pre_put_r3_radar_alert(res):
    """Stage 1: Pre-Put R3 Advance Radar Alert (2-3 Minutes advance notice before breakdown)."""
    s_name = res.get('symbol', '')
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    opt_strike_val = res.get('otm_put_strike', res.get('pe_strike', res.get('strike', '')))
    strike_str = f"₹{int(opt_strike_val)} PE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} PE"
    contract_lbl = res.get('opt_put_contract_name', res.get('contract_name', f"{strike_str}"))
    fyers_code = res.get('opt_put_fyers_symbol', res.get('fyers_symbol', ''))
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{fyers_code}</code>\n" if fyers_code else ""
    opt_p = float(res.get('opt_put_ltp', res.get('opt_ltp', 0.0)))
    opt_r3 = float(res.get('opt_put_r3', res.get('opt_r3', 0.0)))
    tf_lbl = res.get('timeframe_used', '3m')
    vol_val = res.get('vol_5m', res.get('vol_ratio', 1.0))
    diff_val = max(0.05, opt_r3 - opt_p)
    spot_p = float(res.get('price', res.get('spot_price', 0.0)))
    spot_chg = float(res.get('change', res.get('spot_change', 0.0)))
    return (
        f"⚠️ <b>PRE-PUT R3 ADVANCE RADAR! (મંદી સજ્જ રહો - ૨ મિનિટ વહેલું એલર્ટ)</b> ⚠️\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{spot_p:.2f}, {spot_chg:+.2f}%)\n"
        f"🎯 <b>પુટ કોન્ટ્રાક્ટ:</b> <b>{contract_lbl}</b>\n"
        f"{fyers_lbl}"
        f"• <b>વર્તમાન પુટ ભાવ:</b> <b>₹{opt_p:.2f}</b>\n"
        f"• <b>લક્ષ્ય Put R3 બ્રેકડાઉન:</b> <b>₹{opt_r3:.2f}</b> (માત્ર ₹{diff_val:.2f} દૂર!)\n"
        f"• <b>📊 {tf_lbl} વોલ્યુમ:</b> <b>{vol_val:.1f}x 🔥</b> (સંસ્થાકીય સેલિંગ શરૂ)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>એક્શન પ્લાન (Action Plan):</b>\n"
        f"• ડિમેટ એકાઉન્ટમાં આ પુટ સ્ટ્રાઈક વોચલિસ્ટમાં એડ કરીને તૈયાર રાખો.\n"
        f"• અથવા ₹{opt_p:.2f} પર ૫૦% પુટ એન્ટ્રી લઈ શકાય.\n"
        f"• જેવો ₹{opt_r3:.2f} ક્રોસ થશે એટલે પેનિક ફોલ આવશે!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

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
    tf_lbl = res.get('timeframe_used', '5m')
    rsi_val = res.get('rsi_5m', res.get('rsi_15m'))
    vol_val = res.get('vol_5m', res.get('vol_15m', res.get('vol_ratio', 1.0)))
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    rsi_txt = (
        format_rsi_confluence_badge(tf_lbl, rsi_val, is_bearish=False) +
        format_volume_ratio_badge(tf_lbl, vol_val) +
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    ) if rsi_val else f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
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
    tf_lbl = res.get('timeframe_used', '5m')
    rsi_val = res.get('rsi_5m', res.get('rsi_15m', 62.0))
    vol_val = res.get('vol_5m', res.get('vol_15m', res.get('vol_ratio', 1.0)))
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    asset_action = "Index / Future Buy" if is_idx else "Equity / Future Buy"
    target_gain_txt = "૧૫૦% થી ૪૦૦%+ (ઝીરો-ટુ-હીરો સુપર જેકપોટ)" if is_gb else "૧૦૦% થી ૨૦૦%+ (ડબલ / મલ્ટિબેગર નફો)"
    opt_p = float(res.get('opt_ltp', 0.0))
    opt_sl_calc = round(opt_p * 0.75, 2)
    opt_t1_calc = round(opt_p * 1.35, 2)
    opt_t2_calc = round(opt_p * 1.70, 2)
    opt_multi_calc = round(opt_p * 2.0, 2)
    rsi_badge = (
        format_rsi_confluence_badge(tf_lbl, rsi_val, is_bearish=False) +
        format_volume_ratio_badge(tf_lbl, vol_val) +
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    )
    return (
        f"{headline}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"🎯 <b>સેટઅપ:</b> Sniper Buy + OTM R3 Rocket + 5m/15m સ્નાઈપર કન્ફર્મ!\n"
        f"⚡ <b>Hilega-Milega 1H:</b> Green &gt; Red (પાણી 50 ની ઉપર - ૧૦૦% ખરીદી પાકી)\n"
        f"{rsi_badge}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>ACTIONABLE OPTION ENTRY (ઓપ્શન ખરીદો):</b>\n"
        f"• <b>Call Option Buy (CE):</b> <b>{contract_lbl} ખરીદો</b>\n"
        f"• <b>ખરીદ ભાવ (Option LTP):</b> <b>₹{opt_p:.2f}</b>\n"
        f"{fyers_lbl}"
        f"{opt_r3_txt}"
        f"• <b>🛡️ ચુસ્ત ઓપ્શન SL:</b> <b>₹{opt_sl_calc:.2f}</b> (-25%)\n"
        f"• <b>🎯 Option Target 1 (+35%):</b> <b>₹{opt_t1_calc:.2f}</b> (૫૦% નફો બુક & SL to Cost)\n"
        f"• <b>🚀 Option Target 2 (+70%):</b> <b>₹{opt_t2_calc:.2f}</b> (વધુ ૩૦% નફો બુક)\n"
        f"• <b>👑 મલ્ટિબેગર ટાર્ગેટ:</b> <b>₹{opt_multi_calc:.2f}</b> ({target_gain_txt})\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Spot {s_name} Levels (કેશ/ઈન્ડેક્સ સંદર્ભ માટે):</b>\n"
        f"• Spot ભાવ: ₹{res['price']:.2f}\n"
        f"• Spot Stoploss: ₹{res['stop_loss']:.2f} | Spot Target 1: ₹{res['t1']:.2f}\n"
        f"• Spot Pivots: P: ₹{res['pivot_p']:.1f} | R1: ₹{res['r1']:.1f} | R2: ₹{res['r2']:.1f} | R3: ₹{res['r3']:.1f}\n"
        f"• 1-Hour Volume: {res['vol_ratio']:.1f}x {vol_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

def format_100_confirmed_put_alert(res):
    s_name = res['symbol']
    is_idx = res.get('is_index', False)
    inst_lbl = "ઈન્ડેક્સ" if is_idx else "સ્ટોક"
    is_gb = res.get('is_gamma_blast', False)
    if is_gb:
        headline = f"⚡🩸 <b>{s_name.upper()} 0DTE PUT GAMMA BLAST ALERT! (HERO-ZERO ૧૦૦% પુટ કન્ફર્મ)</b> 🩸⚡"
    elif is_idx:
        headline = f"🩸 <b>૧૦૦% કન્ફર્મ {s_name.upper()} પુટ (PE) બાય એલર્ટ! (100% BEARISH PUT BUY)</b> 🩸"
    else:
        headline = "🩸 <b>૧૦૦% કન્ફર્મ પુટ (PE) બાય એલર્ટ! (100% BEARISH BREAKDOWN)</b> 🩸"
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    vol_emoji = "🔥" if res.get('vol_5m', res.get('vol_ratio', 1.0)) >= 1.2 else ""
    opt_strike_val = res.get('otm_put_strike', res.get('pe_strike', ''))
    strike_str = f"₹{int(opt_strike_val)} PE" if (isinstance(opt_strike_val, (int, float)) and float(opt_strike_val) > 0) else f"₹{opt_strike_val} PE"
    contract_lbl = res.get('opt_put_contract_name', f"{strike_str}")
    opt_ltp_txt = f" (LTP: ₹{res['opt_put_ltp']:.2f})" if res.get('opt_put_ltp') else ""
    fyers_lbl = f"• <b>Fyers Symbol:</b> <code>{res['opt_put_fyers_symbol']}</code>\n" if res.get('opt_put_fyers_symbol') else ""
    opt_r3_txt = f"• <b>Put Option R3:</b> ₹{res['opt_put_r3']:.2f} (ક્રોસ થયેલ ✅)\n" if res.get('opt_put_r3') else ""
    tf_lbl = res.get('timeframe_used', '5m')
    rsi_val = res.get('rsi_5m', res.get('rsi_15m', 35.0))
    vol_val = res.get('vol_5m', res.get('vol_15m', res.get('vol_ratio', 1.0)))
    strike_desc = "Weekly OTM Put" if is_idx else "OTM Put Option Strike"
    target_gain_txt = "૧૫૦% થી ૪૦૦%+ (ઝીરો-ટુ-હીરો સુપર જેકપોટ પુટ)" if is_gb else "૧૦૦% થી ૨૦૦%+ (ડબલ / મલ્ટિબેગર નફો)"
    rsi_badge = (
        format_rsi_confluence_badge(tf_lbl, rsi_val, is_bearish=True) +
        format_volume_ratio_badge(tf_lbl, vol_val) +
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    )
    return (
        f"{headline}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{inst_lbl}:</b> {s_name} (LTP: ₹{res['price']:.2f}, {res['change']:+.2f}%)\n"
        f"📉 <b>સેટઅપ:</b> Support S1/S2 Breakdown + Put Option R3 Rocket + 5m પેનિક કન્ફર્મ!\n"
        f"🩸 <b>બ્રેકડાઉન:</b> Daily Support તૂટી ગઈ છે, મંદી વેગ પકડી રહી છે.\n"
        f"{rsi_badge}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>ACTIONABLE TRADE ENTRY (તાત્કાલિક પુટ ખરીદો):</b>\n"
        f"• <b>Put Option Buy (PE):</b> <b>{contract_lbl} ખરીદો{opt_ltp_txt}</b>\n"
        f"• <b>{strike_desc}:</b> <b>{strike_str}</b>\n"
        f"{fyers_lbl}"
        f"{opt_r3_txt}"
        f"• <b>ચુસ્ત પુટ સ્ટોપલોસ:</b> ₹{res.get('opt_put_sl', 0.0):.2f}\n"
        f"• <b>Target 1 (+35%):</b> ₹{res.get('opt_put_t1', 0.0):.2f} (૫૦% નફો બુક & Trail SL to Cost)\n"
        f"• <b>Target 2 (+70%):</b> ₹{res.get('opt_put_t2', 0.0):.2f} (વધુ ૩૦% નફો બુક)\n"
        f"• <b>મલ્ટિબેગર ટાર્ગેટ:</b> {target_gain_txt}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Spot Pivots:</b> P: ₹{res.get('pivot_p', 0):.1f} | S1: ₹{res.get('s1', 0):.1f} | S2: ₹{res.get('s2', 0):.1f} | S3: ₹{res.get('s3', 0):.1f}\n"
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
    tf_lbl = res.get('timeframe_used', '5m')
    rsi_val = res.get('rsi_5m', res.get('rsi_15m'))
    vol_val = res.get('vol_5m', res.get('vol_15m', res.get('vol_ratio', 1.0)))
    strike_desc = "Weekly OTM Strike" if is_idx else "OTM Option Strike"
    asset_action = "Index / Future Buy" if is_idx else "Equity / Future Buy"
    rsi_txt = (
        format_rsi_confluence_badge(tf_lbl, rsi_val, is_bearish=False) +
        format_volume_ratio_badge(tf_lbl, vol_val) +
        f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
    ) if rsi_val else f"• <b>🎯 {strike_desc}:</b> <b>{strike_str}</b> ({contract_lbl})\n"
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

def format_gfs_swing_alert(res):
    """Formats GFS Swing & Positional Multibagger Dip Alert (Grandfather, Father, Son Confluence)."""
    s_name = res['symbol']
    now_str = get_ist_now().strftime('%d %b %Y | %H:%M:%S IST')
    p = float(res['price'])
    rsi_m = float(res.get('rsi_m', 60.0))
    rsi_w = float(res.get('rsi_w', 60.0))
    rsi_d = float(res.get('rsi_d', 42.0))
    c_pat = res.get('candle_pattern', 'HAMMER 🔨')
    bb_m = float(res.get('bb_middle', p))
    div_txt = "\n• 💥 <b>RSI Bullish Divergence:</b> સંસ્થાકીય એક્યુમ્યુલેશન કન્ફર્મ!" if res.get('has_bull_div') else ""
    sl = round(min(res.get('bb_lower', p * 0.95), p * 0.96), 2)
    risk_pct = round(((p - sl) / p) * 100, 1)
    t1 = round(p * 1.08, 2)
    t2 = round(p * 1.15, 2)
    t3 = round(p * 1.25, 2)
    return (
        f"🏔️ <b>GFS SWING MULTIBAGGER DIP BUY! (Grandfather-Father-Son)</b> 🏔️\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>સ્ટોક:</b> {s_name} (Cash / Delivery / Swing)\n"
        f"💰 <b>ખરીદ ભાવ (LTP):</b> ₹{p:.2f} ({res['change']:+.2f}%)\n"
        f"🎯 <b>સેટઅપ:</b> {res.get('gfs_action', 'HIGH-CONFIDENCE GFS ENTRY')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Stop Loss (Swing):</b> ₹{sl:.2f} (-{risk_pct}%)\n"
        f"🎯 <b>Target 1 (શોર્ટ ટર્મ):</b> ₹{t1:.2f} (+8.0%)\n"
        f"🎯 <b>Target 2 (સ્વિંગ ટાર્ગેટ):</b> ₹{t2:.2f} (+15.0%)\n"
        f"🚀 <b>Target 3 (પોઝિશનલ જેકપોટ):</b> ₹{t3:.2f} (+25.0%)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>GFS Multi-Timeframe Matrix:</b>\n"
        f"   • 👴 <b>Grandfather (Monthly RSI):</b> {rsi_m:.1f} (તેજી ✅)\n"
        f"   • 👨 <b>Father (Weekly RSI):</b> {rsi_w:.1f} (તેજી ✅)\n"
        f"   • 👦 <b>Son (Daily RSI Dip):</b> {rsi_d:.1f} (સસ્તો સપોર્ટ ઝોન ✅)\n"
        f"   • 🛡️ <b>Bollinger Support:</b> 20 SMA ₹{bb_m:.1f} નજીક | <b>કેન્ડલ:</b> {c_pat}"
        f"{div_txt}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>ટ્રેડિંગ સલાહ:</b> આ કેશ ડિલિવરી / પોઝિશનલ સ્વિંગ ટ્રેડ છે. ૫૦% કેશમાં અથવા ડીપ In-The-Money (ITM) કોલમાં ૧ થી ૩ અઠવાડિયા માટે હોલ્ડ કરી શકાય.\n"
        f"⏰ <i>{now_str}</i> | 🤖 Patel Trading Bot"
    )

