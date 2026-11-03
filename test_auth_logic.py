import sys
import hmac
import hashlib
from urllib.parse import quote
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

test_app = FastAPI()

AUTH_SECRET = "test_secret"
ADMIN_PWD = "YUKILEGIT0"

def generate_session_token(pwd=None):
    return hmac.new(AUTH_SECRET.encode(), f"admin_authenticated_{pwd or ADMIN_PWD}".encode(), hashlib.sha256).hexdigest()

def is_valid_session(token):
    return hmac.compare_digest(str(token or ""), str(generate_session_token()))

@test_app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    path = request.url.path
    unprotected = ["/health", "/ping", "/login", "/logout"]
    if any(path == p or path.startswith(p + "/") for p in unprotected):
        return await call_next(request)

    token = request.cookies.get("yuki_auth_session")
    if not is_valid_session(token):
        if path.startswith("/api/") or "/api/" in path:
            return JSONResponse({"status": "error", "message": "Unauthorized"}, status_code=401)
        next_p = quote(path) if path != "/" else ""
        return RedirectResponse(f"/login?next={next_p}" if next_p else "/login")
    return await call_next(request)

@test_app.get("/")
def home():
    return {"message": "Welcome Admin"}

@test_app.get("/login")
def login_get():
    return HTMLResponse("<h1>Login Page</h1>")

@test_app.post("/login")
async def login_post(req: Request):
    data = await req.json()
    if data.get("password") == ADMIN_PWD:
        resp = JSONResponse({"status": "ok"})
        resp.set_cookie("yuki_auth_session", generate_session_token(), path="/", httponly=True)
        return resp
    return JSONResponse({"status": "error"}, status_code=400)

print("Auth test logic compiled successfully!")
