# -*- coding: utf-8 -*-
"""
VAA Social Crawler & Zalo Bot (Học Viện Hàng Không Việt Nam)
Hoàn toàn độc lập với HUIT - Lưu trữ DB riêng biệt: seen_posts_vaa.db
Chỉ gửi thông báo vào nhóm Zalo demo (475259879796859360) kèm Tag @All.
"""

import os
import sys
import time
import json
import random
import hashlib
import sqlite3
import re
from datetime import datetime, timezone, timedelta

# Đảm bảo UTF-8 trên Windows Terminal
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VN_TZ = timezone(timedelta(hours=7))

def get_vn_now():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")

def format_vn_time(ts=None):
    if ts is None:
        return datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(ts, (int, float)):
        if ts > 1e11:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
    return str(ts)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_vaa.json")
DB_FILE = os.path.join(SCRIPT_DIR, "seen_posts_vaa.db")
LOG_FILE = os.path.join(SCRIPT_DIR, "vaabot.log")
HISTORY_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_history_vaa.jsonl")
SEEN_POSTS_LEDGER_FILE = os.path.join(SCRIPT_DIR, "persistent_seen_posts_vaa.jsonl")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "persistent_settings_vaa.json")

# Khóa đơn tiến trình cho Bot VAA: Cổng 29998 (HUIT dùng cổng 29999)
import socket
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(('127.0.0.1', 29998))
except OSError:
    print("⚠️ [VAA SINGLE-INSTANCE LOCK] Đã có một tiến trình Bot VAA khác đang hoạt động! Thoát an toàn.")
    sys.exit(0)

from scraper import FacebookCometScraper
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType, Mention

def get_vaa_db():
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn

def append_to_persistent_history(record: dict):
    try:
        with open(HISTORY_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Lỗi ghi VAA history ledger:", e)

def append_to_seen_ledger(record: dict):
    try:
        with open(SEEN_POSTS_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Lỗi ghi VAA seen ledger:", e)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            grp_overrides = settings.get("zalo_group_overrides", {})
            for grp in cfg.get("zalo", {}).get("target_groups", []):
                gid = str(grp.get("id"))
                if gid in grp_overrides:
                    grp["enabled"] = bool(grp_overrides[gid])
        except Exception:
            pass
    return cfg

def extract_form_urls(text: str) -> list:
    if not text:
        return []
    patterns = [
        r'https?://forms\.gle/[a-zA-Z0-9_\-]+',
        r'https?://docs\.google\.com/forms/[^\s\)\"\'>]+',
        r'https?://forms\.office\.com/[^\s\)\"\'>]+',
        r'https?://(?:bit\.ly|tinyurl\.com|shorturl\.at)/[a-zA-Z0-9_\-]+'
    ]
    urls = []
    for pat in patterns:
        for m in re.findall(pat, text, re.IGNORECASE):
            clean = m.rstrip('.,;:)')
            if clean not in urls:
                urls.append(clean)
    return urls

def matches_filter(text: str, keywords: list) -> tuple:
    if not keywords:
        return True, "mặc định"
    txt_lower = text.lower()
    for kw in keywords:
        if kw.lower() in txt_lower:
            return True, kw
    return False, ""

def connect_zalo(zalo_cfg: dict):
    cookies = zalo_cfg.get("cookies", {})
    imei = zalo_cfg.get("imei", "285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7")
    if not cookies:
        return None
    try:
        try:
            client = ZaloAPI(imei=imei, cookies=cookies)
        except TypeError:
            client = ZaloAPI(imei=imei, session_cookies=cookies)
        return client
    except Exception as e:
        print(f"⚠️ [VAA ZALO] Lỗi kết nối Zalo: {e}")
        return None

def send_vaa_alert(zalo_client, post_data: dict, matched_kw: str, page_name: str, target_group_id: str = "475259879796859360", auto_tag_all: bool = True):
    if not zalo_client:
        return False, "Chưa kết nối Zalo"

    content = post_data.get("content", "")
    post_url = post_data.get("post_url", "")
    forms = extract_form_urls(content)
    form_str = "\n".join([f"🔗 Form: {f}" for f in forms]) if forms else "Không có form đăng ký"

    tag_str = "@All " if auto_tag_all else ""
    header_str = f"✈️ [VAA ALERTS] PHÁT HIỆN BÀI VIẾT MỚI (HỌC VIỆN HÀNG KHÔNG)\n"
    meta_str = (
        f"🏢 Nguồn: {page_name}\n"
        f"🎯 Từ khóa: #{matched_kw}\n"
        f"🕒 Đăng lúc: {post_data.get('posted_time') or 'Vừa xong'}\n"
        f"🌐 Link bài: {post_url or 'Xem trên Fanpage'}\n"
        f"{form_str}\n\n"
        f"📝 Nội dung tóm tắt:\n"
        f"{content[:500]}{'...' if len(content) > 500 else ''}"
    )

    full_text = f"{tag_str}{header_str}{meta_str}"

    mentions = None
    if auto_tag_all:
        mentions = [Mention(uid="-1", length=4, offset=0)]

    try:
        msg = Message(text=full_text, mention=mentions) if mentions else Message(text=full_text)
        zalo_client.sendMessage(msg, thread_id=target_group_id, thread_type=ThreadType.GROUP)
        return True, "Thành công"
    except Exception as e:
        return False, str(e)

def scan_once(log_fn=print):
    cfg = load_config()
    targets = cfg.get("targets", [])
    fb_cookies = cfg.get("fb_cookies", {})
    zalo_cfg = cfg.get("zalo", {})
    keywords = cfg.get("filter_keywords", [])
    demo_group_id = zalo_cfg.get("target_thread_id", "475259879796859360")
    auto_tag = bool(zalo_cfg.get("auto_tag_all", True))

    scraper = FacebookCometScraper(fb_cookies)
    zalo_client = connect_zalo(zalo_cfg)

    db = get_vaa_db()
    cur = db.cursor()

    active_targets = [t for t in targets if t.get("enabled", True)]
    log_fn(f"✈️ [VAA SCAN] Bắt đầu quét {len(active_targets)} Fanpage VAA...")

    scanned_count = 0
    new_posts_found = 0

    for idx, target in enumerate(active_targets):
        tname = target.get("name", f"Trang {idx+1}")
        turl = target.get("url", "")
        log_fn(f"🔍 ({idx+1}/{len(active_targets)}) Đang quét VAA: {tname}...")

        html = scraper.fetch_url(turl)
        if not html:
            time.sleep(2)
            continue

        posts = scraper.parse_posts(html, max_age_hours=3.0, page_url=turl)
        scanned_count += len(posts)

        for p in posts:
            p_content = p.get("content", "")
            p_hash = hashlib.md5(p_content.encode("utf-8")).hexdigest()

            # Kiểm tra xem bài đã quét chưa trong SQLite VAA
            cur.execute("SELECT post_hash FROM seen_posts WHERE post_hash = ?", (p_hash,))
            if cur.fetchone():
                continue

            # Kiểm tra khớp từ khóa
            is_match, matched_kw = matches_filter(p_content, keywords)
            if not is_match:
                continue

            forms = extract_form_urls(p_content)
            has_form = 1 if forms else 0
            form_url = forms[0] if forms else ""

            sent_group = 0
            # Gửi vào nhóm Zalo demo
            if zalo_client:
                ok, msg_res = send_vaa_alert(zalo_client, p, matched_kw, tname, target_group_id=demo_group_id, auto_tag_all=auto_tag)
                if ok:
                    sent_group = 1
                    log_fn(f"🚀 [VAA ZALO] Đã bắn thông báo bài viết mới vào nhóm demo (ID: {demo_group_id})!")
                    
                    hist_rec = {
                        "title": f"✈️ [VAA] {tname}",
                        "category": "GROUP",
                        "recipient_name": "demo",
                        "recipient_id": demo_group_id,
                        "content": f"Khớp từ khóa #{matched_kw}. Link: {p.get('post_url', '')}",
                        "status": "SENT_TAG_ALL" if auto_tag else "SENT",
                        "created_at": get_vn_now()
                    }
                    cur.execute("""
                        INSERT INTO notification_history (title, category, recipient_name, recipient_id, content, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        hist_rec["title"], hist_rec["category"], hist_rec["recipient_name"],
                        hist_rec["recipient_id"], hist_rec["content"], hist_rec["status"], hist_rec["created_at"]
                    ))
                    append_to_persistent_history(hist_rec)
                else:
                    log_fn(f"⚠️ [VAA ZALO] Gửi tin thất bại: {msg_res}")

            now_str = get_vn_now()
            cur.execute("""
                INSERT INTO seen_posts (post_hash, page_name, matched_keywords, has_form, form_url, sent_private, sent_group, registered_status, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, 'VAA_DETECTED', ?)
            """, (p_hash, tname, matched_kw, has_form, form_url, sent_group, now_str))
            
            append_to_seen_ledger({
                "post_hash": p_hash,
                "page_name": tname,
                "matched_keywords": matched_kw,
                "created_at": now_str
            })

            db.commit()
            new_posts_found += 1

        time.sleep(4)

    db.close()
    log_fn(f"✅ [VAA SCAN] Hoàn thành vòng quét: Quét {scanned_count} bài, phát hiện {new_posts_found} bài mới.")
    return {"scanned": scanned_count, "new_posts": new_posts_found}

def run_loop():
    print("=" * 60)
    print("🚀 [VAA BOT 24/7] TIẾN TRÌNH CÀO BÀI VIẾT HỌC VIỆN HÀNG KHÔNG")
    print("=" * 60)
    cycle = 0
    while True:
        cycle += 1
        print(f"\n[{get_vn_now()}] 🔄 === [BOT VAA] VÒNG QUÉT THỨ #{cycle} ===")
        try:
            scan_once(print)
        except Exception as e:
            print(f"⚠️ [VAA BOT] Lỗi vòng quét #{cycle}: {e}")
        time.sleep(45)

if __name__ == "__main__":
    run_loop()
