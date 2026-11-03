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

# Messenger (tùy chọn, chỉ chạy khi bật trong config.json)
try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

ADMIN_ZALO_UID = "7662918962461429024"
last_ufm_admin_alert_time = 0

def alert_admin_ufm_error(zalo_inst, error_title: str, detail_msg: str, throttle_secs: int = 1800):
    global last_ufm_admin_alert_time
    now_ts = time.time()
    if now_ts - last_ufm_admin_alert_time < throttle_secs:
        return
    last_ufm_admin_alert_time = now_ts
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        "⚠️ [UFM - CẢNH BÁO LỖI HỆ THỐNG / COOKIE] ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 Lỗi: {error_title}\n"
        f"📌 Chi tiết: {detail_msg}\n"
        f"⏰ Thời gian: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 Vui lòng truy cập Web Dashboard (/bot4) để cập nhật Cookie / kiểm tra ngay!"
    )
    try:
        if not zalo_inst.client:
            zalo_inst.connect()
        if zalo_inst.client:
            from zlapi.models import Message, ThreadType
            zalo_inst.client.send(Message(text=warn_text), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 [UFM Alert] Đã gửi thông báo lỗi UFM tới Zalo Trần Lê Phát ({ADMIN_ZALO_UID})")
            database.log_event("WARN", f"Đã gửi cảnh báo '{error_title}' tới Admin qua Zalo.")
    except Exception as ze:
        print(f"❌ [UFM Alert] Không thể gửi cảnh báo Zalo tới Admin: {ze}")

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

    # Khởi tạo Messenger (nếu bật)
    messenger = None
    if HAS_MESSENGER and config.get("messenger", {}).get("enabled", False):
        messenger = MessengerDispatcher(CONFIG_FILE)
        print("🔌 Khởi động kết nối Facebook Messenger cho Bot UFM...")
        if messenger.connect():
            print("✅ Kết nối Messenger Bot UFM thành công!")
        else:
            print("⚠️ Kết nối Messenger tạm thời chưa khả dụng.")
    elif HAS_MESSENGER:
        print("ℹ️ Module Messenger đã sẵn sàng nhưng chưa được BẬT trong config.json (messenger.enabled = false)")
    else:
        print("ℹ️ Module Messenger chưa cài đặt (fbchat-muqit). Bỏ qua kênh Messenger.")

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

        # Tự động thử kết nối lại Zalo nếu đang mất kết nối / cookie vừa được cập nhật
        if not zalo.client and cycle % 5 == 0:
            if zalo.connect():
                zalo.start_listener()

        # Tự động thử kết nối lại Messenger nếu cần
        if HAS_MESSENGER and messenger and not messenger.client and cycle % 5 == 0:
            messenger.connect()
        # Kiểm tra nếu Messenger vừa được bật trong config
        if HAS_MESSENGER and not messenger and cycle % 10 == 0:
            try:
                cfg_check = load_config()
                if cfg_check.get("messenger", {}).get("enabled", False):
                    messenger = MessengerDispatcher(CONFIG_FILE)
                    if messenger.connect():
                        print("✅ [Messenger] Kết nối Messenger thành công (vừa được bật)!")
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
                alert_admin_ufm_error(zalo, "Phiên UFM cần đăng nhập lại", msg)
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
                    raw_id = str(act.get("raw_id", ""))

                    # ĐIỀU KIỆN LỌC BẮT BUỘC: Chỉ gửi thông báo nếu có ĐRL > 0 hoặc CTXH > 0
                    points_val = float(act.get("points", 0) or 0)
                    ctxh_val = float(act.get("ctxh", 0) or 0)
                    if points_val <= 0 and ctxh_val <= 0:
                        database.record_seen_activity(act, is_sent=False)
                        continue
                    existing = database.get_seen_activity(aid)
                    if not existing and raw_id:
                        existing = database.get_seen_activity(f"UFM_{raw_id}") or \
                                   database.get_seen_activity(f"DK_{raw_id}") or \
                                   database.get_seen_activity(f"SEM_{raw_id}") or \
                                   database.get_seen_activity(raw_id)

                    if existing is not None:
                        matched_id = existing["activity_id"]
                        old_is_full = bool(existing.get("is_full", 0))
                        new_is_full = bool(act.get("is_full", False))
                        old_status = str(existing.get("status", "") or "").lower()
                        new_status = str(act.get("status", "") or "").lower()
                        old_is_sent = bool(existing.get("is_sent", 0))

                        database.update_activity_status(matched_id, act.get("status", ""), new_is_full)

                        is_now_open = ("mở" in new_status or "còn slot" in new_status) and not new_is_full
                        was_previously_open = ("mở" in old_status or "còn slot" in old_status) and not old_is_full

                        # 1. Trước đó chưa gửi thông báo (Baseline) mà bây giờ ĐANG MỞ ĐĂNG KÝ
                        if not old_is_sent and is_now_open:
                            database.update_seen_is_sent(matched_id, is_sent=True)
                            database.add_crawled_activity(act, action_type="NEW", is_sent=True)
                            log_msg = f"🎉 Phát hiện hoạt động MỚI MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg)
                            zalo.send_activity_alert(act, is_reopened=False)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False)
                                except Exception as me:
                                    print(f"⚠️ [Messenger] Lỗi gửi Messenger: {me}")
                            continue

                        # 2. Trước đó đã đầy (old_is_full == True) và bây giờ mở thêm slot (new_is_full == False)
                        if old_is_full and is_now_open:
                            reopened_count += 1
                            database.add_crawled_activity(act, action_type="REOPENED", is_sent=True)
                            log_msg = f"⚡ Phát hiện hoạt động MỞ THÊM SLOT: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg)
                            zalo.send_activity_alert(act, is_reopened=True)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=True)
                                except Exception as me:
                                    print(f"⚠️ [Messenger] Lỗi gửi Messenger mở slot: {me}")
                            continue

                        # 3. Trước đó chưa mở ('Hoạt động học kỳ', 'Chưa mở', ...) và bây giờ MỞ ĐĂNG KÝ
                        if not was_previously_open and is_now_open:
                            database.update_seen_is_sent(matched_id, is_sent=True)
                            database.add_crawled_activity(act, action_type="NEW", is_sent=True)
                            log_msg = f"🔥 Phát hiện hoạt động CHÍNH THỨC MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg)
                            zalo.send_activity_alert(act, is_reopened=False)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False)
                                except Exception as me:
                                    print(f"⚠️ [Messenger] Lỗi gửi Messenger: {me}")
                            continue

                        continue

                    # Hoạt động MỚI 100%
                    new_count += 1
                    database.record_seen_activity(act, is_sent=True)
                    database.add_crawled_activity(act, action_type="NEW", is_sent=True)

                    log_msg = f"🎉 Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)"
                    print(log_msg)
                    database.log_event("ACTIVITY", log_msg)

                    zalo.send_activity_alert(act, is_reopened=False)
                    if messenger and config.get("messenger", {}).get("enabled", False):
                        try:
                            messenger.send_activity_alert(act, is_reopened=False)
                        except Exception as me:
                            print(f"⚠️ [Messenger] Lỗi gửi Messenger bài mới: {me}")

                if new_count > 0 or reopened_count > 0:
                    print(f"✅ [Chu kỳ #{cycle}] Đã xử lý {new_count} bài mới, {reopened_count} bài mở thêm slot.")
                
                database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).")

        except Exception as e:
            err_msg = f"Lỗi chu kỳ #{cycle}: {e}"
            print(f"❌ {err_msg}")
            database.log_event("ERROR", err_msg)
            alert_admin_ufm_error(zalo, "Lỗi ngoại lệ chu kỳ quét UFM", err_msg)

        database.set_bot_status("bot_state", "running")
        time.sleep(interval)

if __name__ == "__main__":
    run_bot()
