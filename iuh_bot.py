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
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_iuh.json")

from iuh_scraper import IUHPortalScraper
from zalo_sender import ZaloDispatcher
import database
from zlapi.models import Message, Mention, ThreadType

try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

DB_TARGET = database.IUH_DB_FILE

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def format_iuh_message(act: dict, is_reopened: bool = False, auto_tag_all: bool = True) -> str:
    tag_str = "@All\n" if auto_tag_all else ""
    header = "⚡ [IUH - HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [IUH - THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    lines = [
        f"{tag_str}{header}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {act.get('title', '')}",
        f"🎯 Điểm rèn luyện: +{act.get('points', 0)} điểm (Học kỳ: {act.get('semester', '')})",
        f"⏰ Hạn kết thúc đăng ký: {act.get('deadline', 'Không rõ')}",
        f"👥 Trạng thái: {act.get('status', 'Đang mở')}" + (f" ({act.get('slots')})" if act.get('slots') else ""),
    ]

    details = act.get("details", "").strip()
    if details:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📋 Chi tiết hoạt động:")
        for dline in details.split("\n"):
            dline = dline.strip()
            if dline:
                lines.append(f"  • {dline}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        "https://doantn.iuh.edu.vn/doanvien.html"
    ])
    return "\n".join(lines)

def send_zalo_iuh(zalo: ZaloDispatcher, act: dict, is_reopened: bool = False, custom_targets: list = None):
    config = load_config()
    zalo_cfg = config.get("zalo", {})
    if custom_targets is not None:
        target_list = custom_targets
    else:
        configured_groups = zalo_cfg.get("target_groups")
        if configured_groups is not None:
            target_list = [t for t in configured_groups if t.get("enabled") is True or str(t.get("enabled", "")).lower() in ("true", "1")]
            if not target_list:
                print("⏸️ [IUH] Tất cả người nhận / nhóm Zalo đều đang ở trạng thái TẮT. Không gửi thông báo.")
                return False
        else:
            fallback_id = zalo_cfg.get("target_thread_id")
            target_list = [{"id": fallback_id, "name": zalo_cfg.get("target_group_name", "demo"), "type": zalo_cfg.get("target_type", "GROUP"), "enabled": True}] if fallback_id else []

    if not target_list:
        return False

    if not zalo.client:
        if not zalo.connect():
            return False

    formatted_msg = format_iuh_message(act, is_reopened, auto_tag_all=zalo_cfg.get("auto_tag_all", True))
    any_success = False

    for target in target_list:
        tid = str(target.get("id"))
        tname = target.get("name", tid)
        is_user = str(target.get("type", "GROUP")).upper() == "USER"
        t_type = ThreadType.USER if is_user else ThreadType.GROUP

        clean_text = formatted_msg
        if clean_text.startswith("@All\n"):
            clean_text = clean_text[5:]
        elif clean_text.startswith("@All "):
            clean_text = clean_text[5:]

        if is_user:
            msg_obj = Message(text=clean_text)
        else:
            if zalo_cfg.get("auto_tag_all", True) and formatted_msg.startswith("@All"):
                mention = Mention(uid="-1", length=len("@All"), offset=0)
                msg_obj = Message(text=formatted_msg, mention=mention)
            else:
                msg_obj = Message(text=clean_text)

        # Kiểm tra nhóm/người nhận này đã từng nhận hoạt động này chưa
        if database.is_activity_already_sent_zalo(str(act.get("activity_id", "")), title=act.get("title"), target_id=tid, db_file=DB_TARGET):
            print(f"🛑 [Chống lặp IUH] Hoạt động [{act.get('title')}] đã được gửi tới {tname} ({tid}) trước đó, bỏ qua!")
            continue

        try:
            zalo.client.send(msg_obj, thread_id=tid, thread_type=t_type)
            kind_str = "cá nhân" if is_user else "nhóm"
            log_str = f"[Yuki 3 - IUH] Đã gửi thông báo tới {kind_str} [{tname}] (ID: {tid})"
            print(f"📨 [Zalo] {log_str}")
            database.log_event("ZALO", log_str, db_file=DB_TARGET)
            # Ghi vào bảng lịch sử gửi bài bất biến - Không bao giờ được xoá
            database.record_delivery(
                post_id=act.get("activity_id", ""),
                post_title=act.get("title", ""),
                source_page="IUH Portal (doantn.iuh.edu.vn)",
                author="Đoàn Thanh Niên IUH",
                post_url=act.get("url", "https://doantn.iuh.edu.vn/doanvien.html"),
                content_snippet=clean_text[:4000],
                has_form=1,
                matched_keyword=f"+{act.get('points', 0)} ĐRL ({act.get('semester', '')})",
                zalo_target_id=tid,
                zalo_target_name=tname,
                target_type=target.get("type", "GROUP"),
                status="SUCCESS",
                crawled_at=datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S"),
                db_file=DB_TARGET
            )
            any_success = True
        except Exception as e:
            err_str = f"Lỗi gửi tin tới {tname} ({tid}): {e}"
            print(f"❌ [Zalo] {err_str}")
            database.log_event("ERROR", err_str, db_file=DB_TARGET)
            # Ghi nhận trạng thái thất bại vào lịch sử bất biến
            database.record_delivery(
                post_id=act.get("activity_id", ""),
                post_title=act.get("title", ""),
                source_page="IUH Portal (doantn.iuh.edu.vn)",
                author="Đoàn Thanh Niên IUH",
                post_url=act.get("url", "https://doantn.iuh.edu.vn/doanvien.html"),
                content_snippet=str(err_str)[:1000],
                has_form=1,
                matched_keyword=f"+{act.get('points', 0)} ĐRL",
                zalo_target_id=tid,
                zalo_target_name=tname,
                target_type=target.get("type", "GROUP"),
                status="FAILED",
                crawled_at=datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S"),
                db_file=DB_TARGET
            )

    return any_success


ADMIN_ZALO_UID = "7662918962461429024"  # Yuki
last_admin_alert_time = 0
last_error_state = False

def alert_admin_iuh_error(zalo_inst, error_title: str, detail_msg: str, throttle_secs: int = 1800):
    global last_admin_alert_time, last_error_state
    now_ts = time.time()
    if now_ts - last_admin_alert_time < throttle_secs:
        return
    last_admin_alert_time = now_ts
    last_error_state = True
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    warn_msg = (
        "⚠️ [IUH - CẢNH BÁO LỖI HỆ THỐNG / COOKIE] ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 Lỗi: {error_title}\n"
        f"📌 Chi tiết: {detail_msg}\n"
        f"⏰ Thời gian: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 Thao tác khắc phục 1 chạm:\n"
        "1. Đăng nhập tại: https://doantn.iuh.edu.vn/login.html\n"
        "2. Lấy cookie PHPSESSID mới\n"
        "3. Dán cập nhật tại Dashboard:\n"
        "🔗 Web Dashboard: Hệ thống Yuki IUH (/bot3)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "(Hệ thống sẽ nhắc lại sau 30 phút nếu lỗi chưa được xử lý)"
    )
    try:
        if not zalo_inst.client:
            zalo_inst.connect()
        if zalo_inst.client:
            zalo_inst.client.send(Message(text=warn_msg), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 [IUH Alert] Đã gửi cảnh báo lỗi tới Zalo Yuki ({ADMIN_ZALO_UID})")
            database.log_event("WARN", f"Đã gửi cảnh báo '{error_title}' tới Admin qua Zalo.", db_file=DB_TARGET)
    except Exception as e_warn:
        print(f"❌ [IUH Alert] Không thể gửi cảnh báo Zalo tới Admin: {e_warn}")

def notify_admin_iuh_recovery(zalo_inst, activity_count: int):
    global last_admin_alert_time, last_error_state
    if not last_error_state:
        return
    last_error_state = False
    last_admin_alert_time = 0  # Reset throttle để lần lỗi tiếp theo báo ngay
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    recovery_msg = (
        "✅ [IUH - HỆ THỐNG ĐÃ PHỤC HỒI THÀNH CÔNG] ✅\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎉 Cổng Đoàn TN & ĐRL IUH đã kết nối bình thường trở lại!\n"
        f"📌 Số hoạt động hiện có: {activity_count}\n"
        f"⏰ Thời gian: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Bot 3 (Yuki IUH) đang tiếp tục chế độ quét tự động 24/7."
    )
    try:
        if not zalo_inst.client:
            zalo_inst.connect()
        if zalo_inst.client:
            zalo_inst.client.send(Message(text=recovery_msg), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"✅ [IUH Recovery] Đã gửi thông báo phục hồi tới Zalo Yuki ({ADMIN_ZALO_UID})")
            database.log_event("SYSTEM", "Đã gửi thông báo phục hồi hệ thống tới Admin qua Zalo.", db_file=DB_TARGET)
    except Exception as e:
        print(f"❌ [IUH Recovery] Không thể gửi thông báo phục hồi: {e}")

def run_bot():
    print("=" * 60)
    print("🚀 [YUKI 3 - IUH BOT] CÀO CỔNG ĐOÀN TN & ĐIỂM RÈN LUYỆN IUH 24/7")
    print("=" * 60)

    config = load_config()
    portal_cfg = config.get("portal", {})
    phpsessid = portal_cfg.get("phpsessid", "")
    username = portal_cfg.get("username", "")
    password = portal_cfg.get("password", "")
    auto_relogin = portal_cfg.get("auto_relogin", True)
    scanner_cfg = config.get("scanner", {})
    interval = scanner_cfg.get("check_interval_seconds", 25)

    scraper = IUHPortalScraper(phpsessid, username=username, password=password, config_path=CONFIG_FILE, auto_relogin=auto_relogin)
    zalo = ZaloDispatcher(CONFIG_FILE)
    messenger = MessengerDispatcher(CONFIG_FILE, db_file=DB_TARGET) if HAS_MESSENGER else None

    print("🔌 Khởi động kết nối Zalo cho Bot IUH (Kênh 3)...")
    if zalo.connect():
        print("✅ Kết nối Zalo Bot IUH thành công!")
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, Bot IUH vẫn tiếp tục cào và lưu DB.")

    if messenger and config.get("messenger", {}).get("enabled", False):
        print("🔌 Khởi động kết nối Facebook Messenger cho Bot 3 (IUH)...")
        if messenger.connect():
            print("✅ Kết nối Facebook Messenger Bot 3 thành công!")
        else:
            print("⚠️ Kết nối Facebook Messenger Bot 3 tạm thời chưa khả dụng.")

    database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot Kênh 3 (IUH) quét tự động.", db_file=DB_TARGET)

    cycle = 0
    last_warn_time = 0
    last_keep_alive_time = time.time()
    KEEP_ALIVE_INTERVAL = 300  # 5 phút gửi heartbeat một lần nếu bot bị tạm dừng

    while True:
        if not database.is_bot_enabled(db_file=DB_TARGET):
            database.set_bot_status("bot_state", "paused", db_file=DB_TARGET)
            now_ts = time.time()
            if now_ts - last_keep_alive_time >= KEEP_ALIVE_INTERVAL:
                is_alive, ka_msg = scraper.keep_alive()
                last_keep_alive_time = now_ts
                if is_alive:
                    database.set_bot_status("portal_cookie_status", "valid", db_file=DB_TARGET)
                    database.log_event("SYSTEM", f"💓 [Keep-Alive khi Tạm Dừng] {ka_msg}", db_file=DB_TARGET)
                else:
                    database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                    alert_admin_iuh_error(zalo, "Phiên IUH hết hạn trong lúc bot tạm dừng", ka_msg)
            time.sleep(5)
            continue

        try:
            config = load_config()
            portal_cfg = config.get("portal", {})
            curr_cookie = portal_cfg.get("phpsessid", "")
            if curr_cookie != scraper.phpsessid:
                scraper.update_cookie(curr_cookie)
            scraper.username = portal_cfg.get("username", "")
            scraper.password = portal_cfg.get("password", "")
            scraper.auto_relogin = portal_cfg.get("auto_relogin", True)
            interval = config.get("scanner", {}).get("check_interval_seconds", 25)
        except Exception:
            pass

        cycle += 1
        database.set_bot_status("total_scans", str(cycle), db_file=DB_TARGET)
        now_str = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
        database.set_bot_status("last_scan_time", now_str, db_file=DB_TARGET)
        database.set_bot_status("bot_state", "scanning", db_file=DB_TARGET)

        try:
            is_logged_in, msg, activities = scraper.fetch_activities()
            last_keep_alive_time = time.time()
            if not is_logged_in:
                database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                alert_admin_iuh_error(zalo, "Cổng IUH báo phiên đăng nhập hết hạn", msg)
            else:
                database.set_bot_status("portal_cookie_status", "valid", db_file=DB_TARGET)
                notify_admin_iuh_recovery(zalo, len(activities))
                last_warn_time = 0  # Reset cảnh báo khi cookie sống lại
                new_count = 0

                # CHẾ ĐỘ BASELINE: Lần quét hợp lệ đầu tiên (DB chưa có hoạt động nào)
                # -> Chỉ lưu toàn bộ hoạt động đang có, KHÔNG gửi Zalo (đó là bài cũ, không phải bài mới thật sự)
                try:
                    _c = database.get_connection(DB_TARGET)
                    seen_total = _c.execute("SELECT COUNT(*) FROM seen_activities").fetchone()[0]
                    _c.close()
                except Exception:
                    seen_total = 1
                if seen_total == 0 and activities:
                    for act in activities:
                        database.record_seen_activity(act, is_sent=False, db_file=DB_TARGET)
                        database.add_crawled_activity(act, action_type="BASELINE", is_sent=False, db_file=DB_TARGET)
                    msg_bl = f"📌 Baseline: đã ghi nhận {len(activities)} hoạt động đang có trên cổng IUH (không gửi Zalo vì không phải bài mới)."
                    print(msg_bl)
                    database.log_event("SYSTEM", msg_bl, db_file=DB_TARGET)
                    activities = []

                for act in activities:
                    aid = str(act["activity_id"])
                    
                    # 1. KIỂM TRA NGHIÊM NGẶT: Hoạt động đã từng được gửi Zalo chưa?
                    if database.is_activity_already_sent_zalo(aid, title=act.get("title"), db_file=DB_TARGET):
                        # Đã từng gửi Zalo -> Cập nhật thông tin trong DB, NGHIÊM CẤM gửi lại lần 2
                        database.update_activity_status(aid, act.get("status", ""), act.get("slots", ""), db_file=DB_TARGET)
                        continue

                    seen_act = database.get_seen_activity(aid, db_file=DB_TARGET)
                    if seen_act is not None:
                        # Đã có trong DB -> Chỉ cập nhật thông tin, không gửi lại
                        database.update_activity_status(aid, act.get("status", ""), act.get("slots", ""), db_file=DB_TARGET)
                        continue

                    # Hoạt động MỚI 100% (vừa xuất hiện trong chu kỳ này, <= 1 chu kỳ quét ~ vài giây)
                    # -> Lưu DB TRƯỚC rồi gửi Zalo đúng 1 lần duy nhất
                    new_count += 1
                    database.record_seen_activity(act, is_sent=True, db_file=DB_TARGET)
                    database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                    
                    database.log_event("ACTIVITY", f"Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)", db_file=DB_TARGET)
                    send_zalo_iuh(zalo, act, is_reopened=False)
                    if messenger and config.get("messenger", {}).get("enabled", False):
                        try:
                            messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                        except Exception as me:
                            print(f"⚠️ [Yuki 3] Lỗi gửi Messenger: {me}")

                if new_count > 0:
                    print(f"🎉 [Chu kỳ #{cycle}] Bắn Zalo thành công {new_count} hoạt động mới!")
                
                database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Quét xong cổng ĐRL IUH ({len(activities)} hoạt động).", db_file=DB_TARGET)

        except Exception as e:
            err_str = f"Lỗi quét: {e}"
            print(f"⚠️ [Chu kỳ #{cycle}] {err_str}")
            database.log_event("ERROR", err_str, db_file=DB_TARGET)
            alert_admin_iuh_error(zalo, "Lỗi ngoại lệ quét IUH", err_str)

        database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
        time.sleep(interval)

if __name__ == "__main__":
    run_bot()
