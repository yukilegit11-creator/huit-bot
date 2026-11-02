import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

from ufm_scraper import UFMPortalScraper
from zalo_sender import ZaloDispatcher, UFMBotZaloClient
from batch_register import execute_batch_registration
import database
import threading

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_bot():
    print("=" * 65)
    print("🚀 [YUKI 4 - UFM BOT] HỆ THỐNG CÀO CỔNG HOẠT ĐỘNG UFM 24/7")
    print("🎓 Đơn vị: Trường Đại học Tài chính - Marketing (UFM)")
    print("👤 Quản trị viên: Trần Lê Phát (@yukilegit11-creator)")
    print("🌐 Cổng hoạt động: https://hoatdong.ufm.edu.vn")
    print("=" * 65)

    config = load_config()
    portal_cfg = config.get("ufm_portal", {})
    username = portal_cfg.get("username", "")
    password = portal_cfg.get("password", "")
    cookies = portal_cfg.get("cookies", {})
    scanner_cfg = config.get("scanner", {})
    interval = scanner_cfg.get("check_interval_seconds", 20)

    scraper = UFMPortalScraper(cookies, username, password, config_path=CONFIG_FILE)
    zalo = ZaloDispatcher(CONFIG_FILE, client_class=UFMBotZaloClient)

    print("🔌 Khởi động kết nối Zalo cho Bot UFM...")
    if zalo.connect():
        print("✅ Kết nối Zalo Bot UFM thành công!")
        zalo.start_listener()
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, Bot UFM vẫn tiếp tục cào và lưu DB.")

    database.set_bot_status("bot_state", "running")
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot UFM quét tự động 24/7.")

    cycle = 0

    while True:
        # 1. Kiểm tra trạng thái Bật / Tắt từ Web Dashboard
        if not database.is_bot_enabled():
            database.set_bot_status("bot_state", "paused")
            time.sleep(5)
            continue

        try:
            config = load_config()
            scanner_cfg = config.get("scanner", {})
            interval = scanner_cfg.get("check_interval_seconds", 20)
            portal_cfg = config.get("ufm_portal", {})
            curr_user = portal_cfg.get("username", "")
            curr_pass = portal_cfg.get("password", "")
            if curr_user != scraper.username or curr_pass != scraper.password:
                scraper.username = curr_user
                scraper.password = curr_pass
        except Exception:
            pass

        cycle += 1
        database.set_bot_status("total_scans", str(cycle))
        now_str = database.get_vn_now_str()
        database.set_bot_status("last_scan_time", now_str)
        database.set_bot_status("bot_state", "scanning")

        try:
            # 2. Thu thập hoạt động từ hệ thống UFM
            is_ok, msg, activities = scraper.fetch_all_events()

            if not is_ok:
                print(f"⚠️ [Chu kỳ #{cycle}] {msg}")
                database.set_bot_status("portal_cookie_status", "expired")
                database.log_event("WARN", f"Phiên UFM cần đăng nhập lại: {msg}")
            else:
                database.set_bot_status("portal_cookie_status", "valid")
                new_count = 0
                reopened_count = 0

                # 3. CHẾ ĐỘ BASELINE: Lần quét đầu tiên (DB chưa có hoạt động nào)
                # Lưu toàn bộ bài hiện có làm mốc gốc, KHÔNG bắn Zalo để tránh spam bài cũ
                try:
                    conn = database.get_connection()
                    seen_total = conn.execute("SELECT COUNT(*) FROM seen_activities").fetchone()[0]
                    conn.close()
                except Exception:
                    seen_total = 1

                if seen_total == 0 and activities:
                    for act in activities:
                        database.record_seen_activity(act, is_sent=False)
                        database.add_crawled_activity(act, action_type="BASELINE", is_sent=False)
                    msg_bl = f"📌 [Baseline] Đã ghi nhận {len(activities)} hoạt động hiện có trên cổng UFM (không bắn Zalo vì đây là bài gốc)."
                    print(msg_bl)
                    database.log_event("SYSTEM", msg_bl)
                    activities = []

                # 4. Quét và phân loại bài mới
                for act in activities:
                    aid = str(act["activity_id"])
                    existing = database.get_seen_activity(aid)

                    if existing is not None:
                        # Hoạt động đã có trong DB -> Kiểm tra xem có mở thêm slot / đổi trạng thái không
                        old_is_full = bool(existing.get("is_full", 0))
                        new_is_full = bool(act.get("is_full", False))
                        
                        # Cập nhật trạng thái mới nhất
                        database.update_activity_status(aid, act.get("status", ""), new_is_full)

                        # Nếu trước đó đã hết slot (is_full = True) mà bây giờ lại mở đăng ký (new_is_full = False)
                        if old_is_full and not new_is_full and "mở đăng ký" in act.get("status", "").lower():
                            reopened_count += 1
                            log_msg = f"⚡ Phát hiện hoạt động MỞ THÊM SLOT: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg)
                            database.add_crawled_activity(act, action_type="REOPENED", is_sent=True)
                            zalo.send_activity_alert(act, is_reopened=True)

                            # Tự động nã đăng ký cho sinh viên nếu bật chế độ Auto-Snipe
                            if config.get("scanner", {}).get("auto_snipe_for_students", False):
                                clean_id = act.get("raw_id") or aid.replace("DK_", "")
                                threading.Thread(target=execute_batch_registration, args=(clean_id, act["title"]), daemon=True).start()

                        continue

                    # Hoạt động MỚI 100% chưa từng xuất hiện trong DB
                    new_count += 1
                    database.record_seen_activity(act, is_sent=True)
                    database.add_crawled_activity(act, action_type="NEW", is_sent=True)

                    log_msg = f"🎉 Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)"
                    print(log_msg)
                    database.log_event("ACTIVITY", log_msg)

                    # Bắn Zalo ngay lập tức
                    zalo.send_activity_alert(act, is_reopened=False)

                    # Tự động nã đăng ký cho sinh viên nếu bật chế độ Auto-Snipe
                    if config.get("scanner", {}).get("auto_snipe_for_students", False) and "mở đăng ký" in act.get("status", "").lower():
                        clean_id = act.get("raw_id") or aid.replace("DK_", "")
                        threading.Thread(target=execute_batch_registration, args=(clean_id, act["title"]), daemon=True).start()

                if new_count > 0 or reopened_count > 0:
                    print(f"✅ [Chu kỳ #{cycle}] Đã xử lý {new_count} bài mới, {reopened_count} bài mở thêm slot.")
                else:
                    if cycle % 10 == 0:
                        print(f"💤 [Chu kỳ #{cycle}] Hoàn tất quét ({now_str}) - Hệ thống không có thông báo mới.")

        except Exception as e:
            err_msg = f"Lỗi chu kỳ #{cycle}: {e}"
            print(f"❌ {err_msg}")
            database.log_event("ERROR", err_msg)

        database.set_bot_status("bot_state", "running")
        time.sleep(interval)

if __name__ == "__main__":
    run_bot()
