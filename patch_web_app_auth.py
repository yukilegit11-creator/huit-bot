import re

patch_code = '''
# ==================== DASHBOARD AUTHENTICATION GUARD ====================
import hmac
import hashlib
from urllib.parse import quote
from fastapi.responses import RedirectResponse

AUTH_SECRET = os.environ.get("DASHBOARD_SECRET_KEY", "yuki_cloud_dashboard_secret_key_2026")
DEFAULT_ADMIN_PASSWORD = "YUKILEGIT0"

def get_admin_password() -> str:
    try:
        cfg = get_config()
        return cfg.get("dashboard_auth", {}).get("password", DEFAULT_ADMIN_PASSWORD)
    except Exception:
        return DEFAULT_ADMIN_PASSWORD

def is_auth_enabled() -> bool:
    try:
        cfg = get_config()
        return cfg.get("dashboard_auth", {}).get("enabled", True)
    except Exception:
        return True

def generate_session_token(password: str = None) -> str:
    pwd = password or get_admin_password()
    return hmac.new(AUTH_SECRET.encode(), f"admin_authenticated_{pwd}".encode(), hashlib.sha256).hexdigest()

def is_valid_session(token: str) -> bool:
    if not token:
        return False
    expected = generate_session_token()
    return hmac.compare_digest(str(token), str(expected))

def get_login_page_html() -> str:
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đăng nhập Quản trị viên • Yuki Multi-Bot</title>
  <link rel="icon" type="image/x-icon" href="https://img.icons8.com/color/48/shield.png">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .glass-card {
      background: rgba(255, 255, 255, 0.96);
      backdrop-filter: blur(24px);
      border: 1px solid rgba(226, 232, 240, 0.85);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.12);
    }
  </style>
</head>
<body class="bg-slate-900 min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
  <div class="absolute -top-32 -left-32 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none"></div>
  <div class="absolute -bottom-32 -right-32 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl pointer-events-none"></div>
  <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

  <div class="w-full max-w-md relative z-10">
    <div class="glass-card rounded-3xl p-8 sm:p-10 text-slate-800">
      <div class="text-center mb-7">
        <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center text-2xl mx-auto mb-4 shadow-lg shadow-indigo-500/30">
          <i class="fa-solid fa-shield-halved"></i>
        </div>
        <h1 class="text-2xl font-extrabold text-slate-900 tracking-tight">Yuki Multi-Bot</h1>
        <p class="text-xs text-slate-500 font-medium mt-1">Hệ thống Giám sát & Quản trị 4 Trường Đại học</p>
        
        <div class="flex flex-wrap items-center justify-center gap-1.5 mt-4">
          <span class="px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-[11px] font-bold border border-indigo-100">🎓 HUIT</span>
          <span class="px-2.5 py-1 bg-sky-50 text-sky-700 rounded-lg text-[11px] font-bold border border-sky-100">✈️ VAA</span>
          <span class="px-2.5 py-1 bg-rose-50 text-rose-700 rounded-lg text-[11px] font-bold border border-rose-100">🔥 IUH</span>
          <span class="px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-[11px] font-bold border border-emerald-100">🏛️ UFM</span>
        </div>
      </div>

      <div id="login-error" class="hidden mb-5 p-3.5 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
        <i class="fa-solid fa-circle-exclamation text-rose-500"></i>
        <span id="login-error-msg">Mật khẩu quản trị không chính xác!</span>
      </div>

      <form id="login-form" onsubmit="handleLogin(event)" class="space-y-5">
        <div>
          <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
            Mật khẩu Quản trị viên
          </label>
          <div class="relative">
            <span class="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none text-slate-400">
              <i class="fa-solid fa-lock text-sm"></i>
            </span>
            <input 
              type="password" 
              id="admin-password" 
              required
              autofocus
              placeholder="Nhập mật khẩu truy cập..." 
              class="w-full pl-10 pr-12 py-3 bg-slate-50 hover:bg-white focus:bg-white border border-slate-200 focus:border-indigo-500 rounded-2xl text-sm font-semibold transition outline-none shadow-xs"
            >
            <button 
              type="button" 
              onclick="togglePassVisibility()" 
              class="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-400 hover:text-slate-600 transition"
              tabindex="-1"
            >
              <i id="eye-icon" class="fa-solid fa-eye text-sm"></i>
            </button>
          </div>
        </div>

        <div class="flex items-center justify-between text-xs">
          <label class="flex items-center gap-2 cursor-pointer select-none text-slate-600 font-medium">
            <input type="checkbox" id="remember-me" checked class="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300">
            Duy trì đăng nhập 30 ngày
          </label>
          <span class="text-slate-400 text-[11px] font-mono">Cloud 24/7</span>
        </div>

        <button 
          type="submit" 
          id="btn-submit"
          class="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold text-sm rounded-2xl shadow-lg shadow-indigo-500/25 transition flex items-center justify-center gap-2 group cursor-pointer"
        >
          <span>Đăng Nhập Quản Trị</span>
          <i class="fa-solid fa-arrow-right text-xs group-hover:translate-x-1 transition-transform"></i>
        </button>
      </form>

      <div class="mt-8 pt-5 border-t border-slate-100 text-center">
        <p class="text-[11px] text-slate-400 font-medium flex items-center justify-center gap-1.5">
          <i class="fa-solid fa-fingerprint text-indigo-500"></i>
          Hệ thống bảo vệ bởi Yuki Multi-Bot Auth Guard
        </p>
      </div>
    </div>
  </div>

  <script>
    function togglePassVisibility() {
      const inp = document.getElementById('admin-password');
      const icon = document.getElementById('eye-icon');
      if (inp.type === 'password') {
        inp.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      } else {
        inp.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      }
    }

    async function handleLogin(e) {
      e.preventDefault();
      const pass = document.getElementById('admin-password').value.trim();
      const remember = document.getElementById('remember-me').checked;
      const btn = document.getElementById('btn-submit');
      const errBox = document.getElementById('login-error');
      const errMsg = document.getElementById('login-error-msg');

      if (!pass) return;

      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang xác thực...';
      errBox.classList.add('hidden');

      try {
        const res = await fetch('/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pass, remember: remember })
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
          const params = new URLSearchParams(window.location.search);
          const nextUrl = params.get('next') || '/';
          window.location.href = nextUrl;
        } else {
          errBox.classList.remove('hidden');
          errMsg.textContent = data.message || 'Mật khẩu quản trị viên không chính xác!';
          document.getElementById('admin-password').select();
          btn.disabled = false;
          btn.innerHTML = '<span>Đăng Nhập Quản Trị</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
        }
      } catch (err) {
        errBox.classList.remove('hidden');
        errMsg.textContent = 'Lỗi kết nối tới máy chủ. Vui lòng thử lại!';
        btn.disabled = false;
        btn.innerHTML = '<span>Đăng Nhập Quản Trị</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
      }
    }
  </script>
</body>
</html>"""

@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    # 1. Trả về 200 OK ngay lập tức cho các yêu cầu kiểm tra trạng thái sống (HEAD method từ UptimeRobot / BetterStack / Render)
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"})

    path = request.url.path

    # 2. Bỏ qua các endpoint không yêu cầu xác thực
    unprotected = ["/health", "/ping", "/login", "/logout", "/favicon.ico"]
    if any(path == p or path.startswith(p + "/") for p in unprotected) or path.startswith("/static/"):
        return await call_next(request)

    # 3. Kiểm tra xác thực nếu Auth được bật
    if is_auth_enabled():
        session_token = request.cookies.get("yuki_auth_session")
        auth_header = request.headers.get("Authorization", "")
        
        is_authed = False
        if session_token and is_valid_session(session_token):
            is_authed = True
        elif auth_header:
            parts = auth_header.split(" ")
            if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == get_admin_password():
                is_authed = True

        if not is_authed:
            # Nếu là API request: trả về 401 JSON
            if path.startswith("/api/") or "/api/" in path:
                return JSONResponse(
                    {"status": "error", "message": "Yêu cầu đăng nhập mật khẩu quản trị viên.", "code": "UNAUTHORIZED"},
                    status_code=401
                )
            # Nếu là duyệt web (HTML page): chuyển hướng sang trang /login
            next_param = quote(path) if path and path != "/" else ""
            redirect_url = f"/login?next={next_param}" if next_param else "/login"
            return RedirectResponse(url=redirect_url)

    return await call_next(request)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_auth_enabled():
        session_token = request.cookies.get("yuki_auth_session")
        if session_token and is_valid_session(session_token):
            return RedirectResponse(url="/")
    return HTMLResponse(content=get_login_page_html())

@app.post("/login")
async def process_login(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    password = str(data.get("password", "")).strip()
    remember = bool(data.get("remember", True))
    
    expected_pwd = get_admin_password()
    if password == expected_pwd:
        token = generate_session_token(password)
        max_age = 30 * 86400 if remember else 86400
        resp = JSONResponse({
            "status": "ok", 
            "message": "Đăng nhập thành công!",
            "redirect": "/"
        })
        resp.set_cookie(
            key="yuki_auth_session",
            value=token,
            max_age=max_age,
            expires=max_age,
            path="/",
            httponly=True,
            samesite="lax"
        )
        return resp
    else:
        return JSONResponse({
            "status": "error",
            "message": "Mật khẩu quản trị viên không chính xác!"
        }, status_code=400)

@app.api_route("/logout", methods=["GET", "POST"])
def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie(key="yuki_auth_session", path="/")
    return resp
'''

p = r'c:\Users\Admin\Documents\HUIT\web_app.py'
with open(p, 'r', encoding='utf-8') as f:
    code = f.read()

target_str = '''@app.middleware("http")
async def handle_head_and_monitor_requests(request: Request, call_next):
    # Trả về 200 OK ngay lập tức cho các yêu cầu kiểm tra trạng thái sống (HEAD method từ UptimeRobot / BetterStack / Render)
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"})
    return await call_next(request)'''

if target_str in code:
    code = code.replace(target_str, patch_code.strip(), 1)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Patched web_app.py with complete auth system successfully!")
else:
    print("target_str not found in web_app.py")
