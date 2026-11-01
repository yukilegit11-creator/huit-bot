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

# Khởi tạo cả 2 database
init_db(DB_FILE)
init_db(BOT2_DB_FILE)
