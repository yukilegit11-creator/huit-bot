# -*- coding: utf-8 -*-
import os
import sys

output_path = r"c:\Users\Admin\Documents\HUIT\vaa\ufm\web_app.py"

python_code = r'''import os
import sys
import json
import sqlite3
import threading
import time
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

import importlib.util

# Nap database rieng cua UFM
_db_spec = importlib.util.spec_from_file_location("ufm_db_local", os.path.join(SCRIPT_DIR, "database.py"))
database = importlib.util.module_from_spec(_db_spec)
_db_spec.loader.exec_module(database)

# Dam bao UFM_DB_FILE luon ton tai tren module
if not hasattr(database, "UFM_DB_FILE") and hasattr(database, "DB_FILE"):
    database.UFM_DB_FILE = database.DB_FILE

# Nap scraper, sender, batch register tu local
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from zalo_sender import ZaloDispatcher
from ufm_scraper import UFMPortalScraper
from batch_register import check_student_cookie, execute_batch_registration, BATCH_PROGRESS
import smart_parser

# Messenger
try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

app = FastAPI(title="Yuki 4 - UFM Bot Dashboard (Đại học Tài chính - Marketing)", version="3.0")

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

    database.log_event("SCAN", f"Quét thủ công xong: Tìm thấy {len(activities)} hoạt động (Mới: {new_count}, Mở lại slot: {reopened_count}).")
    return {"success": True, "message": f"Quét hoàn tất: {len(activities)} hoạt động (Mới: {new_count}, Mở lại slot: {reopened_count})"}

@app.get("/api/activities")
def api_activities(limit: int = 100):
    rows = database.get_crawled_activities(limit=limit)
    return {"status": "ok", "activities": rows}

@app.get("/api/students")
def api_students():
    rows = database.get_all_students()
    return {"status": "ok", "students": rows}

@app.post("/api/student/submit")
def api_student_submit(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    pwd = str(data.get("password", "")).strip()
    name = str(data.get("full_name", "")).strip()
    cookie = str(data.get("cookie_data", "")).strip()
    cls_name = str(data.get("class_name", "")).strip()

    if not mssv:
        return {"success": False, "message": "Vui lòng nhập MSSV!"}

    if not pwd and not cookie:
        return {"success": False, "message": "Cần cung cấp Mật khẩu cổng UFM hoặc Cookie phiên!"}

    is_valid, msg, sess = check_student_cookie(cookie, mssv=mssv, password=pwd)
    status_str = "valid" if is_valid else "expired"

    database.save_student(
        mssv=mssv,
        password=pwd,
        full_name=name or mssv,
        cookie_data=sess or cookie,
        session_status=status_str,
        class_name=cls_name
    )

    if is_valid:
        database.log_event("STUDENT", f"Sinh viên {mssv} ({name or mssv}) đã nạp thông tin thành công. Trạng thái: Hợp lệ.")
        return {"success": True, "message": f"Nạp thành công sinh viên {mssv}! {msg}"}
    else:
        database.log_event("WARN", f"Sinh viên {mssv} đã nạp nhưng xác thực không thành công: {msg}")
        return {"success": False, "message": f"Thông tin đã lưu nhưng chưa xác thực được: {msg}"}

@app.post("/api/student/toggle")
def api_student_toggle(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    is_active = bool(data.get("is_active", True))
    database.set_student_active(mssv, is_active)
    return {"success": True, "message": f"Đã {'BẬT' if is_active else 'TẮT'} tự động đăng ký cho sinh viên {mssv}"}

@app.post("/api/student/delete")
def api_student_delete(data: dict):
    mssv = str(data.get("mssv", "")).strip()
    database.delete_student(mssv)
    database.log_event("STUDENT", f"Đã xóa sinh viên {mssv} khỏi danh sách.")
    return {"success": True, "message": f"Đã xóa sinh viên {mssv}"}

@app.post("/api/students/bulk-import")
def api_students_bulk_import(data: dict):
    text_data = data.get("text_data", "")
    if not text_data:
        return {"success": False, "message": "Vui lòng dán danh sách tài khoản!"}

    parsed_list = smart_parser.parse_bulk_text(text_data)
    if not parsed_list:
        return {"success": False, "message": "Không nhận diện được tài khoản nào. Vui lòng kiểm tra định dạng MSSV | Mật khẩu | Họ tên!"}

    succ_count = 0
    fail_count = 0
    for st in parsed_list:
        mssv = st["mssv"]
        pwd = st.get("password", "")
        name = st.get("full_name") or mssv
        cookie = st.get("cookie_data", "")

        is_valid, msg, sess = check_student_cookie(cookie, mssv=mssv, password=pwd)
        status_str = "valid" if is_valid else "expired"

        database.save_student(
            mssv=mssv,
            password=pwd,
            full_name=name,
            cookie_data=sess or cookie,
            session_status=status_str
        )
        if is_valid:
            succ_count += 1
        else:
            fail_count += 1

    msg = f"Đã import {len(parsed_list)} sinh viên (Hợp lệ: {succ_count}, Cần kiểm tra: {fail_count})"
    database.log_event("STUDENT", msg)
    return {"success": True, "message": msg, "count": len(parsed_list), "valid": succ_count, "expired": fail_count}

@app.post("/api/students/check-all")
def api_students_check_all():
    students = database.get_all_students()
    valid_count = 0
    expired_count = 0

    for st in students:
        is_valid, _, sess = check_student_cookie(st.get("cookie_data"), mssv=st["mssv"], password=st.get("password"))
        new_status = "valid" if is_valid else "expired"
        database.update_student_session(st["mssv"], new_status, sess if is_valid else None)
        if is_valid:
            valid_count += 1
        else:
            expired_count += 1

    msg = f"Đã kiểm tra phiên {len(students)} sinh viên: {valid_count} Hợp lệ, {expired_count} Hết hạn."
    database.log_event("STUDENT", msg)
    return {"success": True, "message": msg, "valid": valid_count, "expired": expired_count}

@app.post("/api/students/relogin-all")
def api_students_relogin_all():
    students = database.get_all_students()
    succ = 0
    fail = 0

    for st in students:
        pwd = st.get("password")
        if not pwd:
            continue
        is_valid, _, sess = check_student_cookie(None, mssv=st["mssv"], password=pwd)
        if is_valid:
            database.update_student_session(st["mssv"], "valid", sess)
            succ += 1
        else:
            database.update_student_session(st["mssv"], "expired", None)
            fail += 1

    msg = f"Đã tự động đăng nhập lại: {succ} thành công, {fail} thất bại."
    database.log_event("STUDENT", msg)
    return {"success": True, "message": msg, "success_count": succ, "fail_count": fail}

@app.post("/api/students/batch-register")
def api_students_batch_register(data: dict):
    act_id = str(data.get("activity_id", "")).strip()
    sem_id = str(data.get("semester_id", "20241")).strip()

    if not act_id:
        return {"success": False, "message": "Vui lòng chọn hoặc nhập Mã Hoạt Động (Activity ID)!"}

    if BATCH_PROGRESS["is_running"]:
        return {"success": False, "message": "Đang có một tiến trình đăng ký hàng loạt chạy nền!"}

    def _worker():
        execute_batch_registration(act_id, sem_id, config_path=CONFIG_FILE)

    th = threading.Thread(target=_worker, daemon=True)
    th.start()

    return {"success": True, "message": f"Đã kích hoạt tiến trình đăng ký hàng loạt cho Hoạt động #{act_id}!"}

@app.get("/api/students/batch-status")
def api_students_batch_status():
    return {"status": "ok", "progress": BATCH_PROGRESS}

@app.get("/api/delivery-history")
def api_delivery_history(limit: int = 100):
    rows = database.get_delivery_history(limit=limit)
    return {"status": "ok", "history": rows}

@app.get("/api/logs")
def api_logs(limit: int = 80):
    rows = database.get_recent_logs(limit=limit)
    return {"status": "ok", "logs": rows}

@app.get("/api/all-logs")
def api_all_logs(limit: int = 150):
    parent_dir = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    all_logs = []
    
    # 1. HUIT
    try:
        h_db = os.path.join(parent_dir, "huit_bot.db")
        if os.path.exists(h_db):
            hl = database.get_recent_logs(limit=limit, db_file=h_db)
            for l in hl:
                ld = dict(l)
                ld["bot"] = "HUIT"
                ld["bot_badge"] = "Bot 1 (HUIT)"
                all_logs.append(ld)
    except Exception:
        pass

    # 2. VAA
    try:
        v_db = os.path.join(parent_dir, "bot2.db")
        if os.path.exists(v_db):
            vl = database.get_recent_logs(limit=limit, db_file=v_db)
            for l in vl:
                ld = dict(l)
                ld["bot"] = "VAA"
                ld["bot_badge"] = "Bot 2 (VAA)"
                all_logs.append(ld)
    except Exception:
        pass

    # 3. IUH
    try:
        i_db = os.path.join(parent_dir, "iuh_bot.db")
        if os.path.exists(i_db):
            il = database.get_recent_logs(limit=limit, db_file=i_db)
            for l in il:
                ld = dict(l)
                ld["bot"] = "IUH"
                ld["bot_badge"] = "Bot 3 (IUH)"
                all_logs.append(ld)
    except Exception:
        pass

    # 4. UFM
    try:
        ul = database.get_recent_logs(limit=limit)
        for l in ul:
            ld = dict(l)
            ld["bot"] = "UFM"
            ld["bot_badge"] = "Bot 4 (UFM)"
            all_logs.append(ld)
    except Exception:
        pass

    all_logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"status": "ok", "logs": all_logs[:limit]}

@app.get("/api/config")
def api_get_config():
    return {"status": "ok", "config": get_config()}

@app.post("/api/config/save")
def api_save_config(cfg: dict):
    save_config(cfg)
    return {"success": True, "message": "Đã lưu cấu hình thành công!"}

@app.post("/api/portal/login")
def api_portal_login():
    cfg = get_config()
    p = cfg.get("ufm_portal", {})
    username = p.get("username", "")
    password = p.get("password", "")

    if not username or not password:
        return {"success": False, "message": "Chưa cấu hình tài khoản hoặc mật khẩu trong config.json!"}

    scraper = UFMPortalScraper(config_path=CONFIG_FILE)
    ok, msg, sess = scraper.login(username, password)
    if ok:
        database.set_bot_status("portal_cookie_status", "valid")
        database.log_event("PORTAL", f"Đăng nhập cổng UFM thành công (Tài khoản: {username}). Session đã cập nhật.")
        return {"success": True, "message": f"Đăng nhập cổng UFM thành công: {msg}"}
    else:
        database.set_bot_status("portal_cookie_status", "expired")
        database.log_event("WARN", f"Đăng nhập cổng UFM thất bại: {msg}")
        return {"success": False, "message": f"Đăng nhập thất bại: {msg}"}

@app.post("/api/zalo/send-test-target")
async def api_ufm_send_test_target(req: Request):
    """Gửi tin nhắn test tới 1 nhóm hoặc người nhận Zalo của UFM."""
    try:
        data = await req.json()
    except Exception:
        data = {}
    target_id = str(data.get("target_id", "")).strip() or "7456361874031804652"
    target_type = data.get("target_type", "GROUP")
    target_name = data.get("target_name", target_id)
    custom_msg = data.get("custom_message", None)
    
    try:
        from zalo_sender import ZaloDispatcher
        db_file = getattr(database, "UFM_DB_FILE", getattr(database, "DB_FILE", None))
        dispatcher = ZaloDispatcher(CONFIG_FILE, db_file=db_file)
        dispatcher.bot_name = "Bot 4 - UFM (Yuki 4 ĐRL)"
        
        ok, msg = dispatcher.send_test_message_to_target(
            target_id=target_id,
            target_type=target_type,
            custom_text=custom_msg,
            db_file=db_file
        )
        if ok:
            return {"status": "ok", "success": True, "message": msg or f"Đã gửi tin nhắn test tới [{target_name}] thành công!"}
        else:
            return {"status": "error", "success": False, "message": msg or f"Không thể gửi tin nhắn tới [{target_name}]. Hãy kiểm tra Cookie Zalo!"}
    except Exception as e:
        return {"status": "error", "success": False, "message": f"Lỗi gửi tin: {e}"}

@app.post("/api/zalo/send-test-all-groups")
async def api_ufm_send_test_all_groups(req: Request):
    """Gửi tin nhắn test tới tất cả các nhóm Zalo đang BẬT của UFM."""
    try:
        from zalo_sender import ZaloDispatcher
        db_file = getattr(database, "UFM_DB_FILE", getattr(database, "DB_FILE", None))
        dispatcher = ZaloDispatcher(CONFIG_FILE, db_file=db_file)
        dispatcher.bot_name = "Bot 4 - UFM (Yuki 4 ĐRL)"
        now_vn = database.get_vn_now_str("%H:%M:%S %d/%m/%Y")
        
        cfg = get_config()
        tgs = [g for g in cfg.get("zalo", {}).get("target_groups", []) if g.get("enabled", True)]
        if not tgs:
            return {"status": "error", "success": False, "message": "Chưa có nhóm Zalo nào được BẬT trong cấu hình!"}

        succ, fail = 0, 0
        for g in tgs:
            ok, _ = dispatcher.send_test_message_to_target(
                target_id=str(g["id"]),
                target_type=g.get("type", "GROUP"),
                custom_text=f"🧪 [TEST TOÀN BỘ NHÓM ZALO - UFM]\n━━━━━━━━━━━━━━━━━━━━\nBot 4 (UFM) kiểm tra kết nối tới các nhóm đang BẬT.\n⏰ Thời gian: {now_vn}",
                db_file=db_file
            )
            if ok: succ += 1
            else: fail += 1
            time.sleep(1)

        return {"status": "ok", "success": succ > 0, "message": f"Đã gửi tin nhắn test tới {succ}/{len(tgs)} nhóm đang bật (Thất bại: {fail})!"}
    except Exception as e:
        return {"status": "error", "success": False, "message": f"Lỗi gửi tin tới tất cả nhóm: {e}"}

@app.get("/api/zalo/quad-target-groups")
async def api_ufm_quad_target_groups():
    """Trả về danh sách nhóm mục tiêu của cả 4 bot để phục vụ modal test quad bot."""
    parent_dir = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    bots_cfg = [
        {"bot_id": "bot1", "name": "Bot 1 - HUIT (Yuki 1)", "cfg_path": os.path.join(parent_dir, "config.json")},
        {"bot_id": "bot2", "name": "Bot 2 - VAA (Yuki 2)", "cfg_path": os.path.join(parent_dir, "vaabot.json")},
        {"bot_id": "bot3", "name": "Bot 3 - IUH (Yuki 3 ĐRL)", "cfg_path": os.path.join(parent_dir, "config_iuh.json")},
        {"bot_id": "bot4", "name": "Bot 4 - UFM (Yuki 4 ĐRL)", "cfg_path": CONFIG_FILE},
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
            except Exception:
                pass
        result.append({
            "bot_id": b["bot_id"],
            "bot_name": b["name"],
            "config_path": cfg_p,
            "groups": groups
        })
    return {"status": "ok", "bots": result}

@app.post("/api/zalo/send-demo-alert")
def api_zalo_send_demo_alert():
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
        return {"success": False, "message": "Định dạng Cookie không đúng!"}
    
    if not cookie_dict.get("zpw_sek") and not cookie_dict.get("zpsid"):
        return {"success": False, "message": "Thiếu token 'zpw_sek' hoặc 'zpsid' trong Cookie!"}
    
    cfg = get_config()
    zalo_cfg = cfg.get("zalo", {})
    imei = zalo_cfg.get("imei") or "285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7"
    
    try:
        from zalo_sender import UFMBotZaloClient
        test_client = UFMBotZaloClient(phone="", password="", imei=imei, cookies=cookie_dict)
        uid = test_client.uid() if callable(test_client.uid) else test_client.uid
        if not uid:
            return {"success": False, "message": "Không lấy được UID từ Cookie Zalo!"}
    except Exception as e:
        return {"success": False, "message": f"Xác thực thất bại với Zalo Server: {e}"}
    
    zalo_cfg["cookies"] = cookie_dict
    zalo_cfg["imei"] = imei
    cfg["zalo"] = zalo_cfg
    save_config(cfg)
    
    db_file = getattr(database, "UFM_DB_FILE", getattr(database, "DB_FILE", None))
    database.set_bot_status("zalo_cookie_status", "valid", db_file=db_file)
    database.set_bot_status("zalo_cookie_error", "", db_file=db_file)
    database.set_bot_status("zalo_account_uid", str(uid), db_file=db_file)
    database.set_bot_status("zalo_last_connected", database.get_vn_now_str(), db_file=db_file)
    database.log_event("ZALO", f"Cập nhật Cookie Zalo Bot UFM thành công! Tài khoản UID: {uid}", db_file=db_file)
    
    return {"success": True, "message": f"Cập nhật Cookie Zalo thành công! UID: {uid}", "uid": str(uid)}

@app.post("/api/zalo/check-status")
def api_zalo_check_status():
    cfg = get_config()
    zalo_cfg = cfg.get("zalo", {})
    cookies = zalo_cfg.get("cookies")
    imei = zalo_cfg.get("imei")
    
    if not cookies or not imei:
        return {"success": False, "status": "missing", "message": "Chưa có cookies hoặc IMEI trong config!"}
    
    try:
        from zalo_sender import UFMBotZaloClient
        test_client = UFMBotZaloClient(phone="", password="", imei=imei, cookies=cookies)
        uid = test_client.uid() if callable(test_client.uid) else test_client.uid
        if uid:
            database.set_bot_status("zalo_cookie_status", "valid")
            database.set_bot_status("zalo_account_uid", str(uid))
            return {"success": True, "status": "valid", "uid": str(uid), "message": f"Cookie Zalo đang hoạt động tốt! UID: {uid}"}
    except Exception as e:
        database.set_bot_status("zalo_cookie_status", "expired")
        database.set_bot_status("zalo_cookie_error", str(e))
        return {"success": False, "status": "expired", "message": f"Cookie Zalo đã hết hạn hoặc bị hủy: {e}"}

@app.get("/api/zalo/fetch-groups")
def api_zalo_fetch_groups():
    cfg = get_config()
    zalo_cfg = cfg.get("zalo", {})
    cookies = zalo_cfg.get("cookies")
    imei = zalo_cfg.get("imei")
    
    if not cookies or not imei:
        return {"success": False, "groups": [], "message": "Chưa có Cookie Zalo hợp lệ!"}
    
    try:
        from zalo_sender import UFMBotZaloClient
        client = UFMBotZaloClient(phone="", password="", imei=imei, cookies=cookies)
        all_chats = client.fetchAllChat(limit=50)
        groups = []
        if all_chats and hasattr(all_chats, "gridInfoMap"):
            for gid, info in all_chats.gridInfoMap.items():
                name = getattr(info, "name", f"Nhóm {gid}")
                groups.append({"id": str(gid), "name": name, "type": "GROUP"})
        return {"success": True, "groups": groups, "count": len(groups)}
    except Exception as e:
        return {"success": False, "groups": [], "message": f"Không thể lấy danh sách nhóm: {e}"}

# ================= MESSENGER ENDPOINTS =================
@app.get("/api/messenger/status")
def api_messenger_status():
    bs = database.get_all_bot_status()
    cfg = get_config()
    return {
        "status": "ok",
        "enabled": cfg.get("messenger", {}).get("enabled", False),
        "cookie_status": bs.get("messenger_cookie_status", "unknown"),
        "cookie_error": bs.get("messenger_cookie_error", ""),
        "account_uid": bs.get("messenger_account_uid", ""),
        "last_connected": bs.get("messenger_last_connected", "")
    }

@app.post("/api/messenger/toggle")
def api_messenger_toggle(data: dict):
    enabled = bool(data.get("enabled", True))
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {}
    cfg["messenger"]["enabled"] = enabled
    save_config(cfg)
    msg = f"Kênh Facebook Messenger Bot 4 đã được {'BẬT' if enabled else 'TẮT'}!"
    database.log_event("MESSENGER", msg)
    return {"status": "ok", "enabled": enabled, "message": msg}

@app.post("/api/messenger/update-cookies")
def api_messenger_update_cookies(data: dict):
    raw_cookies = data.get("cookies")
    if not raw_cookies:
        return {"status": "error", "message": "Vui lòng nhập chuỗi JSON Cookie Messenger!"}
    try:
        from messenger_sender import MessengerDispatcher
        dispatcher = MessengerDispatcher(CONFIG_FILE)
        ok, msg = dispatcher.update_cookies(raw_cookies)
        return {"status": "ok" if ok else "error", "message": msg}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi cập nhật: {e}"}

@app.post("/api/messenger/check-connection")
def api_messenger_check_connection():
    try:
        from messenger_sender import MessengerDispatcher
        dispatcher = MessengerDispatcher(CONFIG_FILE)
        ok, msg = dispatcher.test_connection()
        return {"status": "ok" if ok else "error", "message": msg}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi kiểm tra kết nối: {e}"}

@app.get("/api/messenger/fetch-groups")
def api_messenger_fetch_groups():
    try:
        from messenger_sender import MessengerDispatcher
        dispatcher = MessengerDispatcher(CONFIG_FILE)
        groups = dispatcher.fetch_groups(limit=25)
        return {"status": "ok", "groups": groups}
    except Exception as e:
        return {"status": "error", "groups": [], "message": f"Lỗi: {e}"}

@app.post("/api/messenger/save-groups")
def api_messenger_save_groups(data: dict):
    groups = data.get("groups", [])
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {}
    cfg["messenger"]["target_groups"] = groups
    save_config(cfg)
    msg = f"Đã lưu danh sách {len(groups)} nhóm nhận tin Facebook Messenger!"
    database.log_event("MESSENGER", msg)
    return {"status": "ok", "message": msg}

@app.post("/api/messenger/add-group")
def api_messenger_add_group(data: dict):
    gid = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip() or f"Nhóm {gid}"
    if not gid:
        return {"status": "error", "message": "Thiếu Thread ID nhóm Messenger!"}
    cfg = get_config()
    if "messenger" not in cfg:
        cfg["messenger"] = {}
    tgs = cfg["messenger"].get("target_groups", [])
    if any(str(g.get("id")) == gid for g in tgs):
        return {"status": "error", "message": f"Nhóm {gid} đã tồn tại trong danh sách!"}
    tgs.append({"id": gid, "name": name, "enabled": True})
    cfg["messenger"]["target_groups"] = tgs
    save_config(cfg)
    return {"status": "ok", "message": f"Đã thêm nhóm '{name}' ({gid}) vào Messenger Bot 4!"}

@app.post("/api/messenger/remove-group")
def api_messenger_remove_group(data: dict):
    gid = str(data.get("id", "")).strip()
    cfg = get_config()
    tgs = cfg.get("messenger", {}).get("target_groups", [])
    cfg["messenger"]["target_groups"] = [g for g in tgs if str(g.get("id")) != gid]
    save_config(cfg)
    return {"status": "ok", "message": f"Đã xóa nhóm {gid} khỏi Messenger Bot 4!"}

@app.post("/api/messenger/test-send")
def api_messenger_test_send(data: dict):
    target_id = str(data.get("target_id", "")).strip()
    if not target_id:
        return {"status": "error", "message": "Thiếu target_id!"}
    try:
        from messenger_sender import MessengerDispatcher
        dispatcher = MessengerDispatcher(CONFIG_FILE)
        now_vn = database.get_vn_now_str("%H:%M:%S %d/%m/%Y")
        msg = f"🧪 [TEST MESSENGER - BOT 4 UFM]\n━━━━━━━━━━━━━━━━━━━━\nKiểm tra kết nối gửi tin tức thì tới Messenger.\n⏰ Thời gian: {now_vn}\n✅ Hoạt động tốt!"
        ok, res_msg = dispatcher.send_message(msg, thread_id=target_id)
        return {"status": "ok" if ok else "error", "message": res_msg}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi gửi tin: {e}"}

# ================= PUBLIC SUBMIT COOKIE PAGE =================
@app.get("/submit-cookie", response_class=HTMLResponse)
@app.get("/dang-ky-sv", response_class=HTMLResponse)
def submit_cookie_page():
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nạp Tài Khoản UFM - Tự Động Săn Hoạt Động & ĐRL (Yuki 4)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .font-mono { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col items-center justify-center p-4">
  <div class="max-w-lg w-full bg-white rounded-3xl border border-slate-200/80 shadow-xl overflow-hidden p-8 space-y-6">
    <div class="text-center space-y-2">
      <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-700 flex items-center justify-center text-white text-2xl mx-auto shadow-md shadow-emerald-500/20">
        <i class="fa-solid fa-graduation-cap"></i>
      </div>
      <h2 class="text-xl font-extrabold text-slate-900">Nạp Tài Khoản UFM Săn Hoạt Động</h2>
      <p class="text-xs text-slate-500">Hệ thống Yuki 4 tự động phát hiện sự kiện mới & săn slot điểm rèn luyện 24/7</p>
    </div>

    <div class="space-y-4">
      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Mã Số Sinh Viên (MSSV) <span class="text-rose-500">*</span></label>
        <input type="text" id="mssv" placeholder="Ví dụ: 2621008460" class="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-emerald-500 font-mono">
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Mật Khẩu Cổng UFM <span class="text-emerald-600">(Khuyến nghị để tự đăng nhập 24/7)</span></label>
        <input type="password" id="password" placeholder="Mật khẩu đăng nhập hoatdong.ufm.edu.vn" class="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-emerald-500">
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Họ Và Tên (Tùy chọn)</label>
        <input type="text" id="fullname" placeholder="Ví dụ: Đàm Anh Duy" class="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-emerald-500">
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Hoặc Dán Cookie Phiên .AspNetCore.Cookies (Nếu không muốn nhập pass)</label>
        <textarea id="cookie" rows="2" placeholder="Dán cookie nếu có..." class="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-xs focus:outline-emerald-500 font-mono"></textarea>
      </div>

      <button id="submitBtn" onclick="submitStudentCookie()" class="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm shadow-md shadow-emerald-600/30 transition flex items-center justify-center gap-2">
        <i class="fa-solid fa-cloud-arrow-up"></i>
        <span>Xác Thực & Lưu Tài Khoản</span>
      </button>
    </div>

    <div class="p-4 bg-emerald-50 border border-emerald-100 rounded-2xl text-xs text-emerald-900 space-y-1">
      <p class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved text-emerald-600"></i> Cam kết bảo mật 100%:</p>
      <p class="text-[11px] text-emerald-700">Thông tin sinh viên chỉ được lưu nội bộ trên máy chủ bot và sử dụng duy nhất cho mục đích săn slot hoạt động cộng đồng & điểm rèn luyện.</p>
    </div>
  </div>

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
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Đang xác thực với Cổng UFM...';

      try {
        const prefix = window.location.pathname.startsWith('/ufm') ? '/ufm' : '';
        const res = await fetch(prefix + '/api/student/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv, password: password, full_name: fullname, cookie_data: cookie })
        });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Thành công!', data.message, 'success');
          document.getElementById('password').value = '';
          document.getElementById('cookie').value = '';
        } else {
          Swal.fire('Chưa hoàn tất', data.message, 'warning');
        }
      } catch (e) {
        Swal.fire('Lỗi', 'Không thể kết nối máy chủ: ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up mr-2"></i> Xác Thực & Lưu Tài Khoản';
      }
    }
  </script>
</body>
</html>"""

# ================= MAIN ADMIN DASHBOARD (GET /) =================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.join(SCRIPT_DIR, "templates", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8004, reload=True)
'''

with open(output_path, "w", encoding="utf-8") as f:
    f.write(python_code)

print("Successfully wrote updated vaa/ufm/web_app.py!")
