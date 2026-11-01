import sqlite3
import os
import json
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "huit_bot.db")
BOT2_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot2.db")
IUH_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iuh_bot.db")


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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_sent_zalo INTEGER DEFAULT 0,
            is_sent_supabase INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('is_active', 'true')")
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value) VALUES ('bot_state', 'running')")

    conn.commit()
    conn.close()

def log_event(level: str, message: str, db_file=None):
    try:
        conn = get_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO system_logs (level, message) VALUES (?, ?)", (level.upper(), message))
        
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
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES ('is_active', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    """, (val,))
    state = "running" if enabled else "paused"
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES ('bot_state', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    """, (state,))
    conn.commit()
    conn.close()
    log_event("SYSTEM", f"Người dùng đã {'BẬT (Khởi động)' if enabled else 'TẮT (Tạm dừng)'} tiến trình Bot quét tự động.", db_file=db_file)

def is_post_seen(post_hash: str, content: str = None, db_file=None) -> bool:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (post_hash,))
    seen = cursor.fetchone() is not None
    if not seen and content:
        import hashlib
        c_hash = hashlib.md5(content.strip()[:150].encode("utf-8")).hexdigest()
        cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (c_hash,))
        seen = cursor.fetchone() is not None
    conn.close()
    return seen

def record_seen_post(post_hash: str, page_name: str, content: str = None, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO seen_posts (post_hash, page_name) VALUES (?, ?)",
        (post_hash, page_name)
    )
    if content:
        import hashlib
        c_hash = hashlib.md5(content.strip()[:150].encode("utf-8")).hexdigest()
        if c_hash != post_hash:
            cursor.execute(
                "INSERT OR IGNORE INTO seen_posts (post_hash, page_name) VALUES (?, ?)",
                (c_hash, page_name)
            )
    conn.commit()
    conn.close()

def save_crawled_post(post_id: str, page_name: str, author: str, content: str, post_url: str, posted_time: str, is_sent_zalo: int = 0, db_file=None) -> int:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO crawled_posts 
        (post_id, page_name, author, content, post_url, posted_time, is_sent_zalo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (post_id, page_name, author, content, post_url, posted_time, is_sent_zalo))
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
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    """, (key, str(value)))
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
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    cursor.execute("""
        INSERT INTO seen_activities (activity_id, title, semester, points, deadline, status, slots, details, is_sent, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            slots = excluded.slots,
            details = excluded.details,
            last_updated = CURRENT_TIMESTAMP
    """, (
        str(act.get("activity_id", "")),
        str(act.get("title", "")),
        str(act.get("semester", "")),
        float(act.get("points", 0)),
        str(act.get("deadline", "")),
        str(act.get("status", "")),
        str(act.get("slots", "")),
        str(act.get("details", "")),
        1 if is_sent else 0
    ))
    conn.commit()
    conn.close()

def get_seen_activity(activity_id: str, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_activities WHERE activity_id = ?", (str(activity_id),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def is_activity_seen(activity_id: str, db_file=None) -> bool:
    return get_seen_activity(activity_id, db_file) is not None

def update_activity_status(activity_id: str, status: str, slots: str = "", db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE seen_activities 
        SET status = ?, slots = ?, last_updated = CURRENT_TIMESTAMP 
        WHERE activity_id = ?
    """, (status, slots, str(activity_id)))
    conn.commit()
    conn.close()

def add_crawled_activity(act: dict, action_type: str = "NEW", is_sent: bool = True, db_file=None):
    target = db_file or IUH_DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO crawled_activities (activity_id, title, semester, points, deadline, status, slots, details, action_type, is_sent_zalo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        1 if is_sent else 0
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
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

# Khởi tạo cả 3 database (HUIT, VAA, IUH)
init_db(DB_FILE)
init_db(BOT2_DB_FILE)
init_iuh_db(IUH_DB_FILE)

