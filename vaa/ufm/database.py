import sqlite3
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# Múi giờ chuẩn Việt Nam GMT+7 (Asia/Ho_Chi_Minh)
os.environ["TZ"] = "Asia/Ho_Chi_Minh"
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))

def get_vn_now() -> datetime:
    return datetime.now(VN_TZ)

def get_vn_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(VN_TZ).strftime(fmt)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Thống nhất CSDL UFM về chung root repo ufm_bot.db
_root_db = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ufm_bot.db")
DB_FILE = _root_db
UFM_DB_FILE = DB_FILE

def get_connection(db_file=None):
    target = db_file or DB_FILE
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file=None):
    target = db_file or DB_FILE
    conn = get_connection(target)
    cursor = conn.cursor()

    # Bảng lưu toàn bộ hoạt động đã quét để chống lặp
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_activities (
            activity_id TEXT PRIMARY KEY,
            title TEXT,
            unit TEXT,
            event_time TEXT,
            location TEXT,
            points REAL DEFAULT 0,
            ctxh REAL DEFAULT 0,
            status TEXT,
            is_full INTEGER DEFAULT 0,
            detail_url TEXT,
            register_url TEXT,
            source TEXT,
            is_sent INTEGER DEFAULT 0,
            first_seen TEXT,
            last_updated TEXT
        )
    """)

    # Bảng kiểm toán hoạt động được ghi nhận
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawled_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id TEXT,
            title TEXT,
            unit TEXT,
            points REAL DEFAULT 0,
            status TEXT,
            action_type TEXT DEFAULT 'NEW',
            is_sent_zalo INTEGER DEFAULT 0,
            crawled_at TEXT
        )
    """)

    # BẢNG LỊCH SỬ BẤT BIẾN - KHÔNG BAO GIỜ ĐƯỢC PHÉP XOÁ/SỬA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            post_title TEXT,
            source_page TEXT,
            author TEXT,
            post_url TEXT,
            content_snippet TEXT,
            has_form INTEGER DEFAULT 1,
            matched_keyword TEXT,
            crawled_at TEXT,
            zalo_target_id TEXT,
            zalo_target_name TEXT,
            target_type TEXT,
            sent_at TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_delete_delivery_history 
        BEFORE DELETE ON delivery_history 
        BEGIN 
            SELECT RAISE(FAIL, 'Lịch sử phát tin Zalo UFM là bất biến vĩnh viễn, không được phép xóa!'); 
        END;
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_update_delivery_history 
        BEFORE UPDATE ON delivery_history 
        BEGIN 
            SELECT RAISE(FAIL, 'Lịch sử phát tin Zalo UFM là bất biến vĩnh viễn, không được phép sửa đổi!'); 
        END;
    """)

    # Bảng trạng thái bot
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    """)

    # Bảng log hệ thống
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            created_at TEXT
        )
    """)

    # Bảng lưu trữ 100 tài khoản sinh viên phục vụ tự động đăng ký
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_act_id ON seen_activities (activity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawled_act_time ON crawled_activities (crawled_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_delivery_time ON delivery_history (sent_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_id ON system_logs (id DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_mssv ON student_accounts (mssv)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_active ON student_accounts (is_active)")

    now_vn = get_vn_now_str()
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value, updated_at) VALUES ('is_active', 'true', ?)", (now_vn,))
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value, updated_at) VALUES ('bot_state', 'running', ?)", (now_vn,))
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value, updated_at) VALUES ('portal_cookie_status', 'valid', ?)", (now_vn,))
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value, updated_at) VALUES ('last_scan_time', '', ?)", (now_vn,))
    cursor.execute("INSERT OR IGNORE INTO bot_status (key, value, updated_at) VALUES ('total_scans', '0', ?)", (now_vn,))

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
        cursor.execute("""
            DELETE FROM system_logs WHERE id NOT IN (
                SELECT id FROM system_logs ORDER BY id DESC LIMIT 300
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Lỗi ghi log UFM: {e}")

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
    log_event("SYSTEM", f"Người dùng đã {'BẬT (Khởi động)' if enabled else 'TẮT (Tạm dừng)'} tiến trình Bot UFM.", db_file=db_file)

def get_bot_status(key: str, default: str = "", db_file=None) -> str:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_status WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

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

def get_all_bot_status(db_file=None) -> dict:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM bot_status")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def record_seen_activity(act: dict, is_sent: bool = True, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO seen_activities (
            activity_id, title, unit, event_time, location, points, ctxh, 
            status, is_full, detail_url, register_url, source, is_sent, first_seen, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            is_full = excluded.is_full,
            last_updated = excluded.last_updated
    """, (
        str(act.get("activity_id", "")),
        str(act.get("title", "")),
        str(act.get("unit", "")),
        str(act.get("event_time", "")),
        str(act.get("location", "")),
        float(act.get("points", 0)),
        float(act.get("ctxh", 0)),
        str(act.get("status", "")),
        1 if act.get("is_full") else 0,
        str(act.get("detail_url", "")),
        str(act.get("register_url", "")),
        str(act.get("source", "")),
        1 if is_sent else 0,
        now_vn,
        now_vn
    ))
    conn.commit()
    conn.close()

def get_seen_activity(activity_id: str, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    aid = str(activity_id)
    raw = aid.replace("UFM_", "").replace("DK_", "").replace("SEM_", "").replace("CUST_", "")
    cursor.execute('''
        SELECT * FROM seen_activities 
        WHERE activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ? 
           OR activity_id = ?
        LIMIT 1
    ''', (aid, f"UFM_{raw}", f"DK_{raw}", f"SEM_{raw}", raw))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def is_activity_seen(activity_id: str, db_file=None) -> bool:
    return get_seen_activity(activity_id, db_file) is not None

def update_activity_status(activity_id: str, status: str, is_full: bool, is_sent: bool = None, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    if is_sent is not None:
        cursor.execute('''
            UPDATE seen_activities
            SET status = ?, is_full = ?, is_sent = ?, last_updated = ?
            WHERE activity_id = ?
        ''', (status, 1 if is_full else 0, 1 if is_sent else 0, now_vn, str(activity_id)))
    else:
        cursor.execute('''
            UPDATE seen_activities
            SET status = ?, is_full = ?, last_updated = ?
            WHERE activity_id = ?
        ''', (status, 1 if is_full else 0, now_vn, str(activity_id)))
    conn.commit()
    conn.close()

def update_seen_is_sent(activity_id: str, is_sent: bool = True, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute('''
        UPDATE seen_activities
        SET is_sent = ?, last_updated = ?
        WHERE activity_id = ?
    ''', (1 if is_sent else 0, now_vn, str(activity_id)))
    conn.commit()
    conn.close()

def add_crawled_activity(act: dict, action_type="NEW", is_sent=True, db_file=None):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO crawled_activities (activity_id, title, unit, points, status, action_type, is_sent_zalo, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(act.get("activity_id", "")),
        str(act.get("title", "")),
        str(act.get("unit", "")),
        float(act.get("points", 0)),
        str(act.get("status", "")),
        action_type,
        1 if is_sent else 0,
        now_vn
    ))
    conn.commit()
    conn.close()

def is_activity_already_sent_zalo(activity_id: str, title: str = None, target_id: str = None, db_file=None) -> bool:
    """Kiểm tra nghiêm ngặt: Hoạt động này đã gửi thành công tới người nhận / nhóm này chưa."""
    conn = get_connection(db_file)
    cursor = conn.cursor()

    # 1. Kiểm tra delivery_history theo post_id
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

    # 2. Kiểm tra delivery_history theo title
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

    # 3. Kiểm tra seen_activities is_sent = 1
    cursor.execute("SELECT 1 FROM seen_activities WHERE activity_id = ? AND is_sent = 1", (str(activity_id),))
    if cursor.fetchone() is not None:
        conn.close()
        return True

    conn.close()
    return False

def record_delivery(
    post_id: str, post_title: str, source_page: str, author: str, post_url: str,
    content_snippet: str, has_form: int, matched_keyword: str, zalo_target_id: str,
    zalo_target_name: str, target_type: str, status: str, crawled_at: str, db_file=None
):
    conn = get_connection(db_file)
    cursor = conn.cursor()
    now_vn = get_vn_now_str()
    cursor.execute("""
        INSERT INTO delivery_history (
            post_id, post_title, source_page, author, post_url,
            content_snippet, has_form, matched_keyword, crawled_at,
            zalo_target_id, zalo_target_name, target_type, sent_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(post_id),
        str(post_title),
        str(source_page),
        str(author),
        str(post_url),
        str(content_snippet)[:2000],
        has_form,
        str(matched_keyword),
        crawled_at or now_vn,
        str(zalo_target_id),
        str(zalo_target_name),
        str(target_type),
        now_vn,
        status
    ))
    conn.commit()
    conn.close()

def get_delivery_history(limit: int = 100, db_file=None) -> list:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM delivery_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def get_recent_activities(limit: int = 100, db_file=None) -> list:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_activities ORDER BY last_updated DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def get_stats(db_file=None) -> dict:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    total_seen = cursor.execute("SELECT COUNT(*) FROM seen_activities").fetchone()[0]
    total_sent = cursor.execute("SELECT COUNT(*) FROM delivery_history WHERE status = 'SUCCESS'").fetchone()[0]
    total_crawled = cursor.execute("SELECT COUNT(*) FROM crawled_activities").fetchone()[0]
    conn.close()
    return {
        "total_seen": total_seen,
        "total_sent": total_sent,
        "total_crawled": total_crawled
    }

# ==========================================
# CÁC HÀM QUẢN LÝ 100 TÀI KHOẢN SINH VIÊN
# ==========================================

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
    conn = get_connection(db_file)
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
    conn = get_connection(db_file)
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
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student_accounts WHERE mssv = ?", (str(mssv).strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_student(mssv: str, db_file=None) -> bool:
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM student_accounts WHERE mssv = ?", (str(mssv).strip(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def toggle_student_status(mssv: str, db_file=None) -> tuple:
    conn = get_connection(db_file)
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
    conn = get_connection(db_file)
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
    conn = get_connection(db_file)
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
    conn = get_connection(db_file)
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

# Khởi tạo DB tự động khi import
init_db()
