import sqlite3
import os
import json
import sys
import time
from datetime import datetime, timezone, timedelta

# Cấu hình múi giờ chuẩn Việt Nam GMT+7 (Asia/Ho_Chi_Minh)
os.environ["TZ"] = "Asia/Ho_Chi_Minh"
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))

def get_vn_now() -> datetime:
    """Lấy thời gian hiện tại chuẩn múi giờ Việt Nam (GMT+7)."""
    return datetime.now(VN_TZ)

def get_vn_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Lấy chuỗi thời gian hiện tại chuẩn múi giờ Việt Nam (GMT+7)."""
    return datetime.now(VN_TZ).strftime(fmt)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "huit_bot.db")
BOT2_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot2.db")
IUH_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iuh_bot.db")
UFM_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ufm_bot.db")


def get_connection(db_file=None):
    target = db_file or DB_FILE
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file=None):
    target = db_file or DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            post_hash TEXT PRIMARY KEY,
            page_name TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE,
            page_name TEXT,
            author TEXT,
            content TEXT,
            post_url TEXT,
            posted_time TEXT,
            crawled_at TIMESTAMP DEFAULT (datetime('now','+7 hours')),
            is_sent_zalo INTEGER DEFAULT 0,
            is_sent_supabase INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawled_posts_crawled_at 
        ON crawled_posts (crawled_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_system_logs_created_at
        ON system_logs (id DESC)
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            post_title TEXT,
            source_page TEXT,
            author TEXT,
            post_url TEXT,
            content_snippet TEXT,
            has_form INTEGER DEFAULT 0,
            matched_keyword TEXT,
            crawled_at TEXT,
            zalo_target_id TEXT,
            zalo_target_name TEXT,
            target_type TEXT DEFAULT 'GROUP',
            sent_at TIMESTAMP DEFAULT (datetime('now','+7 hours')),
            status TEXT DEFAULT 'SUCCESS',
            extra_note TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_delivery_history_sent_at 
        ON delivery_history (sent_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_delivery_history_post_id 
        ON delivery_history (post_id)
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_delete_delivery_history 
        BEFORE DELETE ON delivery_history 
        BEGIN 
            SELECT RAISE(FAIL, 'Lịch sử phát tin Zalo là bất biến vĩnh viễn, không được phép xóa!'); 
        END;
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_update_delivery_history 
        BEFORE UPDATE ON delivery_history 
        BEGIN 
            SELECT RAISE(FAIL, 'Lịch sử phát tin Zalo là bất biến vĩnh viễn, không được phép sửa đổi!'); 
        END;
    """)

    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('is_active', 'true')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('bot_state', 'running')")

    # Tự động dọn dẹp các mốc log cũ từng bị lỗi cộng dồn múi giờ (lệch sang 03:xx / 04:xx sáng)
    try:
        cursor.execute("DELETE FROM system_logs WHERE created_at LIKE '2026-11-02 03:%' OR created_at LIKE '2026-11-02 04:%'")
    except Exception:
        pass

    conn.commit()
    conn.close()

def log_event(level: str, message: str, db_file=None):
    try:
        conn = get_connection(db_file)
        cursor = conn.cursor()
        now_vn = get_vn_now_str()
        cursor.execute(
            "INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, ?)",
            (level.upper(), message, now_vn)
        )
        
        # Giữ lại 300 logs gần nhất để tối ưu dung lượng
        cursor.execute("""
            DELETE FROM system_logs WHERE id NOT IN (
                SELECT id FROM system_logs ORDER BY id DESC LIMIT 300
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Lỗi ghi log: {e}")

def get_recent_logs(limit: int = 100, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results

def is_bot_enabled(db_file=None) -> bool:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_status WHERE key = 'is_active'")
    row = cursor.fetchone()
    conn.close()
    if row and row["value"].lower() == "false":
        return False
    return True

def set_bot_enabled(enabled: bool, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    val = "true" if enabled else "false"
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES ('is_active', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (val, now_vn))
    state = "running" if enabled else "paused"
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES ('bot_state', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (state, now_vn))
    conn.commit()
    conn.close()
    log_event("SYSTEM", f"Người dùng đã {'BẬT (Khởi động)' if enabled else 'TẮT (Tạm dừng)'} tiến trình Bot quét tự động.", db_file=db_file)

def normalize_content_text(text: str) -> str:
    if not text:
        return ""
    import re
    return re.sub(r"\s+", " ", text.strip().lower())

def is_post_seen(post_hash: str, content: str = None, db_file=None) -> bool:
    """Kiểm tra tuyệt đối: Bài viết này đã từng được quét/bóc tách qua chưa (Chống quét trùng lặp)."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    # 1. Kiểm tra trong seen_posts theo hash/id
    cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (str(post_hash),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 2. Kiểm tra trong crawled_posts theo post_id
    cursor.execute("SELECT 1 FROM crawled_posts WHERE post_id = ?", (str(post_hash),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 3. Kiểm tra trong delivery_history theo post_id
    cursor.execute("SELECT 1 FROM delivery_history WHERE post_id = ? AND status = 'SUCCESS'", (str(post_hash),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    if content:
        import hashlib
        # Hash tiền tố 150 ký tự
        c_hash = hashlib.md5(content.strip()[:150].encode("utf-8")).hexdigest()
        cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (c_hash,))
        if cursor.fetchone() is not None:
            conn.close()
            return True

        # Hash toàn văn sau chuẩn hóa
        norm_txt = normalize_content_text(content)
        norm_hash = hashlib.md5(norm_txt.encode("utf-8")).hexdigest()
        cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (norm_hash,))
        if cursor.fetchone() is not None:
            conn.close()
            return True

        # Kiểm tra đoạn trích nội dung trong delivery_history (chống trùng nội dung bài đăng)
        snippet = content.strip()[:80]
        if len(snippet) >= 25:
            cursor.execute("SELECT 1 FROM delivery_history WHERE content_snippet LIKE ? AND status = 'SUCCESS'", (f"%{snippet}%",))
            if cursor.fetchone() is not None:
                conn.close()
                return True

    conn.close()
    return False

def record_seen_post(post_hash: str, page_name: str, content: str = None, db_file=None):
    """Ghi nhận bài viết vào bộ nhớ đã quét với nhiều tầng hash khác nhau để chống trùng triệt để."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute(
        "INSERT OR IGNORE INTO seen_posts (post_hash, page_name, created_at) VALUES (?, ?, ?)",
        (str(post_hash), page_name, now_vn)
    )
    if content:
        import hashlib
        c_hash = hashlib.md5(content.strip()[:150].encode("utf-8")).hexdigest()
        norm_txt = normalize_content_text(content)
        norm_hash = hashlib.md5(norm_txt.encode("utf-8")).hexdigest()
        for h in [c_hash, norm_hash]:
            if h and h != str(post_hash):
                cursor.execute(
                    "INSERT OR IGNORE INTO seen_posts (post_hash, page_name, created_at) VALUES (?, ?, ?)",
                    (h, page_name, now_vn)
                )
    conn.commit()
    conn.close()

def is_post_already_sent_zalo(post_id: str, content: str = None, target_id: str = None, db_file=None) -> bool:
    """Nghiêm cấm tuyệt đối: Kiểm tra bài viết đã từng gửi vào Zalo thành công chưa (Ngăn chặn bắn 2 lần)."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    
    # 1. Kiểm tra trong delivery_history theo post_id
    if target_id:
        cursor.execute(
            "SELECT 1 FROM delivery_history WHERE post_id = ? AND zalo_target_id = ? AND status = 'SUCCESS'",
            (str(post_id), str(target_id))
        )
    else:
        cursor.execute(
            "SELECT 1 FROM delivery_history WHERE post_id = ? AND status = 'SUCCESS'",
            (str(post_id),)
        )
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 2. Kiểm tra trong crawled_posts theo is_sent_zalo = 1
    cursor.execute("SELECT 1 FROM crawled_posts WHERE post_id = ? AND is_sent_zalo = 1", (str(post_id),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 3. Kiểm tra nội dung bài viết trong delivery_history
    if content:
        snippet = content.strip()[:80]
        if len(snippet) >= 25:
            if target_id:
                cursor.execute(
                    "SELECT 1 FROM delivery_history WHERE content_snippet LIKE ? AND zalo_target_id = ? AND status = 'SUCCESS'",
                    (f"%{snippet}%", str(target_id))
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM delivery_history WHERE content_snippet LIKE ? AND status = 'SUCCESS'",
                    (f"%{snippet}%",)
                )
            if cursor.fetchone() is not None:
                conn.close()
                return True

    conn.close()
    return False

def save_crawled_post(post_id: str, page_name: str, author: str, content: str, post_url: str, posted_time: str, is_sent_zalo: int = 0, db_file=None) -> int:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT OR IGNORE INTO crawled_posts 
        (post_id, page_name, author, content, post_url, posted_time, is_sent_zalo, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, page_name, author, content, post_url, posted_time, is_sent_zalo, now_vn))
    inserted_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inserted_id

def mark_post_sent_zalo(post_id: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("UPDATE crawled_posts SET is_sent_zalo = 1 WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()

def mark_post_sent_supabase(post_id: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("UPDATE crawled_posts SET is_sent_supabase = 1 WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()

def get_posts(limit: int = 50, page_name: str = None, search: str = None, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    query = "SELECT * FROM crawled_posts WHERE 1=1"
    params = []
    if page_name:
        query += " AND page_name = ?"
        params.append(page_name)
    if search:
        query += " AND (content LIKE ? OR author LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results

def get_stats(db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total_posts FROM crawled_posts")
    total_posts = cursor.fetchone()["total_posts"]
    cursor.execute("SELECT COUNT(*) AS total_zalo FROM crawled_posts WHERE is_sent_zalo = 1")
    total_zalo = cursor.fetchone()["total_zalo"]
    cursor.execute("SELECT COUNT(DISTINCT page_name) AS total_pages FROM crawled_posts")
    total_pages = cursor.fetchone()["total_pages"]

    cursor.execute("SELECT key, value FROM bot_status")
    status_rows = cursor.fetchall()
    status_map = {row["key"]: row["value"] for row in status_rows}

    conn.close()
    return {
        "total_posts": total_posts,
        "total_zalo_sent": total_zalo,
        "total_pages_active": total_pages,
        "last_scan_time": status_map.get("last_scan_time", "Chưa chạy"),
        "scan_cycle": status_map.get("scan_cycle", "0"),
        "bot_state": status_map.get("bot_state", "running"),
        "is_active": status_map.get("is_active", "true").lower() == "true",
        "last_error": status_map.get("last_error", "")
    }

def set_bot_status(key: str, value: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, str(value), now_vn))
    conn.commit()
    conn.close()

# ==================== IUH (BOT 3) DATABASE METHODS ====================
def init_iuh_db(db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_activities (
            activity_id TEXT PRIMARY KEY,
            title TEXT,
            semester TEXT,
            points REAL DEFAULT 0,
            deadline TEXT,
            status TEXT,
            slots TEXT,
            details TEXT,
            first_seen TIMESTAMP DEFAULT (datetime('now','+7 hours')),
            last_updated TIMESTAMP DEFAULT (datetime('now','+7 hours')),
            is_sent INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawled_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id TEXT,
            title TEXT,
            semester TEXT,
            points REAL DEFAULT 0,
            deadline TEXT,
            status TEXT,
            slots TEXT,
            details TEXT,
            action_type TEXT DEFAULT 'NEW',
            is_sent_zalo INTEGER DEFAULT 0,
            crawled_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','+7 hours'))
        )
    """)
    # BẢNG LỊCH SỬ BẤT BIẾN - KHÔNG BAO GIỜ ĐƯỢC PHÉP XOÁ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            post_title TEXT,
            source_page TEXT,
            author TEXT,
            post_url TEXT,
            content_snippet TEXT,
            has_form INTEGER DEFAULT 0,
            matched_keyword TEXT,
            crawled_at TEXT,
            zalo_target_id TEXT,
            zalo_target_name TEXT,
            target_type TEXT,
            sent_at TEXT,
            status TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawled_activities_crawled_at ON crawled_activities (crawled_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_id ON system_logs (id DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_delivery_history_id ON delivery_history (id DESC)")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('is_active', 'true')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('bot_state', 'running')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('portal_cookie_status', 'valid')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('last_scan_time', '')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('total_scans', '0')")
    conn.commit()
    conn.close()


def record_seen_activity(act: dict, is_sent: bool = True, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO seen_activities (activity_id, title, semester, points, deadline, status, slots, details, is_sent, first_seen, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            slots = excluded.slots,
            details = excluded.details,
            last_updated = excluded.last_updated
    """, (
        str(act.get("activity_id", "")),
        str(act.get("title", "")),
        str(act.get("semester", "")),
        float(act.get("points", 0)),
        str(act.get("deadline", "")),
        str(act.get("status", "")),
        str(act.get("slots", "")),
        str(act.get("details", "")),
        1 if is_sent else 0,
        now_vn,
        now_vn
    ))
    conn.commit()
    conn.close()

def get_seen_activity(activity_id: str, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    aid = str(activity_id)
    raw = aid.replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute("""
        SELECT * FROM seen_activities 
        WHERE activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ?
        LIMIT 1
    """, (aid, f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}", raw))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def is_activity_seen(activity_id: str, db_file=None) -> bool:
    return get_seen_activity(activity_id, db_file) is not None

def is_activity_already_sent_zalo(activity_id: str, title: str = None, target_id: str = None, db_file=None) -> bool:
    """Nghiêm cấm tuyệt đối: Kiểm tra hoạt động IUH đã từng gửi Zalo thành công chưa (Ngăn chặn bắn 2 lần)."""
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    # 1. Kiểm tra trong seen_activities where is_sent = 1
    cursor.execute("SELECT 1 FROM seen_activities WHERE activity_id = ? AND is_sent = 1", (str(activity_id),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 2. Kiểm tra trong crawled_activities where is_sent_zalo = 1
    cursor.execute("SELECT 1 FROM crawled_activities WHERE activity_id = ? AND is_sent_zalo = 1", (str(activity_id),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 3. Kiểm tra trong delivery_history theo post_id (hoặc theo target_id nếu có)
    if target_id:
        cursor.execute(
            "SELECT 1 FROM delivery_history WHERE post_id = ? AND zalo_target_id = ? AND status = 'SUCCESS'",
            (str(activity_id), str(target_id))
        )
    else:
        cursor.execute(
            "SELECT 1 FROM delivery_history WHERE post_id = ? AND status = 'SUCCESS'",
            (str(activity_id),)
        )
    if cursor.fetchone() is not None:
        conn.close()
        return True

    # 4. Kiểm tra theo tiêu đề hoạt động trong delivery_history
    if title:
        clean_title = str(title).strip()
        if len(clean_title) >= 10:
            if target_id:
                cursor.execute(
                    "SELECT 1 FROM delivery_history WHERE post_title = ? AND zalo_target_id = ? AND status = 'SUCCESS'",
                    (clean_title, str(target_id))
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM delivery_history WHERE post_title = ? AND status = 'SUCCESS'",
                    (clean_title,)
                )
            if cursor.fetchone() is not None:
                conn.close()
                return True

    conn.close()
    return False

def update_activity_status(activity_id: str, status: str, slots_or_full=None, is_sent: bool = None, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("PRAGMA table_info(seen_activities)")
    cols = [c[1] for c in cursor.fetchall()]
    
    updates = ["status = ?", "last_updated = ?"]
    params = [status, now_vn]
    
    if "is_full" in cols:
        is_full_val = 1 if (isinstance(slots_or_full, bool) and slots_or_full) or (isinstance(slots_or_full, (int, str)) and str(slots_or_full) in ('1', 'True', 'true')) else 0
        updates.append("is_full = ?")
        params.append(is_full_val)
    if "slots" in cols:
        slots_val = str(slots_or_full) if slots_or_full is not None else ""
        updates.append("slots = ?")
        params.append(slots_val)
    if is_sent is not None and "is_sent" in cols:
        updates.append("is_sent = ?")
        params.append(1 if is_sent else 0)
        
    raw = str(activity_id).replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    update_str = ", ".join(updates)
    query = f"UPDATE seen_activities SET {update_str} WHERE activity_id = ? OR activity_id = ? OR activity_id = ? OR activity_id = ?"
    cursor.execute(query, tuple(params) + (str(activity_id), f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}"))
    conn.commit()
    conn.close()

def update_seen_is_sent(activity_id: str, is_sent: bool = True, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    raw = str(activity_id).replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute("""
        UPDATE seen_activities
        SET is_sent = ?, last_updated = ?
        WHERE activity_id = ? OR activity_id = ? OR activity_id = ? OR activity_id = ?
    """, (1 if is_sent else 0, now_vn, str(activity_id), f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}"))
    conn.commit()
    conn.close()

def add_crawled_activity(act: dict, action_type: str = "NEW", is_sent: bool = True, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO crawled_activities (activity_id, title, semester, points, deadline, status, slots, details, action_type, is_sent_zalo, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(act.get("activity_id", "")),
        str(act.get("title", "")),
        str(act.get("semester", "")),
        float(act.get("points", 0)),
        str(act.get("deadline", "")),
        str(act.get("status", "")),
        str(act.get("slots", "")),
        str(act.get("details", "")),
        action_type,
        1 if is_sent else 0,
        now_vn
    ))
    conn.commit()
    conn.close()

def get_activities(limit: int = 50, search: str = None, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    if search:
        cursor.execute("""
            SELECT * FROM seen_activities 
            WHERE title LIKE ? OR semester LIKE ? OR status LIKE ?
            ORDER BY first_seen DESC LIMIT ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", limit))
    else:
        cursor.execute("SELECT * FROM seen_activities ORDER BY first_seen DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_iuh_stats(db_file=None) -> dict:
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM seen_activities")
    total_activities = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) as count FROM crawled_activities WHERE is_sent_zalo = 1")
    total_sent = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) as count FROM system_logs")
    total_logs = cursor.fetchone()["count"]

    cursor.execute("SELECT key, value FROM bot_status")
    status_rows = cursor.fetchall()
    status_map = {row["key"]: row["value"] for row in status_rows}
    conn.close()

    is_act = status_map.get("is_active", "true").lower() == "true"
    return {
        "total_activities": total_activities,
        "total_zalo_sent": total_sent,
        "total_logs": total_logs,
        "bot_state": status_map.get("bot_state", "running"),
        "is_active": is_act,
        "cookie_status": status_map.get("portal_cookie_status", "valid"),
        "last_scan_time": status_map.get("last_scan_time", "Chưa chạy"),
        "total_scans": int(status_map.get("total_scans", 0)) if str(status_map.get("total_scans", 0)).isdigit() else 0
    }

def record_delivery(
    post_id: str,
    post_title: str,
    source_page: str,
    author: str,
    post_url: str,
    content_snippet: str,
    has_form: int,
    matched_keyword: str,
    zalo_target_id: str,
    zalo_target_name: str,
    target_type: str = "GROUP",
    status: str = "SUCCESS",
    crawled_at: str = "",
    db_file=None
):
    """Ghi nhận lịch sử gửi bài vào Zalo - Bất biến, không bao giờ được xóa."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    try:
        now_str = get_vn_now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO delivery_history (
                post_id, post_title, source_page, author, post_url, 
                content_snippet, has_form, matched_keyword, crawled_at, 
                zalo_target_id, zalo_target_name, target_type, sent_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_id, post_title, source_page, author, post_url,
            content_snippet[:4000] if content_snippet else "", has_form, matched_keyword or "Mặc định",
            crawled_at or now_str, str(zalo_target_id), zalo_target_name,
            target_type, now_str, status
        ))
        conn.commit()
    except Exception as e:
        print(f"Lỗi lưu lịch sử gửi bài Zalo: {e}")
    finally:
        conn.close()

def get_delivery_history(limit: int = 100, page: int = 1, search: str = None, target_id: str = None, db_file=None):
    """Lấy danh sách lịch sử gửi bài Zalo kèm phân trang và tìm kiếm."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    offset = max(0, (page - 1) * limit)
    
    query = "SELECT * FROM delivery_history WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM delivery_history WHERE 1=1"
    params = []
    count_params = []
    
    if search:
        s = f"%{search}%"
        query += " AND (post_title LIKE ? OR content_snippet LIKE ? OR source_page LIKE ? OR zalo_target_name LIKE ?)"
        count_query += " AND (post_title LIKE ? OR content_snippet LIKE ? OR source_page LIKE ? OR zalo_target_name LIKE ?)"
        params.extend([s, s, s, s])
        count_params.extend([s, s, s, s])
        
    if target_id:
        query += " AND zalo_target_id = ?"
        count_query += " AND zalo_target_id = ?"
        params.append(str(target_id))
        count_params.append(str(target_id))
        
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return {"total": total_count, "page": page, "limit": limit, "items": results}

# ==================== UFM (BOT 4) STUDENT METHODS ====================
def init_ufm_db(db_file=None):
    target = db_file or UFM_DB_FILE
    init_iuh_db(target)
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mssv TEXT UNIQUE NOT NULL,
            full_name TEXT,
            password TEXT DEFAULT '',
            cookie_data TEXT NOT NULL DEFAULT '',
            class_name TEXT DEFAULT '',
            faculty TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            cookie_status TEXT DEFAULT 'unknown',
            zalo_sender_id TEXT DEFAULT '',
            zalo_sender_name TEXT DEFAULT '',
            last_checked TEXT,
            last_registered_activity TEXT,
            registered_at TEXT,
            created_at TEXT
        )
    """)
    for col_name, col_type in [
        ("password", "TEXT DEFAULT ''"),
        ("class_name", "TEXT DEFAULT ''"),
        ("faculty", "TEXT DEFAULT ''"),
        ("zalo_sender_id", "TEXT DEFAULT ''"),
        ("zalo_sender_name", "TEXT DEFAULT ''")
    ]:
        try:
            cursor.execute(f"ALTER TABLE student_accounts ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_mssv ON student_accounts (mssv)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_active ON student_accounts (is_active)")
    conn.commit()
    conn.close()

def add_or_update_student(
    mssv: str,
    full_name: str = "",
    password: str = "",
    cookie_data: str = "",
    class_name: str = "",
    faculty: str = "",
    is_active: int = 1,
    cookie_status: str = "unknown",
    zalo_sender_id: str = "",
    zalo_sender_name: str = "",
    db_file=None
) -> bool:
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    clean_mssv = str(mssv).strip()
    try:
        cursor.execute("""
            INSERT INTO student_accounts (
                mssv, full_name, password, cookie_data, class_name, faculty,
                is_active, cookie_status, zalo_sender_id, zalo_sender_name, last_checked, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mssv) DO UPDATE SET
                full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE student_accounts.full_name END,
                password = CASE WHEN excluded.password != '' THEN excluded.password ELSE student_accounts.password END,
                cookie_data = CASE WHEN excluded.cookie_data != '' THEN excluded.cookie_data ELSE student_accounts.cookie_data END,
                class_name = CASE WHEN excluded.class_name != '' THEN excluded.class_name ELSE student_accounts.class_name END,
                faculty = CASE WHEN excluded.faculty != '' THEN excluded.faculty ELSE student_accounts.faculty END,
                is_active = excluded.is_active,
                cookie_status = excluded.cookie_status,
                zalo_sender_id = CASE WHEN excluded.zalo_sender_id != '' THEN excluded.zalo_sender_id ELSE student_accounts.zalo_sender_id END,
                zalo_sender_name = CASE WHEN excluded.zalo_sender_name != '' THEN excluded.zalo_sender_name ELSE student_accounts.zalo_sender_name END,
                last_checked = excluded.last_checked
        """, (
            clean_mssv, str(full_name).strip(), str(password).strip(), str(cookie_data).strip(),
            str(class_name).strip(), str(faculty).strip(), is_active, cookie_status,
            str(zalo_sender_id).strip(), str(zalo_sender_name).strip(), now_vn, now_vn
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Lỗi thêm sinh viên {clean_mssv}: {e}")
        conn.close()
        return False

def get_all_students(active_only: bool = False, db_file=None) -> list:
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM student_accounts WHERE is_active = 1 ORDER BY id DESC")
    else:
        cursor.execute("SELECT * FROM student_accounts ORDER BY id DESC")
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def get_student(mssv: str, db_file=None):
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student_accounts WHERE mssv = ?", (str(mssv).strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_student(mssv: str, db_file=None) -> bool:
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM student_accounts WHERE mssv = ?", (str(mssv).strip(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def toggle_student_status(mssv: str, db_file=None) -> tuple:
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM student_accounts WHERE mssv = ?", (str(mssv).strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, 0
    new_state = 0 if row["is_active"] == 1 else 1
    cursor.execute("UPDATE student_accounts SET is_active = ? WHERE mssv = ?", (new_state, str(mssv).strip()))
    conn.commit()
    conn.close()
    return True, new_state

def update_student_cookie_status(mssv: str, status: str, full_name: str = None, db_file=None):
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    if full_name:
        cursor.execute("""
            UPDATE student_accounts 
            SET cookie_status = ?, full_name = ?, last_checked = ? 
            WHERE mssv = ?
        """, (status, str(full_name).strip(), now_vn, str(mssv).strip()))
    else:
        cursor.execute("""
            UPDATE student_accounts 
            SET cookie_status = ?, last_checked = ? 
            WHERE mssv = ?
        """, (status, now_vn, str(mssv).strip()))
    conn.commit()
    conn.close()

def update_student_registered(mssv: str, activity_id: str, status_msg: str, db_file=None):
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    note = f"[{activity_id}] {status_msg}"
    cursor.execute("""
        UPDATE student_accounts 
        SET last_registered_activity = ?, registered_at = ? 
        WHERE mssv = ?
    """, (note, now_vn, str(mssv).strip()))
    conn.commit()
    conn.close()

def get_student_stats(db_file=None) -> dict:
    target = db_file or UFM_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM student_accounts").fetchone()[0]
    active = cursor.execute("SELECT COUNT(*) FROM student_accounts WHERE is_active = 1").fetchone()[0]
    valid = cursor.execute("SELECT COUNT(*) FROM student_accounts WHERE cookie_status = 'valid'").fetchone()[0]
    expired = cursor.execute("SELECT COUNT(*) FROM student_accounts WHERE cookie_status = 'expired'").fetchone()[0]
    has_pass = cursor.execute("SELECT COUNT(*) FROM student_accounts WHERE password IS NOT NULL AND password != ''").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "active": active,
        "valid": valid,
        "expired": expired,
        "has_pass": has_pass
    }

def get_all_bot_status(db_file=None) -> dict:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM bot_status")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

# Khởi tạo cả 4 database (HUIT, VAA, IUH, UFM)
init_db(DB_FILE)
init_db(BOT2_DB_FILE)
init_iuh_db(IUH_DB_FILE)
init_ufm_db(UFM_DB_FILE)



