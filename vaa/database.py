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

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vaabot.db")

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
            content_snippet TEXT,
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
        print(f"Lỗi ghi log VAA: {e}")

def get_recent_logs(limit: int = 100, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results

def save_crawled_post(post_id: str, page_name: str, author: str, content: str, post_url: str, posted_time: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO crawled_posts 
            (post_id, page_name, author, content, post_url, posted_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (post_id, page_name, author, content, post_url, posted_time))
        conn.commit()
    except Exception as e:
        print(f"Lỗi lưu bài viết VAA: {e}")
    finally:
        conn.close()

def is_post_seen(post_hash: str, content: str = "", db_file=None) -> bool:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_posts WHERE post_hash = ?", (post_hash,))
    res = cursor.fetchone()
    if res is not None:
        conn.close()
        return True

    if content and len(content.strip()) >= 30:
        sub = content.strip()[:60]
        cursor.execute("SELECT 1 FROM seen_posts WHERE content_snippet = ?", (sub,))
        res = cursor.fetchone()
        if res is not None:
            conn.close()
            return True

    conn.close()
    return False

def record_seen_post(post_hash: str, page_name: str, content: str = "", db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    try:
        sub = content.strip()[:60] if content else ""
        cursor.execute("""
            INSERT OR IGNORE INTO seen_posts (post_hash, page_name, content_snippet)
            VALUES (?, ?, ?)
        """, (post_hash, page_name, sub))
        conn.commit()
    except Exception as e:
        print(f"Lỗi ghi nhận bài VAA: {e}")
    finally:
        conn.close()

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

    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results

def get_stats(db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM crawled_posts")
    total_posts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM crawled_posts WHERE is_sent_zalo = 1")
    sent_zalo = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM seen_posts")
    total_seen = cursor.fetchone()[0]

    cursor.execute("SELECT key, value FROM bot_status")
    status_rows = cursor.fetchall()
    status_dict = {row["key"]: row["value"] for row in status_rows}

    conn.close()
    is_active_bool = str(status_dict.get("is_active", "true")).lower() in ("true", "1", "yes")
    return {
        "total_posts": total_posts,
        "sent_zalo": sent_zalo,
        "total_zalo_sent": sent_zalo,
        "total_seen": total_seen,
        "is_active": is_active_bool,
        "scan_cycle": status_dict.get("scan_cycle", "0"),
        "last_scan_time": status_dict.get("last_scan_time", "Chưa quét"),
        "status": status_dict
    }

def set_bot_status(key: str, value: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bot_status (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, str(value)))
    conn.commit()
    conn.close()

def get_bot_status(key: str, default: str = None, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_status WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default

def is_bot_enabled(db_file=None) -> bool:
    val = get_bot_status("is_active", default="true", db_file=db_file)
    return str(val).lower() in ("true", "1", "yes")

def set_bot_enabled(active: bool, db_file=None):
    val = "true" if active else "false"
    set_bot_status("is_active", val, db_file=db_file)
    log_event("SYSTEM", f"Người dùng đã {'BẬT' if active else 'TẮT'} bot.", db_file=db_file)

# Khởi tạo DB tự động khi import
init_db()
