import os
import sys
import json
import sqlite3
import threading
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

import importlib.util

# Nạp database riêng của UFM
_db_spec = importlib.util.spec_from_file_location("ufm_db_local", os.path.join(SCRIPT_DIR, "database.py"))
database = importlib.util.module_from_spec(_db_spec)
_db_spec.loader.exec_module(database)

# Nạp scraper, sender, batch register từ local
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from zalo_sender import ZaloDispatcher
from ufm_scraper import UFMPortalScraper
from batch_register import check_student_cookie, execute_batch_registration, BATCH_PROGRESS
import smart_parser

# Messenger (tùy chọn)
try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

app = FastAPI(title="Yuki 4 - UFM Bot Dashboard (Đại học Tài chính - Marketing)", version="2.0")


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

@app.get("/health")
def health():
    return {"status": "ok", "service": "ufm_bot", "time": database.get_vn_now_str()}

@app.get("/ping")
def ping():
    return Response(content="pong", media_type="text/plain", status_code=200)

@app.get("/api/status")
def api_status():
    stats = database.get_stats()
    bot_status = database.get_all_bot_status()
    st_stats = database.get_student_stats()
    cfg = get_config()
    return {
        "is_active": database.is_bot_enabled(),
        "bot_state": bot_status.get("bot_state", "stopped"),
        "total_scans": bot_status.get("total_scans", "0"),
        "last_scan_time": bot_status.get("last_scan_time", "Chưa quét"),
        "portal_cookie_status": bot_status.get("portal_cookie_status", "valid"),
        "zalo_cookie_status": bot_status.get("zalo_cookie_status", "valid"),
        "zalo_cookie_error": bot_status.get("zalo_cookie_error", ""),
        "zalo_account_uid": bot_status.get("zalo_account_uid", ""),
        "zalo_last_connected": bot_status.get("zalo_last_connected", ""),
        "messenger_enabled": cfg.get("messenger", {}).get("enabled", False),
        "messenger_cookie_status": bot_status.get("messenger_cookie_status", "unknown"),
        "messenger_cookie_error": bot_status.get("messenger_cookie_error", ""),
        "messenger_account_uid": bot_status.get("messenger_account_uid", ""),
        "messenger_last_connected": bot_status.get("messenger_last_connected", ""),
        "stats": stats,
        "student_stats": st_stats,
        "bot_name": cfg.get("bot_name", "Yuki 4 (UFM)"),
        "instance_name": cfg.get("instance_name", "Bot UFM")
    }

@app.post("/api/bot/toggle")
def toggle_bot(data: dict = None):
    curr = database.is_bot_enabled()
    new_state = not curr
    database.set_bot_enabled(new_state)
    return {"success": True, "is_active": new_state, "message": f"Bot UFM đã {'BẬT' if new_state else 'TẮT'}"}

@app.post("/api/bot/scan-now")
def scan_now():
    cfg = get_config()
    portal = cfg.get("ufm_portal", {})
    scraper = UFMPortalScraper(portal.get("cookies"), portal.get("username"), portal.get("password"), config_path=CONFIG_FILE)
    ok, msg, activities = scraper.fetch_all_events()
    if not ok:
        database.log_event("WARN", f"Quét thủ công thất bại: {msg}")
        return {"success": False, "message": msg}

    zalo = ZaloDispatcher(CONFIG_FILE)
    # Messenger
    msger = None
    if HAS_MESSENGER and cfg.get("messenger", {}).get("enabled", False):
        msger = MessengerDispatcher(CONFIG_FILE)
    new_count = 0
    reopened_count = 0

    for act in activities:
        aid = str(act["activity_id"])
        existing = database.get_seen_activity(aid)
        if existing is not None:
            old_is_full = bool(existing.get("is_full", 0))
            new_is_full = bool(act.get("is_full", False))
            database.update_activity_status(aid, act.get("status", ""), new_is_full)
            if old_is_full and not new_is_full and "mở đăng ký" in act.get("status", "").lower():
                reopened_count += 1
                database.add_crawled_activity(act, action_type="REOPENED", is_sent=True)
                zalo.send_activity_alert(act, is_reopened=True)
                if msger:
                    try:
                        msger.send_activity_alert(act, is_reopened=True)
                    except Exception:
                        pass
            continue

        new_count += 1
        database.record_seen_activity(act, is_sent=True)
        database.add_crawled_activity(act, action_type="NEW", is_sent=True)
        zalo.send_activity_alert(act, is_reopened=False)
        if msger:
            try:
                msger.send_activity_alert(act, is_reopened=False)
            except Exception:
                pass

    now_str = database.get_vn_now_str()
    database.set_bot_status("last_scan_time", now_str)
    database.log_event("MANUAL", f"Quét thủ công thành công: {len(activities)} hoạt động (Mới: {new_count}, Mở slot: {reopened_count})")
    return {
        "success": True,
        "message": f"Quét thành công {len(activities)} hoạt động! Phát hiện {new_count} bài mới, {reopened_count} bài mở thêm slot.",
        "total_fetched": len(activities),
        "new_count": new_count
    }

@app.post("/api/test-zalo")
def test_zalo(target_id: Optional[str] = None):
    zalo = ZaloDispatcher(CONFIG_FILE)
    success, msg = zalo.send_test_message(target_thread_id=target_id)
    return {"success": success, "message": msg}

@app.get("/api/logs")
def get_logs(limit: int = 150):
    logs = database.get_recent_logs(limit)
    return {"logs": logs, "count": len(logs), "server_time": database.get_vn_now_str()}

@app.get("/api/all-logs")
def get_all_logs(limit: int = 150, bot: Optional[str] = None):
    all_logs = []
    root_huit_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
    
    # 1. HUIT
    huit_db = os.path.join(root_huit_dir, "huit_bot.db")
    if os.path.exists(huit_db):
        try:
            conn = sqlite3.connect(huit_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            for r in rows:
                ld = dict(r)
                ld["bot"] = "HUIT"
                ld["bot_badge"] = "Bot 1 (HUIT)"
                ld["bot_color"] = "text-blue-400 bg-blue-950/80 border-blue-800"
                all_logs.append(ld)
            conn.close()
        except Exception:
            pass

    # 2. VAA
    vaa_db = os.path.join(root_huit_dir, "bot2.db")
    if os.path.exists(vaa_db):
        try:
            conn = sqlite3.connect(vaa_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            for r in rows:
                ld = dict(r)
                ld["bot"] = "VAA"
                ld["bot_badge"] = "Bot 2 (VAA)"
                ld["bot_color"] = "text-sky-400 bg-sky-950/80 border-sky-800"
                all_logs.append(ld)
            conn.close()
        except Exception:
            pass

    # 3. IUH
    iuh_db = os.path.join(root_huit_dir, "iuh_bot.db")
    if os.path.exists(iuh_db):
        try:
            conn = sqlite3.connect(iuh_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            for r in rows:
                ld = dict(r)
                ld["bot"] = "IUH"
                ld["bot_badge"] = "Bot 3 (IUH)"
                ld["bot_color"] = "text-rose-400 bg-rose-950/80 border-rose-800"
                all_logs.append(ld)
            conn.close()
        except Exception:
            pass

    # 4. UFM
    try:
        ufm_logs = database.get_recent_logs(limit)
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

@app.get("/api/activities")
def get_activities(limit: int = 100):
    acts = database.get_recent_activities(limit)
    return {"activities": acts}

@app.get("/api/delivery-history")
def get_history(limit: int = 100):
    hist = database.get_delivery_history(limit)
    return {"history": hist}

@app.get("/api/config")
def api_get_config():
    return get_config()

@app.post("/api/config/save")
def api_save_config(new_cfg: dict):
    save_config(new_cfg)
    database.log_event("CONFIG", "Đã cập nhật cấu hình hệ thống từ Web Dashboard.")
    return {"success": True, "message": "Cấu hình đã được lưu thành công!"}

@app.post("/api/portal/login")
def api_portal_login():
    cfg = get_config()
    portal = cfg.get("ufm_portal", {})
    scraper = UFMPortalScraper(portal.get("cookies"), portal.get("username"), portal.get("password"), config_path=CONFIG_FILE)
    ok, msg = scraper.login()
    if ok:
        database.set_bot_status("portal_cookie_status", "valid")
        database.log_event("AUTH", f"Đăng nhập UFM thủ công thành công: {msg}")
    else:
        database.set_bot_status("portal_cookie_status", "expired")
        database.log_event("AUTH", f"Đăng nhập UFM thủ công thất bại: {msg}")
    return {"success": ok, "message": msg}

@app.get("/api/zalo/fetch-groups")
def api_fetch_zalo_groups():
    zalo = ZaloDispatcher(CONFIG_FILE)
    if not zalo.connect():
        return {"success": False, "message": "Không thể kết nối tới Zalo Web", "groups": []}
    try:
        groups_raw = zalo.client.fetchAllGroups()
        group_list = []
        if hasattr(groups_raw, "gridVerMap"):
            for gid in groups_raw.gridVerMap.keys():
                info = zalo.client.fetchGroupInfo(gid)
                gname = ""
                if hasattr(info, "gridInfoMap") and gid in info.gridInfoMap:
                    gname = info.gridInfoMap[gid].get("name", "")
                elif hasattr(info, "name"):
                    gname = info.name
                group_list.append({"id": str(gid), "name": gname or f"Nhóm {gid}"})
        return {"success": True, "groups": group_list}
    except Exception as e:
        return {"success": False, "message": str(e), "groups": []}

@app.post("/api/zalo/check-status")
def api_zalo_check_status():
    zalo = ZaloDispatcher(CONFIG_FILE)
    ok = zalo.connect()
    b_status = database.get_all_bot_status()
    if ok:
        uid = zalo.client.uid() if callable(zalo.client.uid) else zalo.client.uid
        return {
            "success": True,
            "status": "valid",
            "uid": str(uid),
            "message": f"Cookie Zalo đang hoạt động rất tốt (UID: {uid})!"
        }
    else:
        err = b_status.get("zalo_cookie_error") or "Không thể kết nối tới Zalo Web (Cookie đã hết hạn hoặc bị hủy)"
        return {
            "success": False,
            "status": "expired",
            "message": f"Phiên Zalo đã bị hủy hoặc hết hạn: {err}"
        }

@app.post("/api/zalo/send-demo-alert")
def api_zalo_send_demo_alert():
    """Gửi bài viết/hoạt động thông báo vào nhóm demo (ID: 475259879796859360)."""
    try:
        zalo = ZaloDispatcher(CONFIG_FILE)
        ok, msg = zalo.send_demo_group_alert()
        return {"success": ok, "message": msg}
    except Exception as e:
        err = f"Lỗi thực thi gửi thông báo nhóm demo: {e}"
        database.log_event("ERROR", err)
        return {"success": False, "message": err}

@app.post("/api/zalo/update-cookies")
def api_zalo_update_cookies(data: dict):
    raw_cookie = data.get("cookies")
    if not raw_cookie:
        return {"success": False, "message": "Vui lòng dán chuỗi JSON hoặc mảng Cookie Zalo!"}
    
    cookie_dict = {}
    if isinstance(raw_cookie, str):
        raw_cookie = raw_cookie.strip()
        try:
            parsed = json.loads(raw_cookie)
        except Exception as e:
            return {"success": False, "message": f"Dữ liệu dán vào không phải JSON hợp lệ: {e}"}
    else:
        parsed = raw_cookie
    
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict) and "name" in item and "value" in item:
                cookie_dict[item["name"]] = item["value"]
    elif isinstance(parsed, dict):
        cookie_dict = parsed
    else:
        return {"success": False, "message": "Định dạng Cookie không đúng (phải là mảng hoặc JSON object)!"}
    
    if not cookie_dict.get("zpw_sek") and not cookie_dict.get("zpsid"):
        return {"success": False, "message": "Thiếu token 'zpw_sek' hoặc 'zpsid' trong danh sách Cookie!"}
    
    cfg = get_config()
    zalo_cfg = cfg.get("zalo", {})
    imei = zalo_cfg.get("imei") or "285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7"
    
    try:
        from zlapi import ZaloAPI
        try:
            test_client = ZaloAPI(phone="", password="", imei=imei, cookies=cookie_dict)
        except TypeError:
            test_client = ZaloAPI(phone="", password="", imei=imei, session_cookies=cookie_dict)
        
        test_uid = test_client.uid() if callable(test_client.uid) else test_client.uid
        if not test_uid:
            raise Exception("Không trích xuất được UID Zalo sau khi đăng nhập.")
    except Exception as e:
        return {"success": False, "message": f"Kiểm tra thất bại! Cookie không hợp lệ hoặc đã bị hủy: {e}"}
    
    if "zalo" not in cfg:
        cfg["zalo"] = {}
    cfg["zalo"]["cookies"] = cookie_dict
    save_config(cfg)
    
    # Đồng bộ sang config_ufm.json ở root nếu có
    root_cfg_ufm = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "config_ufm.json"))
    if os.path.exists(root_cfg_ufm):
        try:
            with open(root_cfg_ufm, "r", encoding="utf-8") as f:
                rcfg = json.load(f)
            if "zalo" in rcfg:
                rcfg["zalo"]["cookies"] = cookie_dict
                with open(root_cfg_ufm, "w", encoding="utf-8") as f:
                    json.dump(rcfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    database.set_bot_status("zalo_cookie_status", "valid")
    database.set_bot_status("zalo_cookie_error", "")
    database.set_bot_status("zalo_account_uid", str(test_uid))
    database.set_bot_status("zalo_last_connected", database.get_vn_now_str())
    database.log_event("AUTH", f"✅ Đã cập nhật Cookie Zalo thành công qua Web UI (UID: {test_uid})")
    
    return {
        "success": True, 
        "message": f"Tuyệt vời! Đã cập nhật và xác thực thành công tài khoản Zalo (UID: {test_uid})!",
        "uid": str(test_uid)
    }

# ========================================================
# CÁC API CHO FACEBOOK MESSENGER
# ========================================================

@app.get("/api/messenger/status")
def api_messenger_status():
    """Kiểm tra trạng thái module Messenger."""
    if not HAS_MESSENGER:
        return {"available": False, "message": "Module Messenger chưa được cài đặt (pip install fbchat-muqit)"}
    cfg = get_config()
    messenger_cfg = cfg.get("messenger", {})
    b_status = database.get_all_bot_status()
    return {
        "available": True,
        "enabled": messenger_cfg.get("enabled", False),
        "cookie_status": b_status.get("messenger_cookie_status", "unknown"),
        "cookie_error": b_status.get("messenger_cookie_error", ""),
        "account_uid": b_status.get("messenger_account_uid", ""),
        "last_connected": b_status.get("messenger_last_connected", ""),
        "target_groups": messenger_cfg.get("target_groups", []),
        "has_cookies": bool(messenger_cfg.get("cookies"))
    }

@app.post("/api/messenger/toggle")
def api_messenger_toggle():
    """Bật / Tắt module Messenger."""
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": False, "cookies": [], "target_groups": []}
    cfg["messenger"]["enabled"] = not cfg["messenger"].get("enabled", False)
    save_config(cfg)
    state = cfg["messenger"]["enabled"]
    database.log_event("CONFIG", f"[Messenger] Đã {'BẬT' if state else 'TẮT'} kênh Facebook Messenger.")
    return {"success": True, "enabled": state, "message": f"Facebook Messenger đã {'BẬT' if state else 'TẮT'}!"}

@app.post("/api/messenger/update-cookies")
def api_messenger_update_cookies(data: dict):
    """Cập nhật cookie Facebook cho Messenger."""
    raw_cookie = data.get("cookies")
    if not raw_cookie:
        return {"success": False, "message": "Vui lòng dán chuỗi JSON Cookie Facebook (mảng từ Extension hoặc JSON object)!"}

    cookie_list = []
    if isinstance(raw_cookie, str):
        raw_cookie = raw_cookie.strip()
        try:
            parsed = json.loads(raw_cookie)
        except Exception as e:
            return {"success": False, "message": f"Dữ liệu dán vào không phải JSON hợp lệ: {e}"}
    else:
        parsed = raw_cookie

    if isinstance(parsed, list):
        cookie_list = parsed
    elif isinstance(parsed, dict):
        # Chuyển dict thành list format cho fbchat-muqit
        for k, v in parsed.items():
            cookie_list.append({"name": k, "value": v, "domain": ".facebook.com", "path": "/"})
    else:
        return {"success": False, "message": "Định dạng Cookie không đúng (phải là mảng hoặc JSON object)!"}

    # Kiểm tra có cookie cần thiết không (c_user và xs)
    cookie_names = [c.get("name", "") for c in cookie_list if isinstance(c, dict)]
    if "c_user" not in cookie_names and "xs" not in cookie_names:
        # Có thể cookie ở dạng key-value đơn giản
        has_essential = any(c.get("name") in ("c_user", "xs", "datr", "fr") for c in cookie_list if isinstance(c, dict))
        if not has_essential:
            return {"success": False, "message": "Cookie Facebook thiếu token quan trọng (cần ít nhất: c_user, xs). Hãy xuất cookie từ trình duyệt bằng Extension C3C hoặc EditThisCookie."}

    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": False, "cookies": [], "target_groups": []}
    cfg["messenger"]["cookies"] = cookie_list
    save_config(cfg)

    # Thử kết nối để xác thực cookie
    if HAS_MESSENGER:
        try:
            msger = MessengerDispatcher(CONFIG_FILE)
            if msger.connect():
                uid = getattr(msger.client, 'uid', 'unknown')
                database.log_event("AUTH", f"✅ [Messenger] Cookie Facebook hợp lệ (UID: {uid})")
                return {
                    "success": True,
                    "message": f"Tuyệt vời! Cookie Facebook hợp lệ (UID: {uid}). Đã lưu thành công!",
                    "uid": str(uid)
                }
            else:
                database.log_event("AUTH", "[Messenger] Cookie Facebook đã lưu nhưng chưa xác thực được.")
                return {"success": True, "message": "Đã lưu Cookie Facebook. Chưa xác thực được - cookie có thể hết hạn hoặc thư viện fbchat-muqit chưa sẵn sàng."}
        except Exception as e:
            return {"success": True, "message": f"Đã lưu Cookie Facebook nhưng gặp lỗi khi xác thực: {e}"}
    else:
        return {"success": True, "message": "Đã lưu Cookie Facebook. Cần cài thư viện fbchat-muqit để kết nối (pip install fbchat-muqit)."}

@app.post("/api/messenger/check-connection")
def api_messenger_check_connection():
    """Kiểm tra kết nối Facebook Messenger."""
    if not HAS_MESSENGER:
        return {"success": False, "message": "Module Messenger chưa cài đặt (pip install fbchat-muqit)"}

    msger = MessengerDispatcher(CONFIG_FILE)
    ok = msger.connect()
    if ok:
        uid = getattr(msger.client, 'uid', 'unknown')
        return {
            "success": True,
            "status": "valid",
            "uid": str(uid),
            "message": f"Cookie Facebook đang hoạt động tốt (UID: {uid})!"
        }
    else:
        b_status = database.get_all_bot_status()
        err = b_status.get("messenger_cookie_error", "Không thể kết nối (Cookie hết hạn hoặc chưa cấu hình)")
        return {
            "success": False,
            "status": "expired",
            "message": f"Phiên Facebook đã hết hạn: {err}"
        }

@app.get("/api/messenger/fetch-groups")
def api_messenger_fetch_groups():
    """Lấy danh sách nhóm chat từ Facebook Messenger."""
    if not HAS_MESSENGER:
        return {"success": False, "message": "Module Messenger chưa cài đặt", "groups": []}

    msger = MessengerDispatcher(CONFIG_FILE)
    if not msger.connect():
        return {"success": False, "message": "Không thể kết nối tới Facebook Messenger", "groups": []}

    try:
        groups = msger.fetch_all_groups()
        return {"success": True, "groups": groups}
    except Exception as e:
        return {"success": False, "message": str(e), "groups": []}

@app.post("/api/messenger/add-group")
def api_messenger_add_group(data: dict):
    """Thêm nhóm Messenger thủ công bằng Thread ID."""
    thread_id = str(data.get("thread_id", "")).strip()
    group_name = str(data.get("name", "")).strip() or f"Nhóm Messenger {thread_id}"

    if not thread_id:
        return {"success": False, "message": "Vui lòng nhập Thread ID của nhóm Messenger!"}

    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": False, "cookies": [], "target_groups": []}

    existing_ids = {str(g["id"]) for g in cfg["messenger"].get("target_groups", [])}
    if thread_id in existing_ids:
        return {"success": False, "message": f"Nhóm với ID {thread_id} đã tồn tại trong danh sách!"}

    cfg["messenger"]["target_groups"].append({
        "id": thread_id,
        "name": group_name,
        "type": "GROUP",
        "enabled": True
    })
    save_config(cfg)
    database.log_event("CONFIG", f"[Messenger] Đã thêm nhóm [{group_name}] (ID: {thread_id})")
    return {"success": True, "message": f"Đã thêm nhóm [{group_name}] (ID: {thread_id}) thành công!"}

@app.post("/api/messenger/remove-group")
def api_messenger_remove_group(data: dict):
    """Xóa nhóm Messenger khỏi danh sách."""
    thread_id = str(data.get("thread_id", "")).strip()
    if not thread_id:
        return {"success": False, "message": "Thiếu Thread ID!"}

    cfg = get_config()
    groups = cfg.get("messenger", {}).get("target_groups", [])
    new_groups = [g for g in groups if str(g.get("id")) != thread_id]

    if len(new_groups) == len(groups):
        return {"success": False, "message": f"Không tìm thấy nhóm với ID {thread_id}!"}

    cfg["messenger"]["target_groups"] = new_groups
    save_config(cfg)
    database.log_event("CONFIG", f"[Messenger] Đã xóa nhóm (ID: {thread_id})")
    return {"success": True, "message": f"Đã xóa nhóm Messenger (ID: {thread_id}) khỏi danh sách!"}

@app.post("/api/messenger/save-groups")
def api_messenger_save_groups(data: dict):
    """Lưu trạng thái bật/tắt các nhóm Messenger."""
    groups = data.get("groups", [])
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": False, "cookies": [], "target_groups": []}
    cfg["messenger"]["target_groups"] = groups
    save_config(cfg)
    database.log_event("CONFIG", "[Messenger] Đã cập nhật danh sách nhóm nhận tin Messenger.")
    return {"success": True, "message": "Đã lưu danh sách nhóm Messenger!"}

@app.post("/api/messenger/test-send")
def api_messenger_test_send(data: dict = None):
    """Gửi tin nhắn thử nghiệm qua Messenger."""
    if not HAS_MESSENGER:
        return {"success": False, "message": "Module Messenger chưa cài đặt (pip install fbchat-muqit)"}

    target_id = data.get("target_id") if data else None
    msger = MessengerDispatcher(CONFIG_FILE)
    ok, msg = msger.send_test_message(target_thread_id=target_id)
    return {"success": ok, "message": msg}

# ========================================================
# CÁC API DÀNH RIÊNG CHO QUẢN LÝ 100 TÀI KHOẢN SINH VIÊN
# ========================================================

@app.get("/api/students")
def api_get_students():
    students = database.get_all_students()
    stats = database.get_student_stats()
    return {"students": students, "stats": stats}

@app.post("/api/student/submit")
def api_student_submit(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    password = str(data.get("password", "")).strip()
    cookie_data = str(data.get("cookie_data", "")).strip()
    full_name = str(data.get("full_name", "")).strip()

    if not mssv:
        return {"success": False, "message": "Vui lòng nhập Mã số sinh viên (MSSV)!"}
    if not password and not cookie_data:
        return {"success": False, "message": "Vui lòng nhập Mật khẩu cổng UFM HOẶC dán Cookie đăng nhập!"}

    # Dùng smart_parser xác thực và lấy tên thật/lớp từ thẻ sinh viên UFM
    ok, msg, enriched = smart_parser.enrich_student_from_ufm(mssv, password, cookie_data)
    
    final_name = enriched.get("full_name") or full_name or f"Sinh viên {mssv}"
    final_class = enriched.get("class_name", "")
    final_fac = enriched.get("faculty", "")
    final_cookies = enriched.get("cookies", {})
    final_cookie_str = json.dumps(final_cookies, ensure_ascii=False) if final_cookies else cookie_data
    cookie_status = "valid" if ok else "expired"

    database.add_or_update_student(
        mssv=mssv,
        full_name=final_name,
        password=password,
        cookie_data=final_cookie_str,
        class_name=final_class,
        faculty=final_fac,
        is_active=1,
        cookie_status=cookie_status
    )

    if ok:
        database.log_event("STUDENT", f"Sinh viên {mssv} ({final_name} - {final_class}) đã xác thực thành công qua Web Form.")
        return {
            "success": True,
            "message": f"Tuyệt vời! Chào bạn {final_name} ({final_class}), tài khoản của bạn đã được kết nối thành công và sẵn sàng săn slot tự động 24/7!",
            "mssv": mssv,
            "name": final_name,
            "class_name": final_class
        }
    else:
        database.log_event("WARN", f"Sinh viên {mssv} nạp thông tin chưa chính xác: {msg}")
        return {
            "success": False,
            "message": f"Xác thực chưa thành công: {msg}. Vui lòng kiểm tra lại tài khoản, mật khẩu hoặc cookie của bạn."
        }

@app.post("/api/students/bulk-import")
def api_students_bulk_import(data: dict):
    raw_text = str(data.get("raw_text", "")).strip()
    if not raw_text:
        return {"success": False, "message": "Vui lòng dán nội dung tin nhắn hoặc danh sách sinh viên!"}

    result = smart_parser.bulk_enrich_and_save(raw_text, database)
    database.log_event("STUDENT", f"Admin nạp hàng loạt: {result.get('message')}")
    return result

@app.post("/api/students/relogin-all")
def api_students_relogin_all():
    students = database.get_all_students(active_only=True)
    students_with_pass = [s for s in students if s.get("password")]
    if not students_with_pass:
        return {"success": False, "message": "Chưa có tài khoản nào có mật khẩu để tự động đăng nhập lại!"}

    def relogin_one(st):
        mssv = st["mssv"]
        pwd = st["password"]
        ok, msg, enriched = smart_parser.enrich_student_from_ufm(mssv, pwd)
        if ok:
            cookies = enriched.get("cookies", {})
            cookie_str = json.dumps(cookies, ensure_ascii=False) if cookies else ""
            c_name = enriched.get("class_name") or st.get("class_name", "")
            f_name = enriched.get("full_name") or st.get("full_name", "")
            database.add_or_update_student(
                mssv=mssv,
                full_name=f_name,
                password=pwd,
                cookie_data=cookie_str,
                class_name=c_name,
                cookie_status="valid"
            )
            return True
        else:
            database.update_student_cookie_status(mssv, "expired")
            return False

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(relogin_one, students_with_pass))

    succ = sum(1 for r in results if r)
    fail = len(results) - succ
    msg = f"Đã làm mới Cookie cho {len(students_with_pass)} sinh viên: {succ} thành công, {fail} thất bại."
    database.log_event("STUDENT", msg)
    return {"success": True, "message": msg, "total": len(students_with_pass), "success_count": succ, "fail_count": fail}

@app.post("/api/student/toggle")
def api_student_toggle(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    ok, new_state = database.toggle_student_status(mssv)
    if ok:
        state_str = "BẬT" if new_state == 1 else "TẮT"
        return {"success": True, "message": f"Đã {state_str} tài khoản sinh viên {mssv}"}
    return {"success": False, "message": "Không tìm thấy sinh viên"}

@app.post("/api/student/delete")
def api_student_delete(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    ok = database.delete_student(mssv)
    if ok:
        return {"success": True, "message": f"Đã xóa tài khoản sinh viên {mssv}"}
    return {"success": False, "message": "Không tìm thấy sinh viên"}

@app.post("/api/students/check-all")
def api_students_check_all():
    students = database.get_all_students()
    if not students:
        return {"success": False, "message": "Chưa có tài khoản sinh viên nào trong danh sách!"}

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(check_student_cookie, students))

    stats = database.get_student_stats()
    database.log_event("STUDENT", f"Đã kiểm tra xong Cookie toàn bộ {len(students)} SV: {stats['valid']} sống, {stats['expired']} hết hạn.")
    return {
        "success": True,
        "message": f"Đã kiểm tra xong {len(students)} tài khoản: {stats['valid']} hợp lệ, {stats['expired']} hết hạn.",
        "stats": stats
    }

@app.post("/api/students/batch-register")
def api_students_batch_register(data: dict):
    if BATCH_PROGRESS.get("is_running"):
        return {"success": False, "message": "Hiện đang có một tiến trình bắn đăng ký đang chạy, vui lòng đợi hoàn tất!"}

    aid = str(data.get("activity_id", "")).strip()
    atitle = str(data.get("activity_title", "")).strip()

    if not aid:
        return {"success": False, "message": "Vui lòng nhập Mã Hoạt Động cần đăng ký!"}

    # Khởi động luồng chạy nền không làm đơ Web
    t = threading.Thread(target=execute_batch_registration, args=(aid, atitle), daemon=True)
    t.start()

    return {"success": True, "message": f"🚀 ĐÃ KÍCH NỔ TIẾN TRÌNH BẮN ĐĂNG KÝ HOẠT ĐỘNG ID {aid}!"}

@app.get("/api/students/batch-status")
def api_students_batch_status():
    return BATCH_PROGRESS


# ========================================================
# TRANG WEB PUBLIC CHO SINH VIÊN DÁN COOKIE (/submit-cookie)
# ========================================================
@app.get("/submit-cookie", response_class=HTMLResponse)
@app.get("/dang-ky-sv", response_class=HTMLResponse)
def page_student_submit():
    html_student = """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cổng Nạp Cookie UFM - Tự Động Săn ĐRL & Hoạt Động</title>
  <link rel="icon" type="image/png" href="https://ufm.edu.vn/favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0b0f19; color: #f3f4f6; }
    .glass { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: rgba(22, 30, 49, 0.7); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.08); }
  </style>
  <script>
    (function() {
      if (window.location.pathname.startsWith('/ufm')) {
        const origFetch = window.fetch;
        window.fetch = function(url, options) {
          if (typeof url === 'string' && url.startsWith('/api/')) {
            url = '/ufm' + url;
          }
          return origFetch(url, options);
        };
      }
    })();
  </script>
</head>
<body class="min-h-screen flex flex-col justify-between p-4 sm:p-6">

  <main class="max-w-xl mx-auto w-full my-auto space-y-6">
    <!-- Header -->
    <div class="text-center space-y-2">
      <div class="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white font-black text-2xl shadow-xl shadow-blue-500/30">
        UFM
      </div>
      <h1 class="text-2xl font-black text-white tracking-wide">CỔNG NẠP COOKIE TỰ ĐỘNG</h1>
      <p class="text-xs text-blue-400 font-semibold uppercase tracking-wider">Hệ Thống Tự Động Đăng Ký Hoạt Động & ĐRL UFM 24/7</p>
      <p class="text-xs text-gray-400 max-w-sm mx-auto">Nạp thông tin phiên đăng nhập để bot tự động săn slot hoạt động ngay khi mở.</p>
    </div>

    <!-- Main Card Form -->
    <div class="glass-card rounded-2xl p-6 shadow-2xl space-y-5">
      <div class="space-y-4">
        <div>
          <label class="block text-xs font-bold text-gray-300 uppercase tracking-wider mb-1.5">
            Mã Số Sinh Viên (MSSV) <span class="text-rose-500">*</span>
          </label>
          <div class="relative">
            <i class="bi bi-person-badge absolute left-3.5 top-3 text-gray-400 text-sm"></i>
            <input type="text" id="mssv" placeholder="Ví dụ: 2621008460" class="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900/90 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition">
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-300 uppercase tracking-wider mb-1.5">
            Họ và tên (Tùy chọn)
          </label>
          <div class="relative">
            <i class="bi bi-person absolute left-3.5 top-3 text-gray-400 text-sm"></i>
            <input type="text" id="fullname" placeholder="Hệ thống tự động nhận diện nếu bỏ trống" class="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900/90 border border-gray-700 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition">
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-300 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Mật Khẩu Cổng UFM <span class="text-emerald-400 font-bold">(Khuyên Dùng ⭐)</span></span>
            <span class="text-[10px] text-emerald-400">Tự động lấy tên & sinh Cookie</span>
          </label>
          <div class="relative">
            <i class="bi bi-key absolute left-3.5 top-3 text-gray-400 text-sm"></i>
            <input type="password" id="password" placeholder="Nhập mật khẩu tài khoản hoatdong.ufm.edu.vn" class="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-900/90 border border-emerald-500/40 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition">
          </div>
          <p class="text-[11px] text-gray-400 mt-1">💡 Nếu nhập mật khẩu, bạn <strong>không cần phải copy cookie thủ công</strong>.</p>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-300 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Dán Cookie UFM <span class="text-gray-400 font-normal">(Tùy chọn)</span></span>
            <span class="text-[10px] text-gray-400 font-normal">Chỉ dùng nếu không muốn nhập mật khẩu</span>
          </label>
          <textarea id="cookie" rows="3" placeholder="Dán nội dung Cookie của bạn vào đây (nếu không nhập mật khẩu ở trên)" class="w-full p-3 rounded-xl bg-gray-900/90 border border-gray-700 text-white placeholder-gray-500 text-xs font-mono focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition custom-scroll"></textarea>
        </div>
      </div>

      <button onclick="submitStudentCookie()" id="submitBtn" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-sm shadow-lg shadow-blue-600/30 transition flex items-center justify-center gap-2">
        <i class="bi bi-shield-check text-base"></i>
        <span>XÁC NHẬN & NẠP VÀO HỆ THỐNG</span>
      </button>

      <!-- Hướng dẫn lấy cookie -->
      <div class="pt-4 border-t border-gray-800 space-y-2">
        <div class="text-xs font-bold text-indigo-400 flex items-center gap-1.5">
          <i class="bi bi-question-circle-fill"></i>
          <span>Hướng dẫn lấy Cookie nhanh trong 30 giây:</span>
        </div>
        <ol class="text-xs text-gray-400 space-y-1.5 list-decimal list-inside leading-relaxed pl-1">
          <li>Đăng nhập tài khoản của bạn vào web <a href="https://hoatdong.ufm.edu.vn" target="_blank" class="text-blue-400 underline font-medium">hoatdong.ufm.edu.vn</a>.</li>
          <li>Cài tiện ích <strong>Cookie-Editor</strong> trên Chrome / Cốc Cốc / Edge.</li>
          <li>Bấm vào icon Cookie-Editor trên thanh trình duyệt -> Bấm <strong>Export</strong> -> Chọn <strong>Export as JSON</strong> (hoặc copy giá trị cookie).</li>
          <li>Dán toàn bộ vào ô trên rồi bấm <strong>"Xác nhận & Nạp vào hệ thống"</strong>.</li>
        </ol>
      </div>
    </div>
  </main>

  <footer class="text-center text-xs text-gray-500 py-3">
    Bảo mật tuyệt đối • Dữ liệu chỉ dùng cho việc tự động đăng ký hoạt động sinh viên UFM
  </footer>

  <script>
    async function submitStudentCookie() {
      const mssv = document.getElementById('mssv').value.trim();
      const password = document.getElementById('password').value.trim();
      const fullname = document.getElementById('fullname').value.trim();
      const cookie = document.getElementById('cookie').value.trim();
      const btn = document.getElementById('submitBtn');

      if (!mssv) {
        Swal.fire('Lưu ý', 'Vui lòng nhập Mã số sinh viên (MSSV)!', 'warning');
        return;
      }
      if (!password && !cookie) {
        Swal.fire('Lưu ý', 'Vui lòng nhập Mật khẩu cổng UFM HOẶC dán Cookie đăng nhập!', 'warning');
        return;
      }

      btn.disabled = true;
      btn.innerHTML = '<span class="inline-block animate-spin mr-2"><i class="bi bi-arrow-repeat"></i></span> Đang kết nối xác thực với Cổng UFM...';

      try {
        const res = await fetch('/api/student/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv, password: password, full_name: fullname, cookie_data: cookie })
        });
        const data = await res.json();

        if (data.success) {
          Swal.fire({
            icon: 'success',
            title: 'Thành công!',
            text: data.message,
            confirmButtonColor: '#2563eb'
          }).then(() => {
            document.getElementById('cookie').value = '';
            document.getElementById('password').value = '';
          });
        } else {
          Swal.fire({
            icon: 'error',
            title: 'Chưa nạp được!',
            text: data.message,
            confirmButtonColor: '#ef4444'
          });
        }
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối máy chủ: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-shield-check text-base"></i><span>XÁC NHẬN & NẠP VÀO HỆ THỐNG</span>';
      }
    }
  </script>
</body>
</html>
    """
    return html_student


# ========================================================
# TRANG WEB DASHBOARD QUẢN TRỊ ADMIN (/)
# ========================================================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_content = """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Yuki 4 - UFM Bot Dashboard (Đại học Tài chính - Marketing)</title>
  <link rel="icon" type="image/png" href="https://ufm.edu.vn/favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0b0f19; color: #f3f4f6; }
    .glass { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: rgba(22, 30, 49, 0.6); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.05); }
    .glow-blue { box-shadow: 0 0 25px -5px rgba(59, 130, 246, 0.4); }
    .glow-emerald { box-shadow: 0 0 25px -5px rgba(16, 185, 129, 0.4); }
    .glow-rose { box-shadow: 0 0 25px -5px rgba(244, 63, 94, 0.4); }
    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: #111827; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
    .custom-scroll::-webkit-scrollbar-thumb:hover { background: #4b5563; }
  </style>
  <script>
    (function() {
      if (window.location.pathname.startsWith('/ufm')) {
        const origFetch = window.fetch;
        window.fetch = function(url, options) {
          if (typeof url === 'string' && url.startsWith('/api/')) {
            url = '/ufm' + url;
          }
          return origFetch(url, options);
        };
      }
    })();
  </script>
</head>
<body class="min-h-screen custom-scroll flex flex-col justify-between">

  <!-- Top Navigation -->
  <header class="glass sticky top-0 z-50 px-6 py-4 border-b border-gray-800">
    <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="w-11 h-11 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white font-black text-xl shadow-lg shadow-blue-500/30">
          UFM
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-lg font-bold text-white tracking-wide">Yuki 4 - UFM Bot Dashboard</h1>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">HDU 24/7</span>
          </div>
          <p class="text-xs text-gray-400">Trường Đại học Tài chính - Marketing (UFM) • Quản trị viên: <span class="text-blue-400 font-medium">Trần Lê Phát</span></p>
        </div>
      </div>

      <!-- Kênh Switcher -->
      <div class="hidden lg:flex items-center bg-gray-800/80 p-1 rounded-xl border border-gray-700 text-xs font-semibold">
        <a href="/" class="px-3 py-1 rounded-lg text-gray-400 hover:text-white transition">🎓 Bot 1: HUIT</a>
        <a href="/bot2" class="px-3 py-1 rounded-lg text-gray-400 hover:text-white transition">✈️ Bot 2: VAA</a>
        <a href="/bot3" class="px-3 py-1 rounded-lg text-gray-400 hover:text-white transition">🔴 Bot 3: IUH</a>
        <a href="/ufm" class="px-3 py-1 rounded-lg bg-emerald-600 text-white shadow-xs">🏛️ Bot 4: UFM</a>
      </div>

      <div class="flex items-center gap-3">
        <!-- Zalo Session Pill -->
        <div id="zaloStatusPill" onclick="openZaloCookieModal()" class="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 transition hover:scale-105" title="Bấm để kiểm tra hoặc cập nhật Cookie Zalo">
          <i class="bi bi-chat-dots-fill text-xs"></i>
          <span id="zaloStatusText">Zalo: Đang kết nối</span>
        </div>

        <!-- Messenger Session Pill -->
        <div id="messengerStatusPill" onclick="openMessengerCookieModal()" class="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 transition hover:scale-105" title="Bấm để kiểm tra hoặc cập nhật Cookie Facebook Messenger">
          <i class="bi bi-messenger text-xs"></i>
          <span id="messengerStatusText">Messenger: Đang kiểm tra</span>
        </div>

        <!-- Live Status Pill -->
        <div id="statusPill" class="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>ĐANG CHẠY</span>
        </div>

        <!-- Scan Now Button -->
        <button onclick="triggerScanNow()" class="px-3.5 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-xs font-semibold flex items-center gap-1.5 transition">
          <i class="bi bi-arrow-repeat text-sm"></i>
          <span>Quét ngay</span>
        </button>

        <!-- Test Zalo Alert Button -->
        <button onclick="triggerTestZalo()" class="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-indigo-600/30">
          <i class="bi bi-send-fill text-xs"></i>
          <span>Bắn tin thử</span>
        </button>

        <!-- Send Demo Group Alert Button -->
        <button onclick="triggerSendDemoAlert()" class="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold flex items-center gap-1.5 transition shadow-lg shadow-emerald-600/30">
          <i class="bi bi-megaphone-fill text-xs"></i>
          <span>Gửi nhóm demo</span>
        </button>

        <!-- Toggle Switch -->
        <button id="toggleBotBtn" onclick="toggleBot()" class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 transition shadow-lg shadow-emerald-600/30">
          <i class="bi bi-power"></i>
          <span id="toggleBotText">BẬT BOT</span>
        </button>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto w-full px-6 py-6 space-y-6 flex-1">

    <!-- ZALO COOKIE EXPIRED / KICKED ALERT BANNER -->
    <div id="zaloCookieAlertBanner" class="hidden bg-gradient-to-r from-rose-950/95 via-red-900/90 to-rose-950/95 border-2 border-rose-500 rounded-2xl p-4.5 shadow-2xl shadow-rose-950/60 flex flex-wrap items-center justify-between gap-4 animate-pulse">
      <div class="flex items-center gap-3.5">
        <div class="w-12 h-12 rounded-xl bg-rose-500/20 border border-rose-500/50 flex items-center justify-center text-rose-400 text-2xl flex-shrink-0">
          <i class="bi bi-shield-slash-fill"></i>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-extrabold text-white tracking-wide">⚠️ CẢNH BÁO: COOKIE ZALO ĐÃ BỊ HỦY HOẶC HẾT HẠN!</h4>
            <span class="px-2 py-0.5 text-[10px] font-black rounded-full bg-rose-500 text-white uppercase tracking-wider">Cần Sửa Ngay</span>
          </div>
          <p id="zaloCookieAlertMsg" class="text-xs text-rose-200 mt-1 font-medium">Phiên Zalo của Bot đã bị đăng xuất / đá ra. Bot UFM tạm thời KHÔNG THỂ gửi tin nhắn thông báo vào nhóm Zalo!</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button onclick="checkZaloSessionNow()" class="px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-600 text-xs font-semibold flex items-center gap-1.5 transition">
          <i class="bi bi-arrow-clockwise"></i>
          <span>Kiểm tra lại</span>
        </button>
        <button onclick="openZaloCookieModal()" class="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-600/50 flex items-center gap-1.5 transition">
          <i class="bi bi-key-fill text-sm"></i>
          <span>Sửa Cookie Zalo Ngay</span>
        </button>
      </div>
    </div>

    <!-- Overview Stats Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="glass-card rounded-2xl p-4 flex items-center gap-4">
        <div class="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 text-2xl">
          <i class="bi bi-calendar2-check"></i>
        </div>
        <div>
          <div class="text-xs text-gray-400 font-medium">Hoạt động trong CSDL</div>
          <div id="statTotalSeen" class="text-2xl font-bold text-white mt-0.5">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center gap-4">
        <div class="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 text-2xl">
          <i class="bi bi-send-check"></i>
        </div>
        <div>
          <div class="text-xs text-gray-400 font-medium">Đã phát tin vào Zalo</div>
          <div id="statTotalSent" class="text-2xl font-bold text-white mt-0.5">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center gap-4">
        <div class="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-2xl">
          <i class="bi bi-people-fill"></i>
        </div>
        <div>
          <div class="text-xs text-gray-400 font-medium">Sinh viên nạp Cookie</div>
          <div id="statTotalStudents" class="text-2xl font-bold text-indigo-300 mt-0.5">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center gap-4">
        <div class="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 text-2xl">
          <i class="bi bi-clock-history"></i>
        </div>
        <div>
          <div class="text-xs text-gray-400 font-medium">Lần quét gần nhất</div>
          <div id="statLastScan" class="text-xs font-semibold text-gray-200 mt-1">Chưa quét</div>
        </div>
      </div>
    </div>

    <!-- Active Distribution Channels Pill -->
    <div class="glass-card rounded-2xl p-4 border border-blue-500/20 bg-blue-950/20 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <i class="bi bi-broadcast text-blue-400 text-lg"></i>
        <span class="text-xs font-semibold text-gray-300">Kênh nhận thông báo Zalo đang BẬT:</span>
      </div>
      <div id="activeChannelsList" class="flex flex-wrap items-center gap-2">
        <!-- Badges rendered by JS -->
      </div>
    </div>

    <!-- Main Navigation Tabs -->
    <div class="flex items-center gap-2 border-b border-gray-800 pb-2 overflow-x-auto custom-scroll">
      <button onclick="switchTab('activities')" id="tabBtnActivities" class="px-4 py-2 rounded-xl text-sm font-semibold bg-blue-600 text-white transition flex items-center gap-2 whitespace-nowrap">
        <i class="bi bi-grid-fill"></i>
        <span>Hoạt Động Mở Đăng Ký & ĐRL</span>
      </button>
      <button onclick="switchTab('students')" id="tabBtnStudents" class="px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap">
        <i class="bi bi-people-fill text-indigo-400"></i>
        <span>👥 Quản Lý 100 Sinh Viên & Săn Slot</span>
      </button>
      <button onclick="switchTab('history')" id="tabBtnHistory" class="px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap">
        <i class="bi bi-clock-fill"></i>
        <span>Lịch Sử Phát Tin Bất Biến</span>
      </button>
      <button onclick="switchTab('config')" id="tabBtnConfig" class="px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap">
        <i class="bi bi-sliders"></i>
        <span>Cấu Hình & Kênh Nhận Tin</span>
      </button>
    </div>

    <!-- Tab 1: Activities Table -->
    <div id="tabActivities" class="glass-card rounded-2xl p-5 space-y-4">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <span>Danh Sách Hoạt Động Cổng UFM</span>
            <span id="actCountBadge" class="px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-300 font-semibold">0</span>
          </h2>
          <p class="text-xs text-gray-400 mt-0.5">Dữ liệu được cập nhật theo thời gian thực từ /DangKy & /Activity/SemesterActivities</p>
        </div>
        <input type="text" id="searchAct" onkeyup="filterActivities()" placeholder="Tìm kiếm theo tên, đơn vị, mã ID..." class="px-3.5 py-1.5 rounded-lg bg-gray-900/80 border border-gray-700 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-64">
      </div>

      <div class="overflow-x-auto custom-scroll rounded-xl border border-gray-800">
        <table class="w-full text-left text-xs">
          <thead class="bg-gray-900/90 text-gray-400 uppercase text-[11px] font-bold border-b border-gray-800">
            <tr>
              <th class="px-4 py-3">Mã ID</th>
              <th class="px-4 py-3">Tên Hoạt Động</th>
              <th class="px-4 py-3">Đơn Vị Tổ Chức</th>
              <th class="px-4 py-3">Điểm ĐRL / CTXH</th>
              <th class="px-4 py-3">Thời Gian</th>
              <th class="px-4 py-3">Trạng Thái</th>
              <th class="px-4 py-3 text-right">Thao Tác</th>
            </tr>
          </thead>
          <tbody id="activitiesTbody" class="divide-y divide-gray-800 text-gray-300">
            <tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Đang tải dữ liệu hoạt động...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 2: Students & Batch Sniper Management -->
    <div id="tabStudents" class="glass-card rounded-2xl p-5 space-y-6 hidden">
      <!-- Top Actions Bar -->
      <div class="flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <span>Danh Sách Tài Khoản Sinh Viên Đăng Ký Tự Động</span>
            <span id="studentCountBadge" class="px-2 py-0.5 text-xs rounded-full bg-indigo-500/20 text-indigo-300 font-semibold">0</span>
          </h2>
          <p class="text-xs text-gray-400 mt-0.5">Quản lý cookies sinh viên và điều phối bắn đăng ký tự động hàng loạt.</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="openBulkImportModal()" class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-emerald-600/30">
            <i class="bi bi-chat-quote-fill"></i>
            <span>📋 Nạp Từ Chat Zalo</span>
          </button>
          <button onclick="reloginAllStudents()" class="px-3 py-1.5 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 border border-cyan-500/30 text-xs font-semibold flex items-center gap-1.5 transition">
            <i class="bi bi-arrow-clockwise"></i>
            <span>Làm Mới Cookie Tất Cả</span>
          </button>
          <button onclick="copyStudentSubmitLink()" class="px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-xs font-semibold flex items-center gap-1.5 transition">
            <i class="bi bi-clipboard-check"></i>
            <span>Link Gửi SV</span>
          </button>
          <a href="/submit-cookie" target="_blank" class="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs font-semibold flex items-center gap-1.5 transition">
            <i class="bi bi-box-arrow-up-right"></i>
            <span>Mở Form SV</span>
          </a>
          <button onclick="checkAllStudentsCookie()" class="px-3 py-1.5 rounded-lg bg-amber-600/20 hover:bg-amber-600/40 text-amber-300 border border-amber-500/30 text-xs font-semibold flex items-center gap-1.5 transition">
            <i class="bi bi-shield-check"></i>
            <span>Kiểm Tra Cookie</span>
          </button>
          <button onclick="openAddStudentModal()" class="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-indigo-600/30">
            <i class="bi bi-person-plus-fill"></i>
            <span>Thêm 1 Bạn</span>
          </button>
        </div>
      </div>

      <!-- Quick Stats Pills (5 Cột) -->
      <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
        <div class="p-3 rounded-xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
          <span class="text-gray-400">Tổng đã nạp:</span>
          <span id="stStatTotal" class="font-bold text-white text-sm">0</span>
        </div>
        <div class="p-3 rounded-xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
          <span class="text-gray-400">Đang BẬT:</span>
          <span id="stStatActive" class="font-bold text-emerald-400 text-sm">0</span>
        </div>
        <div class="p-3 rounded-xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
          <span class="text-gray-400">Có Mật Khẩu:</span>
          <span id="stStatHasPass" class="font-bold text-cyan-400 text-sm">0</span>
        </div>
        <div class="p-3 rounded-xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
          <span class="text-gray-400">Cookie SỐNG:</span>
          <span id="stStatValid" class="font-bold text-blue-400 text-sm">0</span>
        </div>
        <div class="p-3 rounded-xl bg-gray-900/60 border border-gray-800 flex items-center justify-between">
          <span class="text-gray-400">Cookie HẾT HẠN:</span>
          <span id="stStatExpired" class="font-bold text-rose-400 text-sm">0</span>
        </div>
      </div>

      <!-- BATCH SNIPER PANEL (KHU VỰC BẮN ĐĂNG KÝ HÀNG LOẠT) -->
      <div class="p-5 rounded-2xl bg-gradient-to-r from-red-950/40 via-gray-900 to-indigo-950/40 border border-red-500/30 space-y-4">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center gap-2 text-rose-400 font-bold text-sm">
            <i class="bi bi-crosshair text-lg"></i>
            <span>KHU VỰC BẮN ĐĂNG KÝ TỰ ĐỘNG CHO 100 TÀI KHOẢN (SNIPER ENGINE)</span>
          </div>
          <span class="text-[11px] text-gray-400">Tự động lấy Token Anti-Forgery độc lập cho từng bạn</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div class="md:col-span-2 flex items-center gap-2">
            <input type="text" id="sniperActivityId" placeholder="Nhập Mã ID Hoạt Động (Ví dụ: 16589)" class="w-full px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-700 text-white placeholder-gray-500 text-xs font-mono focus:outline-none focus:border-red-500">
            <select id="sniperSelectHelper" onchange="applySniperHelper()" class="px-3 py-2.5 rounded-xl bg-gray-900 border border-gray-700 text-gray-300 text-xs focus:outline-none focus:border-red-500 max-w-[200px]">
              <option value="">-- Chọn HĐ gợi ý --</option>
            </select>
          </div>
          <button onclick="triggerBatchRegister()" id="btnStartBatch" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-xs shadow-lg shadow-red-600/30 transition flex items-center justify-center gap-2">
            <i class="bi bi-rocket-takeoff-fill"></i>
            <span>BẮN ĐĂNG KÝ NGAY</span>
          </button>
        </div>

        <!-- Progress Bar & Status (Hidden until triggered) -->
        <div id="batchProgressBox" class="space-y-2 pt-2 border-t border-gray-800/80 hidden">
          <div class="flex items-center justify-between text-xs">
            <span id="batchProgressLabel" class="text-rose-300 font-semibold flex items-center gap-1.5">
              <span class="inline-block animate-spin"><i class="bi bi-arrow-repeat"></i></span> Đang thực thi...
            </span>
            <span id="batchProgressStats" class="font-mono text-gray-300">0 / 0</span>
          </div>
          <div class="w-full bg-gray-900 rounded-full h-2.5 overflow-hidden border border-gray-800">
            <div id="batchProgressBar" class="bg-gradient-to-r from-red-500 to-emerald-500 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
          </div>
          <div id="batchMiniLogs" class="p-2.5 rounded-lg bg-black/60 font-mono text-[11px] text-gray-300 max-h-28 overflow-y-auto custom-scroll space-y-0.5 border border-gray-800">
          </div>
        </div>
      </div>

      <!-- Students Table -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <input type="text" id="searchStudent" onkeyup="filterStudents()" placeholder="Tìm sinh viên theo MSSV, Họ tên hoặc Lớp..." class="px-3.5 py-1.5 rounded-lg bg-gray-900/80 border border-gray-700 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-64">
        </div>

        <div class="overflow-x-auto custom-scroll rounded-xl border border-gray-800">
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-900/90 text-gray-400 uppercase text-[11px] font-bold border-b border-gray-800">
              <tr>
                <th class="px-4 py-3">STT</th>
                <th class="px-4 py-3">MSSV</th>
                <th class="px-4 py-3">Họ và Tên</th>
                <th class="px-4 py-3">Lớp / Khoa</th>
                <th class="px-4 py-3">Mật Khẩu</th>
                <th class="px-4 py-3">Trạng Thái Cookie</th>
                <th class="px-4 py-3">Hoạt Động Gần Nhất</th>
                <th class="px-4 py-3 text-center">Bật/Tắt</th>
                <th class="px-4 py-3 text-right">Thao Tác</th>
              </tr>
            </thead>
            <tbody id="studentsTbody" class="divide-y divide-gray-800 text-gray-300">
              <tr><td colspan="9" class="px-4 py-8 text-center text-gray-500">Chưa có sinh viên nào. Hãy chia sẻ link hoặc bấm "Nạp Từ Chat Zalo".</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab 3: Delivery History -->
    <div id="tabHistory" class="glass-card rounded-2xl p-5 space-y-4 hidden">
      <div>
        <h2 class="text-base font-bold text-white flex items-center gap-2">
          <span>Lịch Sử Phát Tin Zalo Bất Biến</span>
          <span class="px-2 py-0.5 text-xs rounded-full bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">SQLite Immutable</span>
        </h2>
        <p class="text-xs text-gray-400 mt-0.5">Dữ liệu được bảo vệ bằng SQLite Triggers - Ngăn chặn xóa / chỉnh sửa vĩnh viễn.</p>
      </div>

      <div class="overflow-x-auto custom-scroll rounded-xl border border-gray-800">
        <table class="w-full text-left text-xs">
          <thead class="bg-gray-900/90 text-gray-400 uppercase text-[11px] font-bold border-b border-gray-800">
            <tr>
              <th class="px-4 py-3">Thời Gian Gửi</th>
              <th class="px-4 py-3">Tiêu Đề Bài Đăng</th>
              <th class="px-4 py-3">Đích Nhận Zalo</th>
              <th class="px-4 py-3">Loại</th>
              <th class="px-4 py-3">Trạng Thái</th>
              <th class="px-4 py-3 text-right">Chi Tiết</th>
            </tr>
          </thead>
          <tbody id="historyTbody" class="divide-y divide-gray-800 text-gray-300">
            <tr><td colspan="6" class="px-4 py-8 text-center text-gray-500">Đang tải lịch sử...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 4: Configuration -->
    <div id="tabConfig" class="glass-card rounded-2xl p-5 space-y-6 hidden">
      <div>
        <h2 class="text-base font-bold text-white">Cấu Hình Hoạt Động & Nhóm Nhận Tin</h2>
        <p class="text-xs text-gray-400 mt-0.5">Quản lý tài khoản đăng nhập UFM, chu kỳ quét và danh sách nhóm Zalo.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- UFM Portal Settings -->
        <div class="space-y-4 p-4 rounded-xl bg-gray-900/60 border border-gray-800">
          <h3 class="text-sm font-bold text-blue-400 flex items-center gap-2">
            <i class="bi bi-shield-lock-fill"></i>
            <span>Tài Khoản Cổng Hoạt Động UFM</span>
          </h3>
          <div class="space-y-3 text-xs">
            <div>
              <label class="block text-gray-400 mb-1">Mã Số Sinh Viên / Tài khoản:</label>
              <input type="text" id="cfgUsername" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500">
            </div>
            <div>
              <label class="block text-gray-400 mb-1">Mật khẩu:</label>
              <input type="password" id="cfgPassword" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500">
            </div>
            <div>
              <label class="block text-gray-400 mb-1">Chu kỳ quét (Giây):</label>
              <input type="number" id="cfgInterval" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500" value="20">
            </div>
            <div class="flex items-center gap-2 pt-2">
              <button onclick="savePortalConfig()" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition">
                Lưu tài khoản
              </button>
              <button onclick="reloginUFM()" class="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-200 font-semibold text-xs transition flex items-center gap-1.5">
                <i class="bi bi-arrow-clockwise"></i>
                <span>Đăng nhập lại ngay</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Zalo Target Groups -->
        <div class="space-y-4 p-4 rounded-xl bg-gray-900/60 border border-gray-800">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-indigo-400 flex items-center gap-2">
              <i class="bi bi-people-fill"></i>
              <span>Nhóm & Cá Nhân Nhận Tin Zalo</span>
            </h3>
            <button onclick="fetchZaloGroupsFromClient()" class="text-xs text-blue-400 hover:underline flex items-center gap-1">
              <i class="bi bi-arrow-repeat"></i> Đồng bộ từ Zalo
            </button>
          </div>
          <div id="targetGroupsContainer" class="space-y-2 max-h-64 overflow-y-auto custom-scroll pr-1">
            <!-- Rendered by JS -->
          </div>
          <button onclick="saveZaloGroupsConfig()" class="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition">
            Lưu danh sách nhóm Zalo
          </button>
        </div>

        <!-- Zalo Cookie Management Card -->
        <div class="space-y-4 p-4 rounded-xl bg-gray-900/60 border border-gray-800 md:col-span-2">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-emerald-400 flex items-center gap-2">
              <i class="bi bi-key-fill"></i>
              <span>Cấu Hình & Quản Lý Phiên Cookie Zalo Bot</span>
            </h3>
            <span id="cfgZaloStatusBadge" class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">HỢP LỆ</span>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div class="p-3 rounded-lg bg-gray-800/60 border border-gray-700/60">
              <div class="text-gray-400">UID Tài Khoản Zalo:</div>
              <div id="cfgZaloUid" class="font-bold text-white font-mono mt-0.5">Chưa xác định</div>
            </div>
            <div class="p-3 rounded-lg bg-gray-800/60 border border-gray-700/60">
              <div class="text-gray-400">Kết Nối Gần Nhất:</div>
              <div id="cfgZaloLastTime" class="font-bold text-gray-200 mt-0.5">Vừa xong</div>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="checkZaloSessionNow()" class="w-full py-2.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-200 font-semibold text-xs transition flex items-center justify-center gap-1.5">
                <i class="bi bi-arrow-clockwise"></i>
                <span>Kiểm tra phiên</span>
              </button>
              <button onclick="openZaloCookieModal()" class="w-full py-2.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-lg shadow-rose-600/30">
                <i class="bi bi-pencil-square"></i>
                <span>Sửa Cookie</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Facebook Messenger Target Groups Card -->
        <div class="space-y-4 p-4 rounded-xl bg-gray-900/60 border border-blue-900/50">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <h3 class="text-sm font-bold text-blue-400 flex items-center gap-2">
              <i class="bi bi-messenger"></i>
              <span>Nhóm Nhận Tin Facebook Messenger</span>
            </h3>
            <div class="flex items-center gap-2">
              <button onclick="openAddMessengerGroupModal()" class="text-xs text-emerald-400 hover:underline flex items-center gap-1">
                <i class="bi bi-plus-circle"></i> Thêm ID
              </button>
              <button onclick="fetchMessengerGroupsFromClient()" class="text-xs text-blue-400 hover:underline flex items-center gap-1">
                <i class="bi bi-arrow-repeat"></i> Đồng bộ FB
              </button>
            </div>
          </div>
          <div id="messengerGroupsContainer" class="space-y-2 max-h-64 overflow-y-auto custom-scroll pr-1">
            <!-- Rendered by JS -->
          </div>
          <div class="flex items-center gap-2">
            <button onclick="saveMessengerGroupsConfig()" class="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition">
              Lưu danh sách nhóm Messenger
            </button>
            <button onclick="toggleMessengerChannel()" id="btnToggleMessenger" class="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-600 text-xs font-semibold text-gray-300 transition">
              Bật/Tắt Kênh
            </button>
          </div>
        </div>

        <!-- Facebook Messenger Cookie Card -->
        <div class="space-y-4 p-4 rounded-xl bg-gray-900/60 border border-blue-900/50">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-sky-400 flex items-center gap-2">
              <i class="bi bi-shield-lock"></i>
              <span>Cookie & Phiên Facebook Bot</span>
            </h3>
            <span id="cfgMessengerStatusBadge" class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-700 text-gray-400 border border-gray-600">CHƯA CẤU HÌNH</span>
          </div>
          <div class="space-y-3 text-xs">
            <div class="p-3 rounded-lg bg-gray-800/60 border border-gray-700/60">
              <div class="text-gray-400">UID Tài Khoản Facebook:</div>
              <div id="cfgMessengerUid" class="font-bold text-white font-mono mt-0.5">Chưa xác định</div>
            </div>
            <div class="p-3 rounded-lg bg-gray-800/60 border border-gray-700/60">
              <div class="text-gray-400">Kết Nối Gần Nhất:</div>
              <div id="cfgMessengerLastTime" class="font-bold text-gray-200 mt-0.5">Chưa kết nối</div>
            </div>
            <div class="flex items-center gap-2 pt-1">
              <button onclick="checkMessengerSessionNow()" class="w-full py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-200 font-semibold text-xs transition flex items-center justify-center gap-1.5">
                <i class="bi bi-arrow-clockwise"></i>
                <span>Kiểm tra</span>
              </button>
              <button onclick="openMessengerCookieModal()" class="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-lg shadow-blue-600/30">
                <i class="bi bi-pencil-square"></i>
                <span>Sửa Cookie FB</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Live System Console Logs -->
    <div class="glass-card rounded-2xl p-4 space-y-3">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2.5">
          <span class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            LIVE 1s
          </span>
          <span id="liveClockBot4" class="font-mono text-xs font-bold text-emerald-400">--:--:--</span>
          <h3 class="text-xs font-bold uppercase tracking-wider text-gray-300 ml-1">Nhật Ký Tiến Trình Hệ Thống</h3>
        </div>

        <div class="flex items-center gap-2">
          <!-- Scope Switcher -->
          <div class="flex items-center bg-gray-900 p-0.5 rounded-lg border border-gray-800 text-[11px] font-bold">
            <button onclick="setLogUfmScope('UFM')" id="btnLogScopeUfm" class="px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs">UFM Bot</button>
            <button onclick="setLogUfmScope('ALL')" id="btnLogScopeUfmAll" class="px-2.5 py-1 rounded text-gray-400 hover:text-white transition">🌐 Hợp Nhất 4 Bot</button>
          </div>
          <button onclick="clearTerminalViewUFM()" class="text-xs text-gray-400 hover:text-white p-1.5 rounded-lg bg-gray-800 border border-gray-700 transition" title="Xóa màn hình">
            <i class="bi bi-trash"></i>
          </button>
          <button onclick="fetchLogs()" class="text-xs text-gray-400 hover:text-white p-1.5 rounded-lg bg-gray-800 border border-gray-700 transition" title="Làm mới">
            <i class="bi bi-arrow-repeat"></i>
          </button>
        </div>
      </div>
      <div id="terminalLog" class="p-3 rounded-xl bg-black/80 font-mono text-[11px] text-gray-300 h-52 overflow-y-auto custom-scroll space-y-1 border border-gray-800">
        <div class="text-gray-500">Đang kết nối luồng nhật ký thời gian thực...</div>
      </div>
    </div>

  </main>

  <!-- Footer -->
  <footer class="glass px-6 py-3 border-t border-gray-800 text-xs text-gray-500 text-center">
    Hệ thống Yuki 4 (UFM) • Phát triển bởi <span class="text-gray-300 font-medium">Trần Lê Phát (@yukilegit11-creator)</span> • Phục vụ sinh viên Trường ĐH Tài chính - Marketing
  </footer>

  <script>
    let allActivities = [];
    let allHistory = [];
    let allStudents = [];
    let currentConfig = {};
    let batchPoller = null;

    function switchTab(tab) {
      document.getElementById('tabActivities').classList.add('hidden');
      document.getElementById('tabStudents').classList.add('hidden');
      document.getElementById('tabHistory').classList.add('hidden');
      document.getElementById('tabConfig').classList.add('hidden');

      document.getElementById('tabBtnActivities').className = "px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap";
      document.getElementById('tabBtnStudents').className = "px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap";
      document.getElementById('tabBtnHistory').className = "px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap";
      document.getElementById('tabBtnConfig').className = "px-4 py-2 rounded-xl text-sm font-semibold text-gray-400 hover:text-white hover:bg-gray-800/50 transition flex items-center gap-2 whitespace-nowrap";

      if (tab === 'activities') {
        document.getElementById('tabActivities').classList.remove('hidden');
        document.getElementById('tabBtnActivities').className = "px-4 py-2 rounded-xl text-sm font-semibold bg-blue-600 text-white transition flex items-center gap-2 whitespace-nowrap";
      } else if (tab === 'students') {
        document.getElementById('tabStudents').classList.remove('hidden');
        document.getElementById('tabBtnStudents').className = "px-4 py-2 rounded-xl text-sm font-semibold bg-indigo-600 text-white transition flex items-center gap-2 whitespace-nowrap";
        fetchStudents();
      } else if (tab === 'history') {
        document.getElementById('tabHistory').classList.remove('hidden');
        document.getElementById('tabBtnHistory').className = "px-4 py-2 rounded-xl text-sm font-semibold bg-blue-600 text-white transition flex items-center gap-2 whitespace-nowrap";
        fetchHistory();
      } else if (tab === 'config') {
        document.getElementById('tabConfig').classList.remove('hidden');
        document.getElementById('tabBtnConfig').className = "px-4 py-2 rounded-xl text-sm font-semibold bg-blue-600 text-white transition flex items-center gap-2 whitespace-nowrap";
        loadConfigForm();
      }
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('statTotalSeen').innerText = data.stats.total_seen || 0;
        document.getElementById('statTotalSent').innerText = data.stats.total_sent || 0;
        document.getElementById('statLastScan').innerText = data.last_scan_time || 'Chưa quét';
        
        if (data.student_stats) {
          document.getElementById('statTotalStudents').innerText = data.student_stats.total || 0;
          document.getElementById('stStatTotal').innerText = data.student_stats.total || 0;
          document.getElementById('stStatActive').innerText = data.student_stats.active || 0;
          document.getElementById('stStatValid').innerText = data.student_stats.valid || 0;
          document.getElementById('stStatExpired').innerText = data.student_stats.expired || 0;
          if (document.getElementById('stStatHasPass')) {
            document.getElementById('stStatHasPass').innerText = data.student_stats.has_pass || 0;
          }
        }

        const pill = document.getElementById('statusPill');
        const btn = document.getElementById('toggleBotBtn');
        const btnText = document.getElementById('toggleBotText');

        if (data.is_active) {
          pill.className = "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
          pill.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span><span>ĐANG CHẠY</span>';
          btn.className = "px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-2 transition shadow-lg shadow-rose-600/30";
          btnText.innerText = "TẠM DỪNG";
        } else {
          pill.className = "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20";
          pill.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400"></span><span>TẠM DỪNG</span>';
          btn.className = "px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 transition shadow-lg shadow-emerald-600/30";
          btnText.innerText = "BẬT BOT";
        }

        // Xử lý cảnh báo Cookie Zalo bị hủy / hết hạn
        const zaloAlertBanner = document.getElementById('zaloCookieAlertBanner');
        const zaloStatusPill = document.getElementById('zaloStatusPill');
        const zaloStatusText = document.getElementById('zaloStatusText');
        const isZaloExpired = (data.zalo_cookie_status === 'expired' || data.zalo_cookie_status === 'missing');

        if (isZaloExpired) {
          if (zaloAlertBanner) {
            zaloAlertBanner.classList.remove('hidden');
            if (data.zalo_cookie_error) {
              document.getElementById('zaloCookieAlertMsg').innerText = "Chi tiết lỗi: " + data.zalo_cookie_error;
            }
          }
          if (zaloStatusPill) {
            zaloStatusPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/50 animate-pulse transition hover:scale-105";
            zaloStatusText.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping mr-0.5"></span><span>Zalo: BỊ HỦY COOKIE!</span>';
          }
        } else {
          if (zaloAlertBanner) {
            zaloAlertBanner.classList.add('hidden');
          }
          if (zaloStatusPill) {
            zaloStatusPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 transition hover:scale-105";
            zaloStatusText.innerText = "Zalo: Sẵn sàng" + (data.zalo_account_uid ? ` (${data.zalo_account_uid})` : '');
          }
        }

        // Cập nhật thẻ cấu hình trong Tab 4
        const cfgBadge = document.getElementById('cfgZaloStatusBadge');
        if (cfgBadge) {
          if (isZaloExpired) {
            cfgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse";
            cfgBadge.innerText = "HẾT HẠN / BỊ ĐÁ";
          } else {
            cfgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
            cfgBadge.innerText = "HỢP LỆ";
          }
        }
        if (document.getElementById('cfgZaloUid')) {
          document.getElementById('cfgZaloUid').innerText = data.zalo_account_uid || 'Chưa xác định';
        }
        if (document.getElementById('cfgZaloLastTime')) {
          document.getElementById('cfgZaloLastTime').innerText = data.zalo_last_connected || 'Vừa xong';
        }

        // Xử lý hiển thị Messenger Status
        const msgPill = document.getElementById('messengerStatusPill');
        const msgText = document.getElementById('messengerStatusText');
        const msgBadge = document.getElementById('cfgMessengerStatusBadge');
        const msgUid = document.getElementById('cfgMessengerUid');
        const msgLast = document.getElementById('cfgMessengerLastTime');
        const btnToggleMsg = document.getElementById('btnToggleMessenger');

        const isMsgEnabled = Boolean(data.messenger_enabled);
        const msgStatus = data.messenger_cookie_status || 'unknown';

        if (btnToggleMsg) {
          if (isMsgEnabled) {
            btnToggleMsg.className = "px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition";
            btnToggleMsg.innerHTML = '<i class="bi bi-toggle-on"></i> Đang BẬT';
          } else {
            btnToggleMsg.className = "px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-600 text-xs font-semibold text-gray-400 transition";
            btnToggleMsg.innerHTML = '<i class="bi bi-toggle-off"></i> Đang TẮT';
          }
        }

        if (msgPill && msgText) {
          if (!isMsgEnabled) {
            msgPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-gray-800 text-gray-400 border border-gray-700 transition hover:scale-105";
            msgText.innerText = "Messenger: Đang TẮT";
          } else if (msgStatus === 'valid') {
            msgPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 transition hover:scale-105";
            msgText.innerText = "Messenger: Sẵn sàng" + (data.messenger_account_uid ? ` (${data.messenger_account_uid})` : '');
          } else if (msgStatus === 'expired') {
            msgPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/50 animate-pulse transition hover:scale-105";
            msgText.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping mr-0.5"></span><span>Messenger: HẾT HẠN!</span>';
          } else {
            msgPill.className = "cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 transition hover:scale-105";
            msgText.innerText = "Messenger: Chưa có cookie";
          }
        }

        if (msgBadge) {
          if (!isMsgEnabled) {
            msgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-800 text-gray-400 border border-gray-700";
            msgBadge.innerText = "ĐANG TẮT";
          } else if (msgStatus === 'valid') {
            msgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
            msgBadge.innerText = "HỢP LỆ";
          } else if (msgStatus === 'expired') {
            msgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse";
            msgBadge.innerText = "HẾT HẠN";
          } else {
            msgBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30";
            msgBadge.innerText = "CHƯA NẠP";
          }
        }
        if (msgUid) {
          msgUid.innerText = data.messenger_account_uid || 'Chưa xác định';
        }
        if (msgLast) {
          msgLast.innerText = data.messenger_last_connected || 'Chưa kết nối';
        }

      } catch (e) {
        console.error(e);
      }
    }

    async function checkZaloSessionNow() {
      Swal.fire({
        title: 'Đang kiểm tra phiên Zalo...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/zalo/check-status', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Hoàn Hảo!', data.message, 'success');
        } else {
          Swal.fire('Cảnh Báo!', data.message, 'error');
        }
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối API: ' + e, 'error');
      }
    }

    function openZaloCookieModal() {
      Swal.fire({
        title: '🔑 Cập Nhật Cookie Zalo Mới',
        html: `
          <div class="text-left text-xs space-y-3 text-gray-300">
            <p class="text-gray-400">Dán mảng JSON cookie (từ tiện ích Cookie-Editor / EditThisCookie) vào ô bên dưới:</p>
            <textarea id="swalZaloCookieInput" rows="7" class="w-full p-2.5 rounded-xl bg-gray-900 border border-gray-700 font-mono text-[11px] text-emerald-300 focus:outline-none focus:border-blue-500 custom-scroll" placeholder='[&#10;  { "name": "zpw_sek", "value": "..." },&#10;  { "name": "zpsid", "value": "..." }&#10;]'></textarea>
            <div class="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px]">
              💡 <b>Lưu ý vàng:</b> Sau khi copy cookie từ trình duyệt xong, hãy <b>ĐÓNG HẲN tab chat.zalo.me</b> trên trình duyệt để tránh bị Zalo đá phiên!
            </div>
          </div>
        `,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Kiểm Tra & Lưu Ngay',
        cancelButtonText: 'Đóng',
        confirmButtonColor: '#2563eb',
        cancelButtonColor: '#374151',
        focusConfirm: false,
        preConfirm: async () => {
          const val = document.getElementById('swalZaloCookieInput').value.trim();
          if (!val) {
            Swal.showValidationMessage('Vui lòng dán Cookie Zalo vào ô!');
            return false;
          }
          try {
            const res = await fetch('/api/zalo/update-cookies', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ cookies: val })
            });
            const data = await res.json();
            if (!data.success) {
              Swal.showValidationMessage(data.message || 'Lỗi cập nhật cookie');
              return false;
            }
            return data;
          } catch (err) {
            Swal.showValidationMessage('Lỗi kết nối máy chủ: ' + err);
            return false;
          }
        }
      }).then((result) => {
        if (result.isConfirmed && result.value) {
          Swal.fire('Thành Công!', result.value.message, 'success');
          fetchStatus();
        }
      });
    }

    async function toggleBot() {
      const res = await fetch('/api/bot/toggle', { method: 'POST' });
      const data = await res.json();
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: data.is_active ? 'success' : 'info',
        title: data.message,
        showConfirmButton: false,
        timer: 2000
      });
      fetchStatus();
    }

    async function triggerScanNow() {
      Swal.fire({ title: 'Đang quét Cổng UFM...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const res = await fetch('/api/bot/scan-now', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Thành công!', data.message, 'success');
        fetchActivities();
        fetchStatus();
      } else {
        Swal.fire('Thất bại', data.message, 'error');
      }
    }

    async function triggerTestZalo(targetId = null) {
      Swal.fire({ title: 'Đang gửi thông báo thử nghiệm vào Zalo...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const url = targetId ? `/api/test-zalo?target_id=${targetId}` : '/api/test-zalo';
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Đã gửi!', data.message, 'success');
      } else {
        Swal.fire('Lỗi', data.message, 'error');
      }
      fetchStatus();
      fetchLogs();
    }

    async function triggerSendDemoAlert() {
      const confirmRes = await Swal.fire({
        title: '📢 Gửi thông báo vào nhóm demo?',
        text: 'Hệ thống sẽ lấy thông tin sự kiện/hoạt động UFM mới nhất và gửi trực tiếp vào nhóm "demo" (ID: 475259879796859360) kèm tag @All.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#10b981',
        cancelButtonColor: '#6b7280',
        confirmButtonText: '🚀 Bắn Ngay',
        cancelButtonText: 'Hủy'
      });
      if (!confirmRes.isConfirmed) return;

      Swal.fire({
        title: 'Đang gửi thông báo vào nhóm demo...',
        text: 'Vui lòng chờ giây lát trong khi bot kết nối Zalo và phát tin...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });

      try {
        const prefix = window.location.pathname.startsWith('/ufm') ? '/ufm' : '';
        const res = await fetch(prefix + '/api/zalo/send-demo-alert', { method: 'POST' });
        const data = await res.json();
        if (data.success || data.status === 'ok') {
          Swal.fire('Thành công!', data.message || 'Đã gửi thông báo vào nhóm demo!', 'success');
        } else {
          Swal.fire('Thất bại', data.message || 'Chưa gửi được tin nhắn vào nhóm demo. Hãy kiểm tra Cookie Zalo!', 'error');
        }
        fetchStatus();
        fetchLogs();
      } catch (err) {
        Swal.fire('Lỗi kết nối', err.message, 'error');
      }
    }

    async function fetchActivities() {
      try {
        const res = await fetch('/api/activities?limit=100');
        const data = await res.json();
        allActivities = data.activities || [];
        renderActivities(allActivities);
        populateSniperHelper(allActivities);
      } catch (e) {
        console.error(e);
      }
    }

    function renderActivities(list) {
      document.getElementById('actCountBadge').innerText = list.length;
      const tbody = document.getElementById('activitiesTbody');
      if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">Chưa có hoạt động nào trong cơ sở dữ liệu. Bấm "Quét ngay" để đồng bộ.</td></tr>';
        return;
      }

      let html = '';
      for (const a of list) {
        const isFull = a.is_full === 1;
        const statusBadge = isFull 
          ? `<span class="px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium">${a.status || 'Hết slot'}</span>`
          : `<span class="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">${a.status || 'Đang mở'}</span>`;

        let pointsBadge = '';
        if (a.points > 0) pointsBadge += `<span class="text-blue-400 font-semibold">+${a.points} ĐRL</span>`;
        if (a.ctxh > 0) pointsBadge += (pointsBadge ? ' • ' : '') + `<span class="text-emerald-400 font-semibold">+${a.ctxh} CTXH</span>`;
        if (!pointsBadge) pointsBadge = '<span class="text-gray-500">0</span>';

        html += `
          <tr class="hover:bg-gray-800/40 transition">
            <td class="px-4 py-3 font-mono font-bold text-blue-400">${a.activity_id}</td>
            <td class="px-4 py-3 font-semibold text-white max-w-xs">
              <a href="${a.detail_url || '#'}" target="_blank" class="hover:text-blue-400 hover:underline line-clamp-2">${a.title}</a>
            </td>
            <td class="px-4 py-3 text-gray-300">${a.unit || 'Chưa rõ'}</td>
            <td class="px-4 py-3 whitespace-nowrap">${pointsBadge}</td>
            <td class="px-4 py-3 whitespace-nowrap text-gray-400">${a.event_time || 'Chưa rõ'}</td>
            <td class="px-4 py-3 whitespace-nowrap">${statusBadge}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
              <a href="${a.register_url || 'https://hoatdong.ufm.edu.vn/DangKy'}" target="_blank" class="px-2.5 py-1 rounded-md bg-blue-600/30 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 text-xs font-medium transition inline-flex items-center gap-1">
                <span>Đăng ký</span>
                <i class="bi bi-box-arrow-up-right text-[10px]"></i>
              </a>
            </td>
          </tr>
        `;
      }
      tbody.innerHTML = html;
    }

    function filterActivities() {
      const q = document.getElementById('searchAct').value.toLowerCase();
      const filtered = allActivities.filter(a => 
        (a.title && a.title.toLowerCase().includes(q)) ||
        (a.unit && a.unit.toLowerCase().includes(q)) ||
        (a.activity_id && a.activity_id.toLowerCase().includes(q))
      );
      renderActivities(filtered);
    }

    function populateSniperHelper(acts) {
      const select = document.getElementById('sniperSelectHelper');
      if (!select) return;
      let html = '<option value="">-- Chọn HĐ gợi ý --</option>';
      for (const a of acts) {
        const cleanId = a.activity_id.replace(/^[A-Z]+_/, '');
        html += `<option value="${cleanId}" data-title="${a.title}">[ID ${cleanId}] ${a.title.substring(0, 35)}...</option>`;
      }
      select.innerHTML = html;
    }

    function applySniperHelper() {
      const select = document.getElementById('sniperSelectHelper');
      if (select.value) {
        document.getElementById('sniperActivityId').value = select.value;
      }
    }

    // ==========================================
    // JS CHO TAB QUẢN LÝ 100 SINH VIÊN
    // ==========================================

    async function fetchStudents() {
      try {
        const res = await fetch('/api/students');
        const data = await res.json();
        allStudents = data.students || [];
        renderStudents(allStudents);
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    }

    function renderStudents(list) {
      document.getElementById('studentCountBadge').innerText = list.length;
      const tbody = document.getElementById('studentsTbody');
      if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="px-4 py-8 text-center text-gray-500">Chưa có sinh viên nào. Bấm "Nạp Từ Chat Zalo" hoặc "Thêm 1 Bạn" để bắt đầu.</td></tr>';
        return;
      }

      let html = '';
      list.forEach((st, idx) => {
        let cookieBadge = '';
        if (st.cookie_status === 'valid') {
          cookieBadge = '<span class="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold text-[11px]"><i class="bi bi-check-circle mr-1"></i>Sống</span>';
        } else if (st.cookie_status === 'expired') {
          cookieBadge = '<span class="px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold text-[11px]"><i class="bi bi-x-circle mr-1"></i>Hết hạn</span>';
        } else {
          cookieBadge = '<span class="px-2 py-0.5 rounded-md bg-gray-700 text-gray-300 font-semibold text-[11px]">Chưa rõ</span>';
        }

        const isChecked = st.is_active === 1;
        const className = st.class_name ? `<span class="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono text-[11px]">${st.class_name}</span>` : '<span class="text-gray-600 italic">Chưa rõ</span>';
        
        let pwdHtml = '<span class="text-gray-600 italic text-[11px]">Không có</span>';
        if (st.password) {
          pwdHtml = `
            <div class="flex items-center gap-1.5 font-mono text-[11px]">
              <span id="pwd_${st.mssv}" class="text-gray-300">••••••••</span>
              <button onclick="toggleShowPwd('${st.mssv}', '${st.password}')" class="text-gray-400 hover:text-white transition" title="Xem/Ẩn mật khẩu">
                <i id="icon_pwd_${st.mssv}" class="bi bi-eye text-xs"></i>
              </button>
            </div>
          `;
        }

        html += `
          <tr class="hover:bg-gray-800/40 transition">
            <td class="px-4 py-3 text-gray-500 font-mono">${idx + 1}</td>
            <td class="px-4 py-3 font-mono font-bold text-white">${st.mssv}</td>
            <td class="px-4 py-3 font-semibold text-gray-200">${st.full_name || '<span class="text-gray-500 italic">Chưa rõ</span>'}</td>
            <td class="px-4 py-3 whitespace-nowrap">${className}</td>
            <td class="px-4 py-3 whitespace-nowrap">${pwdHtml}</td>
            <td class="px-4 py-3 whitespace-nowrap">${cookieBadge}</td>
            <td class="px-4 py-3 font-mono text-[11px] text-gray-400 max-w-xs truncate">${st.last_registered_activity || '<span class="text-gray-600">Chưa có</span>'}</td>
            <td class="px-4 py-3 text-center">
              <input type="checkbox" onchange="toggleStudentActive('${st.mssv}')" ${isChecked ? 'checked' : ''} class="w-4 h-4 rounded text-indigo-600 bg-gray-900 border-gray-700 focus:ring-indigo-500 cursor-pointer">
            </td>
            <td class="px-4 py-3 text-right space-x-2 whitespace-nowrap">
              <button onclick="deleteStudent('${st.mssv}')" class="text-rose-400 hover:text-rose-300 transition" title="Xóa tài khoản">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    }

    function toggleShowPwd(mssv, pwd) {
      const el = document.getElementById('pwd_' + mssv);
      const icon = document.getElementById('icon_pwd_' + mssv);
      if (!el) return;
      if (el.innerText === '••••••••') {
        el.innerText = pwd;
        if (icon) icon.className = "bi bi-eye-slash text-xs text-indigo-400";
      } else {
        el.innerText = '••••••••';
        if (icon) icon.className = "bi bi-eye text-xs";
      }
    }

    function filterStudents() {
      const q = document.getElementById('searchStudent').value.toLowerCase();
      const filtered = allStudents.filter(s => 
        (s.mssv && s.mssv.toLowerCase().includes(q)) ||
        (s.full_name && s.full_name.toLowerCase().includes(q)) ||
        (s.class_name && s.class_name.toLowerCase().includes(q))
      );
      renderStudents(filtered);
    }

    async function toggleStudentActive(mssv) {
      await fetch('/api/student/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mssv: mssv })
      });
      fetchStatus();
    }

    async function deleteStudent(mssv) {
      const res = await Swal.fire({
        title: 'Xác nhận xóa?',
        text: `Bạn có chắc muốn xóa sinh viên MSSV ${mssv}?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Đồng ý xóa',
        cancelButtonText: 'Hủy'
      });
      if (res.isConfirmed) {
        await fetch('/api/student/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv })
        });
        fetchStudents();
      }
    }

    function copyStudentSubmitLink() {
      const url = window.location.origin + '/submit-cookie';
      navigator.clipboard.writeText(url).then(() => {
        Swal.fire({
          toast: true,
          position: 'top-end',
          icon: 'success',
          title: 'Đã copy link form sinh viên!',
          text: url,
          showConfirmButton: false,
          timer: 2500
        });
      });
    }

    async function checkAllStudentsCookie() {
      Swal.fire({ title: 'Đang kiểm tra Cookie toàn bộ danh sách...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const res = await fetch('/api/students/check-all', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Hoàn tất!', data.message, 'success');
        fetchStudents();
      } else {
        Swal.fire('Lỗi', data.message, 'error');
      }
    }

    async function reloginAllStudents() {
      const confirm = await Swal.fire({
        title: 'Làm mới Cookie toàn bộ?',
        text: 'Hệ thống sẽ dùng mật khẩu đã lưu để tự động đăng nhập lại tất cả sinh viên lên cổng UFM và làm mới Cookie sống.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#06b6d4',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Bắt đầu làm mới',
        cancelButtonText: 'Hủy'
      });
      if (!confirm.isConfirmed) return;

      Swal.fire({ title: 'Đang tự động đăng nhập lại toàn bộ sinh viên...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      try {
        const res = await fetch('/api/students/relogin-all', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Hoàn tất!', data.message, 'success');
          fetchStudents();
        } else {
          Swal.fire('Thông báo', data.message, 'warning');
        }
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối máy chủ: ' + e.message, 'error');
      }
    }

    async function openBulkImportModal() {
      const { value: rawText } = await Swal.fire({
        title: '📋 Nạp Hàng Loạt Từ Tin Nhắn Zalo',
        html: `
          <div class="text-left text-xs text-gray-300 space-y-2 mb-3">
            <p>💡 <strong>Hướng dẫn:</strong> Bạn chỉ cần copy nguyên đoạn chat từ Zalo (1 bạn hoặc nhiều bạn) dán vào ô dưới đây. Bot sẽ tự bóc tách MSSV, Mật khẩu, Họ tên và tự đăng nhập UFM lấy thông tin!</p>
            <div class="p-2 rounded bg-gray-900 border border-gray-700 font-mono text-[11px] text-gray-400">
              Ví dụ 1: Họ tên: Đàm Anh Duy / MSSV: 2621008460 / Pass: 123456<br>
              Ví dụ 2: 2621008460 | matkhau123 | Đàm Anh Duy
            </div>
          </div>
          <textarea id="swalBulkText" class="swal2-textarea custom-scroll" style="height: 180px; font-family: monospace; font-size: 12px;" placeholder="Dán nội dung tin nhắn Zalo vào đây..."></textarea>
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: '⚡ Bóc tách & Nạp ngay',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#059669',
        preConfirm: () => {
          return document.getElementById('swalBulkText').value.trim();
        }
      });

      if (!rawText) return;

      Swal.fire({ title: 'Đang phân tích và xác thực với Cổng UFM...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });

      try {
        const res = await fetch('/api/students/bulk-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ raw_text: rawText })
        });
        const data = await res.json();

        if (data.success) {
          let summaryHtml = `<div class="text-left text-xs space-y-1.5 max-h-60 overflow-y-auto custom-scroll p-2 bg-gray-900 rounded border border-gray-800">`;
          data.items.forEach(it => {
            const icon = it.status === 'success' ? '🟢' : '⚠️';
            summaryHtml += `<div>${icon} <strong>${it.mssv}</strong>: ${it.full_name} (${it.class_name || 'Chưa rõ lớp'}) - <span class="text-gray-400">${it.message}</span></div>`;
          });
          summaryHtml += `</div>`;

          Swal.fire({
            icon: data.failed === 0 ? 'success' : 'info',
            title: 'Kết Quả Nạp Hàng Loạt',
            html: `<p class="mb-3">${data.message}</p>${summaryHtml}`,
            confirmButtonColor: '#059669'
          });
          fetchStudents();
        } else {
          Swal.fire('Lỗi', data.message, 'error');
        }
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối: ' + e.message, 'error');
      }
    }

    async function openAddStudentModal() {
      const { value: formValues } = await Swal.fire({
        title: 'Thêm Sinh Viên Mới',
        html: `
          <div class="text-left text-xs text-gray-400 space-y-1 mb-2">
            <span>💡 Nhập MSSV + Mật khẩu (Hệ thống tự động đăng nhập lấy tên thật và Cookie) HOẶC dán Cookie trực tiếp.</span>
          </div>
          <input id="swalMssv" class="swal2-input" placeholder="Mã số sinh viên (MSSV) *">
          <input id="swalPass" class="swal2-input" type="password" placeholder="Mật khẩu cổng UFM (Khuyên dùng)">
          <input id="swalName" class="swal2-input" placeholder="Họ và tên (Tùy chọn)">
          <textarea id="swalCookie" class="swal2-textarea" placeholder="Dán Cookie (.AspNetCore.Cookies=...) nếu không nhập mật khẩu"></textarea>
        `,
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Xác thực & Lưu',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#4f46e5',
        preConfirm: () => {
          return {
            mssv: document.getElementById('swalMssv').value.trim(),
            password: document.getElementById('swalPass').value.trim(),
            full_name: document.getElementById('swalName').value.trim(),
            cookie_data: document.getElementById('swalCookie').value.trim()
          }
        }
      });

      if (formValues && formValues.mssv && (formValues.password || formValues.cookie_data)) {
        Swal.fire({ title: 'Đang xác thực với Cổng UFM...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
        const res = await fetch('/api/student/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formValues)
        });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Thành công', data.message, 'success');
          fetchStudents();
        } else {
          Swal.fire('Chưa hợp lệ', data.message, 'warning');
          fetchStudents();
        }
      }
    }

    // ==========================================
    // TIẾN TRÌNH BẮN ĐĂNG KÝ HÀNG LOẠT (SNIPER)
    // ==========================================

    async function triggerBatchRegister() {
      const aid = document.getElementById('sniperActivityId').value.trim();
      if (!aid) {
        Swal.fire('Lưu ý', 'Vui lòng nhập Mã ID Hoạt Động (Ví dụ: 16589)!', 'warning');
        return;
      }

      const activeCount = parseInt(document.getElementById('stStatActive').innerText) || 0;
      if (activeCount === 0) {
        Swal.fire('Chưa có tài khoản', 'Hiện không có tài khoản sinh viên nào đang BẬT để bắn đăng ký!', 'warning');
        return;
      }

      const select = document.getElementById('sniperSelectHelper');
      const selectedOption = select.options[select.selectedIndex];
      const title = selectedOption ? (selectedOption.dataset.title || '') : '';

      const confirm = await Swal.fire({
        title: 'Xác nhận BẮN ĐĂNG KÝ?',
        html: `Bạn có chắc chắn muốn nã đăng ký hoạt động <b>[ID ${aid}]</b> cho <b>${activeCount}</b> sinh viên đang bật không?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: '🚀 BẮN NGAY!',
        cancelButtonText: 'Hủy'
      });

      if (!confirm.isConfirmed) return;

      const res = await fetch('/api/students/batch-register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_id: aid, activity_title: title })
      });
      const data = await res.json();

      if (data.success) {
        document.getElementById('batchProgressBox').classList.remove('hidden');
        document.getElementById('btnStartBatch').disabled = true;
        document.getElementById('btnStartBatch').classList.add('opacity-50', 'cursor-not-allowed');

        // Bắt đầu thăm dò tiến trình thực tế
        if (batchPoller) clearInterval(batchPoller);
        batchPoller = setInterval(pollBatchStatus, 1000);
      } else {
        Swal.fire('Lỗi', data.message, 'error');
      }
    }

    async function pollBatchStatus() {
      try {
        const res = await fetch('/api/students/batch-status');
        const data = await res.json();

        const pct = data.total > 0 ? Math.round((data.completed / data.total) * 100) : 0;
        document.getElementById('batchProgressBar').style.width = pct + '%';
        document.getElementById('batchProgressStats').innerText = `${data.completed} / ${data.total} (${pct}%) • ✅ ${data.success} • ❌ ${data.failed}`;

        // Render mini logs
        const logBox = document.getElementById('batchMiniLogs');
        if (data.logs && data.logs.length > 0) {
          logBox.innerHTML = data.logs.slice(-20).map(l => `<div>${l}</div>`).join('');
          logBox.scrollTop = logBox.scrollHeight;
        }

        if (!data.is_running && data.completed >= data.total) {
          clearInterval(batchPoller);
          batchPoller = null;
          document.getElementById('btnStartBatch').disabled = false;
          document.getElementById('btnStartBatch').classList.remove('opacity-50', 'cursor-not-allowed');
          document.getElementById('batchProgressLabel').innerHTML = '✅ Đã hoàn tất toàn bộ!';
          
          Swal.fire({
            icon: 'success',
            title: 'Bắn đăng ký hoàn tất!',
            html: `Đã xử lý xong <b>${data.total}</b> tài khoản:<br>✅ <b>${data.success}</b> thành công<br>❌ <b>${data.failed}</b> thất bại/hết slot.<br>Báo cáo tổng kết đã được gửi tới Zalo!`
          });
          fetchStudents();
        }
      } catch (e) {
        console.error(e);
      }
    }

    // ==========================================
    // JS CHO TAB LỊCH SỬ & CẤU HÌNH
    // ==========================================

    async function fetchHistory() {
      try {
        const res = await fetch('/api/delivery-history?limit=100');
        const data = await res.json();
        allHistory = data.history || [];
        const tbody = document.getElementById('historyTbody');
        if (!allHistory || allHistory.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-500">Chưa có bản ghi phát tin nào.</td></tr>';
          return;
        }

        let html = '';
        for (const h of allHistory) {
          const isSuccess = h.status === 'SUCCESS';
          const statusBadge = isSuccess
            ? '<span class="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">THÀNH CÔNG</span>'
            : '<span class="px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">THẤT BẠI</span>';

          html += `
            <tr class="hover:bg-gray-800/40 transition">
              <td class="px-4 py-3 font-mono text-gray-400 whitespace-nowrap">${h.sent_at}</td>
              <td class="px-4 py-3 font-semibold text-white max-w-sm line-clamp-1">${h.post_title}</td>
              <td class="px-4 py-3 text-indigo-300 font-medium">${h.zalo_target_name}</td>
              <td class="px-4 py-3 font-mono text-gray-400">${h.target_type}</td>
              <td class="px-4 py-3">${statusBadge}</td>
              <td class="px-4 py-3 text-right">
                <a href="${h.post_url}" target="_blank" class="text-blue-400 hover:underline">Link bài</a>
              </td>
            </tr>
          `;
        }
        tbody.innerHTML = html;
      } catch (e) {
        console.error(e);
      }
    }

    async function loadConfigForm() {
      const res = await fetch('/api/config');
      currentConfig = await res.json();
      
      const portal = currentConfig.ufm_portal || {};
      document.getElementById('cfgUsername').value = portal.username || '';
      document.getElementById('cfgPassword').value = portal.password || '';
      document.getElementById('cfgInterval').value = (currentConfig.scanner && currentConfig.scanner.check_interval_seconds) || 20;

      renderTargetGroupsEditor(currentConfig.zalo && currentConfig.zalo.target_groups ? currentConfig.zalo.target_groups : []);
      renderMessengerGroupsEditor(currentConfig.messenger && currentConfig.messenger.target_groups ? currentConfig.messenger.target_groups : []);
      renderAllActiveChannels();
    }

    function renderTargetGroupsEditor(groups) {
      const container = document.getElementById('targetGroupsContainer');
      const activePillContainer = document.getElementById('activeChannelsList');
      if (!groups || groups.length === 0) {
        container.innerHTML = '<div class="text-xs text-gray-500">Chưa có nhóm nào. Bấm "Đồng bộ từ Zalo" để nạp danh sách.</div>';
        activePillContainer.innerHTML = '<span class="text-xs text-gray-500">Chưa có kênh nào bật</span>';
        return;
      }

      let html = '';
      let activePillsHtml = '';

      groups.forEach((g, idx) => {
        const isEnabled = g.enabled === true || g.enabled === 'true';
        if (isEnabled) {
          activePillsHtml += `
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-medium">
              <i class="bi ${g.type === 'USER' ? 'bi-person-fill' : 'bi-people-fill'} text-xs"></i>
              <span>${g.name}</span>
            </span>
          `;
        }

        html += `
          <div class="flex items-center justify-between p-2.5 rounded-lg bg-gray-800/80 border border-gray-700/80 text-xs">
            <div class="flex items-center gap-2">
              <input type="checkbox" id="grp_chk_${idx}" ${isEnabled ? 'checked' : ''} class="w-4 h-4 rounded text-blue-600 bg-gray-900 border-gray-700 focus:ring-blue-500">
              <div>
                <div class="font-semibold text-white flex items-center gap-1.5">
                  <i class="bi ${g.type === 'USER' ? 'bi-person-fill text-purple-400' : 'bi-people-fill text-blue-400'}"></i>
                  <span>${g.name}</span>
                </div>
                <div class="text-[10px] text-gray-500 font-mono">ID: ${g.id} (${g.type || 'GROUP'})</div>
              </div>
            </div>
            <button onclick="triggerTestZalo('${g.id}')" class="px-2 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-[11px] font-medium transition">
              Thử tin
            </button>
          </div>
        `;
      });

      container.innerHTML = html;
      activePillContainer.innerHTML = activePillsHtml || '<span class="text-xs text-gray-500">Chưa có kênh nào bật</span>';
    }

    async function savePortalConfig() {
      if (!currentConfig.ufm_portal) currentConfig.ufm_portal = {};
      currentConfig.ufm_portal.username = document.getElementById('cfgUsername').value.trim();
      currentConfig.ufm_portal.password = document.getElementById('cfgPassword').value.trim();
      if (!currentConfig.scanner) currentConfig.scanner = {};
      currentConfig.scanner.check_interval_seconds = parseInt(document.getElementById('cfgInterval').value) || 20;

      const res = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig)
      });
      const data = await res.json();
      Swal.fire('Thành công', data.message, 'success');
      fetchStatus();
    }

    async function reloginUFM() {
      Swal.fire({ title: 'Đang đăng nhập Cổng UFM...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const res = await fetch('/api/portal/login', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Đăng nhập thành công!', data.message, 'success');
      } else {
        Swal.fire('Thất bại', data.message, 'error');
      }
      fetchStatus();
    }

    async function saveZaloGroupsConfig() {
      if (!currentConfig.zalo) currentConfig.zalo = {};
      const groups = currentConfig.zalo.target_groups || [];
      groups.forEach((g, idx) => {
        const chk = document.getElementById(`grp_chk_${idx}`);
        if (chk) {
          g.enabled = chk.checked;
        }
      });

      const res = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig)
      });
      const data = await res.json();
      Swal.fire('Đã lưu!', 'Danh sách nhóm nhận tin Zalo đã được cập nhật.', 'success');
      renderTargetGroupsEditor(groups);
      fetchStatus();
    }

    async function fetchZaloGroupsFromClient() {
      Swal.fire({ title: 'Đang tải danh sách nhóm từ Zalo...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const res = await fetch('/api/zalo/fetch-groups');
      const data = await res.json();
      if (!data.success) {
        Swal.fire('Lỗi', data.message, 'error');
        return;
      }

      const existingGroups = currentConfig.zalo?.target_groups || [];
      const existingIds = new Set(existingGroups.map(g => String(g.id)));

      for (const g of data.groups) {
        if (!existingIds.has(String(g.id))) {
          existingGroups.push({
            id: String(g.id),
            name: g.name,
            type: "GROUP",
            enabled: g.name.toLowerCase().includes('ufm') || g.name.toLowerCase().includes('demo')
          });
        }
      }

      currentConfig.zalo.target_groups = existingGroups;
      await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig)
      });

      Swal.fire('Đồng bộ xong!', `Đã nạp ${data.groups.length} nhóm từ Zalo!`, 'success');
      renderTargetGroupsEditor(existingGroups);
      renderAllActiveChannels();
    }

    // ==========================================
    // JS CHO KÊNH FACEBOOK MESSENGER
    // ==========================================

    function renderAllActiveChannels() {
      const activePillContainer = document.getElementById('activeChannelsList');
      if (!activePillContainer) return;

      let pillsHtml = '';
      const zaloGroups = currentConfig.zalo?.target_groups || [];
      zaloGroups.forEach(g => {
        if (g.enabled === true || g.enabled === 'true') {
          pillsHtml += `
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-medium">
              <i class="bi bi-chat-dots-fill text-xs"></i>
              <span>[Zalo] ${g.name}</span>
            </span>
          `;
        }
      });

      const isMsgEnabled = currentConfig.messenger?.enabled === true;
      if (isMsgEnabled) {
        const msgGroups = currentConfig.messenger?.target_groups || [];
        msgGroups.forEach(g => {
          if (g.enabled === true || g.enabled === 'true') {
            pillsHtml += `
              <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-500/20 text-sky-300 border border-sky-500/30 text-xs font-medium">
                <i class="bi bi-messenger text-xs"></i>
                <span>[FB] ${g.name}</span>
              </span>
            `;
          }
        });
      }

      activePillContainer.innerHTML = pillsHtml || '<span class="text-xs text-gray-500">Chưa có kênh nào bật nhận tin</span>';
    }

    function renderMessengerGroupsEditor(groups) {
      const container = document.getElementById('messengerGroupsContainer');
      if (!container) return;

      if (!groups || groups.length === 0) {
        container.innerHTML = '<div class="text-xs text-gray-500 py-4 text-center">Chưa có nhóm Messenger nào.<br>Bấm <b>"Thêm ID"</b> để dán Thread ID nhóm hoặc bấm <b>"Đồng bộ FB"</b>.</div>';
        return;
      }

      let html = '';
      groups.forEach((g, idx) => {
        const isEnabled = g.enabled === true || g.enabled === 'true';
        html += `
          <div class="flex items-center justify-between p-2.5 rounded-lg bg-gray-800/80 border border-blue-900/40 text-xs">
            <div class="flex items-center gap-2">
              <input type="checkbox" id="msg_grp_chk_${idx}" ${isEnabled ? 'checked' : ''} class="w-4 h-4 rounded text-blue-600 bg-gray-900 border-gray-700 focus:ring-blue-500">
              <div>
                <div class="font-semibold text-white flex items-center gap-1.5">
                  <i class="bi bi-messenger text-sky-400"></i>
                  <span>${g.name}</span>
                </div>
                <div class="text-[10px] text-gray-500 font-mono">Thread ID: ${g.id}</div>
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <button onclick="triggerTestMessenger('${g.id}')" class="px-2 py-1 rounded bg-blue-600/30 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 text-[11px] font-medium transition" title="Gửi tin thử nghiệm vào nhóm này">
                Thử tin
              </button>
              <button onclick="removeMessengerGroup('${g.id}')" class="px-2 py-1 rounded bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-500/30 text-[11px] font-medium transition" title="Xóa nhóm khỏi danh sách">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    async function toggleMessengerChannel() {
      try {
        const res = await fetch('/api/messenger/toggle', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Thành công', data.message, 'success');
          if (!currentConfig.messenger) currentConfig.messenger = {};
          currentConfig.messenger.enabled = data.enabled;
          fetchStatus();
          renderAllActiveChannels();
        }
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể đổi trạng thái Messenger: ' + e, 'error');
      }
    }

    async function saveMessengerGroupsConfig() {
      if (!currentConfig.messenger) currentConfig.messenger = {};
      const groups = currentConfig.messenger.target_groups || [];
      groups.forEach((g, idx) => {
        const chk = document.getElementById(`msg_grp_chk_${idx}`);
        if (chk) {
          g.enabled = chk.checked;
        }
      });

      try {
        const res = await fetch('/api/messenger/save-groups', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ groups: groups })
        });
        const data = await res.json();
        Swal.fire('Đã lưu!', 'Danh sách nhóm Messenger đã được cập nhật.', 'success');
        renderMessengerGroupsEditor(groups);
        renderAllActiveChannels();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể lưu danh sách: ' + e, 'error');
      }
    }

    async function openAddMessengerGroupModal() {
      const { value: formValues } = await Swal.fire({
        title: '➕ Thêm Nhóm Messenger',
        html: `
          <div class="text-left text-xs space-y-3 text-gray-300">
            <div>
              <label class="block text-gray-400 mb-1 font-semibold">Thread ID nhóm Messenger (*):</label>
              <input id="swalMsgGroupId" class="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white font-mono text-xs focus:outline-none focus:border-blue-500" placeholder="VD: 749281749201948">
              <span class="text-[10px] text-gray-500">Mẹo: Mở nhóm chat trên messenger.com trên máy tính, nhìn vào thanh URL: messenger.com/t/<b>123456789</b> -> dãy số đó chính là Thread ID.</span>
            </div>
            <div>
              <label class="block text-gray-400 mb-1 font-semibold">Tên gợi nhớ của nhóm:</label>
              <input id="swalMsgGroupName" class="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-xs focus:outline-none focus:border-blue-500" placeholder="VD: Nhóm Hoạt Động K26 UFM">
            </div>
          </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Thêm Ngay',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#2563eb',
        preConfirm: () => {
          const tid = document.getElementById('swalMsgGroupId').value.trim();
          const tname = document.getElementById('swalMsgGroupName').value.trim();
          if (!tid) {
            Swal.showValidationMessage('Vui lòng nhập Thread ID nhóm!');
            return false;
          }
          return { thread_id: tid, name: tname };
        }
      });

      if (formValues) {
        try {
          const res = await fetch('/api/messenger/add-group', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formValues)
          });
          const data = await res.json();
          if (data.success) {
            Swal.fire('Thành công', data.message, 'success');
            await loadConfigForm();
            fetchStatus();
          } else {
            Swal.fire('Không thể thêm', data.message, 'error');
          }
        } catch (e) {
          Swal.fire('Lỗi', 'Không thể kết nối API: ' + e, 'error');
        }
      }
    }

    async function removeMessengerGroup(threadId) {
      const confirm = await Swal.fire({
        title: 'Xóa nhóm Messenger?',
        text: `Bạn có chắc muốn xóa nhóm có Thread ID ${threadId} khỏi danh sách nhận thông báo?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Xóa nhóm',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#e11d48'
      });

      if (confirm.isConfirmed) {
        try {
          const res = await fetch('/api/messenger/remove-group', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thread_id: threadId })
          });
          const data = await res.json();
          if (data.success) {
            Swal.fire('Đã xóa', data.message, 'success');
            await loadConfigForm();
            fetchStatus();
          } else {
            Swal.fire('Lỗi', data.message, 'error');
          }
        } catch (e) {
          Swal.fire('Lỗi', 'Không thể xóa nhóm: ' + e, 'error');
        }
      }
    }

    async function fetchMessengerGroupsFromClient() {
      Swal.fire({
        title: 'Đang quét danh sách nhóm từ Facebook...',
        html: '<div class="text-xs text-gray-400">Bot đang dùng cookie để lấy danh sách hội thoại nhóm gần đây.</div>',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });

      try {
        const res = await fetch('/api/messenger/fetch-groups');
        const data = await res.json();
        if (!data.success) {
          Swal.fire('Lỗi', data.message, 'error');
          return;
        }

        const groups = data.groups || [];
        if (groups.length === 0) {
          Swal.fire('Thông báo', 'Không tìm thấy nhóm Messenger nào gần đây trong hộp thư tài khoản.', 'info');
          return;
        }

        const existingGroups = currentConfig.messenger?.target_groups || [];
        const existingIds = new Set(existingGroups.map(g => String(g.id)));

        let addedCount = 0;
        for (const g of groups) {
          if (!existingIds.has(String(g.id))) {
            existingGroups.push({
              id: String(g.id),
              name: g.name || `Nhóm ${g.id}`,
              type: "GROUP",
              enabled: true
            });
            addedCount++;
          }
        }

        if (!currentConfig.messenger) currentConfig.messenger = {};
        currentConfig.messenger.target_groups = existingGroups;

        await fetch('/api/config/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentConfig)
        });

        Swal.fire('Đồng bộ xong!', `Đã nạp ${groups.length} nhóm (Thêm mới ${addedCount} nhóm)!`, 'success');
        renderMessengerGroupsEditor(existingGroups);
        renderAllActiveChannels();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể đồng bộ: ' + e, 'error');
      }
    }

    async function triggerTestMessenger(targetId) {
      Swal.fire({
        title: 'Đang gửi tin thử nghiệm Messenger...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });

      try {
        const res = await fetch('/api/messenger/test-send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_id: targetId || null })
        });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Thất bại', data.message, 'error');
        }
        fetchLogs();
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể gửi tin thử nghiệm: ' + e, 'error');
      }
    }

    async function checkMessengerSessionNow() {
      Swal.fire({
        title: 'Đang kiểm tra kết nối Facebook...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/messenger/check-connection', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Tuyệt vời!', data.message, 'success');
        } else {
          Swal.fire('Cảnh báo phiên!', data.message, 'warning');
        }
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối API: ' + e, 'error');
      }
    }

    function openMessengerCookieModal() {
      Swal.fire({
        title: '🔑 Cập Nhật Cookie Facebook Messenger',
        html: `
          <div class="text-left text-xs space-y-3 text-gray-300">
            <p class="text-gray-400">Dán chuỗi JSON Cookie Facebook (mảng từ tiện ích C3C FB State, Cookie-Editor hoặc EditThisCookie) vào bên dưới:</p>
            <textarea id="swalMessengerCookieInput" rows="7" class="w-full p-2.5 rounded-xl bg-gray-900 border border-gray-700 font-mono text-[11px] text-sky-300 focus:outline-none focus:border-blue-500 custom-scroll" placeholder='[&#10;  { "name": "c_user", "value": "1000..." },&#10;  { "name": "xs", "value": "..." }&#10;]'></textarea>
            <div class="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[11px] space-y-1">
              <div>💡 <b>Cách lấy cookie Facebook dễ nhất:</b></div>
              <div>1. Đăng nhập facebook.com trên trình duyệt máy tính.</div>
              <div>2. Dùng tiện ích <b>Cookie-Editor</b> hoặc <b>C3C State Extractor</b>, bấm Export -> dạng <b>JSON</b>.</div>
              <div>3. Dán toàn bộ vào ô trên và bấm "Xác Thực & Lưu Ngay".</div>
            </div>
          </div>
        `,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Xác Thực & Lưu Ngay',
        cancelButtonText: 'Đóng',
        confirmButtonColor: '#2563eb',
        cancelButtonColor: '#374151',
        focusConfirm: false,
        preConfirm: async () => {
          const val = document.getElementById('swalMessengerCookieInput').value.trim();
          if (!val) {
            Swal.showValidationMessage('Vui lòng dán Cookie Facebook vào ô!');
            return false;
          }
          try {
            const res = await fetch('/api/messenger/update-cookies', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ cookies: val })
            });
            const data = await res.json();
            if (!data.success) {
              Swal.showValidationMessage(data.message || 'Lỗi cập nhật cookie Facebook');
              return false;
            }
            return data;
          } catch (err) {
            Swal.showValidationMessage('Lỗi kết nối máy chủ: ' + err);
            return false;
          }
        }
      }).then((result) => {
        if (result.isConfirmed && result.value) {
          Swal.fire('Thành Công!', result.value.message, 'success');
          loadConfigForm();
          fetchStatus();
        }
      });
    }

    // ================= LIVE CONSOLE LOGS & CLOCK =================
    let currentLogUfmScope = 'UFM';

    function tickClockBot4() {
      const el = document.getElementById('liveClockBot4');
      if (el) {
        const now = new Date();
        el.innerText = now.toTimeString().split(' ')[0];
      }
    }
    setInterval(tickClockBot4, 1000);
    tickClockBot4();

    function setLogUfmScope(scope) {
      currentLogUfmScope = scope;
      const btnUfm = document.getElementById('btnLogScopeUfm');
      const btnAll = document.getElementById('btnLogScopeUfmAll');
      if (btnUfm && btnAll) {
        if (scope === 'UFM') {
          btnUfm.className = 'px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs';
          btnAll.className = 'px-2.5 py-1 rounded text-gray-400 hover:text-white transition';
        } else {
          btnAll.className = 'px-2.5 py-1 rounded bg-blue-600 text-white shadow-xs';
          btnUfm.className = 'px-2.5 py-1 rounded text-gray-400 hover:text-white transition';
        }
      }
      fetchLogs();
    }

    function clearTerminalViewUFM() {
      const term = document.getElementById('terminalLog');
      if (term) term.innerHTML = '<div class="text-gray-500">Màn hình đã xóa. Đang chờ log tiếp theo...</div>';
    }

    async function fetchLogs() {
      try {
        const url = (currentLogUfmScope === 'ALL') ? '/api/all-logs?limit=80' : '/api/logs?limit=80';
        const res = await fetch(url);
        const data = await res.json();
        const term = document.getElementById('terminalLog');
        if (!data.logs || data.logs.length === 0) {
          term.innerHTML = '<div class="text-gray-500">Chưa có nhật ký nào.</div>';
          return;
        }

        let html = '';
        for (const log of data.logs) {
          let lvlColor = 'text-blue-400';
          if (log.level === 'WARN') lvlColor = 'text-amber-400';
          if (log.level === 'ERROR') lvlColor = 'text-rose-400';
          if (log.level === 'ZALO') lvlColor = 'text-emerald-400';
          if (log.level === 'ACTIVITY') lvlColor = 'text-indigo-400';
          if (log.level === 'SNIPER') lvlColor = 'text-red-400 font-bold';
          if (log.level === 'STUDENT') lvlColor = 'text-cyan-400';
          if (log.level === 'SCAN') lvlColor = 'text-teal-400';

          const timeStr = log.created_at ? (log.created_at.includes(' ') ? log.created_at.split(' ')[1] : log.created_at) : '';
          const botBadge = (currentLogUfmScope === 'ALL' && log.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-blue-300 border border-gray-700 shrink-0">[${log.bot}]</span> ` : '';

          html += `<div class="flex items-start gap-1.5 py-0.5"><span class="text-gray-500 shrink-0 font-mono">[${timeStr}]</span> ${botBadge}<span class="${lvlColor} shrink-0">[${log.level}]</span> <span class="break-all">${log.message}</span></div>`;
        }
        term.innerHTML = html;
      } catch (e) {
        console.error(e);
      }
    }

    // Khởi chạy ban đầu
    fetchStatus();
    fetchActivities();
    loadConfigForm();
    fetchLogs();

    setInterval(fetchStatus, 3000);
    setInterval(fetchLogs, 1000);
  </script>
</body>
</html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=5004, reload=False)
