import os
import json
import sqlite3
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import hashlib
from datetime import datetime

import database
from zalo_sender import ZaloDispatcher
from scraper import FacebookCometScraper
from supabase_client import SupabaseDispatcher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

app = FastAPI(title="HUIT Social Crawler Dashboard", version="2.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ==================== API ENDPOINTS ====================

@app.get("/api/posts")
def api_get_posts(limit: int = 50, page_name: Optional[str] = None, search: Optional[str] = None):
    posts = database.get_posts(limit=limit, page_name=page_name, search=search)
    return {"status": "ok", "count": len(posts), "data": posts}

@app.get("/api/stats")
def api_get_stats():
    return database.get_stats()

@app.get("/api/logs")
def api_get_logs(limit: int = 100):
    logs = database.get_recent_logs(limit=limit)
    return {"status": "ok", "count": len(logs), "logs": logs}

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
    database.set_bot_status("last_scan_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
                ident = p.get("post_id") or hashlib.md5(p["content"][:150].encode("utf-8")).hexdigest()
                if not database.is_post_seen(ident):
                    database.save_crawled_post(
                        post_id=ident,
                        page_name=pname,
                        author=p.get("author", "Thành viên nhóm"),
                        content=p.get("content", ""),
                        post_url=p.get("post_url", ""),
                        posted_time=p.get("posted_time", "")
                    )
                    database.record_seen_post(ident, pname)
                    database.log_event("POST", f"[{pname}] Bóc tách bài mới: {p.get('content', '')[:70]}...")

                    if supabase.enabled:
                        supabase.push_post(p, pname)
                    
                    filter_kws = cfg.get("filter_keywords", [])
                    txt_lower = p.get("content", "").lower()
                    has_kw = not filter_kws or any(kw.lower() in txt_lower for kw in filter_kws)
                    if has_kw:
                        database.log_event("FILTER", f"Khớp từ khóa -> Đang gửi vào Zalo...")
                        zalo.send_alert(p, pname)
                        database.mark_post_sent_zalo(ident)
                    else:
                        database.log_event("FILTER", f"Bỏ qua Zalo (không chứa từ khóa lọc)")
                    new_posts.append({"page": pname, "author": p.get("author"), "id": ident, "sent_zalo": has_kw})
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
def api_toggle_zalo_group(group_id: str = Form(...)):
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    target_groups = cfg["zalo"].get("target_groups", [])
    
    found = False
    new_status = False
    gname = group_id
    for g in target_groups:
        if str(g.get("id")) == str(group_id):
            g["enabled"] = not g.get("enabled", False)
            new_status = g["enabled"]
            gname = g.get("name", group_id)
            found = True
            break
            
    if not found:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
        
    save_config(cfg)
    database.log_event("ZALO", f"Đã {'BẬT' if new_status else 'TẮT'} nhận tin cho nhóm Zalo [{gname}]")
    return {"status": "ok", "enabled": new_status, "target_groups": target_groups}

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

@app.post("/api/zalo/test_alert")
def api_test_zalo_alert():
    dispatcher = ZaloDispatcher(CONFIG_FILE)
    test_post = {
        "author": "Ban Quản Trị HUIT",
        "posted_time": datetime.now().strftime("%H:%M - %d/%m/%Y"),
        "content": """🔔 THÔNG BÁO KIỂM TRA HỆ THỐNG BOT 24/7

📌 Bài viết thử nghiệm: Mở đăng ký tham gia chương trình Sinh viên Tình nguyện (Được cộng 10 Điểm Rèn Luyện).

Link đăng ký: https://forms.gle/testHuitDocForm2026

Chúc toàn thể sinh viên HUIT học tập thật tốt!""",
        "post_url": "https://www.facebook.com/dtn.hsv.huit"
    }
    sent = dispatcher.send_alert(test_post, "KÊNH KIỂM TRA BOT")
    if sent:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công (kèm @All và Link Form GG Doc) tới các nhóm Zalo được chọn!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm. Kiểm tra kết nối Zalo hoặc chưa bật nhóm nào!")

# ==================== MAIN DASHBOARD HTML VIEW ====================

@app.get("/", response_class=HTMLResponse)
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
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <i class="fa-solid fa-graduation-cap text-lg"></i>
        </div>
        <div>
          <h1 class="font-bold text-lg leading-tight text-slate-900">HUIT Social Feed & Bot</h1>
          <p class="text-xs text-slate-500 font-medium">Bóc tách Comet SSR 24/7 & Lọc Form Bắn Zalo</p>
        </div>
      </div>

      <div class="flex items-center space-x-3">
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
        <div class="bg-slate-950 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="w-3 h-3 rounded-full bg-rose-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
            <span class="ml-2 text-xs font-mono text-slate-400 flex items-center gap-1.5">
              <i class="fa-solid fa-terminal text-blue-400"></i> HUIT Bot Live Output Stream (Tự động cập nhật 2.5s)
            </span>
          </div>
          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" checked class="rounded text-blue-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa Màn Hình
            </button>
            <button onclick="fetchLogs()" class="px-2.5 py-1 text-xs text-blue-400 hover:text-blue-300 bg-blue-950/60 border border-blue-800/60 rounded-md transition">
              <i class="fa-solid fa-rotate"></i> Làm mới
            </button>
          </div>
        </div>

        <div id="console-stream" class="p-4 font-mono text-xs text-slate-300 h-[520px] overflow-y-auto space-y-2 bg-[#0b0f19]">
          <div class="text-slate-500 italic">Đang tải luồng nhật ký từ hệ thống bot...</div>
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
            <input type="text" id="manual-group-id" placeholder="ID Nhóm (vd: 475259879796859360)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 col-span-2">
            <input type="text" id="manual-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm ĐRL K15)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 col-span-2">
          </div>

          <button onclick="handleAddManualZaloGroup()" class="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-check"></i> Lưu Nhóm Thủ Công
          </button>
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
      ['feed', 'console', 'zalo', 'targets'].forEach(t => {{
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
        renderTargetGroups(allTargetGroups);
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

    // ================= LIVE CONSOLE LOGS =================
    async function fetchLogs() {{
      try {{
        const res = await fetch('/api/logs?limit=80');
        const data = await res.json();
        if (data.status === 'ok') {{
          renderLogs(data.logs || []);
        }}
      }} catch (err) {{
        console.error('Lỗi tải logs:', err);
      }}
    }}

    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      const chronologicalLogs = [...logs].reverse();

      container.innerHTML = chronologicalLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at ? l.created_at.split(' ')[1] || l.created_at : '';

        return `
          <div class="flex items-start gap-2.5 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px]">${{timeStr}}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{l.message}}</span>
          </div>
        `;
      }}).join('');

      if (document.getElementById('console-autoscroll').checked) {{
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
              <i class="fa-solid fa-users"></i>
            </div>
            <div>
              <p class="text-sm font-bold text-slate-900 flex items-center gap-2">
                ${{g.name}}
                ${{g.enabled ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">Đang nhận tin</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-200 text-slate-600">Đã tắt</span>'}}
              </p>
              <p class="text-xs text-slate-400 font-mono">Thread ID: ${{g.id}}</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
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
      const fd = new FormData();
      fd.append('group_id', groupId);
      try {{
        const res = await fetch('/api/zalo/toggle_group', {{ method: 'POST', body: fd }});
        const data = await res.json();
        if (data.status === 'ok') {{
          allTargetGroups = data.target_groups;
          renderTargetGroups(allTargetGroups);
          updateZaloStatsBadge();
        }}
      }} catch (err) {{
        alert('Lỗi đổi trạng thái nhóm: ' + err);
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

    // ================= DATA REFRESH LOOP =================
    async function fetchLatestData() {{
      try {{
        const [postsRes, statsRes, targetsRes, logsRes] = await Promise.all([
          fetch('/api/posts?limit=50'),
          fetch('/api/stats'),
          fetch('/api/targets'),
          fetch('/api/logs?limit=80')
        ]);
        const postsData = await postsRes.json();
        const statsData = await statsRes.json();
        const targetsData = await targetsRes.json();
        const logsData = await logsRes.json();

        allPosts = postsData.data || [];
        allTargets = targetsData.targets || [];

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

    renderPosts(allPosts);
    renderTargets(allTargets);
    renderTargetGroups(allTargetGroups);
    fetchLogs();

    setInterval(fetchLogs, 2500);
    setInterval(fetchLatestData, 15000);
  </script>
</body>
</html>
"""
    return html_content

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)
