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

app = FastAPI(title="HUIT Social Crawler Dashboard", version="2.0")

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

@app.get("/api/posts")
def api_get_posts(limit: int = 50, page_name: Optional[str] = None, search: Optional[str] = None):
    posts = database.get_posts(limit=limit, page_name=page_name, search=search)
    return {"status": "ok", "count": len(posts), "data": posts}

@app.get("/api/stats")
def api_get_stats():
    return database.get_stats()

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
                    if supabase.enabled:
                        supabase.push_post(p, pname)
                    zalo.send_alert(p, pname)
                    new_posts.append({"page": pname, "author": p.get("author"), "id": ident})
        except Exception as e:
            database.set_bot_status("last_error", str(e))

    database.set_bot_status("bot_state", "sleeping")
    return {"status": "ok", "new_posts_count": len(new_posts), "posts": new_posts}


@app.get("/api/targets")
def api_get_targets():
    cfg = get_config()
    return {"status": "ok", "targets": cfg.get("targets", [])}

@app.post("/api/targets")
def api_add_target(name: str = Form(...), url: str = Form(...)):
    cfg = get_config()
    targets = cfg.get("targets", [])
    new_id = f"target_{len(targets) + 1}_{int(database.datetime.now().timestamp())}"
    targets.append({
        "id": new_id,
        "name": name.strip(),
        "url": url.strip()
    })
    cfg["targets"] = targets
    save_config(cfg)
    return {"status": "ok", "message": "Đã thêm trang thành công!", "targets": targets}

@app.delete("/api/targets/{target_id}")
def api_delete_target(target_id: str):
    cfg = get_config()
    targets = cfg.get("targets", [])
    new_targets = [t for t in targets if t.get("id") != target_id]
    cfg["targets"] = new_targets
    save_config(cfg)
    return {"status": "ok", "message": "Đã xóa trang thành công!", "targets": new_targets}

@app.get("/api/zalo/groups")
def api_get_zalo_groups():
    try:
        dispatcher = ZaloDispatcher(CONFIG_FILE)
        groups = dispatcher.get_groups()
        return {"status": "ok", "groups": groups}
    except Exception as e:
        return {"status": "error", "message": str(e), "groups": []}

@app.post("/api/zalo/target")
def api_set_zalo_target(thread_id: str = Form(...), group_name: str = Form(...)):
    cfg = get_config()
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    cfg["zalo"]["target_thread_id"] = thread_id.strip()
    cfg["zalo"]["target_group_name"] = group_name.strip()
    save_config(cfg)
    return {"status": "ok", "message": f"Đã đổi nhóm nhận tin thành '{group_name}'"}

@app.get("/", response_class=HTMLResponse)
def dashboard_view():
    cfg = get_config()
    stats = database.get_stats()
    posts = database.get_posts(limit=30)
    targets = cfg.get("targets", [])
    zalo_cfg = cfg.get("zalo", {})

    posts_json = json.dumps(posts, ensure_ascii=False)
    targets_json = json.dumps(targets, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)
    zalo_cfg_json = json.dumps(zalo_cfg, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HUIT Feed & Zalo Bot Monitor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .glass {{ background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(12px); }}
    .dark .glass {{ background: rgba(17, 24, 39, 0.85); }}
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP NAVBAR -->
  <header class="glass sticky top-0 z-50 border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <i class="fa-solid fa-graduation-cap text-lg"></i>
        </div>
        <div>
          <h1 class="font-bold text-lg leading-tight text-slate-900">HUIT Social Feed & Bot</h1>
          <p class="text-xs text-slate-500 font-medium">Tự động bóc tách Comet SSR 24/7 & Bắn Zalo</p>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <span id="bot-status-badge" class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Bot Đang Chạy 24/7
        </span>
        <button onclick="fetchLatestData()" class="p-2 text-slate-500 hover:text-blue-600 rounded-lg hover:bg-slate-100 transition" title="Làm mới dữ liệu">
          <i class="fa-solid fa-rotate text-sm"></i>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">

    <!-- STATS CARDS -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tổng Bài Đã Cào</p>
          <h3 id="stat-total-posts" class="text-3xl font-extrabold text-slate-900 mt-1">{stats['total_posts']}</h3>
          <p class="text-xs text-slate-400 mt-1">Đã lưu trữ hệ thống</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-newspaper"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Đã Gửi Vào Zalo</p>
          <h3 id="stat-total-zalo" class="text-3xl font-extrabold text-indigo-600 mt-1">{stats['total_zalo_sent']}</h3>
          <p class="text-xs text-slate-400 mt-1">Nhóm: {zalo_cfg.get('target_group_name', 'Mục nhận tin')}</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-paper-plane"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Nguồn Theo Dõi</p>
          <h3 id="stat-total-targets" class="text-3xl font-extrabold text-slate-900 mt-1">{len(targets)}</h3>
          <p class="text-xs text-slate-400 mt-1">Fanpage & Group</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-bullseye"></i>
        </div>
      </div>

      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div>
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vòng Quét Gần Nhất</p>
          <h3 id="stat-scan-cycle" class="text-xl font-bold text-slate-900 mt-1">Vòng #{stats['scan_cycle']}</h3>
          <p id="stat-last-scan" class="text-xs text-slate-400 mt-1 truncate max-w-[150px]">{stats['last_scan_time']}</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock-rotate-left"></i>
        </div>
      </div>
    </div>

    <!-- TABS NAVIGATION -->
    <div class="flex border-b border-slate-200 space-x-6">
      <button onclick="switchTab('feed')" id="tab-btn-feed" class="pb-3 text-sm font-semibold border-b-2 border-blue-600 text-blue-600 flex items-center gap-2">
        <i class="fa-solid fa-stream"></i> Bảng Tin Mới Nhất
      </button>
      <button onclick="switchTab('targets')" id="tab-btn-targets" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2">
        <i class="fa-solid fa-link"></i> Quản Lý Nguồn Quét ({len(targets)})
      </button>
      <button onclick="switchTab('zalo')" id="tab-btn-zalo" class="pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2">
        <i class="fa-solid fa-comments"></i> Cấu Hình Nhóm Zalo
      </button>
    </div>

    <!-- TAB 1: FEED VIEW -->
    <div id="tab-feed" class="space-y-6">
      <!-- FILTERS -->
      <div class="bg-white p-4 rounded-xl border border-slate-200/80 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div class="relative w-full md:w-80">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
          <input type="text" id="search-input" onkeyup="filterPosts()" placeholder="Tìm nội dung, tác giả..." class="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div class="flex gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <button onclick="setFilterPage('')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white">Tất cả</button>
          <button onclick="setFilterPage('Group Sinh Viên HUIT')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">Group SV HUIT</button>
          <button onclick="setFilterPage('Đoàn - Hội HUIT')" class="page-filter-btn px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200">ĐTN - HSV</button>
        </div>
      </div>

      <!-- FEED LIST -->
      <div id="posts-container" class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- Rendered by JavaScript -->
      </div>
    </div>

    <!-- TAB 2: TARGET MANAGEMENT -->
    <div id="tab-targets" class="hidden space-y-6">
      <div class="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm">
        <h3 class="font-bold text-slate-900 text-base mb-1">Thêm Đường Link Fanpage / Group Cần Quét</h3>
        <p class="text-xs text-slate-500 mb-4">Điền link trang Facebook, hệ thống sẽ tự động quét và bóc tách bài đăng mới 24/7.</p>
        <form onsubmit="handleAddTarget(event)" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input type="text" id="new-target-name" required placeholder="Tên Fanpage / Khoa (vd: CLB Marketing)" class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <input type="url" id="new-target-url" required placeholder="https://www.facebook.com/..." class="px-4 py-2.5 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:col-span-2">
          <div class="sm:col-span-3 flex justify-end">
            <button type="submit" class="px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm flex items-center gap-2">
              <i class="fa-solid fa-plus"></i> Thêm Trang Theo Dõi
            </button>
          </div>
        </form>
      </div>

      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-100">
          <h4 class="font-bold text-slate-900 text-sm">Danh Sách Mục Tiêu Đang Quét ({len(targets)})</h4>
        </div>
        <div id="targets-table-body" class="divide-y divide-slate-100">
          <!-- Rendered by JS -->
        </div>
      </div>
    </div>

    <!-- TAB 3: ZALO SETTINGS -->
    <div id="tab-zalo" class="hidden space-y-6">
      <div class="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm max-w-2xl">
        <h3 class="font-bold text-slate-900 text-base mb-1">Cấu Hình Nhóm Zalo Nhận Thông Báo</h3>
        <p class="text-xs text-slate-500 mb-5">Chọn nhóm nhận thông báo tự động từ danh sách các nhóm tài khoản Bot đang tham gia.</p>

        <div class="space-y-4">
          <div class="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <p class="text-xs font-semibold text-slate-500">Nhóm nhận tin hiện tại:</p>
              <p id="current-zalo-target" class="font-bold text-slate-900 text-sm mt-0.5">{zalo_cfg.get('target_group_name', 'Mục nhận tin')} <span class="text-xs font-normal text-slate-500">({zalo_cfg.get('target_thread_id', '')})</span></p>
            </div>
            <button onclick="fetchZaloGroups()" class="px-3 py-1.5 text-xs font-semibold bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-100 flex items-center gap-1.5 shadow-xs">
              <i class="fa-solid fa-arrows-rotate"></i> Quét Danh Sách Nhóm
            </button>
          </div>

          <div id="zalo-groups-selector" class="space-y-2">
            <label class="text-xs font-semibold text-slate-700">Chọn nhóm nhận tin mới:</label>
            <select id="select-zalo-group" class="w-full px-3.5 py-2.5 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">-- Đang tải danh sách nhóm --</option>
            </select>
          </div>

          <button onclick="saveZaloTargetSelection()" class="px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm flex items-center gap-2">
            <i class="fa-solid fa-floppy-disk"></i> Lưu Nhóm Nhận Tin
          </button>
        </div>
      </div>
    </div>

  </main>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    let allPosts = {posts_json};
    let allTargets = {targets_json};
    let currentFilterPage = '';

    function switchTab(tab) {{
      ['feed', 'targets', 'zalo'].forEach(t => {{
        document.getElementById('tab-' + t).classList.add('hidden');
        document.getElementById('tab-btn-' + t).classList.remove('border-blue-600', 'text-blue-600');
        document.getElementById('tab-btn-' + t).classList.add('border-transparent', 'text-slate-500');
      }});
      document.getElementById('tab-' + tab).classList.remove('hidden');
      document.getElementById('tab-btn-' + tab).classList.add('border-blue-600', 'text-blue-600');
      document.getElementById('tab-btn-' + tab).classList.remove('border-transparent', 'text-slate-500');

      if (tab === 'zalo') {{
        fetchZaloGroups();
      }}
    }}

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
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md transition flex flex-col justify-between">
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
              ${{p.is_sent_zalo ? '<span class="text-emerald-600 font-medium flex items-center gap-1"><i class="fa-solid fa-check-circle"></i> Đã gửi Zalo</span>' : '<span class="text-slate-400">Chờ gửi Zalo</span>'}}
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

    async function fetchLatestData() {{
      try {{
        const [postsRes, statsRes, targetsRes] = await Promise.all([
          fetch('/api/posts?limit=50'),
          fetch('/api/stats'),
          fetch('/api/targets')
        ]);
        const postsData = await postsRes.json();
        const statsData = await statsRes.json();
        const targetsData = await targetsRes.json();

        allPosts = postsData.data || [];
        allTargets = targetsData.targets || [];

        document.getElementById('stat-total-posts').innerText = statsData.total_posts;
        document.getElementById('stat-total-zalo').innerText = statsData.total_zalo_sent;
        document.getElementById('stat-total-targets').innerText = allTargets.length;
        document.getElementById('stat-scan-cycle').innerText = 'Vòng #' + statsData.scan_cycle;
        document.getElementById('stat-last-scan').innerText = statsData.last_scan_time;

        filterPosts();
        renderTargets(allTargets);
      }} catch (err) {{
        console.error('Lỗi cập nhật:', err);
      }}
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

    async function fetchZaloGroups() {{
      const select = document.getElementById('select-zalo-group');
      select.innerHTML = '<option value="">Đang tải danh sách nhóm Zalo...</option>';
      try {{
        const res = await fetch('/api/zalo/groups');
        const data = await res.json();
        if (data.groups && data.groups.length > 0) {{
          select.innerHTML = data.groups.map(g => `<option value="${{g.id}}" data-name="${{g.name}}">${{g.name}} (${{g.id}})</option>`).join('');
        }} else {{
          select.innerHTML = '<option value="">Không tìm thấy nhóm hoặc lỗi kết nối</option>';
        }}
      }} catch (err) {{
        select.innerHTML = '<option value="">Lỗi tải nhóm</option>';
      }}
    }}

    async function saveZaloTargetSelection() {{
      const select = document.getElementById('select-zalo-group');
      const opt = select.options[select.selectedIndex];
      if (!opt || !opt.value) return alert('Vui lòng chọn 1 nhóm');
      const threadId = opt.value;
      const groupName = opt.getAttribute('data-name');

      const formData = new FormData();
      formData.append('thread_id', threadId);
      formData.append('group_name', groupName);

      const res = await fetch('/api/zalo/target', {{ method: 'POST', body: formData }});
      if (res.ok) {{
        alert('Đã cập nhật nhóm nhận tin thành: ' + groupName);
        document.getElementById('current-zalo-target').innerHTML = groupName + ` <span class="text-xs font-normal text-slate-500">(${{threadId}})</span>`;
      }}
    }}

    // Khởi tạo ban đầu
    renderPosts(allPosts);
    renderTargets(allTargets);

    // Tự động polling mỗi 20s
    setInterval(fetchLatestData, 20000);
  </script>
</body>
</html>
"""
    return html_content

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)
