"""
Confluence Pro Institutional Security Gate
Provides PIN protection and dual-channel OTP Reset (Gmail SMTP & Telegram Bot).
Stores user custom PIN persistently in SQLite meta_kv table.
"""

import os
import time
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from core.database import get_db_connection
from core.config import (
    get_config_val,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    get_ist_now
)

# Configuration keys
DEFAULT_FALLBACK_PIN = "4082"

def get_config_pin() -> str:
    """Reads configured master PIN from environment or Streamlit secrets."""
    return get_config_val("APP_ACCESS_PIN", DEFAULT_FALLBACK_PIN)

def get_stored_pin() -> str:
    """Fetches custom PIN from SQLite meta_kv, falling back to config/default."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM meta_kv WHERE key = 'app_pin'")
            row = cursor.fetchone()
            if row and row["value"]:
                return str(row["value"]).strip()
    except Exception as e:
        print(f"[AUTH] Error reading PIN from DB: {e}")
    return get_config_pin()

def set_stored_pin(new_pin: str) -> bool:
    """Persistently updates PIN in SQLite meta_kv table."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO meta_kv (key, value) 
                VALUES ('app_pin', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (str(new_pin).strip(),))
            conn.commit()
            return True
    except Exception as e:
        print(f"[AUTH] Error saving PIN to DB: {e}")
        return False

def send_telegram_otp(otp: str) -> tuple[bool, str]:
    """Sends OTP notification directly to the user's private Telegram bot."""
    bot_token = get_config_val("TELEGRAM_BOT_TOKEN", "")
    chat_id = get_config_val("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return False, "Telegram Bot is not configured in settings."

    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        message_text = (
            f"🔐 <b>CONFLUENCE PRO — SECURITY VERIFICATION</b>\n\n"
            f"Your Terminal PIN Reset Verification Code is:\n"
            f"👉 <code>{otp}</code>\n\n"
            f"⏳ <b>Validity:</b> 10 Minutes\n"
            f"📍 <b>Time:</b> {get_ist_now().strftime('%H:%M:%S IST')}\n\n"
            f"<i>If you did not request a PIN reset, please ignore this message.</i>"
        )
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return True, "Telegram alert sent successfully."
        return False, f"Telegram error: {data.get('description')}"
    except Exception as e:
        return False, f"Telegram dispatch failed: {str(e)}"

def send_gmail_otp(otp: str, recipient_email: str) -> tuple[bool, str]:
    """Sends OTP email via Gmail SMTP using Google App Password."""
    smtp_user = get_config_val("GMAIL_USER", "")
    smtp_pass = get_config_val("GMAIL_APP_PASSWORD", "")

    if not smtp_user or not smtp_pass:
        return False, "GMAIL_USER or GMAIL_APP_PASSWORD not set in secrets."

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Confluence Pro Security <{smtp_user}>"
        msg["To"] = recipient_email
        msg["Subject"] = f"🔐 Your Confluence Pro PIN Reset Code: {otp}"

        html_content = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0f19; color: #f3f4f6; padding: 24px;">
            <div style="max-width: 480px; margin: 0 auto; background: #131c2e; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 16px; padding: 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #38bdf8; margin: 0; font-size: 22px; font-weight: 800;">🎯 CONFLUENCE PRO</h2>
                    <p style="color: #94a3b8; font-size: 13px; margin: 4px 0 0 0;">Institutional Trading Terminal Gateway</p>
                </div>
                
                <p style="font-size: 14px; color: #e2e8f0; line-height: 1.5;">A request was made to reset the access PIN for your trading terminal.</p>
                
                <div style="background: rgba(56, 189, 248, 0.08); border: 2px dashed #38bdf8; border-radius: 12px; padding: 18px; text-align: center; margin: 22px 0;">
                    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 6px;">Your 6-Digit Verification OTP</div>
                    <div style="font-size: 34px; font-weight: 800; font-family: 'Courier New', monospace; letter-spacing: 8px; color: #ffffff;">{otp}</div>
                </div>
                
                <p style="font-size: 12px; color: #fbbf24; margin: 0;">⏳ This code is valid for 10 minutes. Do not share it with anyone.</p>
                <div style="border-top: 1px solid rgba(255,255,255,0.08); margin-top: 24px; padding-top: 14px; font-size: 11px; color: #64748b; text-align: center;">
                    Patel Trading Bot • Institutional Confluence Terminal
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=12) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Email delivered successfully via Gmail SMTP."
    except Exception as e:
        return False, f"Gmail SMTP error: {str(e)}"

def dispatch_reset_otp(recipient_email: str) -> tuple[bool, str]:
    """
    Generates a fresh 6-digit OTP and dispatches it via both Gmail (if configured)
    and Telegram bot (guaranteed delivery).
    """
    otp = f"{random.randint(100000, 999999)}"
    st.session_state["reset_otp_code"] = otp
    st.session_state["reset_otp_expiry"] = time.time() + 600 # 10 minutes

    channels_success = []
    errors = []

    # 1. Dispatch via Telegram
    tg_ok, tg_msg = send_telegram_otp(otp)
    if tg_ok:
        channels_success.append("Telegram (@patel_stock_bot)")
    else:
        errors.append(f"Telegram: {tg_msg}")

    # 2. Dispatch via Gmail SMTP
    gm_ok, gm_msg = send_gmail_otp(otp, recipient_email)
    if gm_ok:
        channels_success.append(f"Gmail ({recipient_email})")
    else:
        errors.append(f"Gmail: {gm_msg}")

    if channels_success:
        return True, f"OTP સફળતાપૂર્વક મોકલવામાં આવ્યો છે: {' & '.join(channels_success)}"
    else:
        return False, f"OTP મોકલવામાં નિષ્ફળતા: {'; '.join(errors)}"

def render_login_screen():
    """Renders the Confluence Pro PIN Login & Reset Gateway UI."""
    st.markdown("""
    <style>
    .auth-card {
        max-width: 440px;
        margin: 60px auto 30px auto;
        padding: 32px 36px;
        background: linear-gradient(180deg, rgba(23, 31, 48, 0.98) 0%, rgba(13, 20, 36, 0.99) 100%);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 20px;
        box-shadow: 0 16px 45px rgba(0, 0, 0, 0.6), 0 0 35px rgba(56, 189, 248, 0.15);
        text-align: center;
    }
    .auth-title {
        font-size: 26px;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF 0%, #38BDF8 60%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .auth-badge {
        display: inline-block;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        background: rgba(16, 185, 129, 0.2);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 10px;
        border-radius: 9999px;
        margin-bottom: 16px;
    }
    .auth-desc {
        color: #94A3B8;
        font-size: 13px;
        line-height: 1.5;
        margin-bottom: 24px;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        st.markdown("""
        <div class="auth-card">
            <div class="auth-title">🎯 CONFLUENCE PRO</div>
            <div class="auth-badge">SECURE TERMINAL GATEWAY</div>
            <div class="auth-desc">આ તમારું પ્રાઈવેટ ટ્રેડિંગ ટર્મિનલ છે.<br>કૃપા કરીને આગળ વધવા માટે તમારો <b>સિક્યોરિટી PIN</b> દાખલ કરો.</div>
        </div>
        """, unsafe_allow_html=True)

        # Mode toggle: Login vs Forgot PIN
        show_reset = st.session_state.get("show_pin_reset", False)

        if not show_reset:
            # Login Form
            with st.form("pin_login_form"):
                entered_pin = st.text_input(
                    "🔑 તમારો 4-આંકડાનો સિક્યોરિટી PIN દાખલ કરો:",
                    type="password",
                    max_chars=8,
                    placeholder="દા.ત. 4082",
                    key="input_login_pin"
                )
                submit_btn = st.form_submit_button("🚀 Unlock Terminal", use_container_width=True, type="primary")

                if submit_btn:
                    current_pin = get_stored_pin()
                    if entered_pin.strip() == current_pin:
                        st.session_state["authenticated"] = True
                        st.success("✅ વેરીફીકેશન સફળ! ટર્મિનલ અનલૉક થઈ રહ્યું છે...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ ખોટો PIN! કૃપા કરીને ફરીથી પ્રયત્ન કરો.")

            # Forgot PIN trigger
            st.markdown("<div style='text-align: center; margin-top: 14px;'>", unsafe_allow_html=True)
            if st.button("❓ Forgot PIN? (Gmail / Telegram વડે રીસેટ કરો)", key="btn_toggle_reset"):
                st.session_state["show_pin_reset"] = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        else:
            # PIN Reset Flow
            st.info("🔐 **PIN Reset પ્રક્રિયા:** તમારા રજીસ્ટર્ડ Gmail / Telegram પર 6-આંકડાનો સુરક્ષિત OTP મોકલવામાં આવશે.")
            
            default_email = get_config_val("GMAIL_RECIPIENT", "ggp305ggp@gmail.com")
            reset_email = st.text_input("📧 તમારું રજીસ્ટર્ડ Gmail એડ્રેસ:", value=default_email, key="input_reset_email")
            
            c_otp1, c_otp2 = st.columns([1.2, 1])
            with c_otp1:
                if st.button("📲 Send Reset OTP", type="secondary", use_container_width=True):
                    with st.spinner("OTP મોકલાઈ રહ્યો છે..."):
                        ok, msg = dispatch_reset_otp(reset_email.strip())
                        if ok:
                            st.success(f"✅ {msg}")
                        else:
                            st.warning(f"⚠️ {msg}")
            
            with c_otp2:
                if st.button("🔙 Back to Login", use_container_width=True):
                    st.session_state["show_pin_reset"] = False
                    st.rerun()

            # Verify OTP & Set New PIN
            with st.form("verify_otp_form"):
                entered_otp = st.text_input("🔢 પ્રાપ્ત થયેલ 6-આંકડાનો OTP:", max_chars=6, placeholder="દા.ત. 584920")
                new_pin_1 = st.text_input("🆕 નવો 4-આંકડાનો PIN સેટ કરો:", type="password", max_chars=8, placeholder="નવો PIN")
                new_pin_2 = st.text_input("🔁 નવો PIN ફરીથી દાખલ કરો:", type="password", max_chars=8, placeholder="કન્ફર્મ PIN")
                
                reset_submit = st.form_submit_button("💾 Save New PIN & Unlock", type="primary", use_container_width=True)
                
                if reset_submit:
                    saved_otp = st.session_state.get("reset_otp_code")
                    expiry = st.session_state.get("reset_otp_expiry", 0)
                    
                    if not saved_otp or time.time() > expiry:
                        st.error("❌ OTP એક્સપાયર થઈ ગયો છે અથવા જનરેટ નથી થયો. કૃપા કરીને ફરી 'Send Reset OTP' પર ક્લિક કરો.")
                    elif entered_otp.strip() != saved_otp:
                        st.error("❌ દાખલ કરેલો OTP ખોટો છે.")
                    elif len(new_pin_1.strip()) < 4:
                        st.error("❌ PIN ઓછામાં ઓછો 4 આંકડાનો હોવો જોઈએ.")
                    elif new_pin_1.strip() != new_pin_2.strip():
                        st.error("❌ બંને PIN મેચ થતા નથી.")
                    else:
                        set_stored_pin(new_pin_1.strip())
                        st.session_state["authenticated"] = True
                        st.session_state["show_pin_reset"] = False
                        st.session_state.pop("reset_otp_code", None)
                        st.success("🎉 તમારો નવો PIN સફળતાપૂર્વક સેટ થઈ ગયો છે! ટર્મિનલ અનલૉક થાય છે...")
                        time.sleep(1)
                        st.rerun()

def check_auth_gate() -> bool:
    """
    Checks if session is authenticated.
    If authenticated, returns True to let the main app render.
    If not, renders the login gate and stops Streamlit execution.
    """
    if st.session_state.get("authenticated", False):
        return True
    
    render_login_screen()
    st.stop()
    return False

def render_logout_button():
    """Renders a subtle lock button in the sidebar to re-lock the terminal."""
    if st.sidebar.button("🔒 Lock Terminal", use_container_width=True, help="ટર્મિનલ લૉક કરી લૉગિન પેજ પર પાછા જાઓ"):
        st.session_state["authenticated"] = False
        st.session_state["show_pin_reset"] = False
        st.rerun()
