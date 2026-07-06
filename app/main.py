from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from .settings import settings
from .detection import detect, mint_human_cookie

app = FastAPI(title="AI Lounge Bot Shield (Prototype)", version="1.0.0")

# CORS (adjust before prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Example catalog (replace with DB or WP API integration later)
REAL_PRICES = [
    {"id": 1, "name": "AI Basics", "price": 199},
    {"id": 2, "name": "Deep Learning", "price": 299},
    {"id": 3, "name": "LLM Ops", "price": 349},
]
FAKE_PRICES = [
    {"id": 1, "name": "AI Basics", "price": 999},
    {"id": 2, "name": "Deep Learning", "price": 1999},
    {"id": 3, "name": "LLM Ops", "price": 1499},
]

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/challenge", response_class=HTMLResponse)
def challenge(request: Request):
    """
    Minimal JS challenge: browser hits this page, JS calls /challenge/complete to set human cookie.
    This simulates the JS execution check that many basic scrapers won't run.
    """
    html = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Human Verification</title></head>
<body>
<h3>Verifying you're human…</h3>
<script>
fetch('/challenge/complete', { credentials: 'include' }).then(() => {
  document.body.innerHTML = '<p>✅ Verification cookie set. You can now access real prices.</p><a href="/api/courses">Continue to courses API</a>';
}).catch(() => {
  document.body.innerHTML = '<p>⚠️ Could not set verification cookie.</p>';
});
</script>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)

@app.get("/challenge/complete")
def challenge_complete(request: Request, response: Response):
    """
    Sets a signed cookie bound to IP+UA. Cookie is httponly so scrapers that don't run JS won't get it.
    """
    ip = request.client.host if request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "")
    token = mint_human_cookie(ip, ua)
    response = PlainTextResponse("ok", status_code=200)
    response.set_cookie(
        key=settings.CHALLENGE_COOKIE_NAME,
        value=token,
        max_age=settings.CHALLENGE_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=False,  # set True when using HTTPS in prod
        samesite="Lax",
    )
    return response

@app.get("/api/courses")
def get_courses(request: Request):
    """
    Public API: returns REAL_PRICES to humans, FAKE_PRICES to detected bots.
    If ALLOW_TEST_DEBUG is true, we include raw debug context (only for dev).
    """
    is_bot, ctx = detect(request)
    payload = {
        "status": "bot_detected" if is_bot else "human",
        "courses": FAKE_PRICES if is_bot else REAL_PRICES,
    }
    if settings.ALLOW_TEST_DEBUG:
        payload["debug"] = ctx
    return JSONResponse(payload)

@app.get("/_debug/why")
def debug_why(request: Request):
    """
    Expose detection reasoning for testing. Only enabled when ALLOW_TEST_DEBUG=true.
    """
    if not settings.ALLOW_TEST_DEBUG:
        return JSONResponse({"error": "debug disabled"}, status_code=403)
    is_bot, ctx = detect(request)
    return JSONResponse({"is_bot": is_bot, **ctx})
