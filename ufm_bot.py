import os
import sys
import time
import json
import threading
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_ufm.json")

from ufm_scraper import UFMPortalScraper
from zalo_sender import ZaloDispatcher, UFMBotZaloClient
import database
from zlapi.models import Message, Mention, ThreadType

try:
    from messenger_sender import MessengerDispatcher
    HAS_MESSENGER = True
except ImportError:
    HAS_MESSENGER = False

DB_TARGET = database.UFM_DB_FILE

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def format_ufm_message(act: dict, is_reopened: bool = False, auto_tag_all: bool = True, bot_name: str = "Yuki 4 (UFM ĐRL)") -> str:
    tag_str = "@All\n" if auto_tag_all else ""
    header = "⚡ [UFM - HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [UFM - THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    raw_id = act.get("raw_id", "")
    id_prefix = f"[{raw_id}] " if raw_id and not act.get("title", "").startswith(f"[{raw_id}]") else ""
    title = f"{id_prefix}{act.get('title', 'Không có tiêu đề')}"
    unit = act.get("unit", "Chưa rõ đơn vị")
    event_time = act.get("event_time", "Xem chi tiết tại cổng")
    location = act.get("location", "Theo thông báo của đơn vị")
    status = act.get("status", "Đang mở")
    points = float(act.get("points", 0) or 0)
    ctxh = float(act.get("ctxh", 0) or 0)
    group_criteria = act.get("group_criteria", "")
    reg_url = act.get("register_url") or "https://hoatdong.ufm.edu.vn/DangKy"
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    lines = [
        f"{tag_str}{header}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

    if location and location != "Chưa rõ địa điểm":
        lines.append(f"📍 Địa điểm: {location}")

    if group_criteria:
        lines.append(f"📊 Nhóm: {group_criteria}")

    lines.append(f"👥 Trạng thái: {status}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        reg_url,
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name}"
    ])

    return "\n".join(lines)


def send_zalo_ufm(zalo: ZaloDispatcher, act: dict, is_reopened: bool = False):
    config = load_config()
    zalo_cfg = config.get("zalo", {})
    configured_groups = zalo_cfg.get("target_groups")
    if configured_groups is not None:
        target_list = [t for t in configured_groups if t.get("enabled") is True or str(t.get("enabled", "")).lower() in ("true", "1")]
        if not target_list:
            print("⏸️ [UFM] Tất cả nhóm Zalo nhận tin đều đang ở trạng thái TẮT. Không gửi thông báo.")
            return False
    else:
        fallback_id = zalo_cfg.get("target_thread_id")
        target_list = [{"id": fallback_id, "name": zalo_cfg.get("target_group_name", "demo"), "type": zalo_cfg.get("target_type", "GROUP"), "enabled": True}] if fallback_id else []

    if not target_list:
        return False

    if not zalo.client:
        if not zalo.connect():
            return False

    bot_name = config.get("bot_name", "Yuki 4 (UFM ĐRL)")
    auto_tag_all = zalo_cfg.get("auto_tag_all", True)
    formatted_msg = format_ufm_message(act, is_reopened=is_reopened, auto_tag_all=auto_tag_all, bot_name=bot_name)
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
            if auto_tag_all and formatted_msg.startswith("@All"):
                mention = Mention(uid="-1", length=len("@All"), offset=0)
                msg_obj = Message(text=formatted_msg, mention=mention)
            else:
                msg_obj = Message(text=clean_text)

        # Kiểm tra chống lặp nghiêm ngặt
        if database.is_activity_already_sent_zalo(str(act.get("activity_id", "")), title=act.get("title"), target_id=tid, db_file=DB_TARGET):
            print(f"🛑 [Chống lặp UFM] Hoạt động [{act.get('title')}] đã được gửi tới {tname} ({tid}) trước đó, bỏ qua!")
            continue

        try:
            zalo.client.send(msg_obj, thread_id=tid, thread_type=t_type)
            kind_str = "cá nhân" if is_user else "nhóm"
            log_str = f"[{bot_name}] Đã gửi thông báo tới {kind_str} [{tname}] (ID: {tid})"
            print(f"📨 [Zalo] {log_str}")
            database.log_event("ZALO", log_str, db_file=DB_TARGET)
            database.record_delivery(
                post_id=act.get("activity_id", ""),
                post_title=act.get("title", ""),
                source_page=act.get("source", "UFM Portal"),
                author=act.get("unit", "UFM"),
                post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                content_snippet=clean_text[:3000],
                has_form=1,
                matched_keyword=f"+{act.get('points', 0)} ĐRL",
                zalo_target_id=tid,
                zalo_target_name=tname,
                target_type=target.get("type", "GROUP"),
                status="SUCCESS",
                crawled_at=database.get_vn_now_str(),
                db_file=DB_TARGET
            )
            any_success = True
        except Exception as e:
            err_str = f"Lỗi gửi tin tới {tname} ({tid}): {e}"
            print(f"❌ [Zalo] {err_str}")
            database.log_event("ERROR", err_str, db_file=DB_TARGET)
            database.record_delivery(
                post_id=act.get("activity_id", ""),
                post_title=act.get("title", ""),
                source_page=act.get("source", "UFM Portal"),
                author=act.get("unit", "UFM"),
                post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                content_snippet=str(err_str)[:1000],
                has_form=1,
                matched_keyword=f"+{act.get('points', 0)} ĐRL",
                zalo_target_id=tid,
                zalo_target_name=tname,
                target_type=target.get("type", "GROUP"),
                status="FAILED",
                crawled_at=database.get_vn_now_str(),
                db_file=DB_TARGET
            )

    return any_success


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
            zalo_inst.client.send(Message(text=warn_text), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 [UFM Alert] Đã gửi thông báo lỗi UFM tới Zalo Yuki ({ADMIN_ZALO_UID})")
            database.log_event("WARN", f"Đã gửi cảnh báo '{error_title}' tới Admin qua Zalo.", db_file=DB_TARGET)
    except Exception as ze:
        print(f"❌ [UFM Alert] Không thể gửi cảnh báo Zalo tới Admin: {ze}")

def get_initial_cycle(db_file=None):
    """Lấy số thứ tự chu kỳ quét gần nhất từ DB để chu kỳ luôn tăng dần liên tục, không bị reset về 0 khi khởi động lại."""
    try:
        st = database.get_all_bot_status(db_file=db_file).get("total_scans")
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
    print("=" * 65)
    print("🚀 [YUKI 4 - UFM BOT] HỆ THỐNG CÀO CỔNG HOẠT ĐỘNG UFM 24/7 (RENDER CLOUD)")
    print("🎓 Đơn vị: Trường Đại học Tài chính - Marketing (UFM)")
    print("👤 Quản trị viên: Yuki (@yukilegit11-creator)")
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
    zalo = ZaloDispatcher(CONFIG_FILE, client_class=UFMBotZaloClient, db_file=DB_TARGET)
    messenger = MessengerDispatcher(CONFIG_FILE, db_file=DB_TARGET) if HAS_MESSENGER else None

    print("🔌 Khởi động kết nối Zalo cho Bot UFM (Kênh 4)...")
    if zalo.connect():
        print("✅ Kết nối Zalo Bot UFM thành công!")
        # zalo.start_listener() (Tắt WebSocket listener để tránh xung đột đa bot)
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, Bot UFM vẫn tiếp tục cào và lưu DB.")

    if messenger and config.get("messenger", {}).get("enabled", False):
        print("🔌 Khởi động kết nối Facebook Messenger cho Bot 4 (UFM)...")
        if messenger.connect():
            print("✅ Kết nối Facebook Messenger Bot 4 thành công!")
        else:
            print("⚠️ Kết nối Facebook Messenger Bot 4 tạm thời chưa khả dụng.")

    database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot UFM quét tự động 24/7.", db_file=DB_TARGET)

    cycle = get_initial_cycle(DB_TARGET)

    while True:
        if not database.is_bot_enabled(db_file=DB_TARGET):
            database.set_bot_status("bot_state", "paused", db_file=DB_TARGET)
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
        database.set_bot_status("total_scans", str(cycle), db_file=DB_TARGET)
        now_str = database.get_vn_now_str()
        database.set_bot_status("last_scan_time", now_str, db_file=DB_TARGET)
        database.set_bot_status("bot_state", "scanning", db_file=DB_TARGET)
        database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Bắt đầu quét Cổng Hoạt động UFM...", db_file=DB_TARGET)

        try:
            is_ok, msg, activities = scraper.fetch_dangky_activities()

            if not is_ok:
                print(f"⚠️ [Chu kỳ #{cycle}] {msg}")
                database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                database.log_event("WARN", f"Phiên UFM cần đăng nhập lại: {msg}", db_file=DB_TARGET)
                alert_admin_ufm_error(zalo, "Phiên UFM cần đăng nhập lại", msg)
            else:
                database.set_bot_status("portal_cookie_status", "valid", db_file=DB_TARGET)
                new_count = 0
                reopened_count = 0

                # Chế độ Baseline lần quét đầu tiên
                try:
                    conn = database.get_connection(DB_TARGET)
                    seen_total = conn.execute("SELECT COUNT(*) FROM seen_activities").fetchone()[0]
                    conn.close()
                except Exception:
                    seen_total = 1

                if seen_total == 0 and activities:
                    for act in activities:
                        database.record_seen_activity(act, is_sent=False, db_file=DB_TARGET)
                        database.add_crawled_activity(act, action_type="BASELINE", is_sent=False, db_file=DB_TARGET)
                    msg_bl = f"📌 [Baseline] Đã ghi nhận {len(activities)} hoạt động hiện có trên cổng UFM (không bắn Zalo)."
                    print(msg_bl)
                    database.log_event("SYSTEM", msg_bl, db_file=DB_TARGET)
                    activities = []

                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))

                    # ĐIỀU KIỆN LỌC BẮT BUỘC: Chỉ gửi thông báo nếu có ĐRL > 0 hoặc CTXH > 0
                    points_val = float(act.get("points", 0) or 0)
                    ctxh_val = float(act.get("ctxh", 0) or 0)
                    if points_val <= 0 and ctxh_val <= 0:
                        database.record_seen_activity(act, is_sent=False, db_file=DB_TARGET)
                        continue
                    existing = database.get_seen_activity(aid, db_file=DB_TARGET)
                    if not existing and raw_id:
                        existing = database.get_seen_activity(f"UFM_{raw_id}", db_file=DB_TARGET) or \
                                   database.get_seen_activity(f"DK_{raw_id}", db_file=DB_TARGET) or \
                                   database.get_seen_activity(f"SEM_{raw_id}", db_file=DB_TARGET) or \
                                   database.get_seen_activity(raw_id, db_file=DB_TARGET)

                    if existing is not None:
                        matched_id = existing["activity_id"]
                        old_is_full = bool(existing.get("is_full", 0))
                        new_is_full = bool(act.get("is_full", False))
                        old_status = str(existing.get("status", "") or "").lower()
                        new_status = str(act.get("status", "") or "").lower()
                        old_is_sent = bool(existing.get("is_sent", 0))

                        database.update_activity_status(matched_id, act.get("status", ""), new_is_full, db_file=DB_TARGET)

                        is_now_open = ("mở" in new_status or "còn slot" in new_status) and not new_is_full
                        was_previously_open = ("mở" in old_status or "còn slot" in old_status) and not old_is_full

                        # 1. Trước đó chưa gửi thông báo (Baseline) mà bây giờ ĐANG MỞ ĐĂNG KÝ
                        if not old_is_sent and is_now_open:
                            log_msg = f"🎉 Phát hiện hoạt động MỚI MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            ok = send_zalo_ufm(zalo, act, is_reopened=False)
                            if ok:
                                database.update_seen_is_sent(matched_id, is_sent=True, db_file=DB_TARGET)
                                database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger: {me}")
                            continue

                        # 2. Trước đó đã đầy (old_is_full == True) và bây giờ mở thêm slot (new_is_full == False)
                        if old_is_full and is_now_open:
                            reopened_count += 1
                            database.add_crawled_activity(act, action_type="REOPENED", is_sent=True, db_file=DB_TARGET)
                            log_msg = f"⚡ Phát hiện hoạt động MỞ THÊM SLOT: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            send_zalo_ufm(zalo, act, is_reopened=True)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=True, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger mở slot: {me}")
                            continue

                        # 3. Trước đó chưa mở ('Hoạt động học kỳ', 'Chưa mở', ...) và bây giờ MỞ ĐĂNG KÝ
                        if not was_previously_open and is_now_open:
                            log_msg = f"🔥 Phát hiện hoạt động CHÍNH THỨC MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            ok = send_zalo_ufm(zalo, act, is_reopened=False)
                            if ok:
                                database.update_seen_is_sent(matched_id, is_sent=True, db_file=DB_TARGET)
                                database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger: {me}")
                            continue

                        continue

                    # Hoạt động MỚI 100%
                    new_count += 1
                    database.record_seen_activity(act, is_sent=False, db_file=DB_TARGET)

                    log_msg = f"🎉 Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)"
                    print(log_msg)
                    database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                    ok = send_zalo_ufm(zalo, act, is_reopened=False)
                    if ok:
                        database.update_seen_is_sent(act["activity_id"], is_sent=True, db_file=DB_TARGET)
                        database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                    else:
                        database.add_crawled_activity(act, action_type="NEW", is_sent=False, db_file=DB_TARGET)
                    if messenger and config.get("messenger", {}).get("enabled", False):
                        try:
                            messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                        except Exception as me:
                            print(f"⚠️ [Yuki 4] Lỗi gửi Messenger bài mới: {me}")

                if new_count > 0 or reopened_count > 0:
                    print(f"✅ [Chu kỳ #{cycle}] Đã xử lý {new_count} bài mới, {reopened_count} bài mở thêm slot.")
                
                # Ghi nhận log chu kỳ quét kèm mốc thời gian rõ ràng
                post_stat = f"{new_count} bài mới" if new_count > 0 else "0 bài mới"
                if reopened_count > 0:
                    post_stat += f", {reopened_count} mở slot"
                database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất kiểm tra Cổng Đăng Ký UFM (/DangKy) ({len(activities)} hoạt động mở ĐK, {post_stat}). Tạm nghỉ {interval}s trước chu kỳ #{cycle+1}.", db_file=DB_TARGET)

        except Exception as e:
            err_msg = f"Lỗi chu kỳ #{cycle}: {e}"
            print(f"❌ {err_msg}")
            database.log_event("ERROR", err_msg, db_file=DB_TARGET)
            alert_admin_ufm_error(zalo, "Lỗi ngoại lệ chu kỳ quét UFM", err_msg)

        database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
        time.sleep(interval)

if __name__ == "__main__":
    run_bot()
