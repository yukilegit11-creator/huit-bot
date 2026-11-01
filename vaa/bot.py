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
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "vaabot.json")

from scraper import FacebookCometScraper
from zalo_sender import ZaloDispatcher
from supabase_client import SupabaseDispatcher
import database
import github_sync

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
    print("=" * 65)
    print("🚀 [YUKI 2 - VAA BOT] HỆ THỐNG CÀO FACEBOOK & BẮN ZALO ĐỘC LẬP 24/7")
    print("🎓 Đơn vị: Học Viện Hàng Không Việt Nam (VAA / VAU)")
    print("👤 Quản trị viên: Trần Lê Phát (@yukilegit11-creator)")
    print("=" * 65)

    config = load_config()
    targets = config.get("targets", [])
    fb_cookies = config.get("fb_cookies", {})
    scanner_cfg = config.get("scanner", {})
    max_age_hours = scanner_cfg.get("max_post_age_hours", 1.0)
    check_interval = scanner_cfg.get("check_interval_seconds", 30)
    delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 9)

    # Khởi tạo các module
    scraper = FacebookCometScraper(fb_cookies)
    zalo = ZaloDispatcher(CONFIG_FILE)
    supabase = SupabaseDispatcher(CONFIG_FILE)

    print("🔌 Đang kết nối Zalo Bot VAA...")
    zalo_connected = zalo.connect()
    if zalo_connected:
        print("✅ Kết nối Zalo Bot VAA thành công!")
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, Bot VAA vẫn tiếp tục cào và lưu DB.")

    cycle = 0
    total_new_posts = 0

    database.set_bot_status("bot_state", "running")
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot VAA quét tự động 24/7 độc lập.")

    if supabase.enabled:
        try:
            cloud_seen = supabase.get_seen_identifiers()
            for s_id in cloud_seen:
                database.record_seen_post(s_id, "Cloud_Synced")
            print(f"☁️ [Cloud] Đã nạp {len(cloud_seen)} bài cũ từ Supabase để chống trùng lặp tuyệt đối!")
        except Exception:
            pass

    while True:
        # 1. Kiểm tra trạng thái Bật / Tắt của Bot từ Web Dashboard
        if not database.is_bot_enabled():
            database.set_bot_status("bot_state", "paused")
            print("⏸️ Bot VAA đang ở chế độ TẮT (Tạm dừng bởi người dùng trên Web). Đang chờ kích hoạt lại...")
            time.sleep(5)
            continue

        # Cập nhật lại config mới nhất
        try:
            config = load_config()
            targets = config.get("targets", [])
            fb_cookies = config.get("fb_cookies", {})
            scraper.cookies = fb_cookies
            scanner_cfg = config.get("scanner", {})
            max_age_hours = scanner_cfg.get("max_post_age_hours", 1.0)
            check_interval = scanner_cfg.get("check_interval_seconds", 30)
            delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 9)
        except Exception:
            pass

        if not targets:
            print("⏳ Bot VAA chưa có trang/group Facebook nào trong danh sách. Đang chờ bạn thêm trang...")
            database.set_bot_status("bot_state", "idle")
            time.sleep(10)
            continue

        if not fb_cookies:
            print("⚠️ Bot VAA chưa có Cookie Facebook. Vui lòng dán Cookie trên Web Dashboard để bắt đầu cào...")
            database.set_bot_status("bot_state", "waiting_cookie")
            database.log_event("SYSTEM", "Chờ người dùng cấu hình Cookie Facebook trên Web...")
            time.sleep(10)
            continue

        cycle += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] 🔄 === [BOT VAA] VÒNG QUÉT THỨ #{cycle} ===")
        database.set_bot_status("last_scan_time", now_str)
        database.set_bot_status("scan_cycle", str(cycle))
        database.set_bot_status("bot_state", "scanning")

        database.log_event("SCAN", f"Bắt đầu vòng quét #{cycle} trên {len(targets)} trang VAA.")

        for idx, target in enumerate(targets):
            if not database.is_bot_enabled():
                print("⏸️ Nhận lệnh TẮT Bot VAA giữa vòng quét. Tạm dừng.")
                break

            page_name = target.get("name", f"Trang #{idx+1}")
            page_url = target.get("url", "")

            if not page_url:
                continue

            print(f"👉 ({idx+1}/{len(targets)}) [VAA] Đang quét: {page_name}")
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:
                    ident = p.get("post_id") or hashlib.md5(p["content"][:150].encode("utf-8")).hexdigest()
                    
                    if not database.is_post_seen(ident, content=p["content"]):
                        total_new_posts += 1
                        author_name = p.get("author", "ẩn danh")
                        snippet = p.get("content", "")[:90].replace("\n", " ")
                        print(f"   ✨ [Bài #{total_new_posts}] [Yuki 2 (VAA)] Phát hiện bài mới từ '{author_name}': {snippet}...")
                        database.log_event("POST", f"[{page_name}] Phát hiện bài mới từ '{author_name}': {snippet}...")

                        # 1. Lưu vào SQLite độc lập vaabot.db
                        database.save_crawled_post(
                            post_id=ident,
                            page_name=page_name,
                            author=p.get("author", "Thành viên nhóm"),
                            content=p.get("content", ""),
                            post_url=p.get("post_url", ""),
                            posted_time=p.get("posted_time", "")
                        )
                        database.record_seen_post(ident, page_name, content=p["content"])

                        # 2. Đồng bộ Supabase nếu có
                        if supabase.enabled:
                            supabase_ok = supabase.push_post(p, page_name)
                            if supabase_ok:
                                database.mark_post_sent_supabase(ident)

                        # 3. Gửi thông báo Zalo theo bộ lọc từ khóa & link form
                        filter_kws = config.get("filter_keywords", [])
                        has_kw, matched_kw = matches_filter_keywords(p.get("content", ""), filter_kws)
                        if has_kw:
                            print(f"      🎯 [Yuki 2 (VAA)] Khớp từ khóa [{matched_kw}] -> Đang gửi vào Zalo...")
                            database.log_event("FILTER", f"Khớp từ khóa [{matched_kw}] -> Đang gửi Zalo...")
                            sent_zalo = zalo.send_alert(p, page_name)
                            if sent_zalo:
                                database.mark_post_sent_zalo(ident)
                        else:
                            print(f"      ⏩ [Yuki 2 (VAA)] Bỏ qua gửi Zalo (không chứa từ khóa lọc)")
                            database.log_event("FILTER", f"Bỏ qua gửi Zalo (bài viết không chứa từ khóa lọc)")

                        time.sleep(random.uniform(2.5, 4.0))

            except Exception as e:
                err_msg = f"Lỗi quét {page_name}: {e}"
                print(f"   ⚠️ {err_msg}")
                database.log_event("ERROR", err_msg)
                database.set_bot_status("last_error", err_msg)

            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping")
        print(f"💤 Bot VAA hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"Hoàn thành vòng quét #{cycle}. Tạm nghỉ {check_interval}s trước vòng tiếp theo.")
        time.sleep(check_interval)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Dừng Bot VAA thủ công.")
        database.log_event("SYSTEM", "🛑 Dừng Bot VAA thủ công.")
        database.set_bot_status("bot_state", "stopped")
