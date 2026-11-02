# -*- coding: utf-8 -*-
"""
HUIT Auto Form & Zalo Bot - Web Management Dashboard Backend (FastAPI)
Quản trị toàn diện:
- Thống kê thời gian thực: số lần quét, bài đã gửi, form đã nộp, phân bổ nhóm Zalo
- Bật/tắt (Toggle) từng nhóm Zalo, từng Fanpage mục tiêu
- Quản trị Profile sinh viên & Gemini AI API Key
- Điều khiển tiến trình Bot (Start / Stop / Restart)
- Stream Live Console Logs qua WebSocket
- Thư viện ảnh chụp bằng chứng nộp form
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import asyncio
import threading
import urllib.request
from typing import Optional, List
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (GMT+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_now():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
DB_FILE = os.path.join(SCRIPT_DIR, "seen_posts.db")
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
SCREENSHOTS_DIR = os.path.join(SCRIPT_DIR, "screenshots")
LOG_FILE = os.path.join(SCRIPT_DIR, "bot.log")
HISTORY_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_history.jsonl")

CONFIG_VAA_FILE = os.path.join(SCRIPT_DIR, "config_vaa.json")
DB_VAA_FILE = os.path.join(SCRIPT_DIR, "seen_posts_vaa.db")
LOG_VAA_FILE = os.path.join(SCRIPT_DIR, "vaabot.log")
HISTORY_VAA_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_history_vaa.jsonl")
SEEN_POSTS_VAA_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_seen_posts_vaa.jsonl")
SETTINGS_VAA_FILE = os.path.join(SCRIPT_DIR, "persistent_settings_vaa.json")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# ==================== LƯU TRỮ VĨNH VIỄN RIÊNG CHO VAA ====================
def append_to_vaa_ledger(record: dict):
    try:
        with open(HISTORY_VAA_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Lỗi ghi VAA persistent ledger:", e)

def restore_vaa_history_from_ledger():
    if not os.path.exists(HISTORY_VAA_LEDGER_FILE):
        return
    try:
        conn = get_vaa_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM notification_history")
        if cur.fetchone()[0] == 0:
            with open(HISTORY_VAA_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        rec = json.loads(line)
                        cur.execute("""
                            INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rec.get("title", ""), rec.get("category", "GROUP"),
                            rec.get("recipient_name", "demo"), str(rec.get("recipient_id", "475259879796859360")),
                            rec.get("content", ""), rec.get("status", "SUCCESS"), rec.get("created_at", get_vn_now())
                        ))
                    except Exception: pass
            conn.commit()
        conn.close()
    except Exception as e:
        print("Lỗi phục hồi VAA history ledger:", e)

def restore_vaa_seen_posts_from_ledger():
    if not os.path.exists(SEEN_POSTS_VAA_LEDGER_FILE):
        return
    try:
        conn = get_vaa_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM seen_posts")
        if cur.fetchone()[0] == 0:
            with open(SEEN_POSTS_VAA_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        rec = json.loads(line)
                        h = rec.get("post_hash")
                        if h:
                            cur.execute("""
                                INSERT INTO seen_posts (post_hash, page_name, matched_keywords, has_form, form_url, sent_private, sent_group, registered_status, created_at)
                                VALUES (?, ?, ?, 0, '', 0, 1, 'LEDGER_RESTORED', ?)
                                ON CONFLICT(post_hash) DO NOTHING
                            """, (h, rec.get("page_name", ""), rec.get("matched_keywords", ""), rec.get("created_at", get_vn_now())))
                    except Exception: pass
            conn.commit()
        conn.close()
    except Exception as e:
        print("Lỗi phục hồi VAA seen ledger:", e)


# ==================== LƯU TRỮ LỊCH SỬ VĨNH VIỄN (PERSISTENT LEDGER) ====================
def append_to_persistent_ledger(record: dict):
    """Ghi sổ cái vĩnh viễn (Append-Only JSONL) để không bao giờ bị mất lịch sử qua các tuần"""
    try:
        with open(HISTORY_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Lỗi ghi persistent ledger:", e)

def restore_history_from_ledger():
    """Khôi phục dữ liệu từ sổ cái persistent_history.jsonl vào SQLite nếu bảng rỗng sau khi Render restart/redeploy"""
    if not os.path.exists(HISTORY_LEDGER_FILE):
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM notification_history")
        count = cur.fetchone()[0]
        if count == 0:
            print("📦 [LƯU TRỮ VĨNH VIỄN] Đang phục hồi toàn bộ lịch sử từ sổ cái persistent_history.jsonl...")
            restored = 0
            with open(HISTORY_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        cur.execute("""
                            INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rec.get("title", ""),
                            rec.get("category", "SYSTEM"),
                            rec.get("recipient_name", ""),
                            str(rec.get("recipient_id", "")),
                            rec.get("content", ""),
                            rec.get("status", "SUCCESS"),
                            rec.get("created_at", get_vn_now())
                        ))
                        restored += 1
                    except Exception:
                        pass
            conn.commit()
            print(f"✅ [LƯU TRỮ VĨNH VIỄN] Đã phục hồi thành công {restored} bản ghi lịch sử thông báo!")
        conn.close()
    except Exception as e:
        print("Lỗi phục hồi từ ledger:", e)


SETTINGS_FILE = os.path.join(SCRIPT_DIR, "persistent_settings.json")

def apply_settings_overrides(cfg: dict) -> dict:
    """Áp dụng các trạng thái bật/tắt nhóm Zalo đã lưu vào config để không bao giờ bị reset khi redeploy"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            grp_overrides = settings.get("zalo_group_overrides", {})
            for grp in cfg.get("zalo", {}).get("target_groups", []):
                gid = str(grp.get("id"))
                if gid in grp_overrides:
                    grp["enabled"] = bool(grp_overrides[gid])
            usr_overrides = settings.get("zalo_user_overrides", {})
            for usr in cfg.get("zalo", {}).get("target_users", []):
                uid = str(usr.get("id"))
                if uid in usr_overrides:
                    usr["enabled"] = bool(usr_overrides[uid])
        except Exception as e:
            print("Lỗi apply settings overrides:", e)
    return cfg

def save_recipient_override(rec_type: str, rec_id: str, enabled: bool):
    """Ghi đè trạng thái bật/tắt nhóm/cá nhân vào file persistent_settings.json để lưu vĩnh viễn"""
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    key = "zalo_group_overrides" if rec_type == "GROUP" else "zalo_user_overrides"
    if key not in settings:
        settings[key] = {}
    settings[key][str(rec_id)] = bool(enabled)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Lỗi lưu recipient override:", e)

FORM_REG_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_registrations.jsonl")

def append_to_form_ledger(record: dict):
    """Ghi sổ cái nộp form vĩnh viễn (Append-Only JSONL)"""
    try:
        with open(FORM_REG_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Lỗi ghi form ledger:", e)

def restore_registrations_from_ledger():
    """Khôi phục dữ liệu từ sổ cái persistent_registrations.jsonl vào bảng form_registrations"""
    if not os.path.exists(FORM_REG_LEDGER_FILE):
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM form_registrations")
        count = cur.fetchone()[0]
        if count == 0:
            print("📦 [LƯU TRỮ VĨNH VIỄN] Đang phục hồi toàn bộ lịch sử nộp form từ persistent_registrations.jsonl...")
            restored = 0
            with open(FORM_REG_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        cur.execute("""
                            INSERT INTO form_registrations 
                            (post_hash, page_name, form_url, student_id, student_name, status, message, screenshot_path, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rec.get("post_hash", ""),
                            rec.get("page_name", ""),
                            rec.get("form_url", ""),
                            rec.get("student_id", ""),
                            rec.get("student_name", ""),
                            rec.get("status", "SUCCESS"),
                            rec.get("message", ""),
                            rec.get("screenshot_path", ""),
                            rec.get("created_at", get_vn_now())
                        ))
                        restored += 1
                    except Exception:
                        pass
            conn.commit()
            print(f"✅ [LƯU TRỮ VĨNH VIỄN] Đã phục hồi thành công {restored} lượt nộp form!")
        conn.close()
    except Exception as e:
        print("Lỗi phục hồi form ledger:", e)

SEEN_POSTS_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_seen_posts.jsonl")

def restore_seen_posts_from_ledger():
    """Khôi phục danh sách bài viết đã quét từ persistent_seen_posts.jsonl để Render không bao giờ quên bài cũ sau khi redeploy"""
    if not os.path.exists(SEEN_POSTS_LEDGER_FILE):
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM seen_posts")
        count = cur.fetchone()[0]
        if count == 0:
            restored = 0
            with open(SEEN_POSTS_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        h = rec.get("post_hash")
                        if h:
                            cur.execute("""
                                INSERT INTO seen_posts (post_hash, page_name, matched_keywords, has_form, form_url, sent_private, sent_group, registered_status, created_at)
                                VALUES (?, ?, ?, 0, '', 1, 1, 'LEDGER_RESTORED', ?)
                                ON CONFLICT(post_hash) DO UPDATE SET sent_group = 1, sent_private = 1
                            """, (h, rec.get("page_name", ""), rec.get("matched_keywords", ""), rec.get("created_at", get_vn_now())))
                            restored += 1
                    except Exception:
                        pass
            conn.commit()
            print(f"📦 [LƯU TRỮ VĨNH VIỄN] Đã phục hồi thành công {restored} bài viết đã gửi từ persistent_seen_posts.jsonl!")
        conn.close()
    except Exception as e:
        print("Lỗi phục hồi seen_posts ledger:", e)

app = FastAPI(title="HUIT Auto Form & Zalo Bot Dashboard", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== BOT PROCESS CONTROLLER & WATCHDOG 24/7 ====================
class BotProcessManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.log_file_handle = None
        self.desired_state = "RUNNING"  # Mặc định duy trì chạy liên tục 24/7
        self._watchdog_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ensure_watchdog()

    def _ensure_watchdog(self):
        if self._watchdog_thread is None or not self._watchdog_thread.is_alive():
            self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self._watchdog_thread.start()

    def _watchdog_loop(self):
        """Giám sát tiến trình bot liên tục: Kiểm tra qua cổng socket 29999 để đảm bảo duy nhất 1 bot chạy"""
        while True:
            time.sleep(10)
            try:
                with self._lock:
                    if self.desired_state == "RUNNING":
                        if not self.is_running():
                            now_vn = get_vn_now()
                            print(f"⚠️ [WATCHDOG] Phát hiện Bot chưa chạy hoặc bị dừng. Tự động khởi chạy...")
                            
                            hist_rec = {
                                "title": "⚠️ BOT TỰ HỒI SINH (WATCHDOG)",
                                "category": "SYSTEM",
                                "recipient_name": "Hệ Thống (Watchdog 24/7)",
                                "recipient_id": "RESTART",
                                "content": f"Bot được tự động khởi động lại lúc {now_vn} bởi Watchdog.",
                                "status": "RUNNING",
                                "created_at": now_vn
                            }
                            try:
                                conn = get_db_connection()
                                conn.execute("""
                                    INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"],
                                    hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]
                                ))
                                conn.commit()
                                conn.close()
                                append_to_persistent_ledger(hist_rec)
                            except Exception as e:
                                print("Lỗi ghi log watchdog:", e)

                            self._spawn_process(now_vn=now_vn)
            except Exception as w_err:
                print("Lỗi vòng lặp watchdog:", w_err)

    def _spawn_process(self, now_vn=None):
        if now_vn is None:
            now_vn = get_vn_now()
        try:
            self.log_file_handle = open(LOG_FILE, "a", encoding="utf-8", errors="replace")
            self.log_file_handle.write(f"\n--- [HỆ THỐNG] KHỞI ĐỘNG BOT LÚC {now_vn} ---\n")
            self.log_file_handle.flush()
        except Exception:
            pass

        cmd = [sys.executable, "-u", os.path.join(SCRIPT_DIR, "bot_auto_register.py")]
        self.process = subprocess.Popen(
            cmd,
            stdout=self.log_file_handle,
            stderr=subprocess.STDOUT,
            cwd=SCRIPT_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        self.start_time = time.time()
        print(f"🚀 [HỆ THỐNG] Tiến trình Bot cào bài & đăng ký form đã khởi chạy (PID: {self.process.pid})")

    def is_running(self) -> bool:
        """Kiểm tra chắc chắn qua cổng Socket 29999 để chống hoàn toàn tình trạng chạy trùng lặp"""
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', 29999))
            s.close()
            # Cổng rảnh -> Không có tiến trình Bot nào đang chạy
            return False
        except OSError:
            # Cổng đang bị chiếm -> Đã có Bot đang chạy 100%
            return True

    def start(self) -> dict:
        with self._lock:
            self.desired_state = "RUNNING"
            self._ensure_watchdog()
            if self.is_running():
                return {"status": "already_running", "message": "Bot đang chạy rồi!"}
            
            now_vn = get_vn_now()
            self._spawn_process(now_vn=now_vn)

            hist_rec = {
                "title": "🚀 KHỞI ĐỘNG BOT",
                "category": "SYSTEM",
                "recipient_name": "Hệ Thống (Cloud/Local)",
                "recipient_id": f"PID: {self.process.pid}",
                "content": f"Bot bắt đầu được bật lúc {now_vn}. Tự động cào 14 Fanpage/Group HUIT và sẵn sàng điền form theo hồ sơ sinh viên.",
                "status": "RUNNING",
                "created_at": now_vn
            }
            try:
                conn = get_db_connection()
                conn.execute("""
                    INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"],
                    hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]
                ))
                conn.commit()
                conn.close()
                append_to_persistent_ledger(hist_rec)
            except Exception as err:
                print("Lỗi lưu lịch sử bật bot:", err)

            return {"status": "started", "pid": self.process.pid}

    def stop(self) -> dict:
        with self._lock:
            self.desired_state = "STOPPED"
            if not self.is_running():
                return {"status": "already_stopped", "message": "Bot hiện không chạy."}

            now_vn = get_vn_now()
            uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
            uptime_human = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s" if uptime_sec > 0 else "Vừa khởi động"

            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=4)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
            if self.log_file_handle:
                try:
                    self.log_file_handle.write(f"--- [HỆ THỐNG] BOT ĐÃ DỪNG LÚC {now_vn} ---\n")
                    self.log_file_handle.close()
                except Exception:
                    pass
                self.log_file_handle = None

            # Ghi nhận sự kiện Dừng Bot vào Lịch Sử Hoạt Động & Ledger vĩnh viễn
            hist_rec = {
                "title": "⏹️ DỪNG BOT",
                "category": "SYSTEM",
                "recipient_name": "Hệ Thống (Cloud/Local)",
                "recipient_id": "SYSTEM",
                "content": f"Bot đã dừng hoạt động lúc {now_vn}. Thời gian phiên làm việc này: {uptime_human}. Dữ liệu và trạng thái đã được bảo toàn an toàn vĩnh viễn.",
                "status": "STOPPED",
                "created_at": now_vn
            }
            try:
                conn = get_db_connection()
                conn.execute("""
                    INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"],
                    hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]
                ))
                conn.commit()
                conn.close()
                append_to_persistent_ledger(hist_rec)
            except Exception as err:
                print("Lỗi lưu lịch sử dừng bot:", err)

            return {"status": "stopped"}
    def restart(self) -> dict:
        self.stop()
        time.sleep(1)
        return self.start()

    def get_info(self) -> dict:
        try:
            running = self.is_running()
            uptime_sec = int(time.time() - self.start_time) if (running and self.start_time) else 0
            pid = self.process.pid if (running and self.process) else None
            if running:
                uptime_human = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s" if uptime_sec > 0 else "Đang chạy 24/7"
            else:
                uptime_human = "Đang dừng"
            return {
                "running": running,
                "pid": pid,
                "uptime_seconds": uptime_sec,
                "uptime_human": uptime_human
            }
        except Exception:
            return {
                "running": False,
                "pid": None,
                "uptime_seconds": 0,
                "uptime_human": "Đang dừng"
            }

bot_mgr = BotProcessManager()

# ==================== CÁC API ENDPOINTS ====================

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_hash TEXT PRIMARY KEY,
                page_name TEXT,
                matched_keywords TEXT,
                has_form INTEGER DEFAULT 0,
                form_url TEXT,
                sent_private INTEGER DEFAULT 0,
                sent_group INTEGER DEFAULT 0,
                registered_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS form_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_hash TEXT,
                page_name TEXT,
                form_url TEXT,
                student_id TEXT,
                student_name TEXT,
                status TEXT,
                message TEXT,
                screenshot_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                category TEXT,
                recipient_name TEXT,
                recipient_id TEXT,
                content TEXT,
                status TEXT DEFAULT 'SUCCESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn

def get_vaa_db_connection():
    conn = sqlite3.connect(DB_VAA_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_hash TEXT PRIMARY KEY,
                page_name TEXT,
                matched_keywords TEXT,
                has_form INTEGER DEFAULT 0,
                form_url TEXT,
                sent_private INTEGER DEFAULT 0,
                sent_group INTEGER DEFAULT 0,
                registered_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                category TEXT,
                recipient_name TEXT,
                recipient_id TEXT,
                content TEXT,
                status TEXT DEFAULT 'SUCCESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn

# ==================== VAA BOT PROCESS CONTROLLER ====================
class VaaBotProcessManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.desired_state = "RUNNING"
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(('127.0.0.1', 29998))
                s.close()
                return False
            except OSError:
                return True
        except Exception:
            return self.process is not None and self.process.poll() is None

    def start(self) -> dict:
        with self._lock:
            self.desired_state = "RUNNING"
            if self.is_running():
                return {"status": "already_running", "message": "Bot VAA đang hoạt động!"}
            now_vn = get_vn_now()
            cmd = [sys.executable, "-u", os.path.join(SCRIPT_DIR, "vaabot.py")]
            try:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=SCRIPT_DIR,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )
                self.start_time = time.time()
                hist_rec = {
                    "title": "🚀 KHỞI ĐỘNG BOT VAA",
                    "category": "SYSTEM",
                    "recipient_name": "demo",
                    "recipient_id": "475259879796859360",
                    "content": f"Bot VAA được khởi chạy lúc {now_vn}. Quét 11 Fanpage Học Viện Hàng Không Việt Nam.",
                    "status": "RUNNING",
                    "created_at": now_vn
                }
                try:
                    conn = get_vaa_db_connection()
                    conn.execute("""
                        INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"], hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]))
                    conn.commit()
                    conn.close()
                    append_to_vaa_ledger(hist_rec)
                except Exception:
                    pass
                return {"status": "started", "pid": self.process.pid}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def stop(self) -> dict:
        with self._lock:
            self.desired_state = "STOPPED"
            if not self.is_running():
                return {"status": "already_stopped", "message": "Bot VAA không chạy."}
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
            now_vn = get_vn_now()
            hist_rec = {
                "title": "⏹️ DỪNG BOT VAA",
                "category": "SYSTEM",
                "recipient_name": "demo",
                "recipient_id": "475259879796859360",
                "content": f"Bot VAA đã dừng hoạt động lúc {now_vn}.",
                "status": "STOPPED",
                "created_at": now_vn
            }
            try:
                conn = get_vaa_db_connection()
                conn.execute("""
                    INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"], hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]))
                conn.commit()
                conn.close()
                append_to_vaa_ledger(hist_rec)
            except Exception:
                pass
            return {"status": "stopped"}

    def restart(self) -> dict:
        self.stop()
        time.sleep(1)
        return self.start()

    def get_info(self) -> dict:
        try:
            running = self.is_running()
            uptime_sec = int(time.time() - self.start_time) if (running and self.start_time) else 0
            pid = self.process.pid if (running and self.process) else None
            uptime_human = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s" if running and uptime_sec > 0 else ("Đang chạy 24/7" if running else "Đang dừng")
            return {
                "running": running,
                "pid": pid,
                "uptime_seconds": uptime_sec,
                "uptime_human": uptime_human
            }
        except Exception:
            return {"running": False, "pid": None, "uptime_seconds": 0, "uptime_human": "Đang dừng"}

vaa_bot_mgr = VaaBotProcessManager()


@app.get("/api/status")
def api_status():
    """Lấy trạng thái vận hành của Bot"""
    return bot_mgr.get_info()

@app.post("/api/bot/start")
def api_bot_start():
    return bot_mgr.start()

@app.post("/api/bot/stop")
def api_bot_stop():
    return bot_mgr.stop()

@app.post("/api/bot/restart")
def api_bot_restart():
    return bot_mgr.restart()

@app.get("/api/stats")
def api_stats():
    """Lấy tổng hợp số liệu thống kê thời gian thực"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Tổng số bài đã quét
    cur.execute("SELECT count(*) FROM seen_posts")
    total_posts = cur.fetchone()[0]

    # Tổng số bài đã gửi nhóm Zalo
    cur.execute("SELECT count(*) FROM seen_posts WHERE sent_group = 1")
    total_sent_group = cur.fetchone()[0]

    # Tổng số bài đã gửi riêng Admin
    cur.execute("SELECT count(*) FROM seen_posts WHERE sent_private = 1")
    total_sent_admin = cur.fetchone()[0]

    # Tổng số bài có link Form
    cur.execute("SELECT count(*) FROM seen_posts WHERE has_form = 1")
    total_form_posts = cur.fetchone()[0]

    # Thống kê đăng ký Form
    cur.execute("SELECT count(*) FROM form_registrations WHERE status = 'SUCCESS'")
    form_success = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM form_registrations WHERE status != 'SUCCESS'")
    form_failed = cur.fetchone()[0]

    # Thống kê theo từng trang/fanpage
    cur.execute("""
        SELECT page_name, count(*) as count 
        FROM seen_posts 
        GROUP BY page_name 
        ORDER BY count DESC
    """)
    pages_breakdown = [{"name": r["page_name"], "count": r["count"]} for r in cur.fetchall()]

    conn.close()

    # Đọc cấu hình nhóm Zalo
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    zalo_groups = cfg.get("zalo", {}).get("target_groups", [])
    zalo_users = cfg.get("zalo", {}).get("target_users", [])

    # Kiểm tra Supabase (Cache 60s để API phản hồi siêu tốc không bị nghẽn mạng)
    global _cached_sb_status, _last_sb_check_time
    if '_cached_sb_status' not in globals() or time.time() - _last_sb_check_time > 60:
        try:
            from supabase_sync import check_supabase_connection
            _cached_sb_status = check_supabase_connection()
        except Exception:
            _cached_sb_status = {"connected": False}
        _last_sb_check_time = time.time()
    sb_status = _cached_sb_status

    return {
        "bot": bot_mgr.get_info(),
        "total_posts_scanned": total_posts,
        "total_sent_group": total_sent_group,
        "total_sent_admin": total_sent_admin,
        "total_form_posts": total_form_posts,
        "total_registered_success": form_success,
        "total_registered_failed": form_failed,
        "pages_breakdown": pages_breakdown,
        "zalo_groups": zalo_groups,
        "zalo_users": zalo_users,
        "supabase": sb_status
    }

@app.get("/api/config")
def api_get_config():
    """Đọc file cấu hình hiện tại và áp dụng các trạng thái đã lưu vĩnh viễn"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return apply_settings_overrides(cfg)

@app.post("/api/config")
def api_save_config(new_config: dict):
    """Cập nhật cấu hình config.json"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "Đã lưu cấu hình thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/groups/toggle")
def api_toggle_group(payload: dict):
    """Bật/tắt nhanh một nhóm Zalo nhận tin (Backward compatible)"""
    group_id = str(payload.get("id"))
    enabled = bool(payload.get("enabled"))
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    groups = cfg.get("zalo", {}).get("target_groups", [])
    found = False
    for g in groups:
        if str(g.get("id")) == group_id:
            g["enabled"] = enabled
            found = True
            break
    if found:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": f"Đã {'bật' if enabled else 'tắt'} nhóm Zalo {group_id}!"}
    raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")

@app.post("/api/zalo/recipient/add")
def api_add_recipient(payload: dict):
    """Thêm nhóm hoặc cá nhân Zalo nhận tin"""
    rec_type = str(payload.get("type", "GROUP")).upper()
    rec_id = str(payload.get("id", "")).strip()
    rec_name = str(payload.get("name", "")).strip()
    if not rec_id:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp ID Zalo!")
    if not rec_name:
        rec_name = f"Nhóm {rec_id}" if rec_type == "GROUP" else f"Cá nhân {rec_id}"

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if "zalo" not in cfg:
        cfg["zalo"] = {}

    key = "target_groups" if rec_type == "GROUP" else "target_users"
    if key not in cfg["zalo"]:
        cfg["zalo"][key] = []

    for item in cfg["zalo"][key]:
        if str(item.get("id")) == rec_id:
            item["name"] = rec_name
            item["enabled"] = True
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return {"status": "success", "message": f"Đã cập nhật {'nhóm' if rec_type=='GROUP' else 'cá nhân'} {rec_name}!"}

    cfg["zalo"][key].append({
        "id": rec_id,
        "name": rec_name,
        "enabled": True
    })
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"status": "success", "message": f"Đã thêm {'nhóm' if rec_type=='GROUP' else 'cá nhân'} {rec_name} thành công!"}

@app.post("/api/zalo/recipient/toggle")
def api_toggle_recipient(payload: dict):
    """Bật/tắt nhận tin cho nhóm hoặc cá nhân Zalo"""
    rec_type = str(payload.get("type", "GROUP")).upper()
    rec_id = str(payload.get("id"))
    enabled = bool(payload.get("enabled"))
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    key = "target_groups" if rec_type == "GROUP" else "target_users"
    items = cfg.get("zalo", {}).get(key, [])
    for it in items:
        if str(it.get("id")) == rec_id:
            it["enabled"] = enabled
            if rec_type == "USER" and str(cfg.get("admin_check", {}).get("user_id")) == rec_id:
                if "admin_check" in cfg:
                    cfg["admin_check"]["enabled"] = enabled
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            save_recipient_override(rec_type, rec_id, enabled)
            return {"status": "success", "message": f"Đã {'bật' if enabled else 'tắt'} {it.get('name')}!"}
    raise HTTPException(status_code=404, detail="Không tìm thấy mục cần đổi trạng thái")

@app.delete("/api/zalo/recipient/delete")
def api_delete_recipient(payload: dict):
    """Xóa nhóm hoặc cá nhân Zalo khỏi danh sách"""
    rec_type = str(payload.get("type", "GROUP")).upper()
    rec_id = str(payload.get("id"))
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    key = "target_groups" if rec_type == "GROUP" else "target_users"
    items = cfg.get("zalo", {}).get(key, [])
    new_items = [it for it in items if str(it.get("id")) != rec_id]
    cfg["zalo"][key] = new_items
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"status": "success", "message": "Đã xóa thành công!"}

@app.get("/api/google/sessions")
def api_get_google_sessions():
    """Lấy danh sách các file phiên Google đăng nhập có sẵn trong hệ thống"""
    sessions = []
    try:
        for fname in os.listdir(SCRIPT_DIR):
            if fname.endswith(".json") and ("clone" in fname or "session" in fname or "google" in fname):
                fpath = os.path.join(SCRIPT_DIR, fname)
                try:
                    sz = os.path.getsize(fpath)
                    sessions.append({
                        "filename": fname,
                        "size_bytes": sz,
                        "valid": sz > 100
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return {"sessions": sessions}

@app.get("/api/registrations")
def api_get_registrations(limit: int = 50):
    """Lấy danh sách các lượt nộp Google Form gần nhất kèm thông tin đã điền và ảnh bằng chứng"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, post_hash, page_name, form_url, student_id, student_name, status, message, screenshot_path, created_at
        FROM form_registrations
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Tích hợp danh sách trường đã điền & base64 ảnh từ sổ cái vĩnh viễn
    ledger_fields_map = {}
    ledger_shot_map = {}
    if os.path.exists(FORM_REG_LEDGER_FILE):
        try:
            with open(FORM_REG_LEDGER_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        k = (str(item.get("post_hash")), str(item.get("student_id")))
                        if "filled_fields" in item:
                            ledger_fields_map[k] = item["filled_fields"]
                        if item.get("screenshot_base64"):
                            ledger_shot_map[k] = item["screenshot_base64"]
                    except Exception:
                        pass
        except Exception:
            pass

    for r in rows:
        k = (str(r.get("post_hash")), str(r.get("student_id")))
        if k in ledger_fields_map:
            r["filled_fields"] = ledger_fields_map[k]
        elif r.get("message"):
            r["filled_fields"] = [x.strip() for x in r["message"].split(",") if x.strip()]
        else:
            r["filled_fields"] = []
        if k in ledger_shot_map:
            r["screenshot_base64"] = ledger_shot_map[k]

    return rows


@app.get("/api/posts")
def api_get_posts(limit: int = 50):
    """Lấy danh sách bài viết đã quét và lọc"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT post_hash, page_name, matched_keywords, has_form, form_url, sent_private, sent_group, registered_status, created_at
        FROM seen_posts
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/notifications/history")
def api_get_notifications_history(limit: int = 100, category: Optional[str] = None):
    """Lấy danh sách lịch sử các thông báo và hoạt động của bot kèm số liệu tổng hợp"""
    conn = get_db_connection()
    cur = conn.cursor()
    if category and category.upper() != "ALL":
        cur.execute("""
            SELECT id, title, category, recipient_name, recipient_id, content, status, created_at
            FROM notification_history
            WHERE category = ?
            ORDER BY id DESC
            LIMIT ?
        """, (category.upper(), limit))
    else:
        cur.execute("""
            SELECT id, title, category, recipient_name, recipient_id, content, status, created_at
            FROM notification_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]

    # Thống kê tổng hợp số liệu hoạt động
    cur.execute("SELECT COUNT(*) FROM notification_history WHERE category IN ('GROUP', 'USER', 'ADMIN')")
    count_notifs = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM notification_history WHERE category = 'FORM'")
    count_forms = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM notification_history WHERE category = 'SYSTEM'")
    count_system = cur.fetchone()[0]

    cur.execute("SELECT created_at, content FROM notification_history WHERE title LIKE '%KHỞI ĐỘNG%' ORDER BY id DESC LIMIT 1")
    last_start_row = cur.fetchone()
    last_start_time = last_start_row[0] if last_start_row else None

    cur.execute("SELECT created_at, content FROM notification_history WHERE title LIKE '%DỪNG%' ORDER BY id DESC LIMIT 1")
    last_stop_row = cur.fetchone()
    last_stop_time = last_stop_row[0] if last_stop_row else None

    conn.close()

    bot_info = bot_mgr.get_info()
    return {
        "history": rows,
        "summary": {
            "total_notifications": count_notifs,
            "total_forms": count_forms,
            "total_system": count_system,
            "total_events": len(rows),
            "last_start": last_start_time,
            "last_stop": last_stop_time,
            "is_running": bot_info.get("running", False),
            "uptime_human": bot_info.get("uptime_human", "Đang dừng")
        }
    }

@app.delete("/api/notifications/history/clear")
def api_clear_notifications_history():
    """Khóa vĩnh viễn chức năng xóa lịch sử theo yêu cầu lưu trữ dữ liệu 24/7"""
    return JSONResponse(
        status_code=403,
        content={"status": "forbidden", "message": "Chức năng xóa lịch sử đã bị khóa vĩnh viễn để bảo toàn toàn bộ dữ liệu hoạt động của Bot."}
    )


# ==================== VAA (HỌC VIỆN HÀNG KHÔNG) API ENDPOINTS ====================

@app.get("/api/vaa/status")
def api_vaa_status():
    """Lấy trạng thái vận hành của Bot VAA"""
    return vaa_bot_mgr.get_info()

@app.post("/api/vaa/bot/start")
def api_vaa_bot_start():
    return vaa_bot_mgr.start()

@app.post("/api/vaa/bot/stop")
def api_vaa_bot_stop():
    return vaa_bot_mgr.stop()

@app.post("/api/vaa/bot/restart")
def api_vaa_bot_restart():
    return vaa_bot_mgr.restart()

@app.get("/api/vaa/stats")
def api_vaa_stats():
    """Tổng hợp số liệu thống kê riêng của Bot VAA"""
    conn = get_vaa_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM seen_posts")
    total_posts = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM seen_posts WHERE sent_group = 1")
    total_sent_group = cur.fetchone()[0]

    cur.execute("""
        SELECT page_name, count(*) as count 
        FROM seen_posts 
        GROUP BY page_name 
        ORDER BY count DESC
    """)
    pages_breakdown = [{"name": r["page_name"], "count": r["count"]} for r in cur.fetchall()]
    conn.close()

    cfg = {}
    if os.path.exists(CONFIG_VAA_FILE):
        try:
            with open(CONFIG_VAA_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass

    targets = cfg.get("targets", [])
    zalo_groups = cfg.get("zalo", {}).get("target_groups", [])

    return {
        "bot": vaa_bot_mgr.get_info(),
        "total_posts_scanned": total_posts,
        "total_sent_group": total_sent_group,
        "total_targets": len(targets),
        "pages_breakdown": pages_breakdown,
        "zalo_groups": zalo_groups,
        "auto_tag_all": cfg.get("zalo", {}).get("auto_tag_all", True)
    }

@app.get("/api/vaa/config")
def api_vaa_get_config():
    """Đọc file cấu hình VAA"""
    if not os.path.exists(CONFIG_VAA_FILE):
        return {}
    with open(CONFIG_VAA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/vaa/config")
def api_vaa_save_config(new_config: dict):
    """Cập nhật cấu hình config_vaa.json"""
    try:
        with open(CONFIG_VAA_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "Đã lưu cấu hình VAA thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vaa/groups/toggle")
def api_vaa_toggle_group(payload: dict):
    """Bật/tắt nhóm Zalo nhận tin của VAA (mặc định demo bật)"""
    group_id = str(payload.get("id"))
    enabled = bool(payload.get("enabled"))
    if not os.path.exists(CONFIG_VAA_FILE):
        raise HTTPException(status_code=404, detail="Không tìm thấy config_vaa.json")
    with open(CONFIG_VAA_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    groups = cfg.get("zalo", {}).get("target_groups", [])
    found = False
    for g in groups:
        if str(g.get("id")) == group_id:
            g["enabled"] = enabled
            found = True
            break
    if found:
        with open(CONFIG_VAA_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": f"Đã {'bật' if enabled else 'tắt'} nhóm VAA {group_id}!"}
    raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")

@app.post("/api/vaa/groups/toggle_tag_all")
def api_vaa_toggle_tag_all():
    """Bật/tắt tự động Tag @All cho VAA"""
    if not os.path.exists(CONFIG_VAA_FILE):
        raise HTTPException(status_code=404, detail="Không tìm thấy config_vaa.json")
    with open(CONFIG_VAA_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cur = cfg.get("zalo", {}).get("auto_tag_all", True)
    new_val = not cur
    cfg.setdefault("zalo", {})["auto_tag_all"] = new_val
    with open(CONFIG_VAA_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"status": "success", "auto_tag_all": new_val}

@app.post("/api/vaa/targets/toggle")
def api_vaa_toggle_target(payload: dict):
    """Bật/tắt quét một nguồn Fanpage VAA"""
    target_id = str(payload.get("id"))
    enabled = bool(payload.get("enabled"))
    if not os.path.exists(CONFIG_VAA_FILE):
        raise HTTPException(status_code=404, detail="Không tìm thấy config_vaa.json")
    with open(CONFIG_VAA_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    targets = cfg.get("targets", [])
    found = False
    for t in targets:
        if str(t.get("id")) == target_id:
            t["enabled"] = enabled
            found = True
            break
    if found:
        with open(CONFIG_VAA_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": f"Đã {'bật' if enabled else 'tắt'} nguồn VAA {target_id}!"}
    raise HTTPException(status_code=404, detail="Không tìm thấy nguồn")

@app.get("/api/vaa/posts")
def api_vaa_get_posts(limit: int = 50):
    """Lấy danh sách bài viết VAA đã quét"""
    conn = get_vaa_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT post_hash, page_name, matched_keywords, has_form, form_url, sent_private, sent_group, registered_status, created_at
        FROM seen_posts
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/vaa/history")
def api_vaa_get_history(limit: int = 50):
    """Lấy danh sách lịch sử thông báo riêng của VAA"""
    conn = get_vaa_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, category, recipient_name, recipient_id, content, status, created_at
        FROM notification_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/vaa/scan_now")
def api_vaa_scan_now():
    """Kích hoạt quét VAA ngay lập tức"""
    try:
        from vaabot import scan_once
        result = scan_once()
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/logs")
def api_get_logs(lines: int = 120):
    """Đọc các dòng log cuối cùng"""
    if not os.path.exists(LOG_FILE):
        return {"logs": "Chưa có nhật ký hoạt động."}
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return {"logs": "".join(all_lines[-lines:])}
    except Exception as e:
        return {"logs": f"Lỗi đọc log: {e}"}

# WebSocket stream log real-time
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    last_pos = 0
    if os.path.exists(LOG_FILE):
        last_pos = max(0, os.path.getsize(LOG_FILE) - 8000)

    try:
        while True:
            if os.path.exists(LOG_FILE):
                curr_size = os.path.getsize(LOG_FILE)
                if curr_size > last_pos:
                    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_text = f.read()
                        last_pos = f.tell()
                        if new_text:
                            await websocket.send_text(new_text)
                elif curr_size < last_pos:
                    # Log file was truncated / rotated
                    last_pos = 0
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

# Static files & Screenshots
app.mount("/screenshots", StaticFiles(directory=SCREENSHOTS_DIR), name="screenshots")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Web Dashboard đang chuẩn bị... Hãy tạo file static/index.html</h1>")


async def keep_alive_task():
    """Anti-Sleep 24/7 cho Render: Tự động Ping định kỳ mỗi 8 phút để Render không đưa container vào giấc ngủ"""
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://huit-bot-zalo.onrender.com")
    await asyncio.sleep(45)
    while True:
        try:
            def _ping():
                req = urllib.request.Request(f"{render_url}/api/status", headers={"User-Agent": "Render-KeepAlive/2.0"})
                with urllib.request.urlopen(req, timeout=20) as res:
                    return res.status
            status_code = await asyncio.to_thread(_ping)
            print(f"⚡ [KEEP-ALIVE 24/7] Tự động Ping thành công ({render_url}/api/status -> {status_code}).")
        except Exception as e:
            print(f"⚠️ [KEEP-ALIVE] Ping: {e}")
        await asyncio.sleep(480) # 8 phút

@app.on_event("startup")
async def startup_event():
    # 1. Khởi tạo DB & Phục hồi toàn bộ lịch sử nếu có
    init_conn = get_db_connection()
    init_conn.close()
    restore_history_from_ledger()
    restore_registrations_from_ledger()
    restore_seen_posts_from_ledger()

    # 2. Tự động bật Bot ngay khi web server khởi động (chạy 24/7 không cần bấm tay)
    print("🚀 [STARTUP] Tự động kích hoạt Bot cào bài và đăng ký form 24/7...")
    bot_mgr.start()

    # 3. Khởi tạo DB VAA & Phục hồi toàn bộ lịch sử VAA nếu có
    vaa_conn = get_vaa_db_connection()
    vaa_conn.close()
    restore_vaa_history_from_ledger()
    restore_vaa_seen_posts_from_ledger()
    print("🚀 [STARTUP] Tự động kích hoạt Bot VAA (Học Viện Hàng Không) 24/7...")
    vaa_bot_mgr.start()

    # 4. Kích hoạt Anti-Sleep Keep-Alive loop
    asyncio.create_task(keep_alive_task())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("==================================================")
    print("🚀 KHỞI ĐỘNG HUIT BOT WEB MANAGEMENT DASHBOARD")
    print(f"🌐 Truy cập giao diện tại: http://0.0.0.0:{port}")
    print("==================================================")
    uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False)
