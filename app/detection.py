import hmac
import hashlib
import base64
import time
import re
from typing import Dict, List, Tuple, Optional
from fastapi import Request
from .settings import settings

# In-memory rate limiter state: ip -> [timestamps]
_RATE_BUCKET: Dict[str, List[float]] = {}

BOT_UA_PATTERNS = [
    r"bot", r"crawl", r"spider", r"wget", r"curl",
    r"python-requests", r"libwww-perl", r"httpclient", r"scrapy",
    r"java/", r"go-http-client", r"okhttp"
]

SEARCH_BOT_PATTERNS = [r"googlebot", r"bingbot", r"duckduckbot", r"yandexbot"]

def _now() -> float:
    return time.time()

def _sign(value: str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")

def mint_human_cookie(ip: str, ua: str) -> str:
    """
    Create a short-lived token bound to IP+UA+timestamp, signature appended.
    Returns base64(token|sig).
    """
    issued_at = int(_now())
    payload = f"{ip}|{ua}|{issued_at}"
    signature = _sign(payload)
    token = f"{payload}|{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")

def verify_human_cookie(cookie: str, ip: str, ua: str) -> bool:
    """
    Verify cookie: decode, check parts length, binding (ip & ua), TTL, and signature.
    """
    try:
        token = base64.urlsafe_b64decode(cookie.encode("utf-8")).decode("utf-8")
        parts = token.split("|")
        if len(parts) != 4:
            return False
        ip_c, ua_c, issued_at_s, sig = parts
        # Basic bind to same IP + UA
        if ip_c != ip or ua_c != ua:
            return False
        # TTL check
        issued_at = int(issued_at_s)
        if _now() - issued_at > settings.CHALLENGE_COOKIE_TTL_SECONDS:
            return False
        # Signature check
        expected_sig = _sign("|".join(parts[:-1]))
        return hmac.compare_digest(expected_sig, sig)
    except Exception:
        return False

def _rate_limit_reason(ip: str) -> Optional[str]:
    """
    Simple sliding window token-bucket style limiter in memory.
    Returns a string reason when the rate limit is exceeded, otherwise None.
    """
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    capacity = settings.RATE_LIMIT_REQUESTS
    ts = _now()
    bucket = _RATE_BUCKET.setdefault(ip, [])
    # prune old timestamps outside window
    cutoff = ts - window
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= capacity:
        return f"rate_limited({len(bucket)}/{capacity} in {window}s)"
    bucket.append(ts)
    return None

def _header_anomalies(request: Request) -> List[str]:
    anomalies = []
    headers = request.headers
    # Some scrapers omit common headers or have unusual values
    if "user-agent" not in headers or not headers.get("user-agent"):
        anomalies.append("missing_user_agent")
    if "accept-language" not in headers:
        anomalies.append("missing_accept_language")
    if "accept" not in headers:
        anomalies.append("missing_accept")
    return anomalies

def _matches_any(patterns: List[str], text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in patterns)

def detect(request: Request) -> Tuple[bool, Dict]:
    """
    Returns (is_bot: bool, ctx: dict)
    ctx includes ip, ua, score, reasons.
    Higher score means more likely a bot. Threshold is configurable here (default 3).
    """
    ip = request.client.host if request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "")

    reasons: List[str] = []
    score = 0

    # 1) Allowlist: search engines (optional)
    if settings.ALLOW_SEARCH_BOTS and _matches_any(SEARCH_BOT_PATTERNS, ua):
        return False, {"ip": ip, "ua": ua, "score": 0, "reasons": ["allowed_search_bot"]}

    # 2) Rate limiting
    rl = _rate_limit_reason(ip)
    if rl:
        reasons.append(rl)
        score += 2

    # 3) UA heuristics
    if _matches_any(BOT_UA_PATTERNS, ua):
        reasons.append("bot_ua_pattern")
        score += 2
    if ua.strip() == "":
        reasons.append("empty_ua")
        score += 2

    # 4) Header anomalies
    anomalies = _header_anomalies(request)
    if anomalies:
        reasons.extend(anomalies)
        score += len(anomalies)  # +1 per anomaly

    # 5) JS challenge cookie
    cookie = request.cookies.get(settings.CHALLENGE_COOKIE_NAME)
    if not cookie:
        reasons.append("missing_human_cookie")
        score += 2
    else:
        if not verify_human_cookie(cookie, ip, ua):
            reasons.append("invalid_human_cookie")
            score += 2

    # Final decision
    is_bot = score >= 3  # threshold
    ctx = {"ip": ip, "ua": ua, "score": score, "reasons": reasons}
    return is_bot, ctx
