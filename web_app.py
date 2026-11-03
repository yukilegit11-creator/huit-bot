import os
import sys
import json
import sqlite3
import time
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import hashlib
from datetime import datetime, timezone, timedelta

import database
from zalo_sender import ZaloDispatcher
from scraper import FacebookCometScraper
from supabase_client import SupabaseDispatcher
from iuh_scraper import IUHPortalScraper

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CONFIG_BOT2_FILE = os.path.join(SCRIPT_DIR, "config_bot2.json")
CONFIG_IUH_FILE = os.path.join(SCRIPT_DIR, "config_iuh.json")


app = FastAPI(title="HUIT Social Crawler Dashboard", version="2.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tích hợp Sub-app Bot 4: UFM (Cổng Hoạt Động & ĐRL)
try:
    ufm_dir = os.path.join(SCRIPT_DIR, "vaa", "ufm")
    if os.path.exists(ufm_dir) and ufm_dir not in sys.path:
        sys.path.insert(0, ufm_dir)
    from vaa.ufm import web_app as ufm_module
    app.mount("/ufm", ufm_module.app)
except Exception as _e:
    print(f"⚠️ [Web App] Chưa mount được UFM subapp: {_e}")

# Tích hợp Bot 5: OU (Trường ĐH Mở TP.HCM)
try:
    import web_app_bot5
    app.include_router(web_app_bot5.router)
    print("✅ [Web App] Đã tích hợp thành công Bot 5 (OU ĐRL) router!")
except Exception as _e:
    print(f"⚠️ [Web App] Chưa tích hợp được Bot 5 router: {_e}")

@app.get("/bot4")
def bot4_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ufm")

@app.get("/submit-cookie")
def submit_cookie_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ufm/submit-cookie")


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

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {
        "status": "ok", 
        "service": "huit-bot", 
        "timestamp": datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
    }

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping_check():
    return Response(content="pong", media_type="text/plain", status_code=200)

def get_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        import github_sync
        github_sync.push_async(commit_message="🔄 Auto-sync: Cập nhật cấu hình Bot 1 (HUIT)")
    except Exception:
        pass

@app.post("/api/github/sync")
def api_github_sync(msg: Optional[str] = Form(None)):
    import github_sync
    commit_msg = msg or "🚀 Thủ công đồng bộ dữ liệu lên GitHub từ Web Dashboard"
    ok, message = github_sync.push_to_github(commit_message=commit_msg)
    return {"status": "ok" if ok else "error", "message": message, "detail": github_sync.get_sync_status()}

@app.get("/api/github/status")
def api_github_status():
    import github_sync
    return {"status": "ok", "sync": github_sync.get_sync_status()}

# ==================== API ENDPOINTS ====================

@app.get("/api/logs")
def api_get_logs(limit: int = 100):
    logs = database.get_recent_logs(limit=limit)
    return {"status": "ok", "count": len(logs), "server_time": database.get_vn_now_str(), "logs": logs}

@app.get("/api/all-logs")
def api_get_all_logs(limit: int = 150, bot: Optional[str] = None):
    all_logs = []
    
    # 1. Bot 1 (HUIT)
    try:
        huit_logs = database.get_recent_logs(limit=limit, db_file=database.DB_FILE)
        for l in huit_logs:
            ld = dict(l)
            ld["bot"] = "HUIT"
            ld["bot_badge"] = "Bot 1 (HUIT)"
            ld["bot_color"] = "text-blue-400 bg-blue-950/80 border-blue-800"
            all_logs.append(ld)
    except Exception:
        pass

    # 2. Bot 2 (VAA)
    try:
        vaa_logs = database.get_recent_logs(limit=limit, db_file=database.BOT2_DB_FILE)
        for l in vaa_logs:
            ld = dict(l)
            ld["bot"] = "VAA"
            ld["bot_badge"] = "Bot 2 (VAA)"
            ld["bot_color"] = "text-sky-400 bg-sky-950/80 border-sky-800"
            all_logs.append(ld)
    except Exception:
        pass

    # 3. Bot 3 (IUH)
    try:
        iuh_logs = database.get_recent_logs(limit=limit, db_file=database.IUH_DB_FILE)
        for l in iuh_logs:
            ld = dict(l)
            ld["bot"] = "IUH"
            ld["bot_badge"] = "Bot 3 (IUH)"
            ld["bot_color"] = "text-rose-400 bg-rose-950/80 border-rose-800"
            all_logs.append(ld)
    except Exception:
        pass

    # 4. Bot 4 (UFM)
    try:
        ufm_db_path = os.path.join(SCRIPT_DIR, "vaa", "ufm", "ufm_bot.db")
        if not os.path.exists(ufm_db_path):
            ufm_db_path = database.UFM_DB_FILE
        ufm_logs = database.get_recent_logs(limit=limit, db_file=ufm_db_path)
        for l in ufm_logs:
            ld = dict(l)
            ld["bot"] = "UFM"
            ld["bot_badge"] = "Bot 4 (UFM)"
            ld["bot_color"] = "text-emerald-400 bg-emerald-950/80 border-emerald-800"
            all_logs.append(ld)
    except Exception:
        pass

    if bot and bot.upper() != "ALL":
        b_clean = bot.strip().upper()
        all_logs = [l for l in all_logs if l.get("bot") == b_clean]

    all_logs.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return {
        "status": "ok", 
        "count": len(all_logs), 
        "server_time": database.get_vn_now_str(), 
        "logs": all_logs[:limit]
    }

@app.get("/api/posts")
def api_get_posts(limit: int = 50, page_name: Optional[str] = None, search: Optional[str] = None):
    posts = database.get_posts(limit=limit, page_name=page_name, search=search)
    return {"status": "ok", "count": len(posts), "data": posts}

@app.get("/api/stats")
def api_get_stats():
    return database.get_stats()

@app.get("/api/history")
def api_get_delivery_history(limit: int = 50, page: int = 1, search: Optional[str] = None, target_id: Optional[str] = None):
    return database.get_delivery_history(limit=limit, page=page, search=search, target_id=target_id)

@app.post("/api/bot/toggle")
def api_toggle_bot():
    current_state = database.is_bot_enabled()
    new_state = not current_state
    database.set_bot_enabled(new_state)
    return {
        "status": "ok", 
        "is_active": new_state,
        "message": f"Đã {'BẬT' if new_state else 'TẮT (Tạm dừng)'} bot thành công!"
    }

@app.get("/api/crawl")
def api_crawl_now():
    cfg = get_config()
    targets = cfg.get("targets", [])
    fb_cookies = cfg.get("fb_cookies", {})
    scraper = FacebookCometScraper(fb_cookies)
    zalo = ZaloDispatcher(CONFIG_FILE)
    supabase = SupabaseDispatcher(CONFIG_FILE)
    
    new_posts = []
    database.set_bot_status("last_scan_time", datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S"))
    database.set_bot_status("bot_state", "scanning")
    database.log_event("SCAN", f"[Cào thủ công] Bắt đầu quét nhanh qua {len(targets)} nguồn...")

    for target in targets:
        pname = target.get("name", "Trang")
        purl = target.get("url", "")
        if not purl:
            continue
        try:
            html = scraper.fetch_url(purl)
            posts = scraper.parse_posts(html, max_age_hours=3.0, page_url=purl)
            for p in posts:
                content_txt = p.get("content", "")
                ident = p.get("post_id") or hashlib.md5(content_txt[:150].encode("utf-8")).hexdigest()
                if not database.is_post_seen(ident, content=content_txt):
                    database.save_crawled_post(
                        post_id=ident,
                        page_name=pname,
                        author=p.get("author", "Thành viên nhóm"),
                        content=content_txt,
                        post_url=p.get("post_url", ""),
                        posted_time=p.get("posted_time", "")
                    )
                    database.record_seen_post(ident, pname, content=content_txt)
                    database.log_event("POST", f"[{pname}] Bóc tách bài mới: {content_txt[:70]}...")

                    if supabase.enabled:
                        supabase.push_post(p, pname)
                    
                    filter_kws = cfg.get("filter_keywords", [])
                    txt_lower = content_txt.lower()
                    has_kw = not filter_kws or any(kw.lower() in txt_lower for kw in filter_kws)
                    
                    already_sent = database.is_post_already_sent_zalo(ident, content=content_txt)
                    if has_kw and not already_sent:
                        database.log_event("FILTER", f"Khớp từ khóa -> Đang gửi vào Zalo...")
                        sent_ok = zalo.send_alert(p, pname)
                        if sent_ok:
                            database.mark_post_sent_zalo(ident)
                    elif already_sent:
                        database.log_event("FILTER", f"🛑 [Chống lặp] Bài viết đã từng gửi Zalo trước đó, bỏ qua không gửi lần 2.")
                    else:
                        database.log_event("FILTER", f"Bỏ qua Zalo (không chứa từ khóa lọc)")
                    new_posts.append({"page": pname, "author": p.get("author"), "id": ident, "sent_zalo": has_kw and not already_sent})
        except Exception as e:
            database.log_event("ERROR", f"Lỗi quét {pname}: {e}")
            database.set_bot_status("last_error", str(e))

    database.set_bot_status("bot_state", "sleeping")
    database.log_event("SCAN", f"[Cào thủ công] Hoàn thành. Tìm thấy {len(new_posts)} bài mới.")
    return {"status": "ok", "new_posts_count": len(new_posts), "posts": new_posts}

@app.get("/api/targets")
def api_get_targets():
    cfg = get_config()
    return {"status": "ok", "targets": cfg.get("targets", [])}

@app.post("/api/targets")
def api_add_target(name: str = Form(...), url: str = Form(...)):
    cfg = get_config()
    targets = cfg.get("targets", [])
    new_id = f"target_{len(targets) + 1}_{int(datetime.now().timestamp())}"
    targets.append({
        "id": new_id,
        "name": name.strip(),
        "url": url.strip()
    })
    cfg["targets"] = targets
    save_config(cfg)
    database.log_event("SYSTEM", f"Đã thêm nguồn theo dõi mới: {name.strip()}")
    return {"status": "ok", "message": "Đã thêm trang thành công!", "targets": targets}

@app.delete("/api/targets/{target_id}")
def api_delete_target(target_id: str):
    cfg = get_config()
    targets = cfg.get("targets", [])
    deleted_name = next((t.get("name") for t in targets if t.get("id") == target_id), target_id)
    new_targets = [t for t in targets if t.get("id") != target_id]
    cfg["targets"] = new_targets
    save_config(cfg)
    database.log_event("SYSTEM", f"Đã xóa nguồn theo dõi: {deleted_name}")
    return {"status": "ok", "message": "Đã xóa trang thành công!", "targets": new_targets}

# ==================== ZALO MANAGEMENT APIS ====================

@app.get("/api/zalo/groups")
def api_get_zalo_groups():
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        groups = dispatcher.get_groups()
        return {"status": "ok", "groups": groups}
    except Exception as e:
        return {"status": "error", "message": str(e), "groups": []}

@app.get("/api/zalo/target_groups")
def api_get_target_groups():
    cfg = get_config()
    zalo_cfg = cfg.get("zalo", {})
    return {"status": "ok", "target_groups": zalo_cfg.get("target_groups", [])}

@app.post("/api/zalo/toggle_group")
def api_toggle_zalo_group(group_id: str = Form(...), enabled: Optional[str] = Form(None)):
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    
    gid_clean = str(group_id).strip()
    found = False
    new_status = False
    gname = group_id

    # Parse giá trị enabled tường minh nếu có
    explicit_val = None
    if enabled is not None:
        explicit_val = str(enabled).strip().lower() in ("true", "1", "yes")

    seen_ids = set()
    deduped_groups = []
    for g in target_groups:
        cur_id = str(g.get("id")).strip()
        if cur_id == gid_clean:
            found = True
            gname = g.get("name", group_id)
            if explicit_val is not None:
                g["enabled"] = explicit_val
            else:
                g["enabled"] = not g.get("enabled", False)
            new_status = g["enabled"]

        if cur_id not in seen_ids:
            seen_ids.add(cur_id)
            deduped_groups.append(g)
            
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
        
    cfg["zalo"]["target_groups"] = deduped_groups
    save_config(cfg)
    database.log_event("ZALO", f"Đã {'BẬT' if new_status else 'TẮT'} nhận tin cho nhóm Zalo [{gname}]")
    return {"status": "ok", "enabled": new_status, "target_groups": deduped_groups}

@app.post("/api/zalo/toggle_tag_all")
def api_toggle_tag_all():
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    current = cfg["zalo"].get("auto_tag_all", True)
    new_val = not current
    cfg["zalo"]["auto_tag_all"] = new_val
    save_config(cfg)
    database.log_event("ZALO", f"Đã {'BẬT' if new_val else 'TẮT'} tính năng tự động @All khi có bài mới.")
    return {"status": "ok", "auto_tag_all": new_val}

@app.post("/api/zalo/add_group")
def api_add_zalo_group(group_id: str = Form(...), group_name: str = Form(...)):
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    
    for g in target_groups:
        if str(g.get("id")) == str(group_id).strip():
            g["enabled"] = True
            g["name"] = group_name.strip()
            save_config(cfg)
            return {"status": "ok", "message": "Nhóm đã tồn tại, đã bật gửi tin!", "target_groups": target_groups}
            
    target_groups.append({
        "id": str(group_id).strip(),
        "name": group_name.strip(),
        "enabled": True
    })
    cfg["zalo"]["target_groups"] = target_groups
    save_config(cfg)
    database.log_event("ZALO", f"Đã thêm nhóm Zalo mới vào danh sách nhận tin: [{group_name.strip()}] (ID: {group_id.strip()})")
    return {"status": "ok", "message": f"Đã thêm nhóm '{group_name}'!", "target_groups": target_groups}

@app.delete("/api/zalo/target_groups/{group_id}")
def api_delete_zalo_group(group_id: str):
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    new_groups = [g for g in target_groups if str(g.get("id")) != str(group_id)]
    cfg["zalo"]["target_groups"] = new_groups
    save_config(cfg)
    database.log_event("ZALO", f"Đã xóa nhóm Zalo ID {group_id} khỏi danh sách")
    return {"status": "ok", "message": "Đã xóa nhóm!", "target_groups": new_groups}

@app.post("/api/zalo/cookies")
@app.post("/api/bot2/zalo/cookies")
@app.post("/api/bot3/zalo/cookies")
def api_update_zalo_cookies(raw_cookies: str = Form(...)):
    from zalo_sender import parse_zalo_cookie_input
    parsed = parse_zalo_cookie_input(raw_cookies)
    if not parsed or "zpw_sek" not in parsed:
        raise HTTPException(status_code=400, detail="Cookie Zalo không hợp lệ. Phải chứa tối thiểu trường zpw_sek (hoặc xuất từ Cookie Editor)!")
    
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    cfg["zalo"]["cookies"] = parsed
    save_config(cfg)
    
    # Cập nhật chéo cho tất cả các file cấu hình liên quan
    for p in [
        CONFIG_BOT2_FILE, 
        CONFIG_IUH_FILE, 
        os.path.join(SCRIPT_DIR, "vaabot.json"), 
        os.path.join(SCRIPT_DIR, "config_ufm.json"),
        os.path.join(SCRIPT_DIR, "vaa", "config.json"),
        os.path.join(SCRIPT_DIR, "vaa", "vaabot.json"),
        os.path.join(SCRIPT_DIR, "vaa", "ufm", "config.json")
    ]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if "zalo" in d:
                    d["zalo"]["cookies"] = parsed
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(d, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
                
    try:
        from zlapi import ZaloAPI
        imei = cfg["zalo"].get("imei")
        try:
            client = ZaloAPI(phone="", password="", imei=imei, cookies=parsed)
        except TypeError:
            client = ZaloAPI(phone="", password="", imei=imei, session_cookies=parsed)
        uid = client.uid() if callable(client.uid) else client.uid
        msg = f"Đã lưu và xác thực đăng nhập Zalo Bot thành công! UID: {uid}"
        database.log_event("ZALO", msg)
        return {"status": "ok", "message": msg, "uid": str(uid)}
    except Exception as e:
        msg = f"Đã lưu Cookie Zalo nhưng kiểm tra kết nối cảnh báo: {e}"
        database.log_event("ZALO", msg)
        return {"status": "ok", "message": msg, "warning": str(e)}

@app.post("/api/zalo/test_alert")
def api_test_zalo_alert():
    dispatcher = ZaloDispatcher(CONFIG_FILE)
    test_post = {
        "author": "Ban Quản Trị HUIT",
        "posted_time": datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M - %d/%m/%Y"),
        "content": """🔔 THÔNG BÁO KIỂM TRA HỆ THỐNG BOT 1 (HUIT) - BẮN TEST NỘI BỘ

📌 Bài viết thử nghiệm: Mở đăng ký tham gia chương trình Sinh viên Tình nguyện (Được cộng 10 Điểm Rèn Luyện).

Link đăng ký: https://forms.gle/testHuitDocForm2026

Chúc các bạn một ngày làm việc và học tập hiệu quả!""",
        "post_url": "https://www.facebook.com/dtn.hsv.huit",
        "is_manual_test": True,
        "creation_time": datetime.now().timestamp()
    }
    # CHỈ gửi thử nghiệm cho nhóm 'demo' và cá nhân 'Yuki' (KHÔNG gửi cho tất cả các nhóm)
    test_targets = [
        {"id": "7456361874031804652", "name": "demo"},
        {"id": "7581087306337796515", "name": "Yuki"}
    ]
    sent_any = False
    for t in test_targets:
        try:
            if dispatcher.send_alert(test_post, "KÊNH KIỂM TRA BOT 1", target_thread_id=t["id"]):
                sent_any = True
        except Exception as e:
            print(f"Lỗi gửi test tới {t['name']}: {e}")

    if sent_any:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công CHỈ cho riêng Yuki & nhóm demo!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm tới nhóm demo hoặc Yuki!")

@app.post("/api/zalo/send-demo-alert")
@app.post("/api/ufm/send-demo-alert")
def api_master_send_demo_alert():
    """Gửi bài viết/hoạt động thông báo vào nhóm demo (ID: 7456361874031804652)."""
    # 1. Ưu tiên gửi từ UFM Dispatcher
    try:
        from vaa.ufm.zalo_sender import ZaloDispatcher as UFMDispatcher
        ufm_cfg = os.path.join(SCRIPT_DIR, "config_ufm.json")
        ufm_db = os.path.join(SCRIPT_DIR, "vaa", "ufm", "ufm_bot.db")
        dispatcher = UFMDispatcher(ufm_cfg, db_file=ufm_db)
        ok, msg = dispatcher.send_demo_group_alert(db_file=ufm_db)
        if ok:
            return {"status": "ok", "success": True, "message": msg}
    except Exception as e:
        print(f"⚠️ [UFM Demo Alert] Lỗi Dispatcher UFM: {e}")

    # 2. Thử gửi từ Master Dispatcher
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        if hasattr(dispatcher, "send_demo_group_alert"):
            ok, msg = dispatcher.send_demo_group_alert()
            return {"status": "ok" if ok else "error", "success": ok, "message": msg}
        else:
            return api_test_zalo_alert()
    except Exception as e:
        err_msg = f"Không thể gửi thông báo vào nhóm demo: {e}"
        return {"status": "error", "success": False, "message": err_msg}

# ==================== UNIFIED MESSENGER INTEGRATION APIS (QUAD-BOT) ====================

ALL_BOT_CONFIG_FILES = [
    os.path.join(SCRIPT_DIR, "config.json"),
    os.path.join(SCRIPT_DIR, "config_bot2.json"),
    os.path.join(SCRIPT_DIR, "config_iuh.json"),
    os.path.join(SCRIPT_DIR, "config_ufm.json"),
    os.path.join(SCRIPT_DIR, "vaabot.json"),
    os.path.join(SCRIPT_DIR, "vaa", "config.json"),
    os.path.join(SCRIPT_DIR, "vaa", "vaabot.json"),
    os.path.join(SCRIPT_DIR, "vaa", "ufm", "config.json")
]

def sync_messenger_config_to_all(messenger_block: dict):
    for cp in ALL_BOT_CONFIG_FILES:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    c = json.load(f)
                c["messenger"] = messenger_block
                with open(cp, "w", encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"⚠️ [Messenger Sync] Lỗi cập nhật {cp}: {e}")


# ==================== QUAD BOT ZALO TESTING ENDPOINTS ====================

@app.get("/api/zalo/quad-target-groups")
def api_quad_target_groups():
    """Lấy danh sách toàn bộ các nhóm mục tiêu Zalo của cả 4 Bot để phục vụ kiểm tra/bắn tin."""
    bots_cfg = [
        {"bot_id": "bot1", "name": "Bot 1 - HUIT (Yuki 1)", "cfg_path": CONFIG_FILE},
        {"bot_id": "bot2", "name": "Bot 2 - VAA (Yuki 2)", "cfg_path": os.path.join(SCRIPT_DIR, "vaabot.json")},
        {"bot_id": "bot3", "name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg_path": os.path.join(SCRIPT_DIR, "config_iuh.json")},
        {"bot_id": "bot4", "name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg_path": os.path.join(SCRIPT_DIR, "config_ufm.json")},
        {"bot_id": "bot5", "name": "Bot 5 - OU (Yuki 5 ĐRL)", "cfg_path": os.path.join(SCRIPT_DIR, "config_ou.json")},
    ]
    result = []
    for b in bots_cfg:
        cfg_p = b["cfg_path"]
        groups = []
        if os.path.exists(cfg_p):
            try:
                with open(cfg_p, "r", encoding="utf-8") as fp:
                    cdata = json.load(fp)
                    groups = cdata.get("zalo", {}).get("target_groups", [])
            except Exception as e:
                print(f"Lỗi đọc config {cfg_p}: {e}")
        result.append({
            "bot_id": b["bot_id"],
            "bot_name": b["name"],
            "config_path": cfg_p,
            "groups": groups
        })
    return {"status": "ok", "bots": result}

@app.post("/api/zalo/send-test-target")
async def api_send_test_target(req: Request):
    """Bắn tin nhắn thử nghiệm tới 1 nhóm hoặc người nhận cụ thể của bất kỳ Bot nào trong 4 Bot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    bot_id = data.get("bot_id", "bot1")
    target_id = str(data.get("target_id", "")).strip()
    target_type = data.get("target_type", "GROUP")
    target_name = data.get("target_name", target_id)
    custom_msg = data.get("custom_message", None)

    if not target_id:
        raise HTTPException(status_code=400, detail="Thiếu target_id (ID nhóm hoặc người nhận)!")

    bot_map = {
        "bot1": {"name": "Bot 1 - HUIT (Yuki 1)", "cfg": CONFIG_FILE, "db": database.DB_FILE},
        "bot2": {"name": "Bot 2 - VAA (Yuki 2)", "cfg": os.path.join(SCRIPT_DIR, "vaabot.json"), "db": database.BOT2_DB_FILE},
        "bot3": {"name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_iuh.json"), "db": database.IUH_DB_FILE},
        "bot4": {"name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ufm.json"), "db": database.UFM_DB_FILE},
        "bot5": {"name": "Bot 5 - OU (Yuki 5 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ou.json"), "db": database.OU_DB_FILE},
    }

    bot_info = bot_map.get(bot_id, bot_map["bot1"])
    from zalo_sender import ZaloDispatcher
    dispatcher = ZaloDispatcher(bot_info["cfg"], db_file=bot_info["db"])
    dispatcher.bot_name = bot_info["name"]

    ok, msg = dispatcher.send_test_message_to_target(
        target_id=target_id,
        target_type=target_type,
        custom_text=custom_msg,
        db_file=bot_info["db"]
    )
    if ok:
        return {
            "status": "ok",
            "success": True,
            "message": msg,
            "target_name": target_name,
            "target_id": target_id,
            "bot_name": bot_info["name"]
        }
    else:
        raise HTTPException(status_code=500, detail=f"[{bot_info['name']}] {msg}")

@app.post("/api/zalo/send-test-all-groups")
async def api_send_test_all_groups(req: Request):
    """Bắn tin nhắn thử nghiệm tới toàn bộ các nhóm đang bật của 1 Bot."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    bot_id = data.get("bot_id", "bot1")
    bot_map = {
        "bot1": {"name": "Bot 1 - HUIT (Yuki 1)", "cfg": CONFIG_FILE, "db": database.DB_FILE},
        "bot2": {"name": "Bot 2 - VAA (Yuki 2)", "cfg": os.path.join(SCRIPT_DIR, "vaabot.json"), "db": database.BOT2_DB_FILE},
        "bot3": {"name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_iuh.json"), "db": database.IUH_DB_FILE},
        "bot4": {"name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ufm.json"), "db": database.UFM_DB_FILE},
        "bot5": {"name": "Bot 5 - OU (Yuki 5 ĐRL)", "cfg": os.path.join(SCRIPT_DIR, "config_ou.json"), "db": database.OU_DB_FILE},
    }

    bot_info = bot_map.get(bot_id, bot_map["bot1"])
    from zalo_sender import ZaloDispatcher
    dispatcher = ZaloDispatcher(bot_info["cfg"], db_file=bot_info["db"])
    dispatcher.bot_name = bot_info["name"]

    with open(bot_info["cfg"], "r", encoding="utf-8") as fp:
        cfg_data = json.load(fp)

    tgs = [g for g in cfg_data.get("zalo", {}).get("target_groups", []) if g.get("enabled", True)]
    results = []
    for g in tgs:
        ok, msg = dispatcher.send_test_message_to_target(
            target_id=str(g["id"]),
            target_type=g.get("type", "GROUP"),
            db_file=bot_info["db"]
        )
        results.append({
            "id": g["id"],
            "name": g.get("name"),
            "success": ok,
            "message": msg
        })
        await asyncio.sleep(1)

    succ_count = sum(1 for r in results if r["success"])
    return {
        "status": "ok",
        "bot_name": bot_info["name"],
        "total": len(tgs),
        "success_count": succ_count,
        "details": results
    }

@app.post("/api/zalo/send-demo-alert")
@app.post("/api/ufm/send-demo-alert")
def api_master_send_demo_alert():
    """Gửi bài viết/hoạt động thông báo vào nhóm demo (ID: 7456361874031804652)."""
    # 1. Ưu tiên gửi từ UFM Dispatcher
    try:
        from vaa.ufm.zalo_sender import ZaloDispatcher as UFMDispatcher
        ufm_cfg = os.path.join(SCRIPT_DIR, "config_ufm.json")
        ufm_db = os.path.join(SCRIPT_DIR, "vaa", "ufm", "ufm_bot.db")
        dispatcher = UFMDispatcher(ufm_cfg, db_file=ufm_db)
        ok, msg = dispatcher.send_demo_group_alert(db_file=ufm_db)
        if ok:
            return {"status": "ok", "success": True, "message": msg}
    except Exception as e:
        print(f"⚠️ [UFM Demo Alert] Lỗi Dispatcher UFM: {e}")

    # 2. Thử gửi từ Master Dispatcher
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        if hasattr(dispatcher, "send_demo_group_alert"):
            ok, msg = dispatcher.send_demo_group_alert()
            return {"status": "ok" if ok else "error", "success": ok, "message": msg}
        else:
            return api_test_zalo_alert()
    except Exception as e:
        return {"status": "error", "success": False, "message": str(e)}

@app.get("/api/messenger/status")
@app.get("/api/bot2/messenger/status")
@app.get("/api/bot3/messenger/status")
def api_unified_messenger_status():
    cfg = get_config()
    m_cfg = cfg.get("messenger", {})
    b_status = database.get_all_bot_status()
    return {
        "status": "ok",
        "enabled": m_cfg.get("enabled", False),
        "cookie_status": b_status.get("messenger_cookie_status", "valid" if m_cfg.get("cookies") else "missing"),
        "account_uid": b_status.get("messenger_account_uid", "61574475721537"),
        "last_connected": b_status.get("messenger_last_connected", ""),
        "target_groups": m_cfg.get("target_groups", []),
        "has_cookies": bool(m_cfg.get("cookies"))
    }

@app.post("/api/messenger/toggle")
@app.post("/api/bot2/messenger/toggle")
@app.post("/api/bot3/messenger/toggle")
def api_unified_messenger_toggle():
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": False, "cookies": [], "target_groups": []}
    new_state = not cfg["messenger"].get("enabled", False)
    cfg["messenger"]["enabled"] = new_state
    sync_messenger_config_to_all(cfg["messenger"])
    save_config(cfg)
    msg = f"Đã {'BẬT' if new_state else 'TẮT'} kênh thông báo Facebook Messenger cho toàn bộ 4 con bot!"
    database.log_event("CONFIG", msg)
    return {"status": "ok", "enabled": new_state, "message": msg}

@app.post("/api/messenger/update-cookies")
@app.post("/api/bot2/messenger/update-cookies")
@app.post("/api/bot3/messenger/update-cookies")
def api_unified_messenger_update_cookies(data: dict):
    raw_cookies = data.get("cookies")
    if not raw_cookies:
        return {"status": "error", "message": "Vui lòng dán chuỗi JSON Cookie Facebook!"}

    parsed = []
    if isinstance(raw_cookies, str):
        try:
            parsed = json.loads(raw_cookies.strip())
        except Exception as e:
            return {"status": "error", "message": f"Dữ liệu không phải JSON hợp lệ: {e}"}
    elif isinstance(raw_cookies, list):
        parsed = raw_cookies
    elif isinstance(raw_cookies, dict):
        for k, v in raw_cookies.items():
            parsed.append({"name": k, "value": str(v), "domain": ".facebook.com", "path": "/"})

    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": True, "cookies": [], "target_groups": []}
    cfg["messenger"]["cookies"] = parsed
    sync_messenger_config_to_all(cfg["messenger"])
    save_config(cfg)

    # Thử kết nối
    try:
        from messenger_sender import MessengerDispatcher
        m = MessengerDispatcher(CONFIG_FILE)
        if m.connect():
            uid = getattr(m.client, "uid", "unknown")
            database.log_event("AUTH", f"✅ Đã cập nhật Cookie Facebook Messenger thành công! UID: {uid}")
            return {"status": "ok", "message": f"Xác thực Cookie Facebook thành công! UID: {uid}", "uid": str(uid)}
    except Exception as e:
        print(f"⚠️ [Messenger Connect Check]: {e}")

    return {"status": "ok", "message": "Đã lưu Cookie Facebook và đồng bộ cho cả 4 bot!"}

@app.post("/api/messenger/check-connection")
@app.post("/api/bot2/messenger/check-connection")
@app.post("/api/bot3/messenger/check-connection")
def api_unified_messenger_check_connection():
    try:
        from messenger_sender import MessengerDispatcher
        m = MessengerDispatcher(CONFIG_FILE)
        if m.connect():
            uid = getattr(m.client, "uid", "unknown")
            return {"status": "ok", "success": True, "message": f"Kết nối Facebook Messenger thành công! (UID: {uid})", "uid": str(uid)}
        else:
            return {"status": "error", "success": False, "message": "Không thể kết nối Facebook Messenger (Cookie có thể hết hạn)"}
    except Exception as e:
        return {"status": "error", "success": False, "message": str(e)}

@app.post("/api/messenger/groups/add")
@app.post("/api/bot2/messenger/groups/add")
@app.post("/api/bot3/messenger/groups/add")
def api_unified_messenger_add_group(data: dict):
    tid = str(data.get("thread_id", "")).strip()
    name = str(data.get("name", "")).strip() or f"Nhóm Messenger {tid}"
    if not tid:
        return {"status": "error", "message": "Vui lòng nhập Thread ID của nhóm Facebook Messenger!"}

    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": True, "cookies": [], "target_groups": []}
    groups = cfg["messenger"].get("target_groups", [])

    for g in groups:
        if str(g.get("id")) == tid:
            g["enabled"] = True
            sync_messenger_config_to_all(cfg["messenger"])
            save_config(cfg)
            return {"status": "ok", "message": f"Nhóm {name} ({tid}) đã tồn tại, đã bật lại!"}

    groups.append({
        "id": tid,
        "name": name,
        "type": "GROUP",
        "enabled": True
    })
    cfg["messenger"]["target_groups"] = groups
    sync_messenger_config_to_all(cfg["messenger"])
    save_config(cfg)
    database.log_event("CONFIG", f"Đã thêm nhóm Messenger mới: [{name}] (ID: {tid}) cho cả 4 bot")
    return {"status": "ok", "message": f"Đã thêm nhóm [{name}] (ID: {tid}) thành công!", "target_groups": groups}

@app.post("/api/messenger/groups/toggle")
@app.post("/api/bot2/messenger/groups/toggle")
@app.post("/api/bot3/messenger/groups/toggle")
def api_unified_messenger_toggle_group(data: dict):
    tid = str(data.get("thread_id", "")).strip()
    cfg = get_config()
    groups = cfg.get("messenger", {}).get("target_groups", [])
    found = False
    for g in groups:
        if str(g.get("id")) == tid:
            g["enabled"] = not g.get("enabled", False)
            found = True
            break
    if found:
        sync_messenger_config_to_all(cfg["messenger"])
        save_config(cfg)
        return {"status": "ok", "message": f"Đã đổi trạng thái nhóm ID {tid}", "target_groups": groups}
    return {"status": "error", "message": f"Không tìm thấy nhóm ID {tid}"}

@app.post("/api/messenger/groups/delete")
@app.post("/api/bot2/messenger/groups/delete")
@app.post("/api/bot3/messenger/groups/delete")
def api_unified_messenger_delete_group(data: dict):
    tid = str(data.get("thread_id", "")).strip()
    cfg = get_config()
    groups = cfg.get("messenger", {}).get("target_groups", [])
    new_groups = [g for g in groups if str(g.get("id")) != tid]
    cfg["messenger"]["target_groups"] = new_groups
    sync_messenger_config_to_all(cfg["messenger"])
    save_config(cfg)
    database.log_event("CONFIG", f"Đã xóa nhóm Messenger ID {tid} khỏi danh sách")
    return {"status": "ok", "message": f"Đã xóa nhóm Messenger ID {tid} thành công!", "target_groups": new_groups}

@app.post("/api/messenger/test")
@app.post("/api/bot2/messenger/test")
@app.post("/api/bot3/messenger/test")
def api_unified_messenger_test(data: dict = None):
    tid = data.get("thread_id") if data else None
    try:
        from messenger_sender import MessengerDispatcher
        m = MessengerDispatcher(CONFIG_FILE)
        ok, msg = m.send_test_message(target_thread_id=tid)
        return {"status": "ok" if ok else "error", "success": ok, "message": msg}
    except Exception as e:
        return {"status": "error", "success": False, "message": str(e)}

# ==================== MAIN DASHBOARD HTML VIEW ====================


# ==================== BOT 2 (KÊNH RIÊNG BIỆT) APIS ====================

def get_config_bot2():
    with open(CONFIG_BOT2_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config_bot2(cfg):
    with open(CONFIG_BOT2_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    # Đồng bộ sang các file VAA và thư mục vaabot riêng biệt
    for p in [
        os.path.join(SCRIPT_DIR, "vaabot.json"), 
        os.path.join(SCRIPT_DIR, "vaa", "config.json"), 
        os.path.join(SCRIPT_DIR, "vaa", "vaabot.json"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "vaabot", "config.json"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "vaabot", "vaabot.json")
    ]:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    try:
        import github_sync
        github_sync.push_async(commit_message="🔄 Auto-sync: Cập nhật cấu hình Bot 2 (VAA)")
    except Exception:
        pass

@app.get("/api/bot2/posts")
def api_bot2_get_posts(limit: int = 50, page_name: Optional[str] = None, search: Optional[str] = None):
    posts = database.get_posts(limit=limit, page_name=page_name, search=search, db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "count": len(posts), "data": posts}

@app.get("/api/bot2/stats")
def api_bot2_get_stats():
    return database.get_stats(db_file=database.BOT2_DB_FILE)

@app.get("/api/bot2/logs")
def api_bot2_get_logs(limit: int = 100):
    logs = database.get_recent_logs(limit=limit, db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "count": len(logs), "server_time": database.get_vn_now_str(), "logs": logs}

@app.get("/api/bot2/history")
@app.get("/api/bot2/delivery_history")
def api_bot2_get_delivery_history(limit: int = 50, page: int = 1, search: Optional[str] = None, target_id: Optional[str] = None):
    return database.get_delivery_history(limit=limit, page=page, search=search, target_id=target_id, db_file=database.BOT2_DB_FILE)

@app.get("/api/delivery_history")
def api_get_delivery_history_alias(limit: int = 50, page: int = 1, search: Optional[str] = None, target_id: Optional[str] = None):
    return database.get_delivery_history(limit=limit, page=page, search=search, target_id=target_id)

@app.post("/api/bot2/toggle")
def api_bot2_toggle():
    current_state = database.is_bot_enabled(db_file=database.BOT2_DB_FILE)
    new_state = not current_state
    database.set_bot_enabled(new_state, db_file=database.BOT2_DB_FILE)
    return {
        "status": "ok", 
        "is_active": new_state,
        "message": f"Đã {'BẬT' if new_state else 'TẮT (Tạm dừng)'} Bot 2 thành công!"
    }

@app.get("/api/bot2/targets")
def api_bot2_get_targets():
    cfg = get_config_bot2()
    return {"status": "ok", "targets": cfg.get("targets", [])}

@app.post("/api/bot2/targets")
def api_bot2_add_target(name: str = Form(...), url: str = Form(...)):
    cfg = get_config_bot2()
    targets = cfg.get("targets", [])
    new_id = f"target_{len(targets) + 1}_{int(datetime.now().timestamp())}"
    targets.append({
        "id": new_id,
        "name": name.strip(),
        "url": url.strip()
    })
    cfg["targets"] = targets
    save_config_bot2(cfg)
    database.log_event("SYSTEM", f"Đã thêm nguồn theo dõi Bot 2: {name.strip()}", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "message": "Đã thêm trang thành công!", "targets": targets}

@app.delete("/api/bot2/targets/{target_id}")
def api_bot2_delete_target(target_id: str):
    cfg = get_config_bot2()
    targets = cfg.get("targets", [])
    deleted_name = next((t.get("name") for t in targets if t.get("id") == target_id), target_id)
    new_targets = [t for t in targets if t.get("id") != target_id]
    cfg["targets"] = new_targets
    save_config_bot2(cfg)
    database.log_event("SYSTEM", f"Đã xóa nguồn theo dõi Bot 2: {deleted_name}", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "message": "Đã xóa trang thành công!", "targets": new_targets}

@app.post("/api/bot2/cookies")
def api_bot2_save_cookies(cookie_text: str = Form(...)):
    cfg = get_config_bot2()
    cleaned = cookie_text.strip()
    parsed = {}
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            arr = json.loads(cleaned)
            for item in arr:
                if isinstance(item, dict) and "name" in item and "value" in item:
                    parsed[item["name"]] = item["value"]
        except Exception:
            pass
    elif cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            parsed = json.loads(cleaned)
        except Exception:
            pass
    if not parsed:
        for p in cleaned.split(";"):
            if "=" in p:
                k, v = p.split("=", 1)
                parsed[k.strip()] = v.strip()
    if not parsed or "c_user" not in parsed:
        raise HTTPException(status_code=400, detail="Cookie không hợp lệ! Thiếu c_user hoặc không đúng định dạng.")
    cfg["fb_cookies"] = parsed
    save_config_bot2(cfg)
    uid = parsed.get("c_user", "")
    database.log_event("SYSTEM", f"Đã cập nhật Cookie Facebook mới cho Bot 2 (UID: {uid})", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "message": f"Đã lưu Cookie Facebook thành công! UID: {uid}", "c_user": uid}

@app.get("/api/bot2/zalo/target_groups")
def api_bot2_get_target_groups():
    cfg = get_config_bot2()
    zalo_cfg = cfg.get("zalo", {})
    return {"status": "ok", "target_groups": zalo_cfg.get("target_groups", [])}

@app.post("/api/bot2/zalo/toggle_group")
def api_bot2_toggle_zalo_group(group_id: str = Form(...), enabled: Optional[str] = Form(None)):
    cfg = get_config_bot2()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    
    gid_clean = str(group_id).strip()
    found = False
    new_status = False
    gname = group_id
    
    explicit_val = None
    if enabled is not None:
        explicit_val = str(enabled).strip().lower() in ("true", "1", "yes")

    seen_ids = set()
    deduped_groups = []
    for g in target_groups:
        cur_id = str(g.get("id")).strip()
        if cur_id == gid_clean:
            found = True
            gname = g.get("name", group_id)
            if explicit_val is not None:
                g["enabled"] = explicit_val
            else:
                g["enabled"] = not g.get("enabled", False)
            new_status = g["enabled"]

        if cur_id not in seen_ids:
            seen_ids.add(cur_id)
            deduped_groups.append(g)

    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")

    cfg["zalo"]["target_groups"] = deduped_groups
    save_config_bot2(cfg)
    database.log_event("ZALO", f"[Bot 2] Đã {'BẬT' if new_status else 'TẮT'} nhận tin nhóm [{gname}]", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "enabled": new_status, "target_groups": deduped_groups}

@app.post("/api/bot2/zalo/toggle_tag_all")
def api_bot2_toggle_tag_all():
    cfg = get_config_bot2()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    cur = cfg["zalo"].get("auto_tag_all", True)
    cfg["zalo"]["auto_tag_all"] = not cur
    save_config_bot2(cfg)
    database.log_event("ZALO", f"[Bot 2] Đã {'BẬT' if not cur else 'TẮT'} tự động @All", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "auto_tag_all": not cur}

@app.post("/api/bot2/zalo/add_group")
def api_bot2_add_zalo_group(group_id: str = Form(...), group_name: str = Form(...)):
    cfg = get_config_bot2()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    for g in target_groups:
        if str(g.get("id")) == str(group_id).strip():
            g["enabled"] = True
            g["name"] = group_name.strip()
            save_config_bot2(cfg)
            return {"status": "ok", "message": "Nhóm đã có, đã bật!", "target_groups": target_groups}
    target_groups.append({
        "id": str(group_id).strip(),
        "name": group_name.strip(),
        "enabled": True
    })
    cfg["zalo"]["target_groups"] = target_groups
    save_config_bot2(cfg)
    database.log_event("ZALO", f"[Bot 2] Đã thêm nhóm Zalo: [{group_name.strip()}]", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "message": f"Đã thêm nhóm '{group_name}'!", "target_groups": target_groups}

@app.delete("/api/bot2/zalo/target_groups/{group_id}")
def api_bot2_delete_zalo_group(group_id: str):
    cfg = get_config_bot2()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    new_groups = [g for g in target_groups if str(g.get("id")) != str(group_id)]
    cfg["zalo"]["target_groups"] = new_groups
    save_config_bot2(cfg)
    database.log_event("ZALO", f"[Bot 2] Đã xóa nhóm Zalo ID {group_id}", db_file=database.BOT2_DB_FILE)
    return {"status": "ok", "message": "Đã xóa nhóm!", "target_groups": new_groups}

@app.post("/api/bot2/zalo/test_alert")
def api_bot2_test_zalo_alert():
    dispatcher = ZaloDispatcher(CONFIG_BOT2_FILE)
    test_post = {
        "author": "Ban Quản Trị Bot 2 (VAA)",
        "posted_time": datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M - %d/%m/%Y"),
        "content": """🔔 THÔNG BÁO KIỂM TRA BOT 2 (VAA) - BẮN TEST NỘI BỘ

📌 Bài viết thử nghiệm: Mở form đăng ký tham gia chương trình hoạt động.

Link đăng ký: https://forms.gle/testBot2FormRegistration2026

Chúc các bạn theo dõi thuận lợi!""",
        "post_url": "https://www.facebook.com",
        "is_manual_test": True,
        "creation_time": datetime.now().timestamp()
    }
    # CHỈ gửi thử nghiệm cho nhóm 'demo' và cá nhân 'Yuki' (KHÔNG gửi cho tất cả các nhóm)
    test_targets = [
        {"id": "7456361874031804652", "name": "demo"},
        {"id": "7581087306337796515", "name": "Yuki"}
    ]
    sent_any = False
    for t in test_targets:
        try:
            if dispatcher.send_alert(test_post, "KÊNH KIỂM TRA BOT 2", target_thread_id=t["id"]):
                sent_any = True
        except Exception as e:
            print(f"Lỗi gửi test Bot 2 tới {t['name']}: {e}")

    if sent_any:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công CHỈ cho riêng Yuki & nhóm demo!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm tới nhóm demo hoặc Yuki!")

@app.post("/api/zalo/send-demo-alert")
@app.post("/api/ufm/send-demo-alert")
def api_master_send_demo_alert():
    """Gửi bài viết/hoạt động thông báo vào nhóm demo (ID: 7456361874031804652)."""
    # 1. Ưu tiên gửi từ UFM Dispatcher
    try:
        from vaa.ufm.zalo_sender import ZaloDispatcher as UFMDispatcher
        ufm_cfg = os.path.join(SCRIPT_DIR, "config_ufm.json")
        ufm_db = os.path.join(SCRIPT_DIR, "vaa", "ufm", "ufm_bot.db")
        dispatcher = UFMDispatcher(ufm_cfg, db_file=ufm_db)
        ok, msg = dispatcher.send_demo_group_alert(db_file=ufm_db)
        if ok:
            return {"status": "ok", "success": True, "message": msg}
    except Exception as e:
        print(f"⚠️ [UFM Demo Alert] Lỗi Dispatcher UFM: {e}")

    # 2. Thử gửi từ Master Dispatcher
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        if hasattr(dispatcher, "send_demo_group_alert"):
            ok, msg = dispatcher.send_demo_group_alert()
            return {"status": "ok" if ok else "error", "success": ok, "message": msg}
        else:
            return api_test_zalo_alert()
    except Exception as e:
        err_msg = f"Không thể gửi thông báo vào nhóm demo: {e}"
        return {"status": "error", "success": False, "message": err_msg}

def get_config_iuh():
    with open(CONFIG_IUH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config_iuh(cfg):
    with open(CONFIG_IUH_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        import github_sync
        github_sync.push_async(commit_message="🔄 Auto-sync: Cập nhật cấu hình Bot 3 (IUH)")
    except Exception:
        pass

# ==================== BOT 3 (IUH) API ENDPOINTS ====================
@app.get("/api/bot3/activities")
def api_bot3_get_activities(limit: int = 50, search: Optional[str] = None):
    acts = database.get_activities(limit=limit, search=search, db_file=database.IUH_DB_FILE)
    return {"status": "ok", "count": len(acts), "data": acts}

@app.get("/api/bot3/stats")
def api_bot3_get_stats():
    return database.get_iuh_stats(db_file=database.IUH_DB_FILE)

@app.get("/api/bot3/logs")
def api_bot3_get_logs(limit: int = 100):
    logs = database.get_recent_logs(limit=limit, db_file=database.IUH_DB_FILE)
    return {"status": "ok", "count": len(logs), "server_time": database.get_vn_now_str(), "logs": logs}

@app.post("/api/bot3/toggle")
def api_bot3_toggle():
    current_state = database.is_bot_enabled(db_file=database.IUH_DB_FILE)
    new_state = not current_state
    database.set_bot_enabled(new_state, db_file=database.IUH_DB_FILE)
    return {
        "status": "ok", 
        "is_active": new_state,
        "message": f"Đã {'BẬT' if new_state else 'TẮT (Tạm dừng)'} Bot 3 (IUH) thành công!"
    }

@app.post("/api/bot3/cookie")
def api_bot3_update_cookie(cookie: str = Form(...)):
    cfg = get_config_iuh()
    clean_cookie = IUHPortalScraper.extract_phpsessid(cookie)
    if not clean_cookie:
        raise HTTPException(status_code=400, detail="Không tìm thấy chuỗi cookie PHPSESSID hợp lệ!")
    
    cfg["portal"]["phpsessid"] = clean_cookie
    save_config_iuh(cfg)
    
    scraper = IUHPortalScraper(clean_cookie)
    is_valid, msg = scraper.check_cookie_validity()
    status_str = "valid" if is_valid else "expired"
    database.set_bot_status("portal_cookie_status", status_str, db_file=database.IUH_DB_FILE)
    database.log_event("CONFIG", f"Đã cập nhật cookie IUH PHPSESSID: {clean_cookie[:6]}... (Trạng thái: {msg})", db_file=database.IUH_DB_FILE)
    
    return {
        "status": "ok",
        "phpsessid": clean_cookie,
        "is_valid": is_valid,
        "message": f"Đã lưu cookie! Kết quả xác minh: {msg}"
    }

@app.get("/api/bot3/crawl")
def api_bot3_crawl_now():
    cfg = get_config_iuh()
    phpsessid = cfg.get("portal", {}).get("phpsessid", "")
    scraper = IUHPortalScraper(phpsessid)
    zalo = ZaloDispatcher(CONFIG_IUH_FILE)
    
    database.set_bot_status("last_scan_time", datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S"), db_file=database.IUH_DB_FILE)
    database.set_bot_status("bot_state", "scanning", db_file=database.IUH_DB_FILE)
    database.log_event("SCAN", "[Cào thủ công] Bắt đầu quét cổng hoạt động Đoàn TN IUH...", db_file=database.IUH_DB_FILE)
    
    is_logged_in, msg, activities = scraper.fetch_activities()
    if not is_logged_in:
        database.set_bot_status("portal_cookie_status", "expired", db_file=database.IUH_DB_FILE)
        database.set_bot_status("bot_state", "running", db_file=database.IUH_DB_FILE)
        database.log_event("WARN", f"Cookie IUH không hợp lệ: {msg}", db_file=database.IUH_DB_FILE)
        return {"status": "error", "message": f"Cookie IUH hết hạn: {msg}", "count": 0}

    database.set_bot_status("portal_cookie_status", "valid", db_file=database.IUH_DB_FILE)
    new_count = 0
    from iuh_bot import send_zalo_iuh
    for act in activities:
        aid = str(act["activity_id"])
        
        # 1. KIỂM TRA NGHIÊM NGẶT: Hoạt động đã từng gửi Zalo chưa?
        if database.is_activity_already_sent_zalo(aid, title=act.get("title"), db_file=database.IUH_DB_FILE):
            database.update_activity_status(aid, act.get("status", ""), act.get("slots", ""), db_file=database.IUH_DB_FILE)
            continue

        seen_act = database.get_seen_activity(aid, db_file=database.IUH_DB_FILE)
        if seen_act is not None:
            database.update_activity_status(aid, act.get("status", ""), act.get("slots", ""), db_file=database.IUH_DB_FILE)
            continue

        # Hoạt động MỚI 100% -> Lưu DB và gửi Zalo đúng 1 lần duy nhất
        new_count += 1
        database.record_seen_activity(act, is_sent=True, db_file=database.IUH_DB_FILE)
        database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=database.IUH_DB_FILE)
        send_zalo_iuh(zalo, act, is_reopened=False)

    database.set_bot_status("bot_state", "running", db_file=database.IUH_DB_FILE)
    info_msg = f"Quét xong! Tìm thấy {len(activities)} hoạt động trên bảng (Bắn {new_count} tin mới/mở slot)"
    database.log_event("SCAN", info_msg, db_file=database.IUH_DB_FILE)
    return {"status": "ok", "message": info_msg, "total": len(activities), "new_sent": new_count}

@app.get("/api/bot3/zalo/target_groups")
def api_bot3_get_target_groups():
    cfg = get_config_iuh()
    return {"status": "ok", "target_groups": cfg.get("zalo", {}).get("target_groups", [])}

@app.post("/api/bot3/zalo/toggle_group")
def api_bot3_toggle_group(group_id: str = Form(...), enabled: bool = Form(...)):
    cfg = get_config_iuh()
    groups = cfg["zalo"].get("target_groups", [])
    found = False
    for g in groups:
        if str(g.get("id")) == str(group_id):
            g["enabled"] = enabled
            found = True
            break
    if not found:
        groups.append({"id": str(group_id), "name": f"Người nhận {group_id}", "enabled": enabled, "type": "GROUP"})
    cfg["zalo"]["target_groups"] = groups
    save_config_iuh(cfg)
    database.log_event("ZALO", f"[Bot 3] Đã {'bật' if enabled else 'tắt'} nhận tin cho ID {group_id}", db_file=database.IUH_DB_FILE)
    return {"status": "ok", "target_groups": groups}

@app.post("/api/bot3/zalo/toggle_tag_all")
def api_bot3_toggle_tag_all(enabled: bool = Form(...)):
    cfg = get_config_iuh()
    cfg["zalo"]["auto_tag_all"] = enabled
    save_config_iuh(cfg)
    database.log_event("ZALO", f"[Bot 3] Đã {'BẬT' if enabled else 'TẮT'} tính năng tự động tag @All khi gửi Zalo", db_file=database.IUH_DB_FILE)
    return {"status": "ok", "auto_tag_all": enabled}

@app.post("/api/bot3/zalo/add_group")
def api_bot3_add_group(group_id: str = Form(...), group_name: str = Form(...), target_type: str = Form("GROUP")):
    cfg = get_config_iuh()
    target_groups = cfg["zalo"].get("target_groups", [])
    for g in target_groups:
        if str(g.get("id")) == str(group_id):
            g["name"] = group_name
            g["type"] = target_type
            g["enabled"] = True
            save_config_iuh(cfg)
            return {"status": "ok", "message": "Đã cập nhật đối tượng nhận tin!", "target_groups": target_groups}
    target_groups.append({
        "id": str(group_id),
        "name": group_name,
        "type": target_type,
        "enabled": True
    })
    cfg["zalo"]["target_groups"] = target_groups
    save_config_iuh(cfg)
    database.log_event("ZALO", f"[Bot 3] Thêm người nhận mới: {group_name} ({group_id})", db_file=database.IUH_DB_FILE)
    return {"status": "ok", "message": "Đã thêm đối tượng nhận tin thành công!", "target_groups": target_groups}

@app.delete("/api/bot3/zalo/target_groups/{group_id}")
def api_bot3_delete_target_group(group_id: str):
    cfg = get_config_iuh()
    target_groups = cfg["zalo"].get("target_groups", [])
    new_groups = [g for g in target_groups if str(g.get("id")) != str(group_id)]
    cfg["zalo"]["target_groups"] = new_groups
    save_config_iuh(cfg)
    database.log_event("ZALO", f"[Bot 3] Đã xóa người nhận ID {group_id}", db_file=database.IUH_DB_FILE)
    return {"status": "ok", "message": "Đã xóa người nhận!", "target_groups": new_groups}

@app.post("/api/bot3/zalo/test_alert")
def api_bot3_test_zalo_alert():
    from iuh_bot import send_zalo_iuh
    zalo = ZaloDispatcher(CONFIG_IUH_FILE)
    ts = int(time.time())
    now_vn = datetime.now(timezone(timedelta(hours=7)))
    test_act = {
        "activity_id": f"test_{ts}",
        "title": f"Hoạt động thử nghiệm kiểm tra kết nối Bot IUH & Bắn Zalo (#{ts})",
        "semester": "1/2026 - 2027",
        "points": 3.0,
        "deadline": now_vn.strftime("%d-%m-%Y"),
        "status": "Đang mở",
        "slots": "150/150",
        "details": f"Thời gian: {now_vn.strftime('%H:%M:%S %d/%m/%Y')}\nĐịa điểm: Hội trường E4 IUH\nYêu cầu: Tín hiệu thử nghiệm hoạt động hoàn hảo 100%."
    }
    test_targets = [
        {"id": "7456361874031804652", "name": "demo", "type": "GROUP"},
        {"id": "7581087306337796515", "name": "Yuki", "type": "USER"}
    ]
    sent = send_zalo_iuh(zalo, test_act, is_reopened=False, custom_targets=test_targets)
    if sent:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công CHỈ cho riêng Yuki & nhóm demo!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm. Kiểm tra kết nối Zalo hoặc người nhận!")

@app.get("/api/bot3/history")
def api_bot3_get_history(limit: int = 100, page: int = 1, search: Optional[str] = None, target_id: Optional[str] = None):
    history = database.get_delivery_history(limit=limit, page=page, search=search, target_id=target_id, db_file=database.IUH_DB_FILE)
    return {"status": "ok", "data": history}


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard_view():

    cfg = get_config()
    stats = database.get_stats()
    posts = database.get_posts(limit=30)
    targets = cfg.get("targets", [])
    zalo_cfg = cfg.get("zalo", {})
    target_groups = zalo_cfg.get("target_groups", [])
    filter_kws = cfg.get("filter_keywords", [])
    auto_tag_all = zalo_cfg.get("auto_tag_all", True)

    posts_json = json.dumps(posts, ensure_ascii=False)
    targets_json = json.dumps(targets, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)
    target_groups_json = json.dumps(target_groups, ensure_ascii=False)
    filter_kws_json = json.dumps(filter_kws, ensure_ascii=False)

    is_bot_active = stats.get("is_active", True)
    active_class = "bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20" if is_bot_active else "bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20"
    active_text = "🟢 BOT ĐANG CHẠY (BẬT)" if is_bot_active else "🔴 BOT ĐÃ TẮT (TẠM DỪNG)"

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HUIT Feed & Zalo Bot Monitor 24/7</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    .glass {{ background: rgba(255, 255, 255, 0.92); backdrop-filter: blur(12px); }}
    #console-stream::-webkit-scrollbar {{ width: 6px; }}
    #console-stream::-webkit-scrollbar-track {{ background: #0f172a; }}
    #console-stream::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
    #console-stream::-webkit-scrollbar-thumb:hover {{ background: #475569; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP NAVBAR -->
  <header class="glass sticky top-0 z-50 border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-5">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <i class="fa-solid fa-graduation-cap text-lg"></i>
          </div>
          <div>
            <h1 class="font-bold text-lg leading-tight text-slate-900">HUIT Social Feed & Bot (Yuki 1)</h1>
            <p class="text-xs text-slate-500 font-medium">Bóc tách Comet SSR 24/7 & Lọc Form Bắn Zalo</p>
          </div>
        </div>

        <div class="hidden sm:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <a href="/" class="px-3 py-1.5 rounded-lg bg-white text-blue-700 shadow-xs">
            🎓 Bot 1: HUIT (Yuki 1)
          </a>
          <a href="/bot2" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2: VAA (Yuki 2)
          </a>
          <a href="/bot3" class="px-3 py-1.5 rounded-lg text-rose-700 hover:text-rose-900 transition">
            🔴 Bot 3: IUH (Yuki 3)
          </a>
          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
          <a href="/bot5" class="px-3 py-1.5 rounded-lg text-blue-700 hover:text-blue-900 transition">
            🔵 Bot 5: OU (Yuki 5)
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold" title="Đăng xuất khỏi hệ thống">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span class="hidden sm:inline">Thoát</span>
          </a>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE: TRẦN LÊ PHÁT -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-blue-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Yuki</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Admin Active"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-blue-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
                <!-- TEST ZALO 4 BOT MODAL BUTTON -->
        <button onclick="openQuadTestModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho từng nhóm Zalo của 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
        <button id="btn-sync-github-bot1" onclick="syncWithGitHub()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-white hover:bg-slate-100 text-slate-800 border border-slate-200 shadow-xs transition flex items-center gap-2" title="Đồng bộ toàn bộ thay đổi lên GitHub">
          <i class="fa-brands fa-github text-slate-900"></i>
          <span id="github-sync-label-bot1">GitHub Sync</span>
          <span id="github-sync-dot-bot1" class="w-2 h-2 rounded-full bg-emerald-500"></span>
        </button>

        <button id="bot-toggle-btn" onclick="toggleBotPower()" class="px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 {active_class}">
          <span id="bot-toggle-icon" class="w-2.5 h-2.5 rounded-full {'bg-white animate-pulse' if is_bot_active else 'bg-white'}"></span>
          <span id="bot-toggle-text">{active_text}</span>
        </button>

        <button onclick="fetchLatestData()" class="p-2.5 text-slate-500 hover:text-blue-600 rounded-xl hover:bg-slate-100 transition border border-slate-200 shadow-xs" title="Làm mới dữ liệu">
          <i class="fa-solid fa-rotate text-sm"></i>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7 flex-1 w-full space-y-6">

    <!-- STATS CARDS -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tổng Bài Bóc Tách</p>
          <h3 id="stat-total-posts" class="text-3xl font-extrabold text-slate-900 mt-1">{stats['total_posts']}</h3>
          <p class="text-xs text-slate-400 mt-1">Lưu trữ Web & DB</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-newspaper"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Đã Bắn Vào Zalo</p>
          <h3 id="stat-total-zalo" class="text-3xl font-extrabold text-indigo-600 mt-1">{stats['total_zalo_sent']}</h3>
          <p id="stat-zalo-groups-count" class="text-xs text-slate-400 mt-1">{len([g for g in target_groups if g.get('enabled')])} nhóm đang nhận tin</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-paper-plane"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Nguồn Quét (2p30s/vòng)</p>
          <h3 id="stat-total-targets" class="text-3xl font-extrabold text-slate-900 mt-1">{len(targets)}</h3>
          <p class="text-xs text-slate-400 mt-1">13 Fanpage + Group SV</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-bullseye"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vòng Quét Hiện Tại</p>
          <h3 id="stat-scan-cycle" class="text-2xl font-bold text-slate-900 mt-1">Vòng #{stats['scan_cycle']}</h3>
          <p id="stat-last-scan" class="text-xs text-slate-400 mt-1 truncate max-w-[150px]">{stats['last_scan_time']}</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock-rotate-left"></i>
        </div>
      </div>
    </div>

    <!-- TABS NAVIGATION -->
    <div class="flex border-b border-slate-200 space-x-6 overflow-x-auto pb-0.5">
      <button onclick="switchTab('feed')" id="tab-btn-feed" class="pb-3 text-sm font-semibold border-b-2 border-blue-600 text-blue-600 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-stream"></i> Bảng Tin Mới Nhất
      </button>
      <button onclick="switchTab('console')" id="tab-btn-console" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-terminal"></i> Live Console Terminal
      </button>
      <button onclick="switchTab('zalo')" id="tab-btn-zalo" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-comments"></i> Cấu Hình Nhóm Zalo ({len([g for g in target_groups if g.get('enabled')])}/{len(target_groups)})
      </button>
      <button onclick="switchTab('targets')" id="tab-btn-targets" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-link"></i> Quản Lý Nguồn Quét ({len(targets)})
      </button>
      <button onclick="switchTab('history')" id="tab-btn-history" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-clock-rotate-left"></i> 📜 Lịch Sử Bắn Tin ({stats.get('total_zalo_sent', 0)})
      </button>
    </div>

    <!-- TAB 1: FEED VIEW -->
    <div id="tab-feed" class="space-y-6">
      <div class="bg-white p-4 rounded-xl border border-slate-200/80 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div class="relative w-full md:w-80">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
          <input type="text" id="search-input" onkeyup="filterPosts()" placeholder="Tìm kiếm nội dung, tác giả..." class="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div class="flex gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <button onclick="setFilterPage('')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white">Tất cả</button>
          <button onclick="setFilterPage('Group Sinh Viên HUIT')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">Group SV HUIT</button>
          <button onclick="setFilterPage('Đoàn - Hội HUIT')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">ĐTN - HSV</button>
          <button onclick="setFilterPage('Công nghệ Thông tin')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">Khoa CNTT</button>
        </div>
      </div>

      <div id="posts-container" class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- Rendered by JS -->
      </div>
    </div>

    <!-- TAB 2: LIVE CONSOLE LOG -->
    <div id="tab-console" class="hidden space-y-4">
      <div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden flex flex-col">
        <div class="bg-slate-950 px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center space-x-2">
            <span class="w-3 h-3 rounded-full bg-rose-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
            <span class="ml-2 text-xs font-mono text-slate-300 flex items-center gap-2">
              <span class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                LIVE 1s
              </span>
              <span id="liveClockBot1" class="font-mono text-xs font-bold text-emerald-400">--:--:--</span>
            </span>
          </div>

          <!-- Scope Switcher -->
          <div class="flex items-center bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-[11px] font-bold">
            <button onclick="setLogBotScope('HUIT')" id="btnLogScopeHuit" class="px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs">HUIT Bot</button>
            <button onclick="setLogBotScope('ALL')" id="btnLogScopeAll" class="px-2.5 py-1 rounded text-slate-400 hover:text-white transition">🌐 Hợp Nhất 4 Bot</button>
          </div>

          <div class="flex items-center space-x-3">
            <button onclick="toggleBot1LogSort()" id="bot1-sort-btn" class="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition flex items-center gap-1.5" title="Đổi thứ tự log: Mới nhất trên cùng hoặc cũ nhất trên cùng">
              <i class="fa-solid fa-arrow-down-short-wide text-cyan-400"></i>
              <span id="bot1-sort-text">Mới nhất trên</span>
            </button>
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" class="rounded text-blue-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>
            <button onclick="fetchLogs()" class="px-2.5 py-1 text-xs text-blue-400 hover:text-blue-300 bg-blue-950/60 border border-blue-800/60 rounded-md transition">
              <i class="fa-solid fa-rotate"></i>
            </button>
          </div>
        </div>

        <div id="console-stream" class="p-4 font-mono text-xs text-slate-300 h-[520px] overflow-y-auto space-y-1.5 bg-[#0b0f19]">
          <div class="text-slate-500 italic">Đang kết nối luồng nhật ký thời gian thực...</div>
        </div>
      </div>
    </div>

    <!-- TAB 3: ZALO SETTINGS & MULTI-GROUP SELECTION -->
    <div id="tab-zalo" class="hidden space-y-6">
      
      <!-- QUICK FEATURES: TAG ALL & FORM ONLY FILTER -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- AUTO TAG ALL TOGGLE -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-lg">
              <i class="fa-solid fa-at"></i>
            </div>
            <div>
              <h4 class="font-bold text-slate-900 text-sm">Tự Động Tag @All Khi Có Bài</h4>
              <p class="text-xs text-slate-500">Gọi toàn bộ thành viên nhóm để không bỏ lỡ tin.</p>
            </div>
          </div>
          <button id="btn-toggle-tag-all" onclick="toggleTagAll()" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 { 'bg-emerald-50 text-emerald-700 border border-emerald-200' if auto_tag_all else 'bg-slate-100 text-slate-600 border border-slate-300' }">
            <i class="fa-solid { 'fa-toggle-on text-emerald-600 text-base' if auto_tag_all else 'fa-toggle-off text-slate-400 text-base' }"></i>
            <span id="tag-all-status-text">{'BẬT' if auto_tag_all else 'TẮT'}</span>
          </button>
        </div>

        <!-- FORM EXTRACTOR INFO -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-lg">
              <i class="fa-brands fa-google-drive"></i>
            </div>
            <div>
              <h4 class="font-bold text-slate-900 text-sm">Ưu Tiên Link Form Google Doc</h4>
              <p class="text-xs text-slate-500">Tự động bóc tách link forms.gle / gg docs đưa lên đầu.</p>
            </div>
          </div>
          <span class="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            Đã Kích Hoạt
          </span>
        </div>
      </div>

      <!-- KEYWORDS FILTER INFO -->
      <div class="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200/80 rounded-2xl p-5 shadow-xs">
        <div class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-filter"></i>
          </div>
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Bộ Lọc Từ Khóa Bắn Zalo Bắt Buộc</h4>
            <p class="text-xs text-slate-600 mt-1">
              Chỉ bài viết chứa ít nhất một trong các từ khóa sau mới được gửi vào nhóm Zalo (mọi bài khác vẫn lưu Web đầy đủ):
            </p>
            <div class="flex flex-wrap gap-1.5 mt-2.5">
              <span class="px-2.5 py-1 bg-white border border-blue-200 rounded-md text-xs font-semibold text-blue-700">📌 Link đăng ký</span>
              <span class="px-2.5 py-1 bg-white border border-blue-200 rounded-md text-xs font-semibold text-blue-700">📝 Form</span>
              <span class="px-2.5 py-1 bg-white border border-blue-200 rounded-md text-xs font-semibold text-blue-700">✍️ Đăng ký</span>
              <span class="px-2.5 py-1 bg-white border border-blue-200 rounded-md text-xs font-semibold text-blue-700">⭐ Điểm rèn luyện / ĐRL</span>
            </div>
          </div>
        </div>
      </div>

      <!-- GROUP LIST WITH TOGGLE SWITCHES -->
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h4 class="font-bold text-slate-900 text-base">Danh Sách Nhóm Zalo Nhận Thông Báo</h4>
            <p class="text-xs text-slate-500">Bật hoặc tắt nhóm nào bạn muốn nhận tin nhắn tự động.</p>
          </div>
          <button onclick="testSendZaloAlert()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Bắn Thử Tin Nhắn Test (@All)
          </button>
        </div>

        <div id="zalo-groups-list" class="divide-y divide-slate-100">
          <!-- Rendered by JS -->
        </div>
      </div>

      <!-- ADD NEW GROUP SECTION -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Thêm Nhanh Từ Zalo Đang Đăng Nhập</h4>
            <p class="text-xs text-slate-500 mt-0.5">Tải danh sách các nhóm mà tài khoản Zalo của bạn đang tham gia.</p>
          </div>

          <div class="flex gap-2">
            <select id="select-scanned-groups" class="flex-1 px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">-- Bấm "Quét danh sách" để nạp nhóm --</option>
            </select>
            <button onclick="fetchZaloAccountGroups()" class="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition whitespace-nowrap flex items-center gap-1">
              <i class="fa-solid fa-arrows-rotate"></i> Quét
            </button>
          </div>

          <button onclick="handleAddSelectedZaloGroup()" class="w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-plus"></i> Thêm Nhóm Đã Chọn Vào Danh Sách Nhận Tin
          </button>
        </div>

        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Thêm Thủ Công Bằng Group ID</h4>
            <p class="text-xs text-slate-500 mt-0.5">Dán ID Thread nhóm Zalo nếu bạn đã biết trước.</p>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <input type="text" id="manual-group-id" placeholder="ID Nhóm (vd: 7456361874031804652)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 col-span-2">
            <input type="text" id="manual-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm ĐRL K15)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 col-span-2">
          </div>

          <button onclick="handleAddManualZaloGroup()" class="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-check"></i> Lưu Nhóm Thủ Công
          </button>
        </div>
      </div>

      <!-- SECTION: FACEBOOK MESSENGER MULTI-BOT CHANNEL -->
      <div class="bg-white p-6 rounded-2xl border border-blue-200/80 shadow-xs space-y-5">
        <div class="flex items-center justify-between flex-wrap gap-3 pb-3 border-b border-slate-100">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
              <i class="fa-brands fa-facebook-messenger"></i>
            </div>
            <div>
              <h3 class="font-bold text-slate-900 text-sm">Kênh Thông Báo Facebook Messenger (Đồng Bộ 4 Bot)</h3>
              <p class="text-xs text-slate-500">Tự động bắn tin bài mới & hoạt động ĐRL vào nhóm Messenger song song với Zalo.</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span id="msg-cookie-badge" class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <i class="fa-solid fa-circle-check"></i> UID: 61574475721537 (Bảo Nhi)
            </span>
            <button onclick="toggleMessengerMaster()" id="btn-toggle-messenger" class="px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs">
              <i class="fa-solid fa-toggle-on text-sm"></i> Đang BẬT
            </button>
          </div>
        </div>

        <!-- LIST OF MESSENGER GROUPS -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold text-slate-800 text-xs uppercase tracking-wider">Danh Sách Nhóm Messenger Nhận Tin:</h4>
            <button onclick="testSendMessengerAlert()" class="text-xs text-blue-600 hover:underline flex items-center gap-1 font-semibold">
              <i class="fa-solid fa-paper-plane"></i> Thử tin Messenger
            </button>
          </div>
          <div id="messenger-groups-list" class="space-y-2 max-h-52 overflow-y-auto">
            <!-- Rendered by JS -->
          </div>
        </div>

        <!-- ADD NEW MESSENGER GROUP -->
        <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
          <h5 class="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <i class="fa-solid fa-plus-circle text-blue-600"></i> Thêm Nhóm Messenger Mới (Bằng Thread ID)
          </h5>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input type="text" id="manual-msg-thread-id" placeholder="Thread ID (vd: 1773570903700841)" class="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
            <input type="text" id="manual-msg-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm Demo Messenger)" class="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div class="flex justify-between items-center pt-1">
            <span class="text-[11px] text-slate-500">Mẹo: Mở nhóm trên web messenger.com/t/<b>ID_NHÓM</b> để copy Thread ID.</span>
            <button onclick="handleAddManualMessengerGroup()" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition shadow-xs flex items-center gap-1.5">
              <i class="fa-solid fa-plus"></i> Thêm Vào Cả 4 Bot
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 4: TARGET MANAGEMENT -->
    <div id="tab-targets" class="hidden space-y-6">
      <div class="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <h3 class="font-bold text-slate-900 text-base mb-1">Thêm Đường Link Fanpage / Group Cần Quét</h3>
        <p class="text-xs text-slate-500 mb-4">Điền link trang Facebook, hệ thống sẽ tự động quét và bóc tách bài đăng mới 24/7 (với cơ chế lật trang Comet SSR).</p>
        <form onsubmit="handleAddTarget(event)" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input type="text" id="new-target-name" required placeholder="Tên Fanpage / Khoa (vd: CLB Tin Học HUIT)" class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <input type="url" id="new-target-url" required placeholder="https://www.facebook.com/..." class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:col-span-2">
          <div class="sm:col-span-3 flex justify-end">
            <button type="submit" class="px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-xs flex items-center gap-2">
              <i class="fa-solid fa-plus"></i> Thêm Trang Theo Dõi
            </button>
          </div>
        </form>
      </div>

      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h4 class="font-bold text-slate-900 text-sm">Danh Sách Mục Tiêu Đang Quét ({len(targets)})</h4>
        </div>
        <div id="targets-table-body" class="divide-y divide-slate-100">
          <!-- Rendered by JS -->
        </div>
      </div>
    </div>

    <!-- TAB 5: DELIVERY HISTORY (IMMUTABLE) -->
    <div id="tab-history" class="hidden space-y-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-shield-halved text-emerald-600"></i> Lịch Sử Bắn Tin Zalo Bất Biến
              <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Không Thể Bị Xóa</span>
            </h3>
            <p class="text-xs text-slate-500 mt-1">Lưu trữ vĩnh viễn bài viết nào đã cào, bài nào gửi Zalo, vào nhóm/người nhận nào, lúc mấy giờ. Dữ liệu được bảo vệ bằng SQLite Trigger.</p>
          </div>
          <div class="flex items-center gap-3">
            <div class="relative w-64">
              <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
              <input type="text" id="history-search-input" onkeyup="if(event.key==='Enter') fetchDeliveryHistory(1)" placeholder="Tìm bài, nhóm nhận..." class="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <button onclick="fetchDeliveryHistory(1)" class="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-bold rounded-lg transition flex items-center gap-1.5">
              <i class="fa-solid fa-rotate"></i> Làm mới
            </button>
          </div>
        </div>

        <div class="overflow-x-auto mt-4">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">Thời gian bắn tin</th>
                <th class="px-4 py-3">Nguồn Fanpage</th>
                <th class="px-4 py-3">Tiêu đề / Nội dung bài viết</th>
                <th class="px-4 py-3">Đích nhận Zalo</th>
                <th class="px-4 py-3">Trạng thái</th>
                <th class="px-4 py-3 text-center">Liên kết</th>
              </tr>
            </thead>
            <tbody id="history-table-body" class="divide-y divide-slate-100">
              <tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">Đang tải lịch sử...</td></tr>
            </tbody>
          </table>
        </div>

        <div id="history-pagination" class="flex items-center justify-between pt-4 border-t border-slate-100 text-xs text-slate-500">
          <span id="history-page-info">Trang 1</span>
          <div class="flex items-center gap-2">
            <button id="history-prev-btn" onclick="changeHistoryPage(-1)" class="px-3 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50">Trước</button>
            <button id="history-next-btn" onclick="changeHistoryPage(1)" class="px-3 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50">Sau</button>
          </div>
        </div>
      </div>
    </div>

  </main>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    let allPosts = {posts_json};
    let allTargets = {targets_json};
    let allTargetGroups = {target_groups_json};
    let currentFilterPage = '';
    let isBotActive = { 'true' if is_bot_active else 'false' };
    let autoTagAll = { 'true' if auto_tag_all else 'false' };

    function switchTab(tab) {{
      ['feed', 'console', 'zalo', 'targets', 'history'].forEach(t => {{
        const el = document.getElementById('tab-' + t);
        const btn = document.getElementById('tab-btn-' + t);
        if (el) el.classList.add('hidden');
        if (btn) {{
          btn.classList.remove('border-blue-600', 'text-blue-600');
          btn.classList.add('border-transparent', 'text-slate-500');
        }}
      }});
      const targetEl = document.getElementById('tab-' + tab);
      const targetBtn = document.getElementById('tab-btn-' + tab);
      if (targetEl) targetEl.classList.remove('hidden');
      if (targetBtn) {{
        targetBtn.classList.add('border-blue-600', 'text-blue-600');
        targetBtn.classList.remove('border-transparent', 'text-slate-500');
      }}

      if (tab === 'console') {{
        fetchLogs();
      }} else if (tab === 'zalo') {{
        fetchTargetGroups();
      }} else if (tab === 'history') {{
        fetchDeliveryHistory(1);
      }}
    }}

    // ================= BOT ON/OFF TOGGLE =================
    async function toggleBotPower() {{
      const btn = document.getElementById('bot-toggle-btn');
      btn.disabled = true;
      try {{
        const res = await fetch('/api/bot/toggle', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          isBotActive = data.is_active;
          updateBotButtonUI(isBotActive);
          fetchLogs();
        }}
      }} catch (err) {{
        alert('Lỗi thao tác bật/tắt bot: ' + err);
      }} finally {{
        btn.disabled = false;
      }}
    }}

    function updateBotButtonUI(active) {{
      const btn = document.getElementById('bot-toggle-btn');
      const text = document.getElementById('bot-toggle-text');
      const icon = document.getElementById('bot-toggle-icon');

      if (active) {{
        btn.className = 'px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20';
        text.innerText = '🟢 BOT ĐANG CHẠY (BẬT)';
        icon.className = 'w-2.5 h-2.5 rounded-full bg-white animate-pulse';
      }} else {{
        btn.className = 'px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20';
        text.innerText = '🔴 BOT ĐÃ TẮT (TẠM DỪNG)';
        icon.className = 'w-2.5 h-2.5 rounded-full bg-white';
      }}
    }}

    // ================= LIVE CONSOLE LOGS & CLOCK =================
    let currentLogScope = 'HUIT';

    function tickClockBot1() {{
      const el = document.getElementById('liveClockBot1');
      if (el) {{
        const now = new Date();
        el.innerText = now.toTimeString().split(' ')[0];
      }}
    }}
    setInterval(tickClockBot1, 1000);
    tickClockBot1();

    function setLogBotScope(scope) {{
      currentLogScope = scope;
      const btnHuit = document.getElementById('btnLogScopeHuit');
      const btnAll = document.getElementById('btnLogScopeAll');
      if (btnHuit && btnAll) {{
        if (scope === 'HUIT') {{
          btnHuit.className = 'px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs';
          btnAll.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
        }} else {{
          btnAll.className = 'px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs';
          btnHuit.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
        }}
      }}
      fetchLogs();
    }}

    async function fetchLogs() {{
      try {{
        const url = (currentLogScope === 'ALL') ? '/api/all-logs?limit=80' : '/api/logs?limit=80';
        const res = await fetch(url);
        const data = await res.json();
        if (data.status === 'ok') {{
          renderLogs(data.logs || []);
        }}
      }} catch (err) {{
        console.error('Lỗi tải logs:', err);
      }}
    }}

    let bot1LogSortAsc = false; // Mặc định: false (Mới nhất trên cùng)

    function toggleBot1LogSort() {{
      bot1LogSortAsc = !bot1LogSortAsc;
      const btnText = document.getElementById('bot1-sort-text');
      const btnIcon = document.querySelector('#bot1-sort-btn i');
      if (bot1LogSortAsc) {{
        if (btnText) btnText.innerText = 'Cũ nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-up-short-wide text-amber-400';
      }} else {{
        if (btnText) btnText.innerText = 'Mới nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-down-short-wide text-cyan-400';
      }}
      fetchLogs();
    }}

    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      // Nếu bot1LogSortAsc = true (Cũ nhất trên) -> reverse; ngược lại giữ nguyên DESC (Mới nhất trên)
      const sortedLogs = bot1LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = sortedLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-indigo-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        // Xóa timestamp trùng lặp trong nội dung message
        let cleanMsg = String(l.message || '');
        cleanMsg = cleanMsg.replace(/^(\S+\s*)?\[\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\]\s*/, '$1');
        cleanMsg = cleanMsg.replace(/^\[\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\]\s*/, '');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{cleanMsg}}</span>
          </div>
        `;
      }}).join('');

      if (bot1LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}

    function clearConsoleView() {{
      document.getElementById('console-stream').innerHTML = '<div class="text-slate-500">Màn hình đã xóa. Đang chờ log tiếp theo...</div>';
    }}

    // ================= POSTS RENDERING =================
    function renderPosts(posts) {{
      const container = document.getElementById('posts-container');
      if (!posts || posts.length === 0) {{
        container.innerHTML = `
          <div class="col-span-full py-16 text-center text-slate-400">
            <i class="fa-solid fa-inbox text-4xl mb-3 text-slate-300"></i>
            <p class="font-medium">Chưa có bài viết nào được ghi nhận.</p>
            <p class="text-xs text-slate-400 mt-1">Bot đang chạy quét Facebook trong nền...</p>
          </div>
        `;
        return;
      }}

      container.innerHTML = posts.map(p => `
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between gap-2 mb-3">
              <span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-100">
                ${{p.page_name || 'Fanpage'}}
              </span>
              <span class="text-xs text-slate-400 flex items-center gap-1">
                <i class="fa-regular fa-clock"></i> ${{p.posted_time || p.crawled_at || ''}}
              </span>
            </div>

            <div class="flex items-center gap-2 mb-3">
              <div class="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold">
                ${{(p.author || 'U')[0]}}
              </div>
              <span class="text-xs font-bold text-slate-800">${{p.author || 'Người đăng ẩn danh'}}</span>
            </div>

            <p class="text-sm text-slate-700 leading-relaxed whitespace-pre-line mb-4 line-clamp-6">
              ${{p.content}}
            </p>
          </div>

          <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <div class="flex items-center gap-2">
              ${{p.is_sent_zalo ? '<span class="text-emerald-600 font-semibold flex items-center gap-1"><i class="fa-solid fa-check-circle"></i> Đã gửi Zalo</span>' : '<span class="text-slate-400">Không khớp bộ lọc từ khóa</span>'}}
            </div>
            ${{p.post_url ? `
              <a href="${{p.post_url}}" target="_blank" rel="noopener noreferrer" class="font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1">
                Xem trên Facebook <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
              </a>
            ` : ''}}
          </div>
        </div>
      `).join('');
    }}

    function filterPosts() {{
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const filtered = allPosts.filter(p => {{
        const matchText = (p.content || '').toLowerCase().includes(q) || (p.author || '').toLowerCase().includes(q);
        const matchPage = !currentFilterPage || (p.page_name || '').toLowerCase().includes(currentFilterPage.toLowerCase());
        return matchText && matchPage;
      }});
      renderPosts(filtered);
    }}

    function setFilterPage(page) {{
      currentFilterPage = page;
      document.querySelectorAll('.page-filter-btn').forEach(btn => {{
        if (btn.innerText.includes(page) || (page === '' && btn.innerText === 'Tất cả')) {{
          btn.className = 'page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white';
        }} else {{
          btn.className = 'page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200';
        }}
      }});
      filterPosts();
    }}

    // ================= TARGETS RENDERING =================
    function renderTargets(targets) {{
      const container = document.getElementById('targets-table-body');
      if (!targets || targets.length === 0) {{
        container.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Chưa có nguồn theo dõi nào.</div>';
        return;
      }}
      container.innerHTML = targets.map((t, idx) => `
        <div class="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition">
          <div class="flex items-center gap-3">
            <span class="w-6 text-xs text-slate-400 font-bold">${{idx + 1}}</span>
            <div>
              <p class="text-sm font-bold text-slate-900">${{t.name}}</p>
              <a href="${{t.url}}" target="_blank" class="text-xs text-blue-600 hover:underline truncate max-w-md block">${{t.url}}</a>
            </div>
          </div>
          <button onclick="handleDeleteTarget('${{t.id}}')" class="p-2 text-rose-500 hover:bg-rose-50 rounded-lg transition" title="Xóa nguồn này">
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </div>
      `).join('');
    }}

    async function handleAddTarget(e) {{
      e.preventDefault();
      const name = document.getElementById('new-target-name').value;
      const url = document.getElementById('new-target-url').value;
      const formData = new FormData();
      formData.append('name', name);
      formData.append('url', url);

      const res = await fetch('/api/targets', {{ method: 'POST', body: formData }});
      if (res.ok) {{
        document.getElementById('new-target-name').value = '';
        document.getElementById('new-target-url').value = '';
        fetchLatestData();
      }}
    }}

    async function handleDeleteTarget(id) {{
      if (!confirm('Bạn có chắc muốn xóa nguồn này không?')) return;
      const res = await fetch('/api/targets/' + id, {{ method: 'DELETE' }});
      if (res.ok) fetchLatestData();
    }}

    // ================= ZALO GROUPS MANAGEMENT =================
    function renderTargetGroups(groups) {{
      const container = document.getElementById('zalo-groups-list');
      if (!groups || groups.length === 0) {{
        container.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Chưa cấu hình nhóm Zalo nào.</div>';
        return;
      }}

      container.innerHTML = groups.map(g => `
        <div class="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl ${{g.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-400'}} flex items-center justify-center font-bold text-sm">
              <i class="fa-solid ${{g.type === 'USER' ? 'fa-user' : 'fa-users'}}"></i>
            </div>
            <div>
              <p class="text-sm font-bold text-slate-900 flex items-center gap-2">
                ${{g.name}}
                ${{g.type === 'USER' ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">Cá nhân</span>' : ''}}
                ${{g.enabled ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">Đang nhận tin</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-200 text-slate-600">Đã tắt</span>'}}
              </p>
              <p class="text-xs text-slate-400 font-mono">${{g.type === 'USER' ? 'Zalo UID' : 'Thread ID'}}: ${{g.id}}</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot1')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">
              <i class="fa-solid ${{g.enabled ? 'fa-toggle-on text-emerald-600 text-base' : 'fa-toggle-off text-slate-400 text-base'}}"></i>
              ${{g.enabled ? 'BẬT' : 'TẮT'}}
            </button>
            <button onclick="deleteZaloGroup('${{g.id}}')" class="p-2 text-rose-500 hover:bg-rose-50 rounded-lg transition" title="Xóa khỏi danh sách">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </div>
        </div>
      `).join('');
    }}

    async function toggleZaloGroup(groupId) {{
      const cur = allTargetGroups.find(g => String(g.id) === String(groupId));
      const targetState = cur ? !cur.enabled : true;

      // Optimistic update giao diện ngay lập tức
      if (cur) cur.enabled = targetState;
      renderTargetGroups(allTargetGroups);
      updateZaloStatsBadge();

      const fd = new FormData();
      fd.append('group_id', groupId);
      fd.append('enabled', targetState ? 'true' : 'false');
      try {{
        const res = await fetch('/api/zalo/toggle_group', {{ method: 'POST', body: fd }});
        const data = await res.json();
        if (data.status === 'ok') {{
          allTargetGroups = data.target_groups;
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }} else {{
          alert('Lỗi: ' + (data.detail || 'Không thể đổi trạng thái'));
          fetchTargetGroups();
        }}
      }} catch (err) {{
        alert('Lỗi kết nối khi đổi trạng thái nhóm: ' + err);
        fetchTargetGroups();
      }}
    }}

    async function fetchTargetGroups() {{
      try {{
        const res = await fetch('/api/zalo/target_groups');
        const data = await res.json();
        if (data.status === 'ok') {{
          allTargetGroups = data.target_groups;
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }}
      }} catch (err) {{
        console.error('Lỗi nạp nhóm Zalo:', err);
      }}
    }}

    async function toggleTagAll() {{
      try {{
        const res = await fetch('/api/zalo/toggle_tag_all', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          autoTagAll = data.auto_tag_all;
          const btn = document.getElementById('btn-toggle-tag-all');
          const txt = document.getElementById('tag-all-status-text');
          if (autoTagAll) {{
            btn.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200';
            btn.innerHTML = '<i class="fa-solid fa-toggle-on text-emerald-600 text-base"></i> <span>BẬT</span>';
          }} else {{
            btn.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-100 text-slate-600 border border-slate-300';
            btn.innerHTML = '<i class="fa-solid fa-toggle-off text-slate-400 text-base"></i> <span>TẮT</span>';
          }}
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function deleteZaloGroup(groupId) {{
      if (!confirm('Bạn có chắc muốn xóa nhóm này khỏi danh sách nhận tin?')) return;
      try {{
        const res = await fetch('/api/zalo/target_groups/' + groupId, {{ method: 'DELETE' }});
        if (res.ok) {{
          allTargetGroups = allTargetGroups.filter(g => String(g.id) !== String(groupId));
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }}
      }} catch (err) {{
        alert('Lỗi xóa nhóm: ' + err);
      }}
    }}

    async function fetchZaloAccountGroups() {{
      const select = document.getElementById('select-scanned-groups');
      select.innerHTML = '<option value="">Đang tải danh sách từ Zalo...</option>';
      try {{
        const res = await fetch('/api/zalo/groups');
        const data = await res.json();
        if (data.groups && data.groups.length > 0) {{
          select.innerHTML = data.groups.map(g => `<option value="${{g.id}}" data-name="${{g.name}}">${{g.name}} (${{g.id}})</option>`).join('');
        }} else {{
          select.innerHTML = '<option value="">Không tìm thấy nhóm nào</option>';
        }}
      }} catch (err) {{
        select.innerHTML = '<option value="">Lỗi nạp nhóm</option>';
      }}
    }}

    async function handleAddSelectedZaloGroup() {{
      const select = document.getElementById('select-scanned-groups');
      const opt = select.options[select.selectedIndex];
      if (!opt || !opt.value) return alert('Vui lòng chọn 1 nhóm từ danh sách');

      const fd = new FormData();
      fd.append('group_id', opt.value);
      fd.append('group_name', opt.getAttribute('data-name') || opt.value);

      const res = await fetch('/api/zalo/add_group', {{ method: 'POST', body: fd }});
      const data = await res.json();
      if (data.status === 'ok') {{
        allTargetGroups = data.target_groups;
        renderTargetGroups(allTargetGroups);
        updateZaloStatsBadge();
        alert('Đã thêm nhóm thành công!');
      }}
    }}

    async function handleAddManualZaloGroup() {{
      const gid = document.getElementById('manual-group-id').value.trim();
      const gname = document.getElementById('manual-group-name').value.trim();
      if (!gid || !gname) return alert('Vui lòng nhập cả ID và Tên nhóm');

      const fd = new FormData();
      fd.append('group_id', gid);
      fd.append('group_name', gname);

      const res = await fetch('/api/zalo/add_group', {{ method: 'POST', body: fd }});
      const data = await res.json();
      if (data.status === 'ok') {{
        allTargetGroups = data.target_groups;
        renderTargetGroups(allTargetGroups);
        updateZaloStatsBadge();
        document.getElementById('manual-group-id').value = '';
        document.getElementById('manual-group-name').value = '';
        alert('Đã thêm nhóm thành công!');
      }}
    }}

    async function testSendZaloAlert() {{
      if (!confirm('Gửi tin nhắn mẫu thử nghiệm tới TẤT CẢ các nhóm Zalo đang được BẬT?')) return;
      try {{
        const res = await fetch('/api/zalo/test_alert', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          alert('✅ ' + data.message);
          fetchLogs();
        }} else {{
          alert('❌ ' + (data.message || 'Lỗi gửi tin'));
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    function updateZaloStatsBadge() {{
      const enabledCount = allTargetGroups.filter(g => g.enabled).length;
      document.getElementById('stat-zalo-groups-count').innerText = enabledCount + ' nhóm đang nhận tin';
      document.getElementById('tab-btn-zalo').innerHTML = `<i class="fa-solid fa-comments"></i> Cấu Hình Nhóm Zalo (${{enabledCount}}/${{allTargetGroups.length}})`;
    }}

    // ================= DELIVERY HISTORY (IMMUTABLE) =================
    let currentHistoryPage = 1;
    let totalHistoryPages = 1;

    async function fetchDeliveryHistory(page = 1) {{
      currentHistoryPage = page;
      const qInput = document.getElementById('history-search-input');
      const q = qInput ? qInput.value.trim() : '';
      const tbody = document.getElementById('history-table-body');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Đang tải dữ liệu...</td></tr>';
      try {{
        const url = `/api/history?page=${{page}}&limit=20${{q ? '&search=' + encodeURIComponent(q) : ''}}`;
        const res = await fetch(url);
        const data = await res.json();
        renderDeliveryHistory(data);
      }} catch (err) {{
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-rose-500">Lỗi tải lịch sử: ${{err}}</td></tr>`;
      }}
    }}

    function renderDeliveryHistory(data) {{
      const tbody = document.getElementById('history-table-body');
      const items = data.items || [];
      const total = data.total || 0;
      const limit = data.limit || 20;
      totalHistoryPages = Math.ceil(total / limit) || 1;

      const pageInfo = document.getElementById('history-page-info');
      if (pageInfo) pageInfo.innerText = `Trang ${{currentHistoryPage}} / ${{totalHistoryPages}} (Tổng cộng ${{total}} lượt phát tin)`;

      const prevBtn = document.getElementById('history-prev-btn');
      const nextBtn = document.getElementById('history-next-btn');
      if (prevBtn) prevBtn.disabled = (currentHistoryPage <= 1);
      if (nextBtn) nextBtn.disabled = (currentHistoryPage >= totalHistoryPages);

      if (!items || items.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">Chưa có lịch sử phát tin nào phù hợp.</td></tr>';
        return;
      }}

      tbody.innerHTML = items.map(item => {{
        const isSuccess = (item.status || '').toUpperCase() === 'SUCCESS';
        const statusBadge = isSuccess
          ? '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800"><i class="fa-solid fa-check"></i> Đã gửi</span>'
          : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800" title="${{item.status}}"><i class="fa-solid fa-triangle-exclamation"></i> Thất bại</span>`;

        const isUser = item.target_type === 'USER';
        const targetBadge = isUser
          ? '<span class="px-1.5 py-0.5 text-[9px] font-semibold bg-blue-100 text-blue-700 rounded ml-1">Cá nhân</span>'
          : '<span class="px-1.5 py-0.5 text-[9px] font-semibold bg-slate-100 text-slate-600 rounded ml-1">Nhóm</span>';

        const formBadge = item.has_form 
          ? '<span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-bold bg-amber-100 text-amber-800 rounded mt-1"><i class="fa-brands fa-google-drive"></i> Có Form Đăng Ký</span>'
          : '';

        const kwBadge = item.matched_keyword
          ? `<span class="text-[10px] text-slate-400">Từ khóa: <code class="text-blue-600 bg-blue-50 px-1 py-0.5 rounded font-mono">${{item.matched_keyword}}</code></span>`
          : '';

        return `
          <tr class="hover:bg-slate-50 transition">
            <td class="px-4 py-3 whitespace-nowrap text-slate-500 font-mono text-[11px]">
              <i class="fa-regular fa-clock mr-1 text-slate-400"></i> ${{item.sent_at || ''}}
            </td>
            <td class="px-4 py-3">
              <div class="font-bold text-slate-800">${{item.source_page || 'Ẩn danh'}}</div>
              <div class="text-[10px] text-slate-400">${{item.author || ''}}</div>
            </td>
            <td class="px-4 py-3 max-w-xs">
              <div class="font-semibold text-slate-900 line-clamp-1">${{item.post_title || 'Bài viết mới'}}</div>
              <div class="text-[11px] text-slate-500 line-clamp-2 mt-0.5">${{item.content_snippet || ''}}</div>
              <div class="flex items-center gap-2 mt-1">
                ${{formBadge}}
                ${{kwBadge}}
              </div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="font-bold text-slate-800 flex items-center">
                ${{item.zalo_target_name || item.zalo_target_id}}
                ${{targetBadge}}
              </div>
              <div class="text-[10px] text-slate-400 font-mono">ID: ${{item.zalo_target_id}}</div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              ${{statusBadge}}
            </td>
            <td class="px-4 py-3 text-center whitespace-nowrap">
              ${{item.post_url ? `
                <a href="${{item.post_url}}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition">
                  <i class="fa-brands fa-facebook"></i> Xem
                </a>
              ` : '<span class="text-slate-300">-</span>'}}
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function changeHistoryPage(delta) {{
      const newPage = currentHistoryPage + delta;
      if (newPage >= 1 && newPage <= totalHistoryPages) {{
        fetchDeliveryHistory(newPage);
      }}
    }}

    // ================= DATA REFRESH LOOP =================
    async function fetchLatestData() {{
      try {{
        const [postsRes, statsRes, targetsRes, logsRes, groupsRes] = await Promise.all([
          fetch('/api/posts?limit=50'),
          fetch('/api/stats'),
          fetch('/api/targets'),
          fetch('/api/logs?limit=80'),
          fetch('/api/zalo/target_groups')
        ]);
        const postsData = await postsRes.json();
        const statsData = await statsRes.json();
        const targetsData = await targetsRes.json();
        const logsData = await logsRes.json();
        const groupsData = await groupsRes.json();

        allPosts = postsData.data || [];
        allTargets = targetsData.targets || [];
        if (groupsData && groupsData.target_groups) {{
          allTargetGroups = groupsData.target_groups;
          updateZaloStatsBadge();
        }}

        document.getElementById('stat-total-posts').innerText = statsData.total_posts;
        document.getElementById('stat-total-zalo').innerText = statsData.total_zalo_sent;
        document.getElementById('stat-total-targets').innerText = allTargets.length;
        document.getElementById('stat-scan-cycle').innerText = 'Vòng #' + statsData.scan_cycle;
        document.getElementById('stat-last-scan').innerText = statsData.last_scan_time;

        isBotActive = statsData.is_active;
        updateBotButtonUI(isBotActive);

        filterPosts();
        renderTargets(allTargets);
        renderLogs(logsData.logs || []);
      }} catch (err) {{
        console.error('Lỗi cập nhật định kỳ:', err);
      }}
    }}

    async function syncWithGitHub() {{
      const btn = document.getElementById('btn-sync-github-bot1');
      const label = document.getElementById('github-sync-label-bot1');
      const dot = document.getElementById('github-sync-dot-bot1');
      if (label) label.innerText = 'Đang đồng bộ...';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-ping';
      try {{
        const res = await fetch('/api/github/sync', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          if (label) label.innerText = 'Đã đồng bộ!';
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
          alert('☁️ Đã đồng bộ toàn bộ mã nguồn & dữ liệu lên GitHub thành công!\\n' + (data.message || ''));
        }} else {{
          if (label) label.innerText = 'Lỗi sync';
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
          alert('⚠️ Lỗi đồng bộ: ' + (data.message || 'Thất bại'));
        }}
      }} catch (e) {{
        if (label) label.innerText = 'Lỗi kết nối';
        if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
        alert('⚠️ Không thể kết nối tới GitHub API: ' + e);
      }}
      setTimeout(() => {{
        if (label) label.innerText = 'GitHub Sync';
        if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
      }}, 3000);
    }}

    // ================= FACEBOOK MESSENGER SENDER & GROUPS =================
    let allMessengerGroups = [];

    async function fetchMessengerGroups() {{
      try {{
        const res = await fetch('/api/messenger/status');
        const data = await res.json();
        allMessengerGroups = data.target_groups || [];
        renderMessengerGroups(allMessengerGroups);
        const btn = document.getElementById('btn-toggle-messenger');
        if (btn) {{
          if (data.enabled) {{
            btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs";
            btn.innerHTML = '<i class="fa-solid fa-toggle-on text-sm"></i> Đang BẬT';
          }} else {{
            btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-200 text-slate-700 hover:bg-slate-300 shadow-xs";
            btn.innerHTML = '<i class="fa-solid fa-toggle-off text-sm"></i> Đang TẮT';
          }}
        }}
      }} catch (err) {{
        console.error('Lỗi nạp nhóm Messenger:', err);
      }}
    }}

    function renderMessengerGroups(groups) {{
      const container = document.getElementById('messenger-groups-list');
      if (!container) return;
      if (!groups || groups.length === 0) {{
        container.innerHTML = '<div class="text-xs text-slate-400 py-3 text-center">Chưa có nhóm Messenger nào. Hãy dán Thread ID bên dưới để thêm.</div>';
        return;
      }}
      container.innerHTML = groups.map(g => `
        <div class="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-xs hover:border-blue-300 transition">
          <div class="flex items-center gap-2.5">
            <input type="checkbox" onchange="handleToggleMessengerGroup('${{g.id}}')" ${{g.enabled ? 'checked' : ''}} class="rounded text-blue-600 border-slate-300 focus:ring-blue-500 w-4 h-4 cursor-pointer">
            <div>
              <div class="font-bold text-slate-800 flex items-center gap-1.5">
                <i class="fa-brands fa-facebook-messenger text-blue-600"></i>
                <span>${{g.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">Thread ID: ${{g.id}}</div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="testSendMessengerAlert('${{g.id}}')" class="px-2.5 py-1 text-[11px] font-semibold bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-md transition" title="Gửi tin thử nghiệm vào nhóm này">
              <i class="fa-solid fa-paper-plane mr-1"></i> Thử tin
            </button>
            <button onclick="handleDeleteMessengerGroup('${{g.id}}')" class="px-2 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 rounded-md transition" title="Xóa nhóm">
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </div>
      `).join('');
    }}

    async function toggleMessengerMaster() {{
      try {{
        const res = await fetch('/api/messenger/toggle', {{ method: 'POST' }});
        const data = await res.json();
        alert(data.message);
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleAddManualMessengerGroup() {{
      const tid = document.getElementById('manual-msg-thread-id').value.trim();
      const tname = document.getElementById('manual-msg-group-name').value.trim();
      if (!tid) return alert('Vui lòng nhập Thread ID của nhóm Messenger!');

      try {{
        const res = await fetch('/api/messenger/groups/add', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: tid, name: tname }})
        }});
        const data = await res.json();
        alert(data.message);
        document.getElementById('manual-msg-thread-id').value = '';
        document.getElementById('manual-msg-group-name').value = '';
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleToggleMessengerGroup(threadId) {{
      try {{
        const res = await fetch('/api/messenger/groups/toggle', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId }})
        }});
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleDeleteMessengerGroup(threadId) {{
      if (!confirm('Bạn có chắc muốn xóa nhóm Messenger này khỏi danh sách nhận tin?')) return;
      try {{
        const res = await fetch('/api/messenger/groups/delete', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId }})
        }});
        const data = await res.json();
        alert(data.message);
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function testSendMessengerAlert(threadId) {{
      try {{
        const res = await fetch('/api/messenger/test', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId || null }})
        }});
        const data = await res.json();
        if (data.status === 'ok') {{
          alert('✅ ' + data.message);
        }} else {{
          alert('❌ ' + (data.message || 'Lỗi gửi tin thử nghiệm'));
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    renderPosts(allPosts);
    renderTargets(allTargets);
    renderTargetGroups(allTargetGroups);
    fetchMessengerGroups();
    fetchLogs();

    setInterval(fetchLogs, 1000);
    setInterval(fetchLatestData, 15000);
  </script>

  <!-- ==================== QUAD BOT ZALO TEST MODAL ==================== -->
  <div id="quad-test-modal" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden flex items-center justify-center p-4" style="z-index: 9999;">
    <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-800">
      <!-- Header -->
      <div class="p-4 px-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-md shadow-indigo-500/20">
            <i class="fa-solid fa-vial-circle-check"></i>
          </div>
          <div>
            <h3 class="font-bold text-slate-900 text-base leading-tight">Bắn Tin Nhắn Test Zalo (4 Bot Yuki)</h3>
            <p class="text-xs text-slate-500">Kiểm tra kết nối và gửi tin test riêng lẻ từng nhóm hoặc tất cả nhóm</p>
          </div>
        </div>
        <button onclick="closeQuadTestModal()" class="w-8 h-8 rounded-lg bg-white/80 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition font-bold text-lg">
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 overflow-y-auto space-y-4 flex-1">
        <!-- 4 Bot Selector Tabs -->
        <div class="grid grid-cols-4 gap-2 bg-slate-100 p-1.5 rounded-xl text-xs font-bold text-center">
          <button id="quad-tab-bot1" onclick="switchQuadTestBot('bot1')" class="py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition">
            🎓 Bot 1 (HUIT)
          </button>
          <button id="quad-tab-bot2" onclick="switchQuadTestBot('bot2')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2 (VAA)
          </button>
          <button id="quad-tab-bot3" onclick="switchQuadTestBot('bot3')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🔴 Bot 3 (IUH)
          </button>
          <button id="quad-tab-bot4" onclick="switchQuadTestBot('bot4')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🏛️ Bot 4 (UFM)
          </button>
        </div>

        <!-- Custom message input -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Nội dung tin nhắn test (Để trống để dùng mẫu chuẩn @All):</label>
          <input type="text" id="quad-custom-msg" placeholder="Ví dụ: 🔔 Bot test tín hiệu Zalo hoạt động tốt..." class="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
        </div>

        <!-- Action bar for selected bot -->
        <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div>
            <span id="quad-bot-title" class="text-xs font-bold text-slate-800">Bot 1 - HUIT</span>
            <span id="quad-groups-summary" class="text-[11px] text-slate-500 ml-2">Đang tải...</span>
          </div>
          <button id="btn-test-all-quad" onclick="triggerTestAllForCurrentBot()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Gửi Test Tất Cả Nhóm
          </button>
        </div>

        <!-- Target Groups List -->
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-700">Danh sách nhóm mục tiêu của Bot này (Bấm "Gửi Test" từng nhóm):</label>
          <div id="quad-groups-list" class="space-y-2 max-h-64 overflow-y-auto pr-1">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Live status / log output -->
        <div id="quad-test-status" class="hidden p-3 rounded-xl text-xs font-medium border"></div>
      </div>

      <!-- Footer -->
      <div class="p-3 px-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
        <span>💡 Lệnh trong Zalo: <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/test &lt;tên nhóm&gt;</code> hoặc <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/testall</code></span>
        <button onclick="closeQuadTestModal()" class="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl transition">
          Đóng
        </button>
      </div>
    </div>
  </div>

  <script>
    let currentQuadBot = 'bot1';
    let quadBotsData = {{}};

    async function sendTestToSingleGroup(targetId, targetName, targetType, botId) {{
      if (!confirm('🧪 Bạn có chắc muốn gửi tin nhắn TEST vào: ' + (targetName || targetId) + ' (ID: ' + targetId + ')?')) return;
      try {{
        const res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName
          }})
        }});
        const data = await res.json();
        if (res.ok && data.success) {{
          alert('✅ ' + data.message);
        }} else {{
          alert('❌ ' + (data.detail || data.message || 'Lỗi gửi tin test'));
        }}
      }} catch (err) {{
        alert('Lỗi gửi tin test: ' + err);
      }}
    }}

    async function openQuadTestModal(botId) {{
      if (!botId) botId = 'bot1';
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.remove('hidden');
      await loadQuadTargetGroups();
      switchQuadTestBot(botId);
    }}

    function closeQuadTestModal() {{
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.add('hidden');
    }}

    async function loadQuadTargetGroups() {{
      try {{
        const res = await fetch('/api/zalo/quad-target-groups');
        const data = await res.json();
        if (data.status === 'ok') {{
          data.bots.forEach(function(b) {{
            quadBotsData[b.bot_id] = b;
          }});
        }}
      }} catch (err) {{
        console.error('Lỗi tải danh sách nhóm quad:', err);
      }}
    }}

    function switchQuadTestBot(botId) {{
      currentQuadBot = botId;
      var botTabs = ['bot1', 'bot2', 'bot3', 'bot4'];
      for (var i = 0; i < botTabs.length; i++) {{
        var b = botTabs[i];
        var tab = document.getElementById('quad-tab-' + b);
        if (tab) {{
          if (b === botId) {{
            tab.className = 'py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition';
          }} else {{
            tab.className = 'py-2 rounded-lg text-slate-600 hover:text-slate-900 transition';
          }}
        }}
      }}

      var botData = quadBotsData[botId];
      if (!botData) return;

      var titleEl = document.getElementById('quad-bot-title');
      if (titleEl) titleEl.innerText = botData.bot_name;

      var groups = botData.groups || [];
      var enabledCount = 0;
      for (var j = 0; j < groups.length; j++) {{
        if (groups[j].enabled) enabledCount++;
      }}
      var summaryEl = document.getElementById('quad-groups-summary');
      if (summaryEl) summaryEl.innerText = '(' + enabledCount + '/' + groups.length + ' nhóm đang bật)';

      var container = document.getElementById('quad-groups-list');
      if (!container) return;

      if (groups.length === 0) {{
        container.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs bg-slate-50 rounded-xl">Chưa cấu hình nhóm Zalo nào cho Bot này.</div>';
        return;
      }}

      var itemsHtml = '';
      for (var k = 0; k < groups.length; k++) {{
        var g = groups[k];
        var isUser = (g.type || '').toUpperCase() === 'USER';
        var typeBadge = isUser ? '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded-full">Cá nhân</span>' : '<span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full">Nhóm</span>';
        var statusBadge = g.enabled ? '<span class="text-[10px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">Đang nhận tin</span>' : '<span class="text-[10px] bg-slate-200 text-slate-600 font-semibold px-2 py-0.5 rounded-full">Đã tắt</span>';
        var iconClass = isUser ? 'fa-user' : 'fa-users';
        var bgClass = g.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-400';

        itemsHtml += '<div class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between transition">' +
          '<div class="flex items-center gap-3">' +
            '<div class="w-9 h-9 rounded-xl ' + bgClass + ' flex items-center justify-center font-bold text-sm">' +
              '<i class="fa-solid ' + iconClass + '"></i>' +
            '</div>' +
            '<div>' +
              '<div class="flex items-center gap-2">' +
                '<span class="text-xs font-bold text-slate-900">' + g.name + '</span>' +
                typeBadge + statusBadge +
              '</div>' +
              '<div class="text-[11px] text-slate-400 font-mono mt-0.5">ID: ' + g.id + '</div>' +
            '</div>' +
          '</div>' +
          '<button onclick="sendTestFromQuadModal('' + g.id + '', '' + (g.name || g.id).replace(/'/g, "\'") + '', '' + (g.type || 'GROUP') + '', '' + botId + '')" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5">' +
            '<i class="fa-solid fa-paper-plane text-xs"></i> Gửi Test' +
          '</button>' +
        '</div>';
      }}
      container.innerHTML = itemsHtml;
    }}

    async function sendTestFromQuadModal(targetId, targetName, targetType, botId) {{
      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test tới "' + targetName + '" (' + targetId + ')...';
      }}

      var customMsg = '';
      var inputEl = document.getElementById('quad-custom-msg');
      if (inputEl && inputEl.value) {{
        customMsg = inputEl.value.trim();
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName,
            custom_message: customMsg || null
          }})
        }});
        var data = await res.json();
        if (res.ok && data.success) {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Thành công!</b> ' + data.message;
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || data.message || 'Không thể gửi tin');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}

    async function triggerTestAllForCurrentBot() {{
      var botName = (quadBotsData[currentQuadBot] && quadBotsData[currentQuadBot].bot_name) || currentQuadBot;
      if (!confirm('Bạn có chắc muốn gửi tin nhắn TEST tới TẤT CẢ các nhóm đang bật của ' + botName + '?')) return;

      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test lần lượt tới các nhóm...';
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-all-groups', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ bot_id: currentQuadBot }})
        }});
        var data = await res.json();
        if (res.ok && data.status === 'ok') {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Hoàn tất!</b> Đã gửi thành công ' + data.success_count + '/' + data.total + ' nhóm của ' + data.bot_name + '.';
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || 'Không thể gửi test tất cả');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}
  </script>

</body>
</html>
"""
    return html_content


@app.api_route("/bot2", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard_view_bot2():
    cfg = get_config_bot2()
    stats = database.get_stats(db_file=database.BOT2_DB_FILE)
    posts = database.get_posts(limit=30, db_file=database.BOT2_DB_FILE)
    targets = cfg.get("targets", [])
    zalo_cfg = cfg.get("zalo", {})
    target_groups = zalo_cfg.get("target_groups", [])
    filter_kws = cfg.get("filter_keywords", [])
    auto_tag_all = zalo_cfg.get("auto_tag_all", True)
    fb_cookies = cfg.get("fb_cookies", {})
    c_user_val = fb_cookies.get("c_user", "Chưa cấu hình")

    posts_json = json.dumps(posts, ensure_ascii=False)
    targets_json = json.dumps(targets, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)
    target_groups_json = json.dumps(target_groups, ensure_ascii=False)
    filter_kws_json = json.dumps(filter_kws, ensure_ascii=False)

    is_bot_active = stats.get("is_active", True)
    active_class = "bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20" if is_bot_active else "bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20"
    active_text = "🟢 BOT 2 (VAA) ĐANG CHẠY" if is_bot_active else "🔴 BOT 2 (VAA) ĐÃ TẮT"

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VAA Feed & Zalo Bot Monitor 24/7 (Yuki 2)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    .glass {{ background: rgba(255, 255, 255, 0.92); backdrop-filter: blur(12px); }}
    #console-stream::-webkit-scrollbar {{ width: 6px; }}
    #console-stream::-webkit-scrollbar-track {{ background: #0f172a; }}
    #console-stream::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
    #console-stream::-webkit-scrollbar-thumb:hover {{ background: #475569; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP NAVBAR -->
  <header class="glass sticky top-0 z-50 border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-5">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-blue-700 flex items-center justify-center text-white shadow-md shadow-sky-500/20">
            <i class="fa-solid fa-plane-departure text-lg"></i>
          </div>
          <div>
            <h1 class="font-bold text-lg leading-tight text-slate-900">VAA Social Feed & Bot (Yuki 2)</h1>
            <p class="text-xs text-slate-500 font-medium">Bóc tách Comet SSR 24/7 & Lọc Form Bắn Zalo</p>
          </div>
        </div>

        <div class="hidden sm:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <a href="/" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🎓 Bot 1: HUIT (Yuki 1)
          </a>
          <a href="/bot2" class="px-3 py-1.5 rounded-lg bg-white text-sky-700 shadow-xs">
            ✈️ Bot 2: VAA (Yuki 2)
          </a>
          <a href="/bot3" class="px-3 py-1.5 rounded-lg text-rose-700 hover:text-rose-900 transition">
            🔴 Bot 3: IUH (Yuki 3)
          </a>
          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
          <a href="/bot5" class="px-3 py-1.5 rounded-lg text-blue-700 hover:text-blue-900 transition">
            🔵 Bot 5: OU (Yuki 5)
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold" title="Đăng xuất khỏi hệ thống">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span class="hidden sm:inline">Thoát</span>
          </a>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE: TRẦN LÊ PHÁT -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-sky-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Yuki</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Admin Active"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-sky-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
                <!-- TEST ZALO 4 BOT MODAL BUTTON -->
        <button onclick="openQuadTestModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho từng nhóm Zalo của 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
        <button id="btn-sync-github-bot2" onclick="syncWithGitHub()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-white hover:bg-slate-100 text-slate-800 border border-slate-200 shadow-xs transition flex items-center gap-2" title="Đồng bộ toàn bộ thay đổi lên GitHub">
          <i class="fa-brands fa-github text-slate-900"></i>
          <span id="github-sync-label-bot2">GitHub Sync</span>
          <span id="github-sync-dot-bot2" class="w-2 h-2 rounded-full bg-emerald-500"></span>
        </button>

        <button id="bot-toggle-btn" onclick="toggleBotPower()" class="px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 {active_class}">
          <span id="bot-toggle-icon" class="w-2.5 h-2.5 rounded-full {'bg-white animate-pulse' if is_bot_active else 'bg-white'}"></span>
          <span id="bot-toggle-text">{active_text}</span>
        </button>

        <button onclick="fetchLatestData()" class="p-2.5 text-slate-500 hover:text-sky-600 rounded-xl hover:bg-slate-100 transition border border-slate-200 shadow-xs" title="Làm mới dữ liệu">
          <i class="fa-solid fa-rotate text-sm"></i>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7 flex-1 w-full space-y-6">

    <!-- STATS CARDS -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tổng Bài Bóc Tách</p>
          <h3 id="stat-total-posts" class="text-3xl font-extrabold text-slate-900 mt-1">{stats['total_posts']}</h3>
          <p class="text-xs text-slate-400 mt-1">Lưu trữ Web & DB (bot2.db)</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-newspaper"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Đã Bắn Vào Zalo</p>
          <h3 id="stat-total-zalo" class="text-3xl font-extrabold text-indigo-600 mt-1">{stats['total_zalo_sent']}</h3>
          <p id="stat-zalo-groups-count" class="text-xs text-slate-400 mt-1">{len([g for g in target_groups if g.get('enabled')])} nhóm đang nhận tin</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-paper-plane"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Nguồn Quét (2p30s/vòng)</p>
          <h3 id="stat-total-targets" class="text-3xl font-extrabold text-slate-900 mt-1">{len(targets)}</h3>
          <p class="text-xs text-slate-400 mt-1">{len(targets)} Fanpage + CLB VEPC/VAU</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-bullseye"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vòng Quét Hiện Tại</p>
          <h3 id="stat-scan-cycle" class="text-2xl font-bold text-slate-900 mt-1">Vòng #{stats['scan_cycle']}</h3>
          <p id="stat-last-scan" class="text-xs text-slate-400 mt-1 truncate max-w-[150px]">{stats['last_scan_time']}</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock-rotate-left"></i>
        </div>
      </div>
    </div>

    <!-- TABS NAVIGATION -->
    <div class="flex border-b border-slate-200 space-x-6 overflow-x-auto pb-0.5">
      <button onclick="switchTab('feed')" id="tab-btn-feed" class="pb-3 text-sm font-semibold border-b-2 border-sky-600 text-sky-600 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-stream"></i> Bảng Tin Mới Nhất
      </button>
      <button onclick="switchTab('console')" id="tab-btn-console" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-terminal"></i> Live Console Terminal
      </button>
      <button onclick="switchTab('zalo')" id="tab-btn-zalo" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-comments"></i> Cấu Hình Nhóm Zalo (<span id="tab-zalo-counter">{len([g for g in target_groups if g.get('enabled')])}/{len(target_groups)}</span>)
      </button>
      <button onclick="switchTab('targets')" id="tab-btn-targets" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-link"></i> Quản Lý Nguồn Quét ({len(targets)})
      </button>
      <button onclick="switchTab('cookies')" id="tab-btn-cookies" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-cookie-bite"></i> Cài Đặt Cookie Facebook
      </button>
      <button onclick="switchTab('history')" id="tab-btn-history" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-clock-rotate-left"></i> 📜 Lịch Sử Bắn Tin ({stats.get('total_zalo_sent', 0)})
      </button>
    </div>

    <!-- TAB 1: FEED VIEW -->
    <div id="tab-feed" class="space-y-6">
      <div class="bg-white p-4 rounded-xl border border-slate-200/80 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div class="relative w-full md:w-80">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
          <input type="text" id="search-input" onkeyup="filterPosts()" placeholder="Tìm kiếm nội dung, tác giả..." class="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500">
        </div>
        <div class="flex gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <button onclick="setFilterPage('')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 text-white">Tất cả</button>
          <button onclick="setFilterPage('VEPC')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">CLB VEPC</button>
          <button onclick="setFilterPage('Đoàn Thanh Niên')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">ĐTN - HSV VAU</button>
          <button onclick="setFilterPage('Kỹ thuật')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">Khoa KT Hàng Không</button>
          <button onclick="setFilterPage('Khai thác')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">Khoa Khai Thác HK</button>
        </div>
      </div>

      <div id="posts-container" class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- Rendered by JS -->
      </div>
    </div>

    <!-- TAB 2: LIVE CONSOLE LOG -->
    <div id="tab-console" class="hidden space-y-4">
      <div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden flex flex-col">
        <div class="bg-slate-950 px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center space-x-2">
            <span class="w-3 h-3 rounded-full bg-rose-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
            <span class="ml-2 text-xs font-mono text-slate-300 flex items-center gap-2">
              <span class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30">
                <span class="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
                LIVE 1s
              </span>
              <span id="liveClockBot2" class="font-mono text-xs font-bold text-sky-400">--:--:--</span>
            </span>
          </div>

          <!-- Scope Switcher -->
          <div class="flex items-center bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-[11px] font-bold">
            <button onclick="setLogBot2Scope('VAA')" id="btnLogScopeVaa" class="px-2.5 py-1 rounded bg-sky-600 text-white shadow-xs">VAA Bot</button>
            <button onclick="setLogBot2Scope('ALL')" id="btnLogScopeVaaAll" class="px-2.5 py-1 rounded text-slate-400 hover:text-white transition">🌐 Hợp Nhất 4 Bot</button>
          </div>

          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" checked class="rounded text-sky-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>
            <button onclick="fetchLogs()" class="px-2.5 py-1 text-xs text-sky-400 hover:text-sky-300 bg-sky-950/60 border border-sky-800/60 rounded-md transition">
              <i class="fa-solid fa-rotate"></i>
            </button>
          </div>
        </div>

        <div id="console-stream" class="p-4 font-mono text-xs text-slate-300 h-[520px] overflow-y-auto space-y-2 bg-[#0b0f19]">
          <div class="text-slate-500 italic">Đang tải luồng nhật ký từ hệ thống Bot 2 (VAA)...</div>
        </div>
      </div>
    </div>

    <!-- TAB 3: ZALO SETTINGS & MULTI-GROUP SELECTION -->
    <div id="tab-zalo" class="hidden space-y-6">
      
      <!-- QUICK FEATURES: TAG ALL & FORM ONLY FILTER -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- AUTO TAG ALL TOGGLE -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-lg">
              <i class="fa-solid fa-at"></i>
            </div>
            <div>
              <h4 class="font-bold text-slate-900 text-sm">Tự Động Tag @All Khi Có Bài</h4>
              <p class="text-xs text-slate-500">Gọi toàn bộ thành viên nhóm để không bỏ lỡ tin.</p>
            </div>
          </div>
          <button id="btn-toggle-tag-all" onclick="toggleTagAll()" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 { 'bg-emerald-50 text-emerald-700 border border-emerald-200' if auto_tag_all else 'bg-slate-100 text-slate-600 border border-slate-300' }">
            <i class="fa-solid { 'fa-toggle-on text-emerald-600 text-base' if auto_tag_all else 'fa-toggle-off text-slate-400 text-base' }"></i>
            <span id="tag-all-status-text">{'BẬT' if auto_tag_all else 'TẮT'}</span>
          </button>
        </div>

        <!-- FORM EXTRACTOR INFO -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-lg">
              <i class="fa-brands fa-google-drive"></i>
            </div>
            <div>
              <h4 class="font-bold text-slate-900 text-sm">Ưu Tiên Link Form Google Doc</h4>
              <p class="text-xs text-slate-500">Tự động bóc tách link forms.gle / gg docs đưa lên đầu.</p>
            </div>
          </div>
          <span class="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            Đã Kích Hoạt
          </span>
        </div>
      </div>

      <!-- KEYWORDS FILTER INFO -->
      <div class="bg-gradient-to-r from-sky-50 to-indigo-50 border border-sky-200/80 rounded-2xl p-5 shadow-xs">
        <div class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-xl bg-sky-600 text-white flex items-center justify-center shrink-0 mt-0.5">
            <i class="fa-solid fa-filter"></i>
          </div>
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Bộ Lọc Từ Khóa Bắn Zalo Bắt Buộc</h4>
            <p class="text-xs text-slate-600 mt-1">
              Chỉ bài viết chứa ít nhất một trong các từ khóa sau mới được gửi vào nhóm Zalo (mọi bài khác vẫn lưu Web đầy đủ):
            </p>
            <div class="flex flex-wrap gap-1.5 mt-2.5">
              <span class="px-2.5 py-1 bg-white border border-sky-200 rounded-md text-xs font-semibold text-sky-700">📌 Link đăng ký</span>
              <span class="px-2.5 py-1 bg-white border border-sky-200 rounded-md text-xs font-semibold text-sky-700">📝 Form</span>
              <span class="px-2.5 py-1 bg-white border border-sky-200 rounded-md text-xs font-semibold text-sky-700">✍️ Đăng ký</span>
              <span class="px-2.5 py-1 bg-white border border-sky-200 rounded-md text-xs font-semibold text-sky-700">⭐ Điểm rèn luyện / ĐRL</span>
            </div>
          </div>
        </div>
      </div>

      <!-- GROUP LIST WITH TOGGLE SWITCHES -->
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h4 class="font-bold text-slate-900 text-base">Danh Sách Nhóm Zalo Nhận Thông Báo (Bot 2 - VAA)</h4>
            <p class="text-xs text-slate-500">Bật hoặc tắt nhóm nào bạn muốn Bot 2 nhận tin nhắn tự động.</p>
          </div>
          <button onclick="testSendZaloAlert()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Bắn Thử Tin Nhắn Test (@All)
          </button>
        </div>

        <div id="zalo-groups-list" class="divide-y divide-slate-100">
          <!-- Rendered by JS -->
        </div>
      </div>

      <!-- ADD NEW GROUP SECTION -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Thêm Nhanh Từ Zalo Đang Đăng Nhập</h4>
            <p class="text-xs text-slate-500 mt-0.5">Tải danh sách các nhóm mà tài khoản Zalo của bạn đang tham gia.</p>
          </div>

          <div class="flex gap-2">
            <select id="select-scanned-groups" class="flex-1 px-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500">
              <option value="">-- Bấm "Quét danh sách" để nạp nhóm --</option>
            </select>
            <button onclick="fetchZaloAccountGroups()" class="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition whitespace-nowrap flex items-center gap-1">
              <i class="fa-solid fa-arrows-rotate"></i> Quét
            </button>
          </div>

          <button onclick="handleAddSelectedZaloGroup()" class="w-full px-4 py-2.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-plus"></i> Thêm Nhóm Đã Chọn Vào Bot 2
          </button>
        </div>

        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Thêm Thủ Công Bằng Group ID</h4>
            <p class="text-xs text-slate-500 mt-0.5">Dán ID Thread nhóm Zalo nếu bạn đã biết trước.</p>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <input type="text" id="manual-group-id" placeholder="ID Nhóm (vd: 7456361874031804652)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 col-span-2">
            <input type="text" id="manual-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm Sự Kiện VAA)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 col-span-2">
          </div>

          <button onclick="handleAddManualZaloGroup()" class="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-check"></i> Lưu Nhóm Thủ Công
          </button>
        </div>
      </div>

      <!-- SECTION: FACEBOOK MESSENGER MULTI-BOT CHANNEL -->
      <div class="bg-white p-6 rounded-2xl border border-blue-200/80 shadow-xs space-y-5">
        <div class="flex items-center justify-between flex-wrap gap-3 pb-3 border-b border-slate-100">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
              <i class="fa-brands fa-facebook-messenger"></i>
            </div>
            <div>
              <h3 class="font-bold text-slate-900 text-sm">Kênh Thông Báo Facebook Messenger (Đồng Bộ 4 Bot)</h3>
              <p class="text-xs text-slate-500">Tự động bắn tin bài mới & hoạt động ĐRL vào nhóm Messenger song song với Zalo.</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span id="msg-cookie-badge" class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <i class="fa-solid fa-circle-check"></i> UID: 61574475721537 (Bảo Nhi)
            </span>
            <button onclick="toggleMessengerMaster()" id="btn-toggle-messenger" class="px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs">
              <i class="fa-solid fa-toggle-on text-sm"></i> Đang BẬT
            </button>
          </div>
        </div>

        <!-- LIST OF MESSENGER GROUPS -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold text-slate-800 text-xs uppercase tracking-wider">Danh Sách Nhóm Messenger Nhận Tin:</h4>
            <button onclick="testSendMessengerAlert()" class="text-xs text-blue-600 hover:underline flex items-center gap-1 font-semibold">
              <i class="fa-solid fa-paper-plane"></i> Thử tin Messenger
            </button>
          </div>
          <div id="messenger-groups-list" class="space-y-2 max-h-52 overflow-y-auto">
            <!-- Rendered by JS -->
          </div>
        </div>

        <!-- ADD NEW MESSENGER GROUP -->
        <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
          <h5 class="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <i class="fa-solid fa-plus-circle text-blue-600"></i> Thêm Nhóm Messenger Mới (Bằng Thread ID)
          </h5>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input type="text" id="manual-msg-thread-id" placeholder="Thread ID (vd: 1773570903700841)" class="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
            <input type="text" id="manual-msg-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm Demo Messenger)" class="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div class="flex justify-between items-center pt-1">
            <span class="text-[11px] text-slate-500">Mẹo: Mở nhóm trên web messenger.com/t/<b>ID_NHÓM</b> để copy Thread ID.</span>
            <button onclick="handleAddManualMessengerGroup()" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition shadow-xs flex items-center gap-1.5">
              <i class="fa-solid fa-plus"></i> Thêm Vào Cả 4 Bot
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 4: TARGET MANAGEMENT -->
    <div id="tab-targets" class="hidden space-y-6">
      <div class="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <h3 class="font-bold text-slate-900 text-base mb-1">Thêm Đường Link Fanpage / Group Cần Quét (Bot 2)</h3>
        <p class="text-xs text-slate-500 mb-4">Điền link trang Facebook VAA / CLB, hệ thống sẽ tự động quét và bóc tách bài đăng mới 24/7 (với cơ chế lật trang Comet SSR).</p>
        <form onsubmit="handleAddTarget(event)" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input type="text" id="new-target-name" required placeholder="Tên Fanpage / CLB (vd: CLB Tổ Chức Sự Kiện VEPC - VAA)" class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500">
          <input type="url" id="new-target-url" required placeholder="https://www.facebook.com/..." class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 sm:col-span-2">
          <div class="sm:col-span-3 flex justify-end">
            <button type="submit" class="px-5 py-2.5 bg-sky-600 text-white text-sm font-semibold rounded-lg hover:bg-sky-700 shadow-xs flex items-center gap-2">
              <i class="fa-solid fa-plus"></i> Thêm Trang Theo Dõi
            </button>
          </div>
        </form>
      </div>

      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h4 class="font-bold text-slate-900 text-sm">Danh Sách Mục Tiêu Đang Quét ({len(targets)})</h4>
        </div>
        <div id="targets-table-body" class="divide-y divide-slate-100">
          <!-- Rendered by JS -->
        </div>
      </div>
    </div>

    <!-- TAB 5: COOKIES -->
    <div id="tab-cookies" class="hidden space-y-6">
      <div class="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs max-w-3xl space-y-4">
        <div>
          <h3 class="font-bold text-slate-900 text-base">Cài Đặt Cookie Tài Khoản Facebook Cho Bot 2 (VAA)</h3>
          <p class="text-xs text-slate-500 mt-1">Dán Cookie tài khoản Facebook riêng của bạn vào đây (Dạng JSON từ Cookie Editor hoặc chuỗi cookie header c_user=...; xs=...).</p>
        </div>

        <div class="p-3.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs">
          <div>
            <span class="text-slate-500">Tài khoản Facebook hiện tại của Bot 2:</span>
            <span id="current-cookie-user" class="font-bold text-slate-900 ml-1">UID: {c_user_val}</span>
          </div>
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold {'bg-emerald-100 text-emerald-800' if c_user_val != 'Chưa cấu hình' else 'bg-amber-100 text-amber-800'}">
            {'Đã nạp Cookie' if c_user_val != 'Chưa cấu hình' else 'Chưa có Cookie'}
          </span>
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1.5">Dán mã Cookie Facebook vào ô bên dưới:</label>
          <textarea id="cookie-input" rows="7" placeholder="[
  {{"name": "c_user", "value": "..."}},
  {{"name": "xs", "value": "..."}}
]
Hoặc dán: datr=xxx; c_user=1000xxx; xs=yyy; fr=zzz" class="w-full p-3 font-mono text-xs rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-slate-50"></textarea>
        </div>

        <div class="flex justify-end">
          <button onclick="saveFacebookCookie()" class="px-5 py-2.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded-xl shadow-xs transition flex items-center gap-2">
            <i class="fa-solid fa-floppy-disk"></i> Lưu & Áp Dụng Cookie Facebook Cho Bot 2
          </button>
        </div>
      </div>
    </div>

    <!-- TAB 6: DELIVERY HISTORY (IMMUTABLE) -->
    <div id="tab-history" class="hidden space-y-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-shield-halved text-emerald-600"></i> Lịch Sử Bắn Tin Zalo Bất Biến
              <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Không Thể Bị Xóa</span>
            </h3>
            <p class="text-xs text-slate-500 mt-1">Lưu trữ vĩnh viễn bài viết nào đã cào, bài nào gửi Zalo, vào nhóm/người nhận nào, lúc mấy giờ. Dữ liệu được bảo vệ bằng SQLite Trigger.</p>
          </div>
          <div class="flex items-center gap-3">
            <div class="relative w-64">
              <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
              <input type="text" id="history-search-input" onkeyup="if(event.key==='Enter') fetchDeliveryHistory(1)" placeholder="Tìm bài, nhóm nhận..." class="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500">
            </div>
            <button onclick="fetchDeliveryHistory(1)" class="px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 text-xs font-bold rounded-lg transition flex items-center gap-1.5">
              <i class="fa-solid fa-rotate"></i> Làm mới
            </button>
          </div>
        </div>

        <div class="overflow-x-auto mt-4">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">Thời gian bắn tin</th>
                <th class="px-4 py-3">Nguồn Fanpage</th>
                <th class="px-4 py-3">Tiêu đề / Nội dung bài viết</th>
                <th class="px-4 py-3">Đích nhận Zalo</th>
                <th class="px-4 py-3">Trạng thái</th>
                <th class="px-4 py-3 text-center">Liên kết</th>
              </tr>
            </thead>
            <tbody id="history-table-body" class="divide-y divide-slate-100">
              <tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">Đang tải lịch sử...</td></tr>
            </tbody>
          </table>
        </div>

        <div id="history-pagination" class="flex items-center justify-between pt-4 border-t border-slate-100 text-xs text-slate-500">
          <span id="history-page-info">Trang 1</span>
          <div class="flex items-center gap-2">
            <button id="history-prev-btn" onclick="changeHistoryPage(-1)" class="px-3 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50">Trước</button>
            <button id="history-next-btn" onclick="changeHistoryPage(1)" class="px-3 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50">Sau</button>
          </div>
        </div>
      </div>
    </div>

  </main>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    const API_BASE = '/api/bot2';
    let allPosts = {posts_json};
    let allTargets = {targets_json};
    let allTargetGroups = {target_groups_json};
    let currentFilterPage = '';
    let isBotActive = { 'true' if is_bot_active else 'false' };
    let autoTagAll = { 'true' if auto_tag_all else 'false' };

    function switchTab(tab) {{
      ['feed', 'console', 'zalo', 'targets', 'cookies', 'history'].forEach(t => {{
        const el = document.getElementById('tab-' + t);
        const btn = document.getElementById('tab-btn-' + t);
        if (el) el.classList.add('hidden');
        if (btn) {{
          btn.classList.remove('border-sky-600', 'text-sky-600');
          btn.classList.add('border-transparent', 'text-slate-500');
        }}
      }});
      const targetEl = document.getElementById('tab-' + tab);
      const targetBtn = document.getElementById('tab-btn-' + tab);
      if (targetEl) targetEl.classList.remove('hidden');
      if (targetBtn) {{
        targetBtn.classList.add('border-sky-600', 'text-sky-600');
        targetBtn.classList.remove('border-transparent', 'text-slate-500');
      }}

      if (tab === 'console') {{
        fetchLogs();
      }} else if (tab === 'zalo') {{
        fetchTargetGroups();
      }} else if (tab === 'history') {{
        fetchDeliveryHistory(1);
      }}
    }}

    // ================= BOT ON/OFF TOGGLE =================
    async function toggleBotPower() {{
      const btn = document.getElementById('bot-toggle-btn');
      btn.disabled = true;
      try {{
        const res = await fetch(API_BASE + '/toggle', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          isBotActive = data.is_active;
          updateBotButtonUI(isBotActive);
          fetchLogs();
        }}
      }} catch (err) {{
        alert('Lỗi thao tác bật/tắt bot: ' + err);
      }} finally {{
        btn.disabled = false;
      }}
    }}

    function updateBotButtonUI(active) {{
      const btn = document.getElementById('bot-toggle-btn');
      const text = document.getElementById('bot-toggle-text');
      const icon = document.getElementById('bot-toggle-icon');

      if (active) {{
        btn.className = 'px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20';
        text.innerText = '🟢 BOT 2 (VAA) ĐANG CHẠY';
        icon.className = 'w-2.5 h-2.5 rounded-full bg-white animate-pulse';
      }} else {{
        btn.className = 'px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20';
        text.innerText = '🔴 BOT 2 (VAA) ĐÃ TẮT';
        icon.className = 'w-2.5 h-2.5 rounded-full bg-white';
      }}
    }}

    // ================= LIVE CONSOLE LOGS & CLOCK =================
    let currentLog2Scope = 'VAA';

    function tickClockBot2() {{
      const el = document.getElementById('liveClockBot2');
      if (el) {{
        const now = new Date();
        el.innerText = now.toTimeString().split(' ')[0];
      }}
    }}
    setInterval(tickClockBot2, 1000);
    tickClockBot2();

    function setLogBot2Scope(scope) {{
      currentLog2Scope = scope;
      const btnVaa = document.getElementById('btnLogScopeVaa');
      const btnAll = document.getElementById('btnLogScopeVaaAll');
      if (btnVaa && btnAll) {{
        if (scope === 'VAA') {{
          btnVaa.className = 'px-2.5 py-1 rounded bg-sky-600 text-white shadow-xs';
          btnAll.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
        }} else {{
          btnAll.className = 'px-2.5 py-1 rounded bg-sky-600 text-white shadow-xs';
          btnVaa.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
        }}
      }}
      fetchLogs();
    }}

    async function fetchLogs() {{
      try {{
        const url = (currentLog2Scope === 'ALL') ? '/api/all-logs?limit=80' : (API_BASE + '/logs?limit=80');
        const res = await fetch(url);
        const data = await res.json();
        if (data.status === 'ok') {{
          renderLogs(data.logs || []);
        }}
      }} catch (err) {{
        console.error('Lỗi tải logs:', err);
      }}
    }}

    let bot2LogSortAsc = false; // Mặc định: false (Mới nhất trên cùng)

    function toggleBot2LogSort() {{
      bot2LogSortAsc = !bot2LogSortAsc;
      const btnText = document.getElementById('bot2-sort-text');
      const btnIcon = document.querySelector('#bot2-sort-btn i');
      if (bot2LogSortAsc) {{
        if (btnText) btnText.innerText = 'Cũ nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-up-short-wide text-amber-400';
      }} else {{
        if (btnText) btnText.innerText = 'Mới nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-down-short-wide text-cyan-400';
      }}
      fetchLogs();
    }}

    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      // Nếu bot2LogSortAsc = true (Cũ nhất trên) -> reverse; ngược lại giữ nguyên DESC (Mới nhất trên)
      const sortedLogs = bot2LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = sortedLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLog2Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-sky-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        // Xóa timestamp trùng lặp trong nội dung message
        let cleanMsg = String(l.message || '');
        cleanMsg = cleanMsg.replace(/^(\S+\s*)?\[\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\]\s*/, '$1');
        cleanMsg = cleanMsg.replace(/^\[\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}}\]\s*/, '');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{cleanMsg}}</span>
          </div>
        `;
      }}).join('');

      if (bot2LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}

    function clearConsoleView() {{
      document.getElementById('console-stream').innerHTML = '<div class="text-slate-500">Màn hình đã xóa. Đang chờ log tiếp theo...</div>';
    }}

    // ================= POSTS RENDERING =================
    function renderPosts(posts) {{
      const container = document.getElementById('posts-container');
      if (!posts || posts.length === 0) {{
        container.innerHTML = `
          <div class="col-span-full py-16 text-center text-slate-400">
            <i class="fa-solid fa-inbox text-4xl mb-3 text-slate-300"></i>
            <p class="font-medium">Chưa có bài viết nào được ghi nhận từ Bot 2.</p>
            <p class="text-xs text-slate-400 mt-1">Bot đang chạy quét Facebook trong nền...</p>
          </div>
        `;
        return;
      }}

      container.innerHTML = posts.map(p => `
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between gap-2 mb-3">
              <span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-100">
                ${{p.page_name || 'Fanpage'}}
              </span>
              <span class="text-xs text-slate-400 flex items-center gap-1">
                <i class="fa-regular fa-clock"></i> ${{p.posted_time || p.crawled_at || ''}}
              </span>
            </div>

            <div class="flex items-center gap-2 mb-3">
              <div class="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold">
                ${{(p.author || 'U')[0]}}
              </div>
              <span class="text-xs font-bold text-slate-800">${{p.author || 'Người đăng ẩn danh'}}</span>
            </div>

            <p class="text-sm text-slate-700 leading-relaxed whitespace-pre-line mb-4 line-clamp-6">
              ${{p.content}}
            </p>
          </div>

          <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <div class="flex items-center gap-2">
              ${{p.is_sent_zalo ? '<span class="text-emerald-600 font-semibold flex items-center gap-1"><i class="fa-solid fa-check-circle"></i> Đã gửi Zalo</span>' : '<span class="text-slate-400">Không khớp bộ lọc từ khóa</span>'}}
            </div>
            ${{p.post_url ? `
              <a href="${{p.post_url}}" target="_blank" rel="noopener noreferrer" class="font-semibold text-sky-600 hover:text-sky-800 flex items-center gap-1">
                Xem trên Facebook <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
              </a>
            ` : ''}}
          </div>
        </div>
      `).join('');
    }}

    function filterPosts() {{
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const filtered = allPosts.filter(p => {{
        const matchText = (p.content || '').toLowerCase().includes(q) || (p.author || '').toLowerCase().includes(q);
        const matchPage = !currentFilterPage || (p.page_name || '').toLowerCase().includes(currentFilterPage.toLowerCase());
        return matchText && matchPage;
      }});
      renderPosts(filtered);
    }}

    function setFilterPage(page) {{
      currentFilterPage = page;
      document.querySelectorAll('.page-filter-btn').forEach(btn => {{
        if (btn.innerText.includes(page) || (page === '' && btn.innerText === 'Tất cả')) {{
          btn.className = 'page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 text-white';
        }} else {{
          btn.className = 'page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200';
        }}
      }});
      filterPosts();
    }}

    // ================= TARGETS RENDERING =================
    function renderTargets(targets) {{
      const container = document.getElementById('targets-table-body');
      if (!targets || targets.length === 0) {{
        container.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Chưa có nguồn theo dõi nào cho Bot 2.</div>';
        return;
      }}
      container.innerHTML = targets.map((t, idx) => `
        <div class="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition">
          <div class="flex items-center gap-3">
            <span class="w-6 text-xs text-slate-400 font-bold">${{idx + 1}}</span>
            <div>
              <p class="text-sm font-bold text-slate-900">${{t.name}}</p>
              <a href="${{t.url}}" target="_blank" class="text-xs text-sky-600 hover:underline truncate max-w-md block">${{t.url}}</a>
            </div>
          </div>
          <button onclick="handleDeleteTarget('${{t.id}}')" class="p-2 text-rose-500 hover:bg-rose-50 rounded-lg transition" title="Xóa nguồn này">
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </div>
      `).join('');
    }}

    async function handleAddTarget(e) {{
      e.preventDefault();
      const name = document.getElementById('new-target-name').value;
      const url = document.getElementById('new-target-url').value;
      const formData = new FormData();
      formData.append('name', name);
      formData.append('url', url);

      const res = await fetch(API_BASE + '/targets', {{ method: 'POST', body: formData }});
      if (res.ok) {{
        document.getElementById('new-target-name').value = '';
        document.getElementById('new-target-url').value = '';
        fetchLatestData();
      }}
    }}

    async function handleDeleteTarget(id) {{
      if (!confirm('Bạn có chắc muốn xóa nguồn này khỏi Bot 2?')) return;
      const res = await fetch(API_BASE + '/targets/' + id, {{ method: 'DELETE' }});
      if (res.ok) fetchLatestData();
    }}

    // ================= ZALO GROUPS MANAGEMENT =================
    function renderTargetGroups(groups) {{
      const container = document.getElementById('zalo-groups-list');
      if (!groups || groups.length === 0) {{
        container.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Chưa cấu hình nhóm Zalo nào.</div>';
        return;
      }}

      container.innerHTML = groups.map(g => `
        <div class="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl ${{g.enabled ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-400'}} flex items-center justify-center font-bold text-sm">
              <i class="fa-solid ${{g.type === 'USER' ? 'fa-user' : 'fa-users'}}"></i>
            </div>
            <div>
              <p class="text-sm font-bold text-slate-900 flex items-center gap-2">
                ${{g.name}}
                ${{g.type === 'USER' ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">Cá nhân</span>' : ''}}
                ${{g.enabled ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">Đang nhận tin</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-200 text-slate-600">Đã tắt</span>'}}
              </p>
              <p class="text-xs text-slate-400 font-mono">${{g.type === 'USER' ? 'Zalo UID' : 'Thread ID'}}: ${{g.id}}</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot2')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${{g.id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${{g.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-300'}}">
              <i class="fa-solid ${{g.enabled ? 'fa-toggle-on text-emerald-600 text-base' : 'fa-toggle-off text-slate-400 text-base'}}"></i>
              ${{g.enabled ? 'BẬT' : 'TẮT'}}
            </button>
            <button onclick="deleteZaloGroup('${{g.id}}')" class="p-2 text-rose-500 hover:bg-rose-50 rounded-lg transition" title="Xóa khỏi danh sách">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </div>
        </div>
      `).join('');
    }}

    async function toggleZaloGroup(groupId) {{
      const cur = allTargetGroups.find(g => String(g.id) === String(groupId));
      const targetState = cur ? !cur.enabled : true;

      // Optimistic update giao diện ngay lập tức
      if (cur) cur.enabled = targetState;
      renderTargetGroups(allTargetGroups);
      updateZaloStatsBadge();

      const fd = new FormData();
      fd.append('group_id', groupId);
      fd.append('enabled', targetState ? 'true' : 'false');
      try {{
        const res = await fetch(API_BASE + '/zalo/toggle_group', {{ method: 'POST', body: fd }});
        const data = await res.json();
        if (data.status === 'ok') {{
          allTargetGroups = data.target_groups;
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }} else {{
          alert('Lỗi: ' + (data.detail || 'Không thể đổi trạng thái'));
          fetchTargetGroups();
        }}
      }} catch (err) {{
        alert('Lỗi kết nối khi đổi trạng thái nhóm: ' + err);
        fetchTargetGroups();
      }}
    }}

    async function fetchTargetGroups() {{
      try {{
        const res = await fetch(API_BASE + '/zalo/target_groups');
        const data = await res.json();
        if (data.status === 'ok') {{
          allTargetGroups = data.target_groups;
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }}
      }} catch (err) {{
        console.error('Lỗi nạp nhóm Zalo:', err);
      }}
    }}

    async function toggleTagAll() {{
      try {{
        const res = await fetch(API_BASE + '/zalo/toggle_tag_all', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          autoTagAll = data.auto_tag_all;
          const btn = document.getElementById('btn-toggle-tag-all');
          const txt = document.getElementById('tag-all-status-text');
          if (autoTagAll) {{
            btn.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200';
            btn.innerHTML = '<i class="fa-solid fa-toggle-on text-emerald-600 text-base"></i> <span>BẬT</span>';
          }} else {{
            btn.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-100 text-slate-600 border border-slate-300';
            btn.innerHTML = '<i class="fa-solid fa-toggle-off text-slate-400 text-base"></i> <span>TẮT</span>';
          }}
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function deleteZaloGroup(groupId) {{
      if (!confirm('Bạn có chắc muốn xóa nhóm này khỏi Bot 2?')) return;
      try {{
        const res = await fetch(API_BASE + '/zalo/target_groups/' + groupId, {{ method: 'DELETE' }});
        if (res.ok) {{
          allTargetGroups = allTargetGroups.filter(g => String(g.id) !== String(groupId));
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }}
      }} catch (err) {{
        alert('Lỗi xóa nhóm: ' + err);
      }}
    }}

    async function fetchZaloAccountGroups() {{
      const select = document.getElementById('select-scanned-groups');
      select.innerHTML = '<option value="">Đang tải danh sách từ Zalo...</option>';
      try {{
        const res = await fetch('/api/zalo/groups');
        const data = await res.json();
        if (data.groups && data.groups.length > 0) {{
          select.innerHTML = data.groups.map(g => `<option value="${{g.id}}" data-name="${{g.name}}">${{g.name}} (${{g.id}})</option>`).join('');
        }} else {{
          select.innerHTML = '<option value="">Không tìm thấy nhóm nào</option>';
        }}
      }} catch (err) {{
        select.innerHTML = '<option value="">Lỗi nạp nhóm</option>';
      }}
    }}

    async function handleAddSelectedZaloGroup() {{
      const select = document.getElementById('select-scanned-groups');
      const opt = select.options[select.selectedIndex];
      if (!opt || !opt.value) return alert('Vui lòng chọn 1 nhóm từ danh sách');

      const fd = new FormData();
      fd.append('group_id', opt.value);
      fd.append('group_name', opt.getAttribute('data-name') || opt.value);

      const res = await fetch(API_BASE + '/zalo/add_group', {{ method: 'POST', body: fd }});
      const data = await res.json();
      if (data.status === 'ok') {{
        allTargetGroups = data.target_groups;
        renderTargetGroups(allTargetGroups);
        updateZaloStatsBadge();
        alert('Đã thêm nhóm vào Bot 2 thành công!');
      }}
    }}

    async function handleAddManualZaloGroup() {{
      const gid = document.getElementById('manual-group-id').value.trim();
      const gname = document.getElementById('manual-group-name').value.trim();
      if (!gid || !gname) return alert('Vui lòng nhập cả ID và Tên nhóm');

      const fd = new FormData();
      fd.append('group_id', gid);
      fd.append('group_name', gname);

      const res = await fetch(API_BASE + '/zalo/add_group', {{ method: 'POST', body: fd }});
      const data = await res.json();
      if (data.status === 'ok') {{
        allTargetGroups = data.target_groups;
        renderTargetGroups(allTargetGroups);
        updateZaloStatsBadge();
        document.getElementById('manual-group-id').value = '';
        document.getElementById('manual-group-name').value = '';
        alert('Đã thêm nhóm vào Bot 2 thành công!');
      }}
    }}

    async function testSendZaloAlert() {{
      if (!confirm('Gửi tin nhắn mẫu thử nghiệm tới TẤT CẢ các nhóm Zalo Bot 2 đang được BẬT?')) return;
      try {{
        const res = await fetch(API_BASE + '/zalo/test_alert', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          alert('✅ ' + data.message);
          fetchLogs();
        }} else {{
          alert('❌ ' + (data.message || 'Lỗi gửi tin'));
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    function updateZaloStatsBadge() {{
      const enabledCount = allTargetGroups.filter(g => g.enabled).length;
      document.getElementById('stat-zalo-groups-count').innerText = enabledCount + ' nhóm đang nhận tin';
      document.getElementById('tab-btn-zalo').innerHTML = `<i class="fa-solid fa-comments"></i> Cấu Hình Nhóm Zalo (<span id="tab-zalo-counter">${{enabledCount}}/${{allTargetGroups.length}}</span>)`;
    }}

    // ================= FACEBOOK COOKIE SAVER =================
    async function saveFacebookCookie() {{
      const text = document.getElementById('cookie-input').value.trim();
      if (!text) return alert('Vui lòng dán cookie vào ô trước');
      const fd = new FormData();
      fd.append('cookie_text', text);
      const res = await fetch('/api/bot2/cookies', {{ method: 'POST', body: fd }});
      const data = await res.json();
      if (res.ok) {{
        alert('✅ ' + data.message);
        document.getElementById('current-cookie-user').innerText = 'UID: ' + data.c_user;
        document.getElementById('cookie-input').value = '';
        fetchLogs();
      }} else {{
        alert('❌ ' + (data.detail || 'Lỗi lưu cookie'));
      }}
    }}

    // ================= DELIVERY HISTORY (IMMUTABLE) =================
    let currentHistoryPage = 1;
    let totalHistoryPages = 1;

    async function fetchDeliveryHistory(page = 1) {{
      currentHistoryPage = page;
      const qInput = document.getElementById('history-search-input');
      const q = qInput ? qInput.value.trim() : '';
      const tbody = document.getElementById('history-table-body');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Đang tải dữ liệu...</td></tr>';
      try {{
        const url = `${{API_BASE}}/history?page=${{page}}&limit=20${{q ? '&search=' + encodeURIComponent(q) : ''}}`;
        const res = await fetch(url);
        const data = await res.json();
        renderDeliveryHistory(data);
      }} catch (err) {{
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-rose-500">Lỗi tải lịch sử: ${{err}}</td></tr>`;
      }}
    }}

    function renderDeliveryHistory(data) {{
      const tbody = document.getElementById('history-table-body');
      const items = data.items || [];
      const total = data.total || 0;
      const limit = data.limit || 20;
      totalHistoryPages = Math.ceil(total / limit) || 1;

      const pageInfo = document.getElementById('history-page-info');
      if (pageInfo) pageInfo.innerText = `Trang ${{currentHistoryPage}} / ${{totalHistoryPages}} (Tổng cộng ${{total}} lượt phát tin)`;

      const prevBtn = document.getElementById('history-prev-btn');
      const nextBtn = document.getElementById('history-next-btn');
      if (prevBtn) prevBtn.disabled = (currentHistoryPage <= 1);
      if (nextBtn) nextBtn.disabled = (currentHistoryPage >= totalHistoryPages);

      if (!items || items.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400">Chưa có lịch sử phát tin nào phù hợp.</td></tr>';
        return;
      }}

      tbody.innerHTML = items.map(item => {{
        const isSuccess = (item.status || '').toUpperCase() === 'SUCCESS';
        const statusBadge = isSuccess
          ? '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800"><i class="fa-solid fa-check"></i> Đã gửi</span>'
          : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800" title="${{item.status}}"><i class="fa-solid fa-triangle-exclamation"></i> Thất bại</span>`;

        const isUser = item.target_type === 'USER';
        const targetBadge = isUser
          ? '<span class="px-1.5 py-0.5 text-[9px] font-semibold bg-blue-100 text-blue-700 rounded ml-1">Cá nhân</span>'
          : '<span class="px-1.5 py-0.5 text-[9px] font-semibold bg-slate-100 text-slate-600 rounded ml-1">Nhóm</span>';

        const formBadge = item.has_form 
          ? '<span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-bold bg-amber-100 text-amber-800 rounded mt-1"><i class="fa-brands fa-google-drive"></i> Có Form Đăng Ký</span>'
          : '';

        const kwBadge = item.matched_keyword
          ? `<span class="text-[10px] text-slate-400">Từ khóa: <code class="text-sky-600 bg-sky-50 px-1 py-0.5 rounded font-mono">${{item.matched_keyword}}</code></span>`
          : '';

        return `
          <tr class="hover:bg-slate-50 transition">
            <td class="px-4 py-3 whitespace-nowrap text-slate-500 font-mono text-[11px]">
              <i class="fa-regular fa-clock mr-1 text-slate-400"></i> ${{item.sent_at || ''}}
            </td>
            <td class="px-4 py-3">
              <div class="font-bold text-slate-800">${{item.source_page || 'Ẩn danh'}}</div>
              <div class="text-[10px] text-slate-400">${{item.author || ''}}</div>
            </td>
            <td class="px-4 py-3 max-w-xs">
              <div class="font-semibold text-slate-900 line-clamp-1">${{item.post_title || 'Bài viết mới'}}</div>
              <div class="text-[11px] text-slate-500 line-clamp-2 mt-0.5">${{item.content_snippet || ''}}</div>
              <div class="flex items-center gap-2 mt-1">
                ${{formBadge}}
                ${{kwBadge}}
              </div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="font-bold text-slate-800 flex items-center">
                ${{item.zalo_target_name || item.zalo_target_id}}
                ${{targetBadge}}
              </div>
              <div class="text-[10px] text-slate-400 font-mono">ID: ${{item.zalo_target_id}}</div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              ${{statusBadge}}
            </td>
            <td class="px-4 py-3 text-center whitespace-nowrap">
              ${{item.post_url ? `
                <a href="${{item.post_url}}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-sky-600 hover:text-sky-800 hover:bg-sky-50 rounded-lg transition">
                  <i class="fa-brands fa-facebook"></i> Xem
                </a>
              ` : '<span class="text-slate-300">-</span>'}}
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function changeHistoryPage(delta) {{
      const newPage = currentHistoryPage + delta;
      if (newPage >= 1 && newPage <= totalHistoryPages) {{
        fetchDeliveryHistory(newPage);
      }}
    }}

    // ================= DATA REFRESH LOOP =================
    async function fetchLatestData() {{
      try {{
        const [postsRes, statsRes, targetsRes, logsRes, groupsRes] = await Promise.all([
          fetch(API_BASE + '/posts?limit=50'),
          fetch(API_BASE + '/stats'),
          fetch(API_BASE + '/targets'),
          fetch(API_BASE + '/logs?limit=80'),
          fetch(API_BASE + '/zalo/target_groups')
        ]);
        const postsData = await postsRes.json();
        const statsData = await statsRes.json();
        const targetsData = await targetsRes.json();
        const logsData = await logsRes.json();
        const groupsData = await groupsRes.json();

        allPosts = postsData.data || [];
        allTargets = targetsData.targets || [];
        if (groupsData && groupsData.target_groups) {{
          allTargetGroups = groupsData.target_groups;
          updateZaloStatsBadge();
        }}

        document.getElementById('stat-total-posts').innerText = statsData.total_posts;
        document.getElementById('stat-total-zalo').innerText = statsData.total_zalo_sent;
        document.getElementById('stat-total-targets').innerText = allTargets.length;
        document.getElementById('stat-scan-cycle').innerText = 'Vòng #' + statsData.scan_cycle;
        document.getElementById('stat-last-scan').innerText = statsData.last_scan_time;

        isBotActive = statsData.is_active;
        updateBotButtonUI(isBotActive);

        filterPosts();
        renderTargets(allTargets);
        renderLogs(logsData.logs || []);
      }} catch (err) {{
        console.error('Lỗi cập nhật định kỳ:', err);
      }}
    }}

    async function syncWithGitHub() {{
      const btn = document.getElementById('btn-sync-github-bot2');
      const label = document.getElementById('github-sync-label-bot2');
      const dot = document.getElementById('github-sync-dot-bot2');
      if (label) label.innerText = 'Đang đồng bộ...';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-ping';
      try {{
        const res = await fetch('/api/github/sync', {{ method: 'POST' }});
        const data = await res.json();
        if (data.status === 'ok') {{
          if (label) label.innerText = 'Đã đồng bộ!';
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
          alert('☁️ Đã đồng bộ toàn bộ mã nguồn & dữ liệu lên GitHub thành công!\\n' + (data.message || ''));
        }} else {{
          if (label) label.innerText = 'Lỗi sync';
          if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
          alert('⚠️ Lỗi đồng bộ: ' + (data.message || 'Thất bại'));
        }}
      }} catch (e) {{
        if (label) label.innerText = 'Lỗi kết nối';
        if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
        alert('⚠️ Không thể kết nối tới GitHub API: ' + e);
      }}
      setTimeout(() => {{
        if (label) label.innerText = 'GitHub Sync';
        if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
      }}, 3000);
    }}

    // ================= FACEBOOK MESSENGER SENDER & GROUPS =================
    let allMessengerGroups = [];

    async function fetchMessengerGroups() {{
      try {{
        const res = await fetch('/api/messenger/status');
        const data = await res.json();
        allMessengerGroups = data.target_groups || [];
        renderMessengerGroups(allMessengerGroups);
        const btn = document.getElementById('btn-toggle-messenger');
        if (btn) {{
          if (data.enabled) {{
            btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs";
            btn.innerHTML = '<i class="fa-solid fa-toggle-on text-sm"></i> Đang BẬT';
          }} else {{
            btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-200 text-slate-700 hover:bg-slate-300 shadow-xs";
            btn.innerHTML = '<i class="fa-solid fa-toggle-off text-sm"></i> Đang TẮT';
          }}
        }}
      }} catch (err) {{
        console.error('Lỗi nạp nhóm Messenger:', err);
      }}
    }}

    function renderMessengerGroups(groups) {{
      const container = document.getElementById('messenger-groups-list');
      if (!container) return;
      if (!groups || groups.length === 0) {{
        container.innerHTML = '<div class="text-xs text-slate-400 py-3 text-center">Chưa có nhóm Messenger nào. Hãy dán Thread ID bên dưới để thêm.</div>';
        return;
      }}
      container.innerHTML = groups.map(g => `
        <div class="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-xs hover:border-blue-300 transition">
          <div class="flex items-center gap-2.5">
            <input type="checkbox" onchange="handleToggleMessengerGroup('${{g.id}}')" ${{g.enabled ? 'checked' : ''}} class="rounded text-blue-600 border-slate-300 focus:ring-blue-500 w-4 h-4 cursor-pointer">
            <div>
              <div class="font-bold text-slate-800 flex items-center gap-1.5">
                <i class="fa-brands fa-facebook-messenger text-blue-600"></i>
                <span>${{g.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">Thread ID: ${{g.id}}</div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="testSendMessengerAlert('${{g.id}}')" class="px-2.5 py-1 text-[11px] font-semibold bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-md transition" title="Gửi tin thử nghiệm vào nhóm này">
              <i class="fa-solid fa-paper-plane mr-1"></i> Thử tin
            </button>
            <button onclick="handleDeleteMessengerGroup('${{g.id}}')" class="px-2 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 rounded-md transition" title="Xóa nhóm">
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </div>
      `).join('');
    }}

    async function toggleMessengerMaster() {{
      try {{
        const res = await fetch('/api/messenger/toggle', {{ method: 'POST' }});
        const data = await res.json();
        alert(data.message);
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleAddManualMessengerGroup() {{
      const tid = document.getElementById('manual-msg-thread-id').value.trim();
      const tname = document.getElementById('manual-msg-group-name').value.trim();
      if (!tid) return alert('Vui lòng nhập Thread ID của nhóm Messenger!');

      try {{
        const res = await fetch('/api/messenger/groups/add', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: tid, name: tname }})
        }});
        const data = await res.json();
        alert(data.message);
        document.getElementById('manual-msg-thread-id').value = '';
        document.getElementById('manual-msg-group-name').value = '';
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleToggleMessengerGroup(threadId) {{
      try {{
        const res = await fetch('/api/messenger/groups/toggle', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId }})
        }});
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function handleDeleteMessengerGroup(threadId) {{
      if (!confirm('Bạn có chắc muốn xóa nhóm Messenger này khỏi danh sách nhận tin?')) return;
      try {{
        const res = await fetch('/api/messenger/groups/delete', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId }})
        }});
        const data = await res.json();
        alert(data.message);
        fetchMessengerGroups();
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    async function testSendMessengerAlert(threadId) {{
      try {{
        const res = await fetch('/api/messenger/test', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ thread_id: threadId || null }})
        }});
        const data = await res.json();
        if (data.status === 'ok') {{
          alert('✅ ' + data.message);
        }} else {{
          alert('❌ ' + (data.message || 'Lỗi gửi tin thử nghiệm'));
        }}
      }} catch (err) {{
        alert('Lỗi: ' + err);
      }}
    }}

    renderPosts(allPosts);
    renderTargets(allTargets);
    renderTargetGroups(allTargetGroups);
    fetchMessengerGroups();
    fetchLogs();

    setInterval(fetchLogs, 1000);
    setInterval(fetchLatestData, 15000);
  </script>

  <!-- ==================== QUAD BOT ZALO TEST MODAL ==================== -->
  <div id="quad-test-modal" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden flex items-center justify-center p-4" style="z-index: 9999;">
    <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-800">
      <!-- Header -->
      <div class="p-4 px-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-md shadow-indigo-500/20">
            <i class="fa-solid fa-vial-circle-check"></i>
          </div>
          <div>
            <h3 class="font-bold text-slate-900 text-base leading-tight">Bắn Tin Nhắn Test Zalo (4 Bot Yuki)</h3>
            <p class="text-xs text-slate-500">Kiểm tra kết nối và gửi tin test riêng lẻ từng nhóm hoặc tất cả nhóm</p>
          </div>
        </div>
        <button onclick="closeQuadTestModal()" class="w-8 h-8 rounded-lg bg-white/80 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition font-bold text-lg">
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 overflow-y-auto space-y-4 flex-1">
        <!-- 4 Bot Selector Tabs -->
        <div class="grid grid-cols-4 gap-2 bg-slate-100 p-1.5 rounded-xl text-xs font-bold text-center">
          <button id="quad-tab-bot1" onclick="switchQuadTestBot('bot1')" class="py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition">
            🎓 Bot 1 (HUIT)
          </button>
          <button id="quad-tab-bot2" onclick="switchQuadTestBot('bot2')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2 (VAA)
          </button>
          <button id="quad-tab-bot3" onclick="switchQuadTestBot('bot3')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🔴 Bot 3 (IUH)
          </button>
          <button id="quad-tab-bot4" onclick="switchQuadTestBot('bot4')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🏛️ Bot 4 (UFM)
          </button>
        </div>

        <!-- Custom message input -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Nội dung tin nhắn test (Để trống để dùng mẫu chuẩn @All):</label>
          <input type="text" id="quad-custom-msg" placeholder="Ví dụ: 🔔 Bot test tín hiệu Zalo hoạt động tốt..." class="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
        </div>

        <!-- Action bar for selected bot -->
        <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div>
            <span id="quad-bot-title" class="text-xs font-bold text-slate-800">Bot 1 - HUIT</span>
            <span id="quad-groups-summary" class="text-[11px] text-slate-500 ml-2">Đang tải...</span>
          </div>
          <button id="btn-test-all-quad" onclick="triggerTestAllForCurrentBot()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Gửi Test Tất Cả Nhóm
          </button>
        </div>

        <!-- Target Groups List -->
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-700">Danh sách nhóm mục tiêu của Bot này (Bấm "Gửi Test" từng nhóm):</label>
          <div id="quad-groups-list" class="space-y-2 max-h-64 overflow-y-auto pr-1">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Live status / log output -->
        <div id="quad-test-status" class="hidden p-3 rounded-xl text-xs font-medium border"></div>
      </div>

      <!-- Footer -->
      <div class="p-3 px-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
        <span>💡 Lệnh trong Zalo: <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/test &lt;tên nhóm&gt;</code> hoặc <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/testall</code></span>
        <button onclick="closeQuadTestModal()" class="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl transition">
          Đóng
        </button>
      </div>
    </div>
  </div>

  <script>
    let currentQuadBot = 'bot1';
    let quadBotsData = {{}};

    async function sendTestToSingleGroup(targetId, targetName, targetType, botId) {{
      if (!confirm('🧪 Bạn có chắc muốn gửi tin nhắn TEST vào: ' + (targetName || targetId) + ' (ID: ' + targetId + ')?')) return;
      try {{
        const res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName
          }})
        }});
        const data = await res.json();
        if (res.ok && data.success) {{
          alert('✅ ' + data.message);
        }} else {{
          alert('❌ ' + (data.detail || data.message || 'Lỗi gửi tin test'));
        }}
      }} catch (err) {{
        alert('Lỗi gửi tin test: ' + err);
      }}
    }}

    async function openQuadTestModal(botId) {{
      if (!botId) botId = 'bot1';
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.remove('hidden');
      await loadQuadTargetGroups();
      switchQuadTestBot(botId);
    }}

    function closeQuadTestModal() {{
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.add('hidden');
    }}

    async function loadQuadTargetGroups() {{
      try {{
        const res = await fetch('/api/zalo/quad-target-groups');
        const data = await res.json();
        if (data.status === 'ok') {{
          data.bots.forEach(function(b) {{
            quadBotsData[b.bot_id] = b;
          }});
        }}
      }} catch (err) {{
        console.error('Lỗi tải danh sách nhóm quad:', err);
      }}
    }}

    function switchQuadTestBot(botId) {{
      currentQuadBot = botId;
      var botTabs = ['bot1', 'bot2', 'bot3', 'bot4'];
      for (var i = 0; i < botTabs.length; i++) {{
        var b = botTabs[i];
        var tab = document.getElementById('quad-tab-' + b);
        if (tab) {{
          if (b === botId) {{
            tab.className = 'py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition';
          }} else {{
            tab.className = 'py-2 rounded-lg text-slate-600 hover:text-slate-900 transition';
          }}
        }}
      }}

      var botData = quadBotsData[botId];
      if (!botData) return;

      var titleEl = document.getElementById('quad-bot-title');
      if (titleEl) titleEl.innerText = botData.bot_name;

      var groups = botData.groups || [];
      var enabledCount = 0;
      for (var j = 0; j < groups.length; j++) {{
        if (groups[j].enabled) enabledCount++;
      }}
      var summaryEl = document.getElementById('quad-groups-summary');
      if (summaryEl) summaryEl.innerText = '(' + enabledCount + '/' + groups.length + ' nhóm đang bật)';

      var container = document.getElementById('quad-groups-list');
      if (!container) return;

      if (groups.length === 0) {{
        container.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs bg-slate-50 rounded-xl">Chưa cấu hình nhóm Zalo nào cho Bot này.</div>';
        return;
      }}

      var itemsHtml = '';
      for (var k = 0; k < groups.length; k++) {{
        var g = groups[k];
        var isUser = (g.type || '').toUpperCase() === 'USER';
        var typeBadge = isUser ? '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded-full">Cá nhân</span>' : '<span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full">Nhóm</span>';
        var statusBadge = g.enabled ? '<span class="text-[10px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">Đang nhận tin</span>' : '<span class="text-[10px] bg-slate-200 text-slate-600 font-semibold px-2 py-0.5 rounded-full">Đã tắt</span>';
        var iconClass = isUser ? 'fa-user' : 'fa-users';
        var bgClass = g.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-400';

        itemsHtml += '<div class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between transition">' +
          '<div class="flex items-center gap-3">' +
            '<div class="w-9 h-9 rounded-xl ' + bgClass + ' flex items-center justify-center font-bold text-sm">' +
              '<i class="fa-solid ' + iconClass + '"></i>' +
            '</div>' +
            '<div>' +
              '<div class="flex items-center gap-2">' +
                '<span class="text-xs font-bold text-slate-900">' + g.name + '</span>' +
                typeBadge + statusBadge +
              '</div>' +
              '<div class="text-[11px] text-slate-400 font-mono mt-0.5">ID: ' + g.id + '</div>' +
            '</div>' +
          '</div>' +
          '<button onclick="sendTestFromQuadModal('' + g.id + '', '' + (g.name || g.id).replace(/'/g, "\'") + '', '' + (g.type || 'GROUP') + '', '' + botId + '')" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5">' +
            '<i class="fa-solid fa-paper-plane text-xs"></i> Gửi Test' +
          '</button>' +
        '</div>';
      }}
      container.innerHTML = itemsHtml;
    }}

    async function sendTestFromQuadModal(targetId, targetName, targetType, botId) {{
      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test tới "' + targetName + '" (' + targetId + ')...';
      }}

      var customMsg = '';
      var inputEl = document.getElementById('quad-custom-msg');
      if (inputEl && inputEl.value) {{
        customMsg = inputEl.value.trim();
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName,
            custom_message: customMsg || null
          }})
        }});
        var data = await res.json();
        if (res.ok && data.success) {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Thành công!</b> ' + data.message;
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || data.message || 'Không thể gửi tin');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}

    async function triggerTestAllForCurrentBot() {{
      var botName = (quadBotsData[currentQuadBot] && quadBotsData[currentQuadBot].bot_name) || currentQuadBot;
      if (!confirm('Bạn có chắc muốn gửi tin nhắn TEST tới TẤT CẢ các nhóm đang bật của ' + botName + '?')) return;

      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test lần lượt tới các nhóm...';
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-all-groups', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ bot_id: currentQuadBot }})
        }});
        var data = await res.json();
        if (res.ok && data.status === 'ok') {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Hoàn tất!</b> Đã gửi thành công ' + data.success_count + '/' + data.total + ' nhóm của ' + data.bot_name + '.';
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || 'Không thể gửi test tất cả');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}
  </script>

</body>
</html>
"""
    return html

@app.api_route("/bot3", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/iuh", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard_view_bot3():
    cfg = get_config_iuh()
    stats = database.get_iuh_stats(db_file=database.IUH_DB_FILE)
    activities = database.get_activities(limit=50, db_file=database.IUH_DB_FILE)
    zalo_cfg = cfg.get("zalo", {})
    target_groups = zalo_cfg.get("target_groups", [])
    portal_cfg = cfg.get("portal", {})
    phpsessid = portal_cfg.get("phpsessid", "")
    auto_tag_all = zalo_cfg.get("auto_tag_all", True)

    activities_json = json.dumps(activities, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)
    target_groups_json = json.dumps(target_groups, ensure_ascii=False)

    history_data = database.get_delivery_history(limit=50, db_file=database.IUH_DB_FILE)
    history_json = json.dumps(history_data.get("items", []), ensure_ascii=False)

    is_bot_active = stats.get("is_active", True)

    active_class = "bg-rose-600 hover:bg-rose-700 text-white shadow-rose-600/20" if is_bot_active else "bg-slate-500 hover:bg-slate-600 text-white shadow-slate-500/20"
    active_text = "🟢 BOT IUH ĐANG BẬT" if is_bot_active else "🔴 BOT IUH ĐÃ TẮT"

    cookie_status = stats.get("cookie_status", "valid")
    cookie_badge = '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300">🟢 Cookie Hoạt Động</span>' if cookie_status == "valid" else '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">🔴 Cookie Hết Hạn / Chưa Đăng Nhập</span>'

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IUH Portal & Zalo Bot Monitor 24/7 (Yuki 3)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    .glass {{ background: rgba(255, 255, 255, 0.94); backdrop-filter: blur(12px); }}
    #console-stream::-webkit-scrollbar {{ width: 6px; }}
    #console-stream::-webkit-scrollbar-track {{ background: #0f172a; }}
    #console-stream::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP NAVBAR -->
  <header class="glass sticky top-0 z-50 border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-5">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-rose-600 to-red-700 flex items-center justify-center text-white shadow-md shadow-rose-500/20">
            <i class="fa-solid fa-bullhorn text-lg"></i>
          </div>
          <div>
            <h1 class="font-bold text-lg leading-tight text-slate-900">IUH Portal Feed & Bot (Yuki 3)</h1>
            <p class="text-xs text-slate-500 font-medium">Cào doantn.iuh.edu.vn & Săn Điểm Rèn Luyện 24/7</p>
          </div>
        </div>

        <div class="hidden sm:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <a href="/" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🎓 Bot 1: HUIT (Yuki 1)
          </a>
          <a href="/bot2" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2: VAA (Yuki 2)
          </a>
          <a href="/bot3" class="px-3 py-1.5 rounded-lg bg-white text-rose-700 shadow-xs">
            🔴 Bot 3: IUH (Yuki 3)
          </a>
          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
          <a href="/bot5" class="px-3 py-1.5 rounded-lg text-blue-700 hover:text-blue-900 transition">
            🔵 Bot 5: OU (Yuki 5)
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold" title="Đăng xuất khỏi hệ thống">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span class="hidden sm:inline">Thoát</span>
          </a>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-rose-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Yuki</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-rose-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
                <!-- TEST ZALO 4 BOT MODAL BUTTON -->
        <button onclick="openQuadTestModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho từng nhóm Zalo của 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
        <button id="btn-sync-github-bot3" onclick="syncWithGitHub()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-white hover:bg-slate-100 text-slate-800 border border-slate-200 shadow-xs transition flex items-center gap-2">
          <i class="fa-brands fa-github text-slate-900"></i>
          <span id="github-sync-label-bot3">GitHub Sync</span>
          <span id="github-sync-dot-bot3" class="w-2 h-2 rounded-full bg-emerald-500"></span>
        </button>

        <button id="bot-toggle-btn-bot3" onclick="toggleBotPower()" class="px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 {active_class}">
          <span id="bot-toggle-icon-bot3" class="w-2.5 h-2.5 rounded-full bg-white"></span>
          <span id="bot-toggle-text-bot3">{active_text}</span>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full space-y-6">

    <!-- BANNER CẢNH BÁO COOKIE HẾT HẠN -->
    <div id="iuh-cookie-alert-banner" class="{'hidden' if cookie_status == 'valid' else ''} bg-gradient-to-r from-rose-600 to-red-600 rounded-2xl p-4 text-white shadow-lg shadow-rose-600/30 flex flex-wrap items-center justify-between gap-4 animate-pulse">
      <div class="flex items-center gap-3.5">
        <div class="w-11 h-11 rounded-xl bg-white/20 flex items-center justify-center text-xl">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
        <div>
          <h4 class="font-extrabold text-sm tracking-wide">⚠️ CẢNH BÁO: COOKIE CỔNG ĐOÀN TN IUH ĐÃ HẾT HẠN!</h4>
          <p class="text-xs text-rose-100 mt-0.5">Phiên PHPSESSID đã hết hạn. Bot IUH tạm thời ngừng cào hoạt động mới cho đến khi nạp cookie mới!</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <input type="text" id="quick-banner-cookie" placeholder="Dán PHPSESSID mới vào đây..." class="px-3 py-1.5 text-xs text-slate-800 rounded-lg focus:outline-none font-mono w-60">
        <button onclick="saveCookieFromBanner()" class="px-3.5 py-1.5 bg-slate-900 hover:bg-black text-white text-xs font-bold rounded-lg transition whitespace-nowrap">
          Lưu & Sửa Ngay
        </button>
      </div>
    </div>

    <!-- KPI STATS CARDS -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Tổng HĐ Quét Được</p>
          <h3 id="stat-total-activities" class="text-2xl font-extrabold text-slate-900 mt-1">{stats.get('total_activities', 0)}</h3>
          <p class="text-[11px] text-slate-400 mt-0.5">Tab Đăng ký tham gia</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-calendar-check"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Tin Bắn Zalo</p>
          <h3 id="stat-total-sent" class="text-2xl font-extrabold text-emerald-600 mt-1">{stats.get('total_zalo_sent', 0)}</h3>
          <p class="text-[11px] text-slate-400 mt-0.5">demo & Yuki</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-paper-plane"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Phiên Cookie Web</p>
          <div id="stat-cookie-badge" class="mt-2">{cookie_badge}</div>
          <p class="text-[11px] text-slate-400 mt-1 font-mono">PHPSESSID</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-cookie-bite"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Lần Quét Cuối</p>
          <h3 id="stat-last-scan" class="text-sm font-bold text-slate-800 mt-2 font-mono">{stats.get('last_scan_time') or 'Vừa xong'}</h3>
          <p id="stat-cycle-count" class="text-[11px] text-slate-400 mt-0.5">Chu kỳ: #{stats.get('total_scans', 0)}</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock-rotate-left"></i>
        </div>
      </div>
    </div>

    <!-- ACTION CONTROLS & COOKIE INPUT -->
    <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <button onclick="crawlNow()" class="px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-2">
          <i class="fa-solid fa-rotate text-sm"></i>
          <span>Quét Ngay Lập Tức</span>
        </button>
        <button onclick="sendTestAlert()" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-2">
          <i class="fa-solid fa-vial text-sm"></i>
          <span>Gửi Test Vào Zalo</span>
        </button>
        <label class="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer ml-2">
          <input type="checkbox" id="chk-auto-tag-all" {"checked" if auto_tag_all else ""} onchange="toggleTagAll(this.checked)" class="w-4 h-4 text-rose-600 rounded">
          <span>Tự động tag @All khi gửi nhóm</span>
        </label>
      </div>

      <!-- Quick Cookie Input -->
      <div class="flex items-center gap-2 w-full lg:w-auto">
        <input type="text" id="input-cookie-iuh" value="{phpsessid}" placeholder="Dán PHPSESSID hoặc JSON cookies IUH..." class="px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-rose-500 w-full sm:w-72 font-mono">
        <button onclick="saveCookie()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold whitespace-nowrap shadow-xs transition flex items-center gap-1.5">
          <i class="fa-solid fa-floppy-disk"></i>
          <span>Lưu & Kiểm Tra</span>
        </button>
      </div>
    </div>

    <!-- MAIN GRID CONTENT -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

      <!-- LEFT: ACTIVITIES TABLE (8 COLS) -->
      <div class="lg:col-span-8 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col overflow-hidden">
        <div class="p-5 border-b border-slate-100 flex items-center justify-between gap-4">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
              <i class="fa-solid fa-list-check text-sm"></i>
            </div>
            <div>
              <h2 class="font-bold text-sm text-slate-900">Danh Sách Hoạt Động & Điểm Rèn Luyện IUH</h2>
              <p class="text-[11px] text-slate-500">Dữ liệu cào trực tiếp từ cổng doantn.iuh.edu.vn (Tab 1)</p>
            </div>
          </div>
          <div class="relative w-48 sm:w-64">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-slate-400"></i>
            <input type="text" id="search-activity-input" oninput="filterActivities(this.value)" placeholder="Tìm kiếm sự kiện..." class="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-rose-500">
          </div>
        </div>

        <!-- Table Container -->
        <div class="overflow-x-auto flex-1">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-100 font-bold">
              <tr>
                <th class="px-4 py-3">Tên Hoạt Động</th>
                <th class="px-3 py-3 text-center">ĐRL</th>
                <th class="px-3 py-3 text-center">Học Kỳ</th>
                <th class="px-3 py-3 text-center">Hạn Chót</th>
                <th class="px-3 py-3 text-center">Trạng Thái</th>
                <th class="px-3 py-3 text-center">Chi Tiết</th>
              </tr>
            </thead>
            <tbody id="activities-table-body" class="divide-y divide-slate-100 font-medium">
              <!-- Rendered by JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- RIGHT: ZALO RECIPIENTS & CONSOLE STREAM (4 COLS) -->
      <div class="lg:col-span-4 space-y-6">

        <!-- Zalo Target Recipients Card -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-xs">
                <i class="fa-solid fa-users"></i>
              </div>
              <h3 class="font-bold text-xs text-slate-900 uppercase tracking-wider">Người Nhận Zalo Bot IUH</h3>
            </div>
            <button onclick="openAddGroupModal()" class="text-xs text-rose-600 hover:text-rose-700 font-bold flex items-center gap-1">
              <i class="fa-solid fa-plus"></i> Thêm
            </button>
          </div>

          <div id="target-groups-container" class="space-y-2.5">
            <!-- Rendered by JS -->
          </div>
        </div>

        <!-- Console System Logs Card -->
        <div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-md p-5 flex flex-col h-[400px]">
          <div class="flex flex-wrap items-center justify-between pb-3 border-b border-slate-800 mb-2 gap-2">
            <div class="flex items-center gap-2">
              <span class="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <span class="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping"></span>
                LIVE 1s
              </span>
              <span id="liveClockBot3" class="font-mono text-xs font-bold text-rose-400">--:--:--</span>
            </div>
            <!-- Scope Switcher -->
            <div class="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[10px] font-bold">
              <button onclick="setLogBot3Scope('IUH')" id="btnLogScopeIuh" class="px-2 py-0.5 rounded bg-rose-600 text-white shadow-xs">IUH Bot</button>
              <button onclick="setLogBot3Scope('ALL')" id="btnLogScopeIuhAll" class="px-2 py-0.5 rounded text-slate-400 hover:text-white transition">🌐 Hợp Nhất 4 Bot</button>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="clearConsoleViewBot3()" class="text-[11px] text-slate-400 hover:text-white transition font-mono px-1.5 py-0.5 rounded bg-slate-800" title="Xóa màn hình">
                <i class="fa-solid fa-broom"></i>
              </button>
              <button onclick="fetchLogs()" class="text-[11px] text-slate-400 hover:text-white transition font-mono p-1 rounded bg-slate-800" title="Làm mới">
                <i class="fa-solid fa-rotate-right"></i>
              </button>
            </div>
          </div>
          <div id="console-stream" class="flex-1 overflow-y-auto space-y-1.5 text-[11px] font-mono text-slate-300 pr-1">
            <!-- Stream logs -->
          </div>
        </div>

      </div>
    </div>

    <!-- BẢNG LỊCH SỬ BẤT BIẾN: BÀI NÀO ĐÃ GỬI VÀO ZALO, VÀO NHÓM NÀO, LÚC MẤY GIỜ -->
    <div class="bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col overflow-hidden">
      <div class="p-5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <i class="fa-solid fa-clock-rotate-left text-sm"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="font-bold text-sm text-slate-900">Lịch Sử Gửi Bài Zalo Bất Biến (Audit Trail)</h2>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">Không bao giờ bị xoá</span>
            </div>
            <p class="text-[11px] text-slate-500">Ghi nhận chi tiết từng bài viết được gửi vào nhóm/cá nhân nào, lúc mấy giờ và nội dung cụ thể</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <input type="text" id="search-history-input" oninput="filterHistory(this.value)" placeholder="Lọc theo bài, nhóm hoặc nội dung..." class="w-56 sm:w-64 pl-3 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-emerald-500">
          <button onclick="fetchHistory()" class="px-3 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-xl font-bold text-slate-600">
            <i class="fa-solid fa-rotate-right"></i>
          </button>
        </div>
      </div>
      <div class="overflow-x-auto flex-1 max-h-96">
        <table class="w-full text-left text-xs text-slate-600">
          <thead class="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-100 font-bold sticky top-0">
            <tr>
              <th class="px-4 py-3">Thời Gian Gửi</th>
              <th class="px-4 py-3">Bài Viết / Hoạt Động</th>
              <th class="px-4 py-3">Gửi Tới Nhóm / Người Nhận</th>
              <th class="px-3 py-3 text-center">Trạng Thái</th>
              <th class="px-3 py-3 text-center">Nội Dung Gửi</th>
            </tr>
          </thead>
          <tbody id="history-table-body" class="divide-y divide-slate-100 font-medium">
            <!-- Rendered by JS -->
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- MODAL: CHI TIẾT SỰ KIỆN -->
  <div id="detail-modal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-4">
      <div class="flex items-start justify-between">
        <h3 id="modal-title" class="font-bold text-slate-900 text-base leading-tight">Chi Tiết Hoạt Động</h3>
        <button onclick="closeDetailModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <div class="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-slate-200/70">
        <div><span class="text-slate-400">Điểm rèn luyện:</span> <strong id="modal-points" class="text-rose-600 font-bold">+0 điểm</strong></div>
        <div><span class="text-slate-400">Học kỳ:</span> <strong id="modal-semester" class="text-slate-700">1/2026</strong></div>
        <div><span class="text-slate-400">Hạn đăng ký:</span> <strong id="modal-deadline" class="text-slate-700">--</strong></div>
        <div><span class="text-slate-400">Trạng thái:</span> <strong id="modal-status" class="text-slate-700">--</strong></div>
      </div>
      <div>
        <p class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Nội dung chi tiết sự kiện:</p>
        <div id="modal-body-text" class="text-xs text-slate-700 bg-slate-50 p-3.5 rounded-xl border border-slate-200/70 whitespace-pre-wrap max-h-56 overflow-y-auto font-sans leading-relaxed"></div>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <a id="modal-link-register" href="https://doantn.iuh.edu.vn/doanvien.html" target="_blank" class="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold">Vào Cổng Đăng Ký</a>
        <button onclick="closeDetailModal()" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold">Đóng</button>
      </div>
    </div>
  </div>

  <!-- MODAL: XEM NỘI DUNG TIN NHẮN ĐÃ GỬI VÀO ZALO -->
  <div id="history-modal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-4">
      <div class="flex items-start justify-between">
        <h3 id="history-modal-title" class="font-bold text-slate-900 text-base leading-tight">Nội Dung Đã Gửi Vào Zalo</h3>
        <button onclick="closeHistoryModal()" class="text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>
      <div class="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-slate-200/70">
        <div><span class="text-slate-400">Thời gian gửi:</span> <strong id="history-modal-time" class="text-slate-700">--</strong></div>
        <div><span class="text-slate-400">Người/Nhóm nhận:</span> <strong id="history-modal-recipient" class="text-emerald-700 font-bold">--</strong></div>
      </div>
      <div>
        <p class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Bản tin chi tiết Zalo:</p>
        <div id="history-modal-body" class="text-xs text-slate-700 bg-slate-50 p-3.5 rounded-xl border border-slate-200/70 whitespace-pre-wrap max-h-56 overflow-y-auto font-sans leading-relaxed"></div>
      </div>
      <div class="flex justify-end pt-2">
        <button onclick="closeHistoryModal()" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold">Đóng</button>
      </div>
    </div>
  </div>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    let allActivities = {activities_json};
    let allTargetGroups = {target_groups_json};
    let allHistory = {history_json};


    function renderActivities(list) {{
      const tbody = document.getElementById('activities-table-body');
      if (!list || list.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-400 text-xs">Chưa có hoạt động nào trong cơ sở dữ liệu. Hãy bấm "Quét Ngay Lập Tức"!</td></tr>`;
        return;
      }}

      tbody.innerHTML = list.map((a, idx) => {{
        const isFull = (a.status || '').toLowerCase().includes('đủ số lượng');
        const statusBadge = isFull 
          ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">Đã đủ chỗ</span>` 
          : `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">Đang mở</span>`;
        const slotText = a.slots ? `<span class="text-[10px] text-slate-400 font-mono">(${{a.slots}})</span>` : '';

        return `
          <tr class="hover:bg-slate-50/80 transition">
            <td class="px-4 py-3">
              <div class="font-bold text-slate-900 leading-snug line-clamp-2">${{a.title}}</div>
              <div class="text-[10px] text-slate-400 mt-0.5">ID: <span class="font-mono">${{a.activity_id}}</span></div>
            </td>
            <td class="px-3 py-3 text-center">
              <span class="px-2 py-0.5 bg-rose-50 text-rose-600 font-extrabold rounded-md text-xs border border-rose-200/60">+${{a.points}}</span>
            </td>
            <td class="px-3 py-3 text-center text-slate-600 font-medium">${{a.semester || '-'}}</td>
            <td class="px-3 py-3 text-center text-slate-600 font-mono text-[11px]">${{a.deadline || '-'}}</td>
            <td class="px-3 py-3 text-center whitespace-nowrap">${{statusBadge}} ${{slotText}}</td>
            <td class="px-3 py-3 text-center">
              <button onclick='openDetailModalByIndex(${{idx}})' class="px-2.5 py-1 text-xs text-rose-600 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 rounded-lg font-bold transition">
                <i class="fa-solid fa-eye"></i> Xem
              </button>
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function renderTargetGroups(groups) {{
      const container = document.getElementById('target-groups-container');
      if (!groups || groups.length === 0) {{
        container.innerHTML = `<p class="text-xs text-slate-400 text-center py-4">Chưa có người nhận nào</p>`;
        return;
      }}

      container.innerHTML = groups.map(g => {{
        const isUser = (g.type || '').toUpperCase() === 'USER';
        const typeBadge = isUser ? '<span class="text-[9px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-bold">Cá nhân</span>' : '<span class="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold">Nhóm</span>';
        return `
          <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
            <div>
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-bold text-slate-800">${{g.name}}</span>
                ${{typeBadge}}
              </div>
              <div class="text-[10px] text-slate-400 font-mono mt-0.5">ID: ${{g.id}}</div>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="sendTestToSingleGroup('${{g.id}}', '${{g.name}}', '${{g.type || 'GROUP'}}', 'bot3')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 flex items-center gap-1" title="Gửi tin nhắn test riêng vào nhóm này">
                <i class="fa-solid fa-paper-plane text-[10px]"></i> Test
              </button>
              <button onclick="toggleTargetGroup('${{g.id}}', ${{!g.enabled}})" class="px-2.5 py-1 rounded-lg text-[11px] font-bold ${{g.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}}">
                ${{g.enabled ? 'Đang nhận' : 'Tắt'}}
              </button>
              <button onclick="deleteTargetGroup('${{g.id}}')" class="text-slate-400 hover:text-rose-600 p-1"><i class="fa-solid fa-trash-can text-xs"></i></button>
            </div>
          </div>
        `;
      }}).join('');
    }}

    async function toggleBotPower() {{
      const res = await fetch('/api/bot3/toggle', {{ method: 'POST' }});
      const data = await res.json();
      const btn = document.getElementById('bot-toggle-btn-bot3');
      const text = document.getElementById('bot-toggle-text-bot3');
      if (data.is_active) {{
        btn.className = "px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-rose-600 hover:bg-rose-700 text-white shadow-rose-600/20";
        text.innerText = "🟢 BOT IUH ĐANG BẬT";
      }} else {{
        btn.className = "px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-slate-500 hover:bg-slate-600 text-white shadow-slate-500/20";
        text.innerText = "🔴 BOT IUH ĐÃ TẮT";
      }}
    }}

    async function crawlNow() {{
      const res = await fetch('/api/bot3/crawl');
      const data = await res.json();
      alert(data.message || 'Quét thành công');
      fetchLatestData();
    }}

    async function sendTestAlert() {{
      const res = await fetch('/api/bot3/zalo/test_alert', {{ method: 'POST' }});
      const data = await res.json();
      alert(data.message || 'Đã gửi test');
    }}

    async function saveCookie() {{
      const cookieVal = document.getElementById('input-cookie-iuh').value.trim();
      if (!cookieVal) return alert('Vui lòng dán cookie PHPSESSID!');
      const fd = new FormData();
      fd.append('cookie', cookieVal);
      const res = await fetch('/api/bot3/cookie', {{ method: 'POST', body: fd }});
      const data = await res.json();
      alert(data.message);
      fetchLatestData();
    }}

    async function toggleTargetGroup(gid, enabled) {{
      const fd = new FormData();
      fd.append('group_id', gid);
      fd.append('enabled', enabled);
      const res = await fetch('/api/bot3/zalo/toggle_group', {{ method: 'POST', body: fd }});
      const data = await res.json();
      allTargetGroups = data.target_groups;
      renderTargetGroups(allTargetGroups);
    }}

    async function toggleTagAll(enabled) {{
      const fd = new FormData();
      fd.append('enabled', enabled);
      await fetch('/api/bot3/zalo/toggle_tag_all', {{ method: 'POST', body: fd }});
    }}

    async function deleteTargetGroup(gid) {{
      if (!confirm('Xác nhận xóa người nhận này?')) return;
      const res = await fetch('/api/bot3/zalo/target_groups/' + gid, {{ method: 'DELETE' }});
      const data = await res.json();
      allTargetGroups = data.target_groups;
      renderTargetGroups(allTargetGroups);
    }}

    function openAddGroupModal() {{
      const gid = prompt('Nhập ID Zalo của nhóm hoặc cá nhân:');
      if (!gid) return;
      const gname = prompt('Nhập Tên gợi nhớ (Ví dụ: demo hoặc Yuki):', 'demo');
      const isUser = confirm('Đối tượng này là CÁ NHÂN? (Bấm OK nếu là Cá nhân, bấm Cancel nếu là Nhóm)');
      const fd = new FormData();
      fd.append('group_id', gid);
      fd.append('group_name', gname || gid);
      fd.append('target_type', isUser ? 'USER' : 'GROUP');
      fetch('/api/bot3/zalo/add_group', {{ method: 'POST', body: fd }}).then(r => r.json()).then(data => {{
        allTargetGroups = data.target_groups;
        renderTargetGroups(allTargetGroups);
      }});
    }}

    function openDetailModalByIndex(idx) {{
      const a = allActivities[idx];
      if (!a) return;
      document.getElementById('modal-title').innerText = a.title;
      document.getElementById('modal-points').innerText = '+' + a.points + ' điểm';
      document.getElementById('modal-semester').innerText = a.semester || 'Chưa rõ';
      document.getElementById('modal-deadline').innerText = a.deadline || 'Chưa rõ';
      document.getElementById('modal-status').innerText = a.status + (a.slots ? ' (' + a.slots + ')' : '');
      document.getElementById('modal-body-text').innerText = a.details || 'Không có mô tả chi tiết thêm từ modal.';
      document.getElementById('detail-modal').classList.remove('hidden');
    }}

    function closeDetailModal() {{
      document.getElementById('detail-modal').classList.add('hidden');
    }}

    function filterActivities(query) {{
      const q = (query || '').toLowerCase().trim();
      if (!q) {{
        renderActivities(allActivities);
        return;
      }}
      const filtered = allActivities.filter(a => 
        (a.title || '').toLowerCase().includes(q) || 
        (a.semester || '').toLowerCase().includes(q) || 
        (a.details || '').toLowerCase().includes(q)
      );
      renderActivities(filtered);
    }}

    // ================= LIVE CONSOLE LOGS & CLOCK =================
    let currentLog3Scope = 'IUH';

    function tickClockBot3() {{
      const el = document.getElementById('liveClockBot3');
      if (el) {{
        const now = new Date();
        el.innerText = now.toTimeString().split(' ')[0];
      }}
    }}
    setInterval(tickClockBot3, 1000);
    tickClockBot3();

    function setLogBot3Scope(scope) {{
      currentLog3Scope = scope;
      const btnIuh = document.getElementById('btnLogScopeIuh');
      const btnAll = document.getElementById('btnLogScopeIuhAll');
      if (btnIuh && btnAll) {{
        if (scope === 'IUH') {{
          btnIuh.className = 'px-2 py-0.5 rounded bg-rose-600 text-white shadow-xs';
          btnAll.className = 'px-2 py-0.5 rounded text-slate-400 hover:text-white transition';
        }} else {{
          btnAll.className = 'px-2 py-0.5 rounded bg-rose-600 text-white shadow-xs';
          btnIuh.className = 'px-2 py-0.5 rounded text-slate-400 hover:text-white transition';
        }}
      }}
      fetchLogs();
    }}

    function clearConsoleViewBot3() {{
      const container = document.getElementById('console-stream');
      if (container) container.innerHTML = '<div class="text-slate-500">Màn hình đã xóa. Đang chờ log tiếp theo...</div>';
    }}

    async function fetchLogs() {{
      try {{
        const url = (currentLog3Scope === 'ALL') ? '/api/all-logs?limit=80' : '/api/bot3/logs?limit=40';
        const res = await fetch(url);
        const data = await res.json();
        const container = document.getElementById('console-stream');
        if (data.logs) {{
          container.innerHTML = data.logs.map(l => {{
            let color = 'text-slate-400';
            if (l.level === 'WARN') color = 'text-amber-400';
            else if (l.level === 'ERROR') color = 'text-rose-400';
            else if (l.level === 'ZALO' || l.level === 'ACTIVITY') color = 'text-emerald-400';
            else if (l.level === 'SCAN') color = 'text-cyan-400';

            const timeStr = l.created_at || '';
            const botBadge = (currentLog3Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-rose-300 border border-slate-700 shrink-0">[${{l.bot}}]</span> ` : '';

            return `<div class="flex items-start gap-1.5 py-0.5"><span class="text-slate-500 font-mono shrink-0">[${{timeStr}}]</span> ${{botBadge}}<span class="font-bold ${{color}} shrink-0">[${{l.level}}]</span> <span class="break-all text-slate-200">${{l.message}}</span></div>`;
          }}).join('');
        }}
      }} catch (e) {{}}
    }}

    async function fetchLatestData() {{
      try {{
        const [statsRes, actsRes] = await Promise.all([
          fetch('/api/bot3/stats'),
          fetch('/api/bot3/activities?limit=50')
        ]);
        const s = await statsRes.json();
        const a = await actsRes.json();
        document.getElementById('stat-total-activities').innerText = s.total_activities || 0;
        document.getElementById('stat-total-sent').innerText = s.total_zalo_sent || 0;
        document.getElementById('stat-last-scan').innerText = s.last_scan_time || 'Chưa chạy';
        document.getElementById('stat-cycle-count').innerText = 'Chu kỳ: #' + (s.total_scans || 0);

        const cookieBadge = document.getElementById('stat-cookie-badge');
        const cookieBanner = document.getElementById('iuh-cookie-alert-banner');
        if (s.cookie_status === 'valid') {{
          cookieBadge.innerHTML = '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300">🟢 Cookie Hoạt Động</span>';
          if (cookieBanner) cookieBanner.classList.add('hidden');
        }} else {{
          cookieBadge.innerHTML = '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">🔴 Cookie Hết Hạn / Chưa Đăng Nhập</span>';
          if (cookieBanner) cookieBanner.classList.remove('hidden');
        }}

        if (a.data) {{
          allActivities = a.data;
          renderActivities(allActivities);
        }}
        await fetchHistory();
      }} catch (e) {{}}
    }}

    async function saveCookieFromBanner() {{
      const cookieVal = document.getElementById('quick-banner-cookie').value.trim();
      if (!cookieVal) return alert('Vui lòng dán cookie PHPSESSID!');
      const fd = new FormData();
      fd.append('cookie', cookieVal);
      const res = await fetch('/api/bot3/cookie', {{ method: 'POST', body: fd }});
      const data = await res.json();
      alert(data.message);
      fetchLatestData();
    }}

    function renderHistory(list) {{
      const tbody = document.getElementById('history-table-body');
      if (!tbody) return;
      if (!list || list.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-400 text-xs">Chưa có lịch sử gửi tin nào. Khi bot gửi bài vào Zalo, toàn bộ nhật ký sẽ được lưu trữ vĩnh viễn tại đây!</td></tr>`;
        return;
      }}

      tbody.innerHTML = list.map((h, idx) => {{
        const isUser = (h.target_type || '').toUpperCase() === 'USER';
        const typeBadge = isUser ? '<span class="text-[9px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-bold ml-1">Cá nhân</span>' : '<span class="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold ml-1">Nhóm</span>';
        const isSuccess = (h.status || '').toUpperCase() === 'SUCCESS';
        const statusBadge = isSuccess 
          ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">🟢 Thành công</span>` 
          : `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-100 text-rose-700 border border-rose-200">🔴 Thất bại</span>`;

        return `
          <tr class="hover:bg-slate-50/80 transition">
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="font-mono text-[11px] font-bold text-slate-700">${{h.sent_at || '-'}}</div>
              <div class="text-[10px] text-slate-400">${{h.crawled_at ? 'Quét: ' + h.crawled_at : ''}}</div>
            </td>
            <td class="px-4 py-3">
              <div class="font-bold text-slate-900 leading-snug line-clamp-1">${{h.post_title || 'Hoạt động IUH'}}</div>
              <div class="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                <span class="font-mono">ID: ${{h.post_id || '-'}}</span>
                ${{h.matched_keyword ? '• <span class="text-rose-600 font-semibold">' + h.matched_keyword + '</span>' : ''}}
              </div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="flex items-center">
                <span class="font-bold text-slate-800 text-xs">${{h.zalo_target_name || '-'}}</span>
                ${{typeBadge}}
              </div>
              <div class="text-[10px] text-slate-400 font-mono mt-0.5">ID: ${{h.zalo_target_id || '-'}}</div>
            </td>
            <td class="px-3 py-3 text-center whitespace-nowrap">
              ${{statusBadge}}
            </td>
            <td class="px-3 py-3 text-center whitespace-nowrap">
              <button onclick="openHistoryModalByIndex(${{idx}})" class="px-2.5 py-1 text-xs text-emerald-700 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 rounded-lg font-bold transition flex items-center gap-1 mx-auto">
                <i class="fa-solid fa-message"></i> Xem nội dung
              </button>
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function openHistoryModalByIndex(idx) {{
      const h = allHistory[idx];
      if (!h) return;
      document.getElementById('history-modal-title').innerText = h.post_title || 'Nội Dung Đã Gửi Vào Zalo';
      document.getElementById('history-modal-time').innerText = h.sent_at || '--';
      const isUser = (h.target_type || '').toUpperCase() === 'USER';
      const kindStr = isUser ? 'Cá nhân: ' : 'Nhóm: ';
      document.getElementById('history-modal-recipient').innerText = kindStr + (h.zalo_target_name || '-') + ' (' + (h.zalo_target_id || '-') + ')';
      document.getElementById('history-modal-body').innerText = h.content_snippet || 'Không có bản sao lưu nội dung.';
      document.getElementById('history-modal').classList.remove('hidden');
    }}

    function closeHistoryModal() {{
      document.getElementById('history-modal').classList.add('hidden');
    }}

    function filterHistory(query) {{
      const q = (query || '').toLowerCase().trim();
      if (!q) {{
        renderHistory(allHistory);
        return;
      }}
      const filtered = allHistory.filter(h => 
        (h.post_title || '').toLowerCase().includes(q) || 
        (h.zalo_target_name || '').toLowerCase().includes(q) || 
        (h.zalo_target_id || '').toLowerCase().includes(q) || 
        (h.content_snippet || '').toLowerCase().includes(q) ||
        (h.sent_at || '').toLowerCase().includes(q)
      );
      renderHistory(filtered);
    }}

    async function fetchHistory() {{
      try {{
        const res = await fetch('/api/bot3/history?limit=50');
        const d = await res.json();
        if (d.data && d.data.items) {{
          allHistory = d.data.items;
          const searchInput = document.getElementById('search-history-input');
          const searchVal = searchInput ? searchInput.value : '';
          if (searchVal) {{
            filterHistory(searchVal);
          }} else {{
            renderHistory(allHistory);
          }}
        }}
      }} catch (e) {{
        console.error('Lỗi tải lịch sử gửi tin:', e);
      }}
    }}

    async function syncWithGitHub() {{
      const label = document.getElementById('github-sync-label-bot3');
      const dot = document.getElementById('github-sync-dot-bot3');
      if (label) label.innerText = 'Đang đồng bộ...';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-ping';
      try {{
        const fd = new FormData();
        fd.append('msg', '🔄 Auto-sync: Cập nhật Bot 3 IUH từ Web Dashboard');
        const res = await fetch('/api/github/sync', {{ method: 'POST', body: fd }});
        const d = await res.json();
        alert(d.message);
      }} catch (e) {{
        alert('Lỗi: ' + e);
      }}
      if (label) label.innerText = 'GitHub Sync';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
    }}

    renderActivities(allActivities);
    renderTargetGroups(allTargetGroups);
    renderHistory(allHistory);
    fetchLogs();
    setInterval(fetchLogs, 1000);
    setInterval(fetchLatestData, 10000);
    setInterval(fetchHistory, 10000);
  </script>

  <!-- ==================== QUAD BOT ZALO TEST MODAL ==================== -->
  <div id="quad-test-modal" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden flex items-center justify-center p-4" style="z-index: 9999;">
    <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-800">
      <!-- Header -->
      <div class="p-4 px-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-md shadow-indigo-500/20">
            <i class="fa-solid fa-vial-circle-check"></i>
          </div>
          <div>
            <h3 class="font-bold text-slate-900 text-base leading-tight">Bắn Tin Nhắn Test Zalo (4 Bot Yuki)</h3>
            <p class="text-xs text-slate-500">Kiểm tra kết nối và gửi tin test riêng lẻ từng nhóm hoặc tất cả nhóm</p>
          </div>
        </div>
        <button onclick="closeQuadTestModal()" class="w-8 h-8 rounded-lg bg-white/80 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition font-bold text-lg">
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 overflow-y-auto space-y-4 flex-1">
        <!-- 4 Bot Selector Tabs -->
        <div class="grid grid-cols-4 gap-2 bg-slate-100 p-1.5 rounded-xl text-xs font-bold text-center">
          <button id="quad-tab-bot1" onclick="switchQuadTestBot('bot1')" class="py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition">
            🎓 Bot 1 (HUIT)
          </button>
          <button id="quad-tab-bot2" onclick="switchQuadTestBot('bot2')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2 (VAA)
          </button>
          <button id="quad-tab-bot3" onclick="switchQuadTestBot('bot3')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🔴 Bot 3 (IUH)
          </button>
          <button id="quad-tab-bot4" onclick="switchQuadTestBot('bot4')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🏛️ Bot 4 (UFM)
          </button>
        </div>

        <!-- Custom message input -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Nội dung tin nhắn test (Để trống để dùng mẫu chuẩn @All):</label>
          <input type="text" id="quad-custom-msg" placeholder="Ví dụ: 🔔 Bot test tín hiệu Zalo hoạt động tốt..." class="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
        </div>

        <!-- Action bar for selected bot -->
        <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div>
            <span id="quad-bot-title" class="text-xs font-bold text-slate-800">Bot 1 - HUIT</span>
            <span id="quad-groups-summary" class="text-[11px] text-slate-500 ml-2">Đang tải...</span>
          </div>
          <button id="btn-test-all-quad" onclick="triggerTestAllForCurrentBot()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Gửi Test Tất Cả Nhóm
          </button>
        </div>

        <!-- Target Groups List -->
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-700">Danh sách nhóm mục tiêu của Bot này (Bấm "Gửi Test" từng nhóm):</label>
          <div id="quad-groups-list" class="space-y-2 max-h-64 overflow-y-auto pr-1">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Live status / log output -->
        <div id="quad-test-status" class="hidden p-3 rounded-xl text-xs font-medium border"></div>
      </div>

      <!-- Footer -->
      <div class="p-3 px-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
        <span>💡 Lệnh trong Zalo: <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/test &lt;tên nhóm&gt;</code> hoặc <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/testall</code></span>
        <button onclick="closeQuadTestModal()" class="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl transition">
          Đóng
        </button>
      </div>
    </div>
  </div>

  <script>
    let currentQuadBot = 'bot1';
    let quadBotsData = {{}};

    async function sendTestToSingleGroup(targetId, targetName, targetType, botId) {{
      if (!confirm('🧪 Bạn có chắc muốn gửi tin nhắn TEST vào: ' + (targetName || targetId) + ' (ID: ' + targetId + ')?')) return;
      try {{
        const res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName
          }})
        }});
        const data = await res.json();
        if (res.ok && data.success) {{
          alert('✅ ' + data.message);
        }} else {{
          alert('❌ ' + (data.detail || data.message || 'Lỗi gửi tin test'));
        }}
      }} catch (err) {{
        alert('Lỗi gửi tin test: ' + err);
      }}
    }}

    async function openQuadTestModal(botId) {{
      if (!botId) botId = 'bot1';
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.remove('hidden');
      await loadQuadTargetGroups();
      switchQuadTestBot(botId);
    }}

    function closeQuadTestModal() {{
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.add('hidden');
    }}

    async function loadQuadTargetGroups() {{
      try {{
        const res = await fetch('/api/zalo/quad-target-groups');
        const data = await res.json();
        if (data.status === 'ok') {{
          data.bots.forEach(function(b) {{
            quadBotsData[b.bot_id] = b;
          }});
        }}
      }} catch (err) {{
        console.error('Lỗi tải danh sách nhóm quad:', err);
      }}
    }}

    function switchQuadTestBot(botId) {{
      currentQuadBot = botId;
      var botTabs = ['bot1', 'bot2', 'bot3', 'bot4'];
      for (var i = 0; i < botTabs.length; i++) {{
        var b = botTabs[i];
        var tab = document.getElementById('quad-tab-' + b);
        if (tab) {{
          if (b === botId) {{
            tab.className = 'py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition';
          }} else {{
            tab.className = 'py-2 rounded-lg text-slate-600 hover:text-slate-900 transition';
          }}
        }}
      }}

      var botData = quadBotsData[botId];
      if (!botData) return;

      var titleEl = document.getElementById('quad-bot-title');
      if (titleEl) titleEl.innerText = botData.bot_name;

      var groups = botData.groups || [];
      var enabledCount = 0;
      for (var j = 0; j < groups.length; j++) {{
        if (groups[j].enabled) enabledCount++;
      }}
      var summaryEl = document.getElementById('quad-groups-summary');
      if (summaryEl) summaryEl.innerText = '(' + enabledCount + '/' + groups.length + ' nhóm đang bật)';

      var container = document.getElementById('quad-groups-list');
      if (!container) return;

      if (groups.length === 0) {{
        container.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs bg-slate-50 rounded-xl">Chưa cấu hình nhóm Zalo nào cho Bot này.</div>';
        return;
      }}

      var itemsHtml = '';
      for (var k = 0; k < groups.length; k++) {{
        var g = groups[k];
        var isUser = (g.type || '').toUpperCase() === 'USER';
        var typeBadge = isUser ? '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded-full">Cá nhân</span>' : '<span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full">Nhóm</span>';
        var statusBadge = g.enabled ? '<span class="text-[10px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">Đang nhận tin</span>' : '<span class="text-[10px] bg-slate-200 text-slate-600 font-semibold px-2 py-0.5 rounded-full">Đã tắt</span>';
        var iconClass = isUser ? 'fa-user' : 'fa-users';
        var bgClass = g.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-400';

        itemsHtml += '<div class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between transition">' +
          '<div class="flex items-center gap-3">' +
            '<div class="w-9 h-9 rounded-xl ' + bgClass + ' flex items-center justify-center font-bold text-sm">' +
              '<i class="fa-solid ' + iconClass + '"></i>' +
            '</div>' +
            '<div>' +
              '<div class="flex items-center gap-2">' +
                '<span class="text-xs font-bold text-slate-900">' + g.name + '</span>' +
                typeBadge + statusBadge +
              '</div>' +
              '<div class="text-[11px] text-slate-400 font-mono mt-0.5">ID: ' + g.id + '</div>' +
            '</div>' +
          '</div>' +
          '<button onclick="sendTestFromQuadModal('' + g.id + '', '' + (g.name || g.id).replace(/'/g, "\'") + '', '' + (g.type || 'GROUP') + '', '' + botId + '')" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5">' +
            '<i class="fa-solid fa-paper-plane text-xs"></i> Gửi Test' +
          '</button>' +
        '</div>';
      }}
      container.innerHTML = itemsHtml;
    }}

    async function sendTestFromQuadModal(targetId, targetName, targetType, botId) {{
      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test tới "' + targetName + '" (' + targetId + ')...';
      }}

      var customMsg = '';
      var inputEl = document.getElementById('quad-custom-msg');
      if (inputEl && inputEl.value) {{
        customMsg = inputEl.value.trim();
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-target', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName,
            custom_message: customMsg || null
          }})
        }});
        var data = await res.json();
        if (res.ok && data.success) {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Thành công!</b> ' + data.message;
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || data.message || 'Không thể gửi tin');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}

    async function triggerTestAllForCurrentBot() {{
      var botName = (quadBotsData[currentQuadBot] && quadBotsData[currentQuadBot].bot_name) || currentQuadBot;
      if (!confirm('Bạn có chắc muốn gửi tin nhắn TEST tới TẤT CẢ các nhóm đang bật của ' + botName + '?')) return;

      var statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {{
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test lần lượt tới các nhóm...';
      }}

      try {{
        var res = await fetch('/api/zalo/send-test-all-groups', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ bot_id: currentQuadBot }})
        }});
        var data = await res.json();
        if (res.ok && data.status === 'ok') {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = '✅ <b>Hoàn tất!</b> Đã gửi thành công ' + data.success_count + '/' + data.total + ' nhóm của ' + data.bot_name + '.';
          }}
        }} else {{
          if (statusDiv) {{
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = '❌ <b>Lỗi:</b> ' + (data.detail || 'Không thể gửi test tất cả');
          }}
        }}
      }} catch (err) {{
        if (statusDiv) {{
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = '❌ <b>Lỗi kết nối:</b> ' + err;
        }}
      }}
    }}
  </script>

</body>
</html>
"""
    return html

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)

