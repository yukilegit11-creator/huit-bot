import os
import json
import sqlite3
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

@app.middleware("http")
async def handle_head_and_monitor_requests(request: Request, call_next):
    # Trả về 200 OK ngay lập tức cho các yêu cầu kiểm tra trạng thái sống (HEAD method từ UptimeRobot / BetterStack / Render)
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"})
    return await call_next(request)

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
    return {"status": "ok", "count": len(logs), "logs": logs}

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

@app.post("/api/zalo/test_alert")
def api_test_zalo_alert():
    dispatcher = ZaloDispatcher(CONFIG_FILE)
    test_post = {
        "author": "Ban Quản Trị HUIT",
        "posted_time": datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M - %d/%m/%Y"),
        "content": """🔔 THÔNG BÁO KIỂM TRA HỆ THỐNG BOT 24/7

📌 Bài viết thử nghiệm: Mở đăng ký tham gia chương trình Sinh viên Tình nguyện (Được cộng 10 Điểm Rèn Luyện).

Link đăng ký: https://forms.gle/testHuitDocForm2026

Chúc toàn thể sinh viên HUIT học tập thật tốt!""",
        "post_url": "https://www.facebook.com/dtn.hsv.huit",
        "is_manual_test": True,
        "creation_time": datetime.now().timestamp()
    }
    sent = dispatcher.send_alert(test_post, "KÊNH KIỂM TRA BOT")
    if sent:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công (kèm @All và Link Form GG Doc) tới các nhóm Zalo được chọn!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm. Kiểm tra kết nối Zalo hoặc chưa bật nhóm nào!")

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
    return {"status": "ok", "count": len(logs), "logs": logs}

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
        "author": "Ban Quản Trị Bot Kênh 2",
        "posted_time": datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M - %d/%m/%Y"),
        "content": """🔔 THÔNG BÁO KIỂM TRA BOT KÊNH 2 (RIÊNG BIỆT)

📌 Bài viết thử nghiệm: Mở form đăng ký tham gia chương trình hoạt động.

Link đăng ký: https://forms.gle/testBot2FormRegistration2026

Chúc các bạn theo dõi thuận lợi!""",
        "post_url": "https://www.facebook.com",
        "is_manual_test": True,
        "creation_time": datetime.now().timestamp()
    }
    sent = dispatcher.send_alert(test_post, "KÊNH KIỂM TRA BOT 2")
    if sent:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công (kèm @All và Link Form GG Doc) cho Bot 2!"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi tin thử nghiệm. Kiểm tra kết nối Zalo hoặc chưa bật nhóm nào!")

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
    return {"status": "ok", "count": len(logs), "logs": logs}

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
    test_act = {
        "activity_id": "test_9999",
        "title": "Hoạt động thử nghiệm kiểm tra kết nối Bot IUH & Bắn Zalo",
        "semester": "1/2026 - 2027",
        "points": 3.0,
        "deadline": datetime.now(timezone(timedelta(hours=7))).strftime("%d-%m-%Y"),
        "status": "Đang mở",
        "slots": "150/150",
        "details": "Thời gian: Ngay bây giờ\nĐịa điểm: Hội trường E4 IUH\nYêu cầu: Tham gia nghiêm túc, đúng giờ."
    }
    sent = send_zalo_iuh(zalo, test_act, is_reopened=False)
    if sent:
        return {"status": "ok", "message": "Đã bắn tin thử nghiệm thành công tới nhóm demo và Trần Lê Phát!"}
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
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE: TRẦN LÊ PHÁT -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-blue-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Trần Lê Phát</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Admin Active"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-blue-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
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
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE: TRẦN LÊ PHÁT -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-sky-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Trần Lê Phát</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Admin Active"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-sky-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
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
        <div class="bg-slate-950 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="w-3 h-3 rounded-full bg-rose-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
            <span class="ml-2 text-xs font-mono text-slate-400 flex items-center gap-1.5">
              <i class="fa-solid fa-terminal text-sky-400"></i> VAA Bot Live Output Stream (Tự động cập nhật 2.5s)
            </span>
          </div>
          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" checked class="rounded text-sky-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa Màn Hình
            </button>
            <button onclick="fetchLogs()" class="px-2.5 py-1 text-xs text-sky-400 hover:text-sky-300 bg-sky-950/60 border border-sky-800/60 rounded-md transition">
              <i class="fa-solid fa-rotate"></i> Làm mới
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
            <input type="text" id="manual-group-id" placeholder="ID Nhóm (vd: 475259879796859360)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 col-span-2">
            <input type="text" id="manual-group-name" placeholder="Tên gợi nhớ nhóm (vd: Nhóm Sự Kiện VAA)" class="px-3 py-2 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 col-span-2">
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

    // ================= LIVE CONSOLE LOGS =================
    async function fetchLogs() {{
      try {{
        const res = await fetch(API_BASE + '/logs?limit=80');
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
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-rose-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Trần Lê Phát</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-rose-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- GITHUB SYNC BUTTON -->
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
          <p class="text-[11px] text-slate-400 mt-0.5">demo & Trần Lê Phát</p>
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
        <div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-md p-5 flex flex-col h-[380px]">
          <div class="flex items-center justify-between pb-3 border-b border-slate-800 mb-2">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <h3 class="font-bold text-xs text-slate-200 font-mono tracking-wider uppercase">System Console Logs</h3>
            </div>
            <button onclick="fetchLogs()" class="text-[11px] text-slate-400 hover:text-white transition font-mono">
              <i class="fa-solid fa-rotate-right"></i>
            </button>
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
      const gname = prompt('Nhập Tên gợi nhớ (Ví dụ: demo hoặc Trần Lê Phát):', 'demo');
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

    async function fetchLogs() {{
      try {{
        const res = await fetch('/api/bot3/logs?limit=40');
        const data = await res.json();
        const container = document.getElementById('console-stream');
        if (data.logs) {{
          container.innerHTML = data.logs.map(l => {{
            let color = 'text-slate-400';
            if (l.level === 'WARN') color = 'text-amber-400';
            else if (l.level === 'ERROR') color = 'text-rose-400';
            else if (l.level === 'ZALO' || l.level === 'ACTIVITY') color = 'text-emerald-400';
            return `<div><span class="text-slate-500 font-mono">[${{l.created_at.split(' ')[1] || l.created_at}}]</span> <span class="font-bold ${{color}}">[${{l.level}}]</span> ${{l.message}}</div>`;
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
        if (s.cookie_status === 'valid') {{
          cookieBadge.innerHTML = '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-100 text-emerald-800 border border-emerald-300">🟢 Cookie Hoạt Động</span>';
        }} else {{
          cookieBadge.innerHTML = '<span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">🔴 Cookie Hết Hạn / Chưa Đăng Nhập</span>';
        }}

        if (a.data) {{
          allActivities = a.data;
          renderActivities(allActivities);
        }}
        await fetchHistory();
      }} catch (e) {{}}
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
    setInterval(fetchLogs, 2500);
    setInterval(fetchLatestData, 10000);
    setInterval(fetchHistory, 10000);
  </script>
</body>
</html>
"""
    return html

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)

