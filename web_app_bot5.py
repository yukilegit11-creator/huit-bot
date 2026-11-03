import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import database
from zalo_sender import ZaloDispatcher
from zlapi.models import Message, ThreadType

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_OU_FILE = os.path.join(SCRIPT_DIR, "config_ou.json")
DB_FILE = database.OU_DB_FILE
VN_TZ = timezone(timedelta(hours=7))

router = APIRouter()


def get_config_ou() -> dict:
    if not os.path.exists(CONFIG_OU_FILE):
        return {}
    with open(CONFIG_OU_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config_ou(cfg: dict):
    with open(CONFIG_OU_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        import github_sync
        github_sync.push_async(commit_message="🔄 Auto-sync: Cập nhật cấu hình Bot 5 (OU)")
    except Exception:
        pass


# ==================== API ENDPOINTS BOT 5 (OU) ====================

@router.get("/api/bot5/posts")
def api_bot5_get_posts(limit: int = 50, search: Optional[str] = None):
    posts = database.get_posts(limit=limit, search=search, db_file=DB_FILE)
    return {"status": "ok", "count": len(posts), "data": posts}


@router.get("/api/bot5/activities")
def api_bot5_get_activities(limit: int = 50, search: Optional[str] = None):
    acts = database.get_activities(limit=limit, search=search, db_file=DB_FILE)
    return {"status": "ok", "count": len(acts), "data": acts}


@router.get("/api/bot5/stats")
def api_bot5_get_stats():
    stats = database.get_stats(db_file=DB_FILE)
    st = database.get_all_bot_status(db_file=DB_FILE)
    cfg = get_config_ou()
    portal_cfg = cfg.get("ou_portal", {})
    return {
        "status": "ok",
        "bot_enabled": database.is_bot_enabled(db_file=DB_FILE),
        "scan_cycle": st.get("scan_cycle", "0"),
        "last_scan": st.get("last_scan", "Chưa quét"),
        "total_posts": stats.get("total_posts", 0),
        "total_activities": len(database.get_activities(limit=500, db_file=DB_FILE)),
        "student_account": portal_cfg.get("username", "2654092020"),
        "student_name": portal_cfg.get("student_name", "Phan Thị Thu Phương"),
        "stats": stats
    }


@router.get("/api/bot5/logs")
def api_bot5_get_logs(limit: int = 100):
    logs = database.get_recent_logs(limit=limit, db_file=DB_FILE)
    return {"status": "ok", "logs": logs}


@router.post("/api/bot5/toggle")
async def api_bot5_toggle(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    current = database.is_bot_enabled(db_file=DB_FILE)
    new_state = body.get("enabled", not current)
    database.set_bot_enabled(new_state, db_file=DB_FILE)
    action_str = "BẬT" if new_state else "TẮT"
    database.log_event("SYSTEM", f"Admin đã {action_str} Bot 5 (OU) từ Dashboard.", db_file=DB_FILE)
    return {"status": "ok", "enabled": new_state, "message": f"Đã {action_str} Bot 5 (OU ĐRL)"}


@router.get("/api/bot5/zalo/target_groups")
def api_bot5_get_target_groups():
    cfg = get_config_ou()
    tgs = cfg.get("zalo", {}).get("target_groups", [])
    return {"status": "ok", "target_groups": tgs}


@router.post("/api/bot5/zalo/toggle_group")
async def api_bot5_toggle_group(req: Request):
    data = await req.json()
    gid = str(data.get("group_id", "")).strip()
    cfg = get_config_ou()
    tgs = cfg.setdefault("zalo", {}).setdefault("target_groups", [])
    updated = False
    new_val = False
    for g in tgs:
        if str(g.get("id", "")).strip() == gid or (not gid and "phương" in str(g.get("name", "")).lower()):
            cur = g.get("enabled", True)
            g["enabled"] = not cur
            new_val = g["enabled"]
            updated = True
            break
    if updated:
        save_config_ou(cfg)
        return {"status": "ok", "group_id": gid, "enabled": new_val}
    raise HTTPException(status_code=404, detail="Không tìm thấy mục tiêu nhận tin!")


@router.post("/api/bot5/zalo/add_group")
async def api_bot5_add_group(req: Request):
    data = await req.json()
    gid = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip() or gid
    gtype = str(data.get("type", "GROUP")).upper()
    if not gid:
        raise HTTPException(status_code=400, detail="Vui lòng nhập ID hoặc SĐT!")
    cfg = get_config_ou()
    tgs = cfg.setdefault("zalo", {}).setdefault("target_groups", [])
    # Update if exists, else append
    found = False
    for g in tgs:
        if str(g.get("id", "")).strip() == gid or (not g.get("id") and "phương" in name.lower() and "phương" in str(g.get("name", "")).lower()):
            g["id"] = gid
            g["name"] = name
            g["type"] = gtype
            g["enabled"] = True
            found = True
            break
    if not found:
        tgs.append({"id": gid, "name": name, "type": gtype, "enabled": True})
    save_config_ou(cfg)
    return {"status": "ok", "message": f"Đã lưu mục nhận tin '{name}' ({gid})"}


@router.delete("/api/bot5/zalo/target_groups/{group_id}")
def api_bot5_delete_group(group_id: str):
    gid = str(group_id).strip()
    cfg = get_config_ou()
    tgs = cfg.setdefault("zalo", {}).setdefault("target_groups", [])
    cfg["zalo"]["target_groups"] = [g for g in tgs if str(g.get("id", "")).strip() != gid]
    save_config_ou(cfg)
    return {"status": "ok", "message": f"Đã xóa mục tiêu {gid}"}


@router.post("/api/bot5/portal/relogin")
def api_bot5_portal_relogin():
    """Kích hoạt giải Captcha AI và đăng nhập lại Cổng ĐRL OU ngay lập tức."""
    from ou_scraper import OUPortalScraper
    cfg = get_config_ou()
    p_cfg = cfg.get("ou_portal", {})
    scraper = OUPortalScraper(
        username=p_cfg.get("username", "2654092020"),
        password=p_cfg.get("password", "079308035034"),
        config_path=CONFIG_OU_FILE
    )
    ok, msg, cookies = scraper.auto_login()
    if ok:
        database.log_event("SYSTEM", f"Admin đã kích hoạt đăng nhập lại cổng ĐRL OU thành công: {msg}", db_file=DB_FILE)
        return {"status": "ok", "message": msg, "cookies_count": len(cookies)}
    else:
        database.log_event("WARN", f"Đăng nhập lại cổng ĐRL OU thất bại: {msg}", db_file=DB_FILE)
        raise HTTPException(status_code=500, detail=msg)


@router.post("/api/bot5/test_cookie_alert")
def api_bot5_test_cookie_alert():
    """Bắn tin nhắn thử nghiệm Cảnh báo lỗi Cookie về Nhóm demo (7456361874031804652)."""
    cfg = get_config_ou()
    zalo_disp = ZaloDispatcher(config_file=CONFIG_OU_FILE, db_file=DB_FILE)
    if not zalo_disp.connect():
        raise HTTPException(status_code=500, detail="Không thể kết nối Zalo để gửi cảnh báo lỗi!")

    now_vn = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        "⚠️ [Yuki 5 (OU ĐRL) - TEST CẢNH BÁO LỖI COOKIE] ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚨 Nguồn kiểm tra: Web Dashboard Bot 5 (OU)\n"
        "✅ Trạng thái: Kênh gửi cảnh báo sự cố Cookie hoạt động hoàn hảo 100%!\n"
        "👥 Nơi nhận: Nhóm demo (7456361874031804652) & Admin Yuki\n"
        f"⏰ Thời gian: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 Hệ thống điều hành Yuki Multi-Bot 24/7"
    )

    demo_id = "7456361874031804652"
    admin_id = "7581087306337796515"
    results = []

    try:
        zalo_disp.client.send(Message(text=warn_text), thread_id=demo_id, thread_type=ThreadType.GROUP)
        results.append(f"Nhóm demo ({demo_id}): Thành công")
    except Exception as e:
        results.append(f"Nhóm demo ({demo_id}): Thất bại ({e})")

    try:
        zalo_disp.client.send(Message(text=warn_text), thread_id=admin_id, thread_type=ThreadType.USER)
        results.append(f"Admin Yuki ({admin_id}): Thành công")
    except Exception as e:
        results.append(f"Admin Yuki ({admin_id}): Thất bại ({e})")

    database.log_event("TEST", "Đã gửi tin nhắn test cảnh báo lỗi cookie vào Nhóm demo.", db_file=DB_FILE)
    return {"status": "ok", "message": " | ".join(results)}


# ==================== HTML DASHBOARD BOT 5 (OU) ====================

@router.api_route("/bot5", methods=["GET", "HEAD"], response_class=HTMLResponse)
@router.api_route("/ou", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard_view_bot5():
    cfg = get_config_ou()
    stats = database.get_stats(db_file=DB_FILE)
    posts = database.get_posts(limit=25, db_file=DB_FILE)
    activities = database.get_activities(limit=25, db_file=DB_FILE)
    zalo_cfg = cfg.get("zalo", {})
    target_groups = zalo_cfg.get("target_groups", [])
    portal_cfg = cfg.get("ou_portal", {})

    is_bot_active = database.is_bot_enabled(db_file=DB_FILE)
    active_class = "bg-blue-600 hover:bg-blue-700 text-white shadow-blue-600/20" if is_bot_active else "bg-slate-500 hover:bg-slate-600 text-white shadow-slate-500/20"
    active_text = "🟢 BOT OU ĐANG BẬT" if is_bot_active else "🔴 BOT OU ĐÃ TẮT"

    student_name = portal_cfg.get("student_name", "Phan Thị Thu Phương")
    student_user = portal_cfg.get("username", "2654092020")

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bot 5: OU Điểm Rèn Luyện 24/7 (Yuki 5)</title>
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
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <i class="fa-solid fa-graduation-cap text-lg"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-extrabold text-base tracking-tight text-slate-900">Yuki 5</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">OU ĐRL 24/7</span>
            </div>
            <p class="text-[11px] text-slate-500 font-medium">Đại học Mở TP.HCM & Cổng Điểm Rèn Luyện</p>
          </div>
        </div>

        <!-- 5-BOT NAV TABS -->
        <div class="hidden sm:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <a href="/" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🎓 Bot 1: HUIT
          </a>
          <a href="/bot2" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2: VAA
          </a>
          <a href="/bot3" class="px-3 py-1.5 rounded-lg text-rose-700 hover:text-rose-900 transition">
            🔴 Bot 3: IUH
          </a>
          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM
          </a>
          <a href="/bot5" class="px-3 py-1.5 rounded-lg bg-white text-blue-700 shadow-xs border border-blue-200">
            🔵 Bot 5: OU
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold">
            <i class="fa-solid fa-right-from-bracket"></i>
          </a>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <button onclick="toggleBot()" id="bot-toggle-btn" class="px-3.5 py-1.5 rounded-xl font-bold text-xs shadow-md transition flex items-center gap-2 {active_class}">
          <i class="fa-solid fa-power-off"></i>
          <span id="bot-toggle-text">{active_text}</span>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 space-y-6">

    <!-- HERO CARDS -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div class="flex items-center justify-between text-slate-500 mb-2">
          <span class="text-xs font-bold uppercase tracking-wider">Cổng ĐRL OU</span>
          <i class="fa-solid fa-server text-blue-600 text-lg"></i>
        </div>
        <div class="text-lg font-black text-slate-900">{student_name}</div>
        <div class="text-xs text-slate-500 font-mono mt-1">MSSV: {student_user}</div>
        <div class="mt-3 flex items-center gap-2">
          <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">🟢 Giữ Web Sống 24/7</span>
          <button onclick="triggerPortalRelogin()" class="text-[11px] text-blue-600 hover:underline font-bold">Làm mới</button>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div class="flex items-center justify-between text-slate-500 mb-2">
          <span class="text-xs font-bold uppercase tracking-wider">Facebook Fanpage</span>
          <i class="fa-brands fa-facebook text-blue-600 text-lg"></i>
        </div>
        <div class="text-lg font-black text-slate-900">Điểm rèn luyện OU</div>
        <div class="text-xs text-slate-500 mt-1">Cào tự động (Không lọc từ khóa)</div>
        <div class="mt-3">
          <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-sky-100 text-sky-800 border border-sky-200">🍪 Dùng Cookie VAA</span>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div class="flex items-center justify-between text-slate-500 mb-2">
          <span class="text-xs font-bold uppercase tracking-wider">Người Nhận Tin Đích</span>
          <i class="fa-solid fa-user-check text-purple-600 text-lg"></i>
        </div>
        <div class="text-lg font-black text-slate-900">Thu Phương & Nhóm Demo</div>
        <div class="text-xs text-slate-500 mt-1">Zalo 1-on-1 & Nhóm Zalo</div>
        <div class="mt-3 flex items-center gap-1.5">
          <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">Gửi Tin Riêng</span>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div class="flex items-center justify-between text-slate-500 mb-2">
          <span class="text-xs font-bold uppercase tracking-wider">Cảnh Báo Lỗi Cookie</span>
          <i class="fa-solid fa-triangle-exclamation text-amber-500 text-lg"></i>
        </div>
        <div class="text-lg font-black text-slate-900">Bắn Về Nhóm Demo</div>
        <div class="text-xs text-slate-500 mt-1">ID: 7456361874031804652</div>
        <div class="mt-3">
          <button onclick="testCookieAlert()" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane text-[10px]"></i> Bắn Test Cảnh Báo
          </button>
        </div>
      </div>
    </div>

    <!-- MAIN BODY GRID -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- LEFT: CONSOLE LOGS & DATA -->
      <div class="lg:col-span-2 space-y-6">

        <!-- CONSOLE STREAM -->
        <div class="bg-slate-900 rounded-2xl p-5 shadow-lg border border-slate-800">
          <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-rose-500"></span>
              <span class="w-3 h-3 rounded-full bg-amber-500"></span>
              <span class="w-3 h-3 rounded-full bg-emerald-500"></span>
              <span class="text-xs font-bold font-mono text-slate-400 ml-2">Console Live Stream (Bot 5 - OU)</span>
            </div>
            <button onclick="loadLogs()" class="text-slate-400 hover:text-white text-xs font-mono flex items-center gap-1">
              <i class="fa-solid fa-rotate text-[10px]"></i> Làm mới
            </button>
          </div>
          <div id="console-stream" class="h-64 overflow-y-auto font-mono text-xs text-emerald-400 py-3 space-y-1.5">
            <div class="text-slate-500">// Đang tải nhật ký vận hành Bot 5...</div>
          </div>
        </div>

        <!-- RECENT POSTS TABLE -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div class="p-4 border-b border-slate-200 flex items-center justify-between">
            <h3 class="font-bold text-sm text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-newspaper text-blue-600"></i> Bài viết Facebook & Thông báo ĐRL đã cào
            </h3>
            <span class="text-xs text-slate-500 font-semibold">{len(posts)} bài viết</span>
          </div>
          <div class="divide-y divide-slate-100 max-h-96 overflow-y-auto">
            {"".join([f'''
            <div class="p-4 hover:bg-slate-50 transition">
              <div class="flex items-center justify-between text-xs text-slate-500 mb-1">
                <span class="font-bold text-blue-700">{p.get("author", "Điểm rèn luyện OU")}</span>
                <span class="font-mono">{p.get("posted_time", "Vừa xong")}</span>
              </div>
              <div class="text-xs text-slate-800 line-clamp-2">{p.get("content", "")[:200]}</div>
              <div class="mt-2 flex items-center justify-between text-[11px]">
                <a href="{p.get('post_url', '#')}" target="_blank" class="text-blue-600 hover:underline flex items-center gap-1">
                  <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i> Xem bài gốc
                </a>
                <span class="text-slate-400 font-mono">ID: {p.get('post_id', '')}</span>
              </div>
            </div>
            ''' for p in posts]) if posts else '<div class="p-8 text-center text-slate-400 text-xs">Chưa có bài viết nào được ghi nhận.</div>'}
          </div>
        </div>

      </div>

      <!-- RIGHT: TARGET RECIPIENTS & CONFIG -->
      <div class="space-y-6">

        <!-- THU PHƯƠNG & TARGETS CARD -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-bold text-sm text-slate-900 flex items-center gap-2">
              <i class="fa-solid fa-users text-purple-600"></i> Danh sách nhận tin (OU)
            </h3>
            <span class="text-xs font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-lg border border-purple-200">
              {len(target_groups)} mục
            </span>
          </div>

          <div class="space-y-2.5" id="target-groups-list">
            {"".join([f'''
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-bold text-slate-900">{g.get("name", "Mục tiêu")}</span>
                  <span class="text-[10px] font-bold px-1.5 py-0.2 rounded {"bg-purple-100 text-purple-800" if g.get("type") == "USER" else "bg-blue-100 text-blue-800"}">{g.get("type", "GROUP")}</span>
                </div>
                <div class="text-[11px] text-slate-400 font-mono mt-0.5">{g.get("id") or "⚠️ Chưa có UID - Nhập bên dưới"}</div>
              </div>
              <button onclick="toggleGroup('{g.get("id")}')" class="px-2.5 py-1 text-xs font-bold rounded-lg transition { 'bg-emerald-100 text-emerald-800' if g.get('enabled') else 'bg-slate-200 text-slate-500' }">
                { "BẬT" if g.get("enabled") else "TẮT" }
              </button>
            </div>
            ''' for g in target_groups])}
          </div>

          <!-- FORM CẬP NHẬT UID CHO THU PHƯƠNG -->
          <div class="p-3.5 bg-purple-50/70 border border-purple-200 rounded-xl space-y-2">
            <div class="text-xs font-bold text-purple-900 flex items-center gap-1.5">
              <i class="fa-solid fa-user-pen"></i> Cập nhật UID / SĐT cho Thu Phương:
            </div>
            <div class="flex gap-2">
              <input type="text" id="thu-phuong-uid-input" placeholder="Dán Zalo UID hoặc SĐT..." class="flex-1 px-3 py-1.5 bg-white border border-purple-300 rounded-lg text-xs font-mono outline-none focus:border-purple-600">
              <button onclick="saveThuPhuongUid()" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-bold transition">
                Lưu
              </button>
            </div>
            <p class="text-[10px] text-purple-700">Khi có UID Zalo, bot sẽ tự động gửi thẳng bài viết và sự kiện 1-1 cho Thu Phương.</p>
          </div>
        </div>

        <!-- QUICK ACTIONS & SYSTEM INFO -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <h3 class="font-bold text-sm text-slate-900 flex items-center gap-2">
            <i class="fa-solid fa-sliders text-blue-600"></i> Điều khiển nhanh
          </h3>
          <div class="grid grid-cols-1 gap-2">
            <button onclick="triggerPortalRelogin()" class="w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2">
              <i class="fa-solid fa-robot text-blue-600"></i> Giải Captcha & Đăng nhập lại Portal OU
            </button>
            <button onclick="testCookieAlert()" class="w-full py-2.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2">
              <i class="fa-solid fa-triangle-exclamation text-amber-600"></i> Test Bắn Cảnh Báo Cookie (Nhóm demo)
            </button>
            <a href="https://diemrl.ou.edu.vn/test/diemrl/dangkysukien" target="_blank" class="w-full py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-800 border border-blue-200 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2">
              <i class="fa-solid fa-arrow-up-right-from-square"></i> Mở Cổng Đăng Ký Sự Kiện OU
            </a>
          </div>
        </div>

      </div>

    </div>

  </main>

  <script>
    async function loadLogs() {{
      try {{
        const res = await fetch('/api/bot5/logs?limit=50');
        const data = await res.json();
        const container = document.getElementById('console-stream');
        if (data.status === 'ok' && data.logs && data.logs.length > 0) {{
          container.innerHTML = data.logs.map(l => {{
            const color = l.level === 'ERROR' ? 'text-rose-400' : (l.level === 'WARN' ? 'text-amber-400' : 'text-emerald-400');
            return `<div class="${{color}}">[${{l.created_at}}] [${{l.level}}] ${{l.message}}</div>`;
          }}).join('');
          container.scrollTop = container.scrollHeight;
        }}
      }} catch (e) {{}}
    }}

    async function toggleBot() {{
      const res = await fetch('/api/bot5/toggle', {{ method: 'POST' }});
      const data = await res.json();
      if (data.status === 'ok') {{
        location.reload();
      }}
    }}

    async function triggerPortalRelogin() {{
      alert('Đang yêu cầu giải Captcha AI và đăng nhập lại cổng ĐRL OU...');
      try {{
        const res = await fetch('/api/bot5/portal/relogin', {{ method: 'POST' }});
        const data = await res.json();
        alert('Kết quả: ' + data.message);
        loadLogs();
      }} catch (e) {{
        alert('Lỗi: ' + e);
      }}
    }}

    async function testCookieAlert() {{
      if (!confirm('Gửi tin nhắn cảnh báo lỗi cookie thử nghiệm vào Nhóm demo (7456361874031804652)?')) return;
      try {{
        const res = await fetch('/api/bot5/test_cookie_alert', {{ method: 'POST' }});
        const data = await res.json();
        alert('Đã gửi: ' + data.message);
        loadLogs();
      }} catch (e) {{
        alert('Lỗi: ' + e);
      }}
    }}

    async function toggleGroup(gid) {{
      await fetch('/api/bot5/zalo/toggle_group', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ group_id: gid }})
      }});
      location.reload();
    }}

    async function saveThuPhuongUid() {{
      const input = document.getElementById('thu-phuong-uid-input');
      const val = input.value.trim();
      if (!val) {{
        alert('Vui lòng nhập UID hoặc SĐT của Thu Phương!');
        return;
      }}
      const res = await fetch('/api/bot5/zalo/add_group', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ id: val, name: 'Thu Phương', type: 'USER' }})
      }});
      const data = await res.json();
      alert('Thành công: ' + data.message);
      location.reload();
    }}

    // Auto-refresh logs every 4 seconds
    loadLogs();
    setInterval(loadLogs, 4000);
  </script>
</body>
</html>
"""
    return html
