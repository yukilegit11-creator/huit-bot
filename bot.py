import os
import sys
import time
import json
import random
import hashlib
from datetime import datetime, timezone, timedelta

# Đảm bảo UTF-8 trên Windows Terminal
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

from scraper import FacebookCometScraper
from zalo_sender import ZaloDispatcher
import zalo_sender
from supabase_client import SupabaseDispatcher
import database

try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

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



ADMIN_ZALO_UID = "7662918962461429024"
last_fb_cookie_alert_time = 0

def alert_admin_fb_cookie_expired(zalo_inst, bot_name="Bot 1 (HUIT)", throttle_secs=3600):
    global last_fb_cookie_alert_time
    now_ts = time.time()
    if now_ts - last_fb_cookie_alert_time < throttle_secs:
        return
    last_fb_cookie_alert_time = now_ts
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        f"⚠️ [{bot_name} - CẢNH BÁO COOKIE FACEBOOK HẾT HẠN] ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚨 Trạng thái: Phiên Cookie Facebook vừa bị đăng xuất hoặc hết hạn!\n"
        "🌐 Hệ thống: Đã tự động bật Chế độ Ẩn danh (Guest Mode) để tiếp tục quét bài công khai.\n"
        f"⏰ Thời gian: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 Để tối ưu, bạn vui lòng truy cập Web Dashboard (mật khẩu YUKILEGIT0) để dán Cookie mới nhé!"
    )
    try:
        if zalo_inst and zalo_inst.client:
            from zlapi.models import Message, ThreadType
            zalo_inst.client.send(Message(text=warn_text), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 Đã gửi cảnh báo Cookie Facebook tới Zalo Admin ({ADMIN_ZALO_UID})")
            database.log_event("WARN", "Đã gửi cảnh báo Cookie Facebook hết hạn tới Zalo Admin.")
    except Exception as e:
        print(f"⚠️ Lỗi gửi cảnh báo Zalo tới Admin: {e}")

def get_initial_cycle(db_file=None):
    """Lấy số thứ tự chu kỳ quét gần nhất từ DB để chu kỳ luôn tăng dần liên tục, không bị reset về #1 khi khởi động lại."""
    try:
        st = database.get_all_bot_status(db_file=db_file).get("scan_cycle")
        if st and str(st).isdigit() and int(st) > 0:
            return int(st)
    except Exception:
        pass
    try:
        conn = database.get_connection(db_file)
        cur = conn.cursor()
        cur.execute("SELECT message FROM system_logs WHERE message LIKE '%Chu kỳ #%' ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        max_c = 0
        for r in rows:
            msg = r[0] if isinstance(r, (tuple, list)) else r["message"]
            m = re.search(r"Chu kỳ #(\d+)", msg)
            if m:
                c_num = int(m.group(1))
                if c_num > max_c:
                    max_c = c_num
        if max_c > 0:
            return max_c
    except Exception:
        pass
    return 0

def run_bot():
    print("=" * 60)
    print("🚀 HỆ THỐNG TỰ ĐỘNG CÀO FACEBOOK - ĐẨY WEB & BẮN ZALO 24/7")
    print("=" * 60)

    config = load_config()
    targets = config.get("targets", [])
    fb_cookies = config.get("fb_cookies", {})
    scanner_cfg = config.get("scanner", {})
    max_age_hours = scanner_cfg.get("max_post_age_hours", 0.1667)
    check_interval = scanner_cfg.get("check_interval_seconds", 600)
    delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 12)

    # Khởi tạo các module
    scraper = FacebookCometScraper(fb_cookies)
    zalo = ZaloDispatcher(CONFIG_FILE)
    supabase = SupabaseDispatcher(CONFIG_FILE)
    messenger = MessengerDispatcher(CONFIG_FILE) if HAS_MESSENGER else None

    print("🔌 Khởi động kết nối Zalo...")
    zalo_connected = zalo.connect()
    if zalo_connected:
        print("✅ Kết nối Zalo thành công!")
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, bot vẫn tiếp tục cào và lưu Web/DB.")

    if messenger and config.get("messenger", {}).get("enabled", False):
        print("🔌 Khởi động kết nối Facebook Messenger cho Bot 1...")
        if messenger.connect():
            print("✅ Kết nối Facebook Messenger Bot 1 thành công!")
        else:
            print("⚠️ Kết nối Facebook Messenger tạm thời chưa khả dụng.")

    cycle = get_initial_cycle()
    total_new_posts = 0

    database.set_bot_status("bot_state", "running")
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot quét tự động.")

    # Tải danh sách bài viết từ Supabase Cloud để chống gửi lặp khi Render/Server khởi động lại
    if supabase.enabled:
        try:
            cloud_seen = supabase.get_seen_identifiers()
            for s_id in cloud_seen:
                database.record_seen_post(s_id, "Cloud_Synced")
            print(f"☁️ [Cloud] Đã nạp {len(cloud_seen)} bài cũ từ Supabase để chống trùng lặp tuyệt đối!")
        except Exception as e:
            pass

    while True:
        # 1. Kiểm tra trạng thái Bật / Tắt của Bot từ Web Dashboard
        if not database.is_bot_enabled():
            database.set_bot_status("bot_state", "paused")
            print("⏸️ Bot đang ở chế độ TẮT (Tạm dừng bởi người dùng trên Web). Đang chờ kích hoạt lại...")
            time.sleep(5)
            continue

        cycle += 1
        now_str = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] 🔄 === VÒNG QUÉT THỨ #{cycle} ===")
        database.set_bot_status("last_scan_time", now_str)
        database.set_bot_status("scan_cycle", str(cycle))
        database.set_bot_status("bot_state", "scanning")

        # Cập nhật lại config mới nhất (nếu người dùng vừa thêm/bớt nhóm Zalo, link FB, từ khóa)
        try:
            config = load_config()
            targets = config.get("targets", [])
            scanner_cfg = config.get("scanner", {})
            max_age_hours = scanner_cfg.get("max_post_age_hours", 2.0)
            check_interval = scanner_cfg.get("check_interval_seconds", 30)
            delay_between_pages = scanner_cfg.get("delay_between_pages_seconds", 9)
        except Exception:
            pass

        database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Bắt đầu quét {len(targets)} trang mục tiêu.")

        for idx, target in enumerate(targets):
            # Kiểm tra lại bot có bị ngắt ngang xương giữa vòng quét không
            if not database.is_bot_enabled():
                print("⏸️ Nhận lệnh TẮT bot giữa vòng quét. Tạm dừng.")
                break

            page_name = target.get("name", f"Trang #{idx+1}")
            page_url = target.get("url", "")

            if not page_url:
                continue

            curr_idx = idx + 1
            total_targets = len(targets)
            print(f"👉 ({curr_idx}/{total_targets}) Đang quét: {page_name}")
            database.log_event("SCAN", f"🔍 [{curr_idx}/{total_targets}] Đang quét: {page_name}...")
            new_found = 0
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:
                    ident = p.get("post_id") or hashlib.md5(p["content"][:150].encode("utf-8")).hexdigest()
                    
                    # Kiểm tra xem bài đã gửi/lưu chưa
                    if not database.is_post_seen(ident, content=p["content"]):
                        new_found += 1
                        total_new_posts += 1
                        author_name = p.get("author", "ẩn danh")
                        snippet = p.get("content", "")[:90].replace("\n", " ")
                        print(f"   ✨ [Bài #{total_new_posts}] [Yuki 1 (HUIT)] Phát hiện bài mới từ '{author_name}': {snippet}...")
                        database.log_event("POST", f"[Yuki 1 (HUIT)] [{page_name}] Phát hiện bài mới từ '{author_name}': {snippet}...")

                        # 1. Lưu vào cơ sở dữ liệu Web (SQLite)
                        database.save_crawled_post(
                            post_id=ident,
                            page_name=page_name,
                            author=p.get("author", "Thành viên nhóm"),
                            content=p.get("content", ""),
                            post_url=p.get("post_url", ""),
                            posted_time=p.get("posted_time", "")
                        )
                        database.record_seen_post(ident, page_name, content=p["content"])

                        # 2. Đồng bộ lên Supabase nếu có cấu hình
                        if supabase.enabled:
                            supabase_ok = supabase.push_post(p, page_name)
                            if supabase_ok:
                                database.mark_post_sent_supabase(ident)

                        # 3. Gửi thông báo tức thì vào nhóm Zalo (nếu khớp bộ lọc từ khóa)
                        filter_kws = config.get("filter_keywords", [])
                        has_kw, matched_kw = matches_filter_keywords(p.get("content", ""), filter_kws)
                        if has_kw:
                            # 3.1. Kiểm tra nghiêm ngặt quy định 10 phút trước khi gửi
                            is_fresh, fresh_reason = zalo_sender.is_post_fresh_within_10_minutes(p)
                            if not is_fresh:
                                print(f"      ⏳ [Yuki 1 (HUIT)] Bỏ qua gửi Zalo: {fresh_reason}")
                                database.log_event("FILTER", f"[Yuki 1 (HUIT)] Bỏ qua gửi Zalo do đã quá 10 phút: {fresh_reason}")
                                continue

                            # 3.2. Nghiêm cấm gửi trùng lặp bài viết đã gửi thành công trước đó
                            if database.is_post_already_sent_zalo(ident, content=p.get("content", "")):
                                print(f"      🛑 [Yuki 1 (HUIT)] Bài viết [{ident}] đã từng gửi Zalo trước đó, nghiêm cấm gửi lần 2!")
                                continue

                            print(f"      🎯 [Yuki 1 (HUIT)] Khớp từ khóa [{matched_kw}] -> Đang gửi vào Zalo...")
                            database.log_event("FILTER", f"[Yuki 1 (HUIT)] Khớp từ khóa [{matched_kw}] -> Đang gửi Zalo...")
                            sent_zalo = zalo.send_alert(p, page_name, matched_kw=matched_kw)
                            if sent_zalo:
                                database.mark_post_sent_zalo(ident)

                            # Gửi song song qua Facebook Messenger
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_post_alert(p, page_name, matched_kw=matched_kw)
                                except Exception as me:
                                    print(f"      ⚠️ [Yuki 1] Lỗi gửi Messenger: {me}")
                        else:
                            print(f"      ⏩ [Yuki 1 (HUIT)] Bỏ qua gửi Zalo (không chứa từ khóa lọc)")
                            database.log_event("FILTER", f"[Yuki 1 (HUIT)] Bỏ qua gửi Zalo (không chứa từ khóa lọc)")

                        # Nghỉ nhẹ giữa các bài gửi để tránh spam
                        time.sleep(random.uniform(2.5, 4.0))

            except Exception as e:
                err_msg = f"Lỗi quét {page_name}: {e}"
                print(f"   ⚠️ {err_msg}")
                database.log_event("ERROR", err_msg)
                database.set_bot_status("last_error", err_msg)

            # Nghỉ giữa các trang để chống chặn rate limit từ Facebook
            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            next_str = f"chuyển qua trang [{curr_idx+1}/{total_targets}]" if curr_idx < total_targets else "hoàn tất vòng quét"
            post_stat = f"phát hiện {new_found} bài mới" if new_found > 0 else "0 bài mới"
            database.log_event("SCAN", f"✅ [{curr_idx}/{total_targets}] Hoàn thành: {page_name} ({post_stat}). Nghỉ {int(sleep_time)}s -> {next_str}.")
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping")
        print(f"💤 Đã hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"🎉 Chu kỳ #{cycle}: Hoàn tất quét toàn bộ {len(targets)} trang. Tạm nghỉ {check_interval}s trước chu kỳ #{cycle+1}.")
        time.sleep(check_interval)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Người dùng dừng bot thủ công.")
        database.log_event("SYSTEM", "🛑 Người dùng đã dừng tiến trình Bot thủ công (KeyboardInterrupt).")
        database.set_bot_status("bot_state", "stopped")

