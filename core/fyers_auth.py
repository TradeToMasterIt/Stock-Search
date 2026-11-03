"""
Fyers API v3 Automated Authentication & Client Manager
Fully automated daily access token generation using External TOTP (RFC 6238).
Tokens are automatically refreshed daily after 6:30 AM IST.
"""

import os
import json
import time
import socket
import base64
import struct
import hmac
import hashlib
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import requests
import threading
from fyers_apiv3 import fyersModel

# Set default socket timeout so no network socket hangs indefinitely
socket.setdefaulttimeout(10.0)

from core.config import (
    FYERS_CLIENT_ID,
    FYERS_PIN,
    FYERS_TOTP_KEY,
    FYERS_APP_ID,
    FYERS_SECRET_KEY,
    FYERS_REDIRECT_URI,
    FYERS_TOKEN_FILE,
    IST_TZ,
    get_ist_now
)

def generate_totp(secret: str, interval: int = 30) -> str:
    """
    Pure Python RFC 6238 TOTP generator.
    Works independently of external libraries (zero dependencies).
    """
    # Safeguard against boundary expiration
    rem = interval - int(time.time() % interval)
    if rem < 3:
        time.sleep(rem + 1)

    cleaned_secret = secret.replace(" ", "").strip().upper()
    missing_padding = len(cleaned_secret) % 8
    if missing_padding != 0:
        cleaned_secret += '=' * (8 - missing_padding)
    
    key = base64.b32decode(cleaned_secret)
    counter = int(time.time() // interval)
    msg = struct.pack('>Q', counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 15
    code = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"

def is_token_valid_for_today(saved_timestamp: float) -> bool:
    """
    Checks if a saved token is still valid.
    Fyers tokens expire daily at 06:30 AM IST.
    A token is valid if it was generated after today's 06:30 AM IST.
    """
    now_ist = get_ist_now()
    token_time_ist = datetime.fromtimestamp(saved_timestamp, tz=IST_TZ)
    
    # Today's 6:30 AM cutoff
    today_cutoff = now_ist.replace(hour=6, minute=30, second=0, microsecond=0)
    
    if now_ist >= today_cutoff:
        return token_time_ist >= today_cutoff
    else:
        yesterday_cutoff = today_cutoff - timedelta(days=1)
        return token_time_ist >= yesterday_cutoff

def get_cached_token() -> str | None:
    """Reads cached token from file if present and still valid."""
    if not os.path.exists(FYERS_TOKEN_FILE):
        return None
    try:
        with open(FYERS_TOKEN_FILE, "r") as f:
            data = json.load(f)
            token = data.get("access_token")
            saved_time = data.get("timestamp", 0)
            if token and is_token_valid_for_today(saved_time):
                return token
    except Exception as e:
        print(f"[FYERS] Error reading cached token: {e}")
    return None

def save_token_cache(access_token: str, refresh_token: str = ""):
    """Saves generated access token with current timestamp."""
    try:
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "timestamp": time.time(),
            "created_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
        with open(FYERS_TOKEN_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[FYERS] Error caching token: {e}")

def login_and_generate_token() -> tuple[bool, str]:
    """
    Executes automated Fyers V3 login flow using TOTP and PIN.
    Returns (True, access_token) on success, or (False, error_message).
    """
    if not all([FYERS_CLIENT_ID, FYERS_PIN, FYERS_TOTP_KEY, FYERS_APP_ID, FYERS_SECRET_KEY]):
        missing = []
        if not FYERS_CLIENT_ID: missing.append("FYERS_CLIENT_ID")
        if not FYERS_PIN: missing.append("FYERS_PIN")
        if not FYERS_TOTP_KEY: missing.append("FYERS_TOTP_KEY")
        if not FYERS_APP_ID: missing.append("FYERS_APP_ID")
        if not FYERS_SECRET_KEY: missing.append("FYERS_SECRET_KEY")
        return False, f"Missing credentials in config: {', '.join(missing)}"

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        # Step 1: Send Login OTP Request
        url_otp = "https://api-t2.fyers.in/vagator/v2/send_login_otp"
        payload_otp = {"fy_id": FYERS_CLIENT_ID, "app_id": "2"}
        resp1 = session.post(url_otp, json=payload_otp, headers=headers, timeout=12)
        data1 = resp1.json()

        if data1.get("s") != "ok":
            return False, f"Step 1 Failed (Send OTP): {data1.get('message', resp1.text)}"

        request_key = data1.get("request_key")
        if not request_key:
            return False, "Step 1 Failed: 'request_key' not returned by Fyers."

        # Step 2: Verify TOTP Code
        totp_code = generate_totp(FYERS_TOTP_KEY)
        url_totp = "https://api-t2.fyers.in/vagator/v2/verify_otp"
        payload_totp = {"request_key": request_key, "otp": str(totp_code)}
        resp2 = session.post(url_totp, json=payload_totp, headers=headers, timeout=12)
        data2 = resp2.json()

        if data2.get("s") != "ok":
            return False, f"Step 2 Failed (Verify TOTP): {data2.get('message', resp2.text)}"

        request_key_totp = data2.get("data", {}).get("request_key") or data2.get("request_key") or request_key

        # Step 3: Verify 4-digit PIN (Base64 encoded identifier)
        url_pin = "https://api-t2.fyers.in/vagator/v2/verify_pin_v2"
        pin_b64 = base64.b64encode(str(FYERS_PIN).encode('ascii')).decode('ascii')
        payload_pin = {
            "request_key": request_key_totp,
            "identity_type": "pin",
            "identifier": pin_b64
        }
        resp3 = session.post(url_pin, json=payload_pin, headers=headers, timeout=12)
        data3 = resp3.json()

        if data3.get("s") != "ok":
            return False, f"Step 3 Failed (Verify PIN): {data3.get('message', resp3.text)}"

        intermediate_token = data3.get("data", {}).get("access_token")
        if not intermediate_token:
            return False, f"Step 3 Failed: No intermediate access_token returned: {data3}"

        # Step 4: Request Auth Code via Fyers V3 Token endpoint
        raw_app_id = FYERS_APP_ID.split('-')[0]
        app_type = FYERS_APP_ID.split('-')[1] if '-' in FYERS_APP_ID else '100'

        auth_headers = {
            "authorization": f"Bearer {intermediate_token}",
            "content-type": "application/json; charset=UTF-8"
        }
        token_payload = {
            "fyers_id": FYERS_CLIENT_ID,
            "app_id": raw_app_id,
            "redirect_uri": FYERS_REDIRECT_URI,
            "appType": app_type,
            "code_challenge": "",
            "state": "None",
            "scope": "",
            "nonce": "",
            "response_type": "code",
            "create_cookie": True
        }

        resp4 = session.post("https://api-t1.fyers.in/api/v3/token", headers=auth_headers, json=token_payload, timeout=12)
        data4 = resp4.json()

        login_url = data4.get("Url") or data4.get("data", {}).get("url")
        if not login_url:
            return False, f"Step 4 Failed (Generate AuthCode): {data4.get('message', data4)}"

        parsed_url = urlparse(login_url)
        query_params = parse_qs(parsed_url.query)
        auth_code_list = query_params.get("auth_code")

        if not auth_code_list:
            return False, f"Step 4 Failed: auth_code not present in redirect URL: {login_url}"

        auth_code = auth_code_list[0]

        # Step 5: Exchange Auth Code for Access Token
        app_session = fyersModel.SessionModel(
            client_id=FYERS_APP_ID,
            secret_key=FYERS_SECRET_KEY,
            redirect_uri=FYERS_REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code"
        )
        app_session.set_token(auth_code)
        token_resp = app_session.generate_token()

        if not isinstance(token_resp, dict) or token_resp.get("s") != "ok":
            return False, f"Step 5 Failed (Generate Token): {token_resp}"

        access_token = token_resp.get("access_token")
        refresh_token = token_resp.get("refresh_token", "")
        if not access_token:
            return False, f"Step 5 Failed: access_token not found in response: {token_resp}"

        # Save to cache
        save_token_cache(access_token, refresh_token)
        return True, access_token

    except Exception as e:
        return False, f"Exception during Fyers login: {str(e)}"

_auth_lock = threading.Lock()

def get_fyers_token(force_refresh: bool = False) -> tuple[bool, str]:
    """
    Returns valid access_token, either from cache or by triggering fresh login.
    Thread-safe to prevent race conditions during multi-threaded scanning.
    """
    with _auth_lock:
        if not force_refresh:
            cached = get_cached_token()
            if cached:
                return True, cached

        return login_and_generate_token()

_cached_fyers_client = None
_cached_fyers_token = None

def get_fyers_client(force_refresh: bool = False) -> tuple[bool, fyersModel.FyersModel | str]:
    """
    Returns an authenticated instance of fyersModel.FyersModel.
    Automatically refreshes token if expired.
    Uses in-memory cache to prevent multiple concurrent re-instantiations.
    Thread-safe with request timeout protection.
    """
    global _cached_fyers_client, _cached_fyers_token
    with _auth_lock:
        success, token_or_err = get_fyers_token(force_refresh=force_refresh)
        if not success:
            return False, token_or_err

        if not force_refresh and _cached_fyers_client is not None and _cached_fyers_token == token_or_err:
            return True, _cached_fyers_client

        try:
            fyers = fyersModel.FyersModel(
                client_id=FYERS_APP_ID,
                token=token_or_err,
                is_async=False
            )
            # Safeguard requests.Session with timeout protection
            if hasattr(fyers, "service") and hasattr(fyers.service, "session"):
                orig_request = fyers.service.session.request
                def safe_req(*args, **kwargs):
                    if "timeout" not in kwargs or kwargs["timeout"] is None:
                        kwargs["timeout"] = 10.0
                    return orig_request(*args, **kwargs)
                fyers.service.session.request = safe_req

            _cached_fyers_client = fyers
            _cached_fyers_token = token_or_err
            return True, fyers
        except Exception as e:
            return False, f"Failed to instantiate FyersModel: {str(e)}"

def test_fyers_connection() -> tuple[bool, dict | str]:
    """
    Tests Fyers API connection by fetching the user profile.
    If token expired, forces refresh.
    """
    success, client_or_err = get_fyers_client()
    if not success:
        return False, f"Auth Error: {client_or_err}"

    try:
        profile = client_or_err.get_profile()
        if isinstance(profile, dict) and profile.get("s") == "ok":
            return True, profile.get("data", {})
        elif "token" in str(profile).lower() or (isinstance(profile, dict) and profile.get("code") in [401, -15, -16]):
            # Token might be invalid or expired, retry with force_refresh
            success, client_or_err = get_fyers_client(force_refresh=True)
            if not success:
                return False, f"Refresh Auth Error: {client_or_err}"
            profile = client_or_err.get_profile()
            if isinstance(profile, dict) and profile.get("s") == "ok":
                return True, profile.get("data", {})
        return False, f"Fyers API Error: {profile}"
    except Exception as e:
        return False, f"Exception in test_fyers_connection: {str(e)}"

# -------------------------------------------------------------
# Rate-Limited Safe API Callers (5 req/sec Standard Plan Limit)
# -------------------------------------------------------------
_fyers_rate_lock = threading.Lock()
_last_fyers_req_ts = 0.0

def safe_fyers_history(fyers_client, data: dict, retries: int = 2) -> dict:
    """
    Thread-safe history caller with strict rate-limiting (max 4.5 req/sec).
    Prevents 'Standard plan limit of 5 requests/second' errors.
    Automatically retries with backoff if rate-limited.
    """
    global _last_fyers_req_ts
    for attempt in range(retries + 1):
        with _fyers_rate_lock:
            now = time.time()
            elapsed = now - _last_fyers_req_ts
            if elapsed < 0.22:
                time.sleep(0.22 - elapsed)
            _last_fyers_req_ts = time.time()

        try:
            res = fyers_client.history(data=data)
            if isinstance(res, dict):
                msg = str(res.get("message", "")).lower()
                if "requests/second" in msg or "limit" in msg or res.get("code") in [-99, 429]:
                    time.sleep(0.4 + attempt * 0.25)
                    continue
            return res
        except Exception as e:
            if attempt < retries:
                time.sleep(0.4 + attempt * 0.25)
                continue
            return {"s": "error", "message": str(e)}
    return {"s": "error", "message": "Max retries exceeded"}

def safe_fyers_quotes(fyers_client, data: dict, retries: int = 2) -> dict:
    """
    Thread-safe quotes caller with strict rate-limiting.
    """
    global _last_fyers_req_ts
    for attempt in range(retries + 1):
        with _fyers_rate_lock:
            now = time.time()
            elapsed = now - _last_fyers_req_ts
            if elapsed < 0.22:
                time.sleep(0.22 - elapsed)
            _last_fyers_req_ts = time.time()

        try:
            res = fyers_client.quotes(data=data)
            if isinstance(res, dict):
                msg = str(res.get("message", "")).lower()
                if "requests/second" in msg or "limit" in msg or res.get("code") in [-99, 429]:
                    time.sleep(0.4 + attempt * 0.25)
                    continue
            return res
        except Exception as e:
            if attempt < retries:
                time.sleep(0.4 + attempt * 0.25)
                continue
            return {"s": "error", "message": str(e)}
    return {"s": "error", "message": "Max retries exceeded"}
