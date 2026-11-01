import os
import sys
import time
import json
import random
import hashlib
from datetime import datetime

# Đảm bảo UTF-8 trên Windows Terminal
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

from scraper import FacebookCometScraper
from zalo_sender import ZaloDispatcher
from supabase_client import SupabaseDispatcher
import database

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def matches_filter_keywords(text: str, keywords: list) -> tuple:
    if not keywords:
        return True, "mặc định"
    txt_lower = text.lower()
    for kw in keywords:
        if kw.lower() in txt_lower:
            return True, kw
    return False, ""


def run_bot():
    print("=" * 60)
    print("🚀 HỆ THỐNG TỰ ĐỘNG CÀO FACEBOOK - ĐẨY WEB & BẮN ZALO 24/7")
    print("=" * 60)

    config = load_config()
    targets = config.get("targets", [])
    fb_cookies = config.get("fb_cookies", {})
    scanner_cfg = config.get("scanner", {})
    max_age_hours = scanner_cfg.get("max_post_age_hours", 3.0)
    check_interval = scanner_cfg.get("check_interval_seconds", 600)
    delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 12)

    # Khởi tạo các module
    scraper = FacebookCometScraper(fb_cookies)
    zalo = ZaloDispatcher(CONFIG_FILE)
    supabase = SupabaseDispatcher(CONFIG_FILE)

    print("🔌 Khởi động kết nối Zalo...")
    zalo_connected = zalo.connect()
    if zalo_connected:
        print("✅ Kết nối Zalo thành công!")
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, bot vẫn tiếp tục cào và lưu Web/DB.")

    cycle = 0
    total_new_posts = 0

    database.set_bot_status("bot_state", "running")
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot quét tự động.")

    while True:
        # 1. Kiểm tra trạng thái Bật / Tắt của Bot từ Web Dashboard
        if not database.is_bot_enabled():
            database.set_bot_status("bot_state", "paused")
            print("⏸️ Bot đang ở chế độ TẮT (Tạm dừng bởi người dùng trên Web). Đang chờ kích hoạt lại...")
            time.sleep(5)
            continue

        cycle += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] 🔄 === VÒNG QUÉT THỨ #{cycle} ===")
        database.set_bot_status("last_scan_time", now_str)
        database.set_bot_status("scan_cycle", str(cycle))
        database.set_bot_status("bot_state", "scanning")

        # Cập nhật lại config mới nhất (nếu người dùng vừa thêm/bớt nhóm Zalo, link FB, từ khóa)
        try:
            config = load_config()
            targets = config.get("targets", [])
            scanner_cfg = config.get("scanner", {})
            max_age_hours = scanner_cfg.get("max_post_age_hours", 3.0)
            check_interval = scanner_cfg.get("check_interval_seconds", 30)
            delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 9)
        except Exception:
            pass

        database.log_event("SCAN", f"Bắt đầu vòng quét #{cycle} trên {len(targets)} trang mục tiêu.")

        for idx, target in enumerate(targets):
            # Kiểm tra lại bot có bị ngắt ngang xương giữa vòng quét không
            if not database.is_bot_enabled():
                print("⏸️ Nhận lệnh TẮT bot giữa vòng quét. Tạm dừng.")
                break

            page_name = target.get("name", f"Trang #{idx+1}")
            page_url = target.get("url", "")

            if not page_url:
                continue

            print(f"👉 ({idx+1}/{len(targets)}) Đang quét: {page_name}")
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:
                    ident = p.get("post_id") or hashlib.md5(p["content"][:150].encode("utf-8")).hexdigest()
                    
                    # Kiểm tra xem bài đã gửi/lưu chưa
                    if not database.is_post_seen(ident):
                        total_new_posts += 1
                        author_name = p.get("author", "ẩn danh")
                        snippet = p.get("content", "")[:90].replace("\n", " ")
                        print(f"   ✨ [Bài #{total_new_posts}] Phát hiện bài mới từ '{author_name}': {snippet}...")
                        database.log_event("POST", f"[{page_name}] Phát hiện bài mới từ '{author_name}': {snippet}...")

                        # 1. Lưu vào cơ sở dữ liệu Web (SQLite)
                        database.save_crawled_post(
                            post_id=ident,
                            page_name=page_name,
                            author=p.get("author", "Thành viên nhóm"),
                            content=p.get("content", ""),
                            post_url=p.get("post_url", ""),
                            posted_time=p.get("posted_time", "")
                        )
                        database.record_seen_post(ident, page_name)

                        # 2. Đồng bộ lên Supabase nếu có cấu hình
                        if supabase.enabled:
                            supabase_ok = supabase.push_post(p, page_name)
                            if supabase_ok:
                                database.mark_post_sent_supabase(ident)

                        # 3. Gửi thông báo tức thì vào nhóm Zalo (nếu khớp bộ lọc từ khóa)
                        filter_kws = config.get("filter_keywords", [])
                        has_kw, matched_kw = matches_filter_keywords(p.get("content", ""), filter_kws)
                        if has_kw:
                            print(f"      🎯 Bài viết khớp từ khóa [{matched_kw}] -> Đang gửi vào Zalo...")
                            database.log_event("FILTER", f"Khớp từ khóa [{matched_kw}] -> Đang gửi Zalo...")
                            sent_zalo = zalo.send_alert(p, page_name)
                            if sent_zalo:
                                database.mark_post_sent_zalo(ident)
                        else:
                            print(f"      ⏩ Bỏ qua gửi Zalo (không chứa từ khóa lọc)")
                            database.log_event("FILTER", f"Bỏ qua gửi Zalo (bài viết không chứa từ khóa tuyển sinh/form/đăng ký/đrl)")

                        # Nghỉ nhẹ giữa các bài gửi để tránh spam
                        time.sleep(random.uniform(2.5, 4.0))

            except Exception as e:
                err_msg = f"Lỗi quét {page_name}: {e}"
                print(f"   ⚠️ {err_msg}")
                database.log_event("ERROR", err_msg)
                database.set_bot_status("last_error", err_msg)

            # Nghỉ giữa các trang để chống chặn rate limit từ Facebook
            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping")
        print(f"💤 Đã hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"Hoàn thành vòng quét #{cycle}. Tạm nghỉ {check_interval}s trước vòng tiếp theo.")
        time.sleep(check_interval)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Người dùng dừng bot thủ công.")
        database.log_event("SYSTEM", "🛑 Người dùng đã dừng tiến trình Bot thủ công (KeyboardInterrupt).")
        database.set_bot_status("bot_state", "stopped")

