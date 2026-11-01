import os
import sys
import time
import json
from datetime import datetime

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

def send_zalo_iuh(zalo: ZaloDispatcher, act: dict, is_reopened: bool = False):
    config = load_config()
    zalo_cfg = config.get("zalo", {})
    target_list = [t for t in zalo_cfg.get("target_groups", []) if t.get("enabled", True)]
    
    if not target_list:
        fallback_id = zalo_cfg.get("target_thread_id")
        if fallback_id:
            target_list = [{
                "id": fallback_id,
                "name": zalo_cfg.get("target_group_name", "demo"),
                "type": zalo_cfg.get("target_type", "GROUP"),
                "enabled": True
            }]

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

        if is_user:
            clean_text = formatted_msg
            if clean_text.startswith("@All\n"):
                clean_text = clean_text[5:]
            elif clean_text.startswith("@All "):
                clean_text = clean_text[5:]
            msg_obj = Message(text=clean_text)
        else:
            if zalo_cfg.get("auto_tag_all", True) and formatted_msg.startswith("@All"):
                mention = Mention(uid="-1", length=len("@All"), offset=0)
                msg_obj = Message(text=formatted_msg, mention=mention)
            else:
                clean_text = formatted_msg[5:] if formatted_msg.startswith("@All\n") else formatted_msg
                msg_obj = Message(text=clean_text)

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
                crawled_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                crawled_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                db_file=DB_TARGET
            )

    return any_success


def run_bot():
    print("=" * 60)
    print("🚀 [YUKI 3 - IUH BOT] CÀO CỔNG ĐOÀN TN & ĐIỂM RÈN LUYỆN IUH 24/7")
    print("=" * 60)

    config = load_config()
    portal_cfg = config.get("portal", {})
    phpsessid = portal_cfg.get("phpsessid", "")
    scanner_cfg = config.get("scanner", {})
    interval = scanner_cfg.get("check_interval_seconds", 15)

    scraper = IUHPortalScraper(phpsessid)
    zalo = ZaloDispatcher(CONFIG_FILE)

    print("🔌 Khởi động kết nối Zalo cho Bot IUH (Kênh 3)...")
    if zalo.connect():
        print("✅ Kết nối Zalo Bot IUH thành công!")
    else:
        print("⚠️ Kết nối Zalo tạm thời chưa khả dụng, Bot IUH vẫn tiếp tục cào và lưu DB.")

    database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
    database.log_event("SYSTEM", "🚀 Khởi động tiến trình Bot Kênh 3 (IUH) quét tự động.", db_file=DB_TARGET)

    cycle = 0
    last_warn_time = 0

    while True:
        if not database.is_bot_enabled(db_file=DB_TARGET):
            database.set_bot_status("bot_state", "paused", db_file=DB_TARGET)
            time.sleep(5)
            continue

        try:
            config = load_config()
            portal_cfg = config.get("portal", {})
            curr_cookie = portal_cfg.get("phpsessid", "")
            if curr_cookie != scraper.phpsessid:
                scraper.update_cookie(curr_cookie)
            interval = config.get("scanner", {}).get("check_interval_seconds", 15)
        except Exception:
            pass

        cycle += 1
        database.set_bot_status("total_scans", str(cycle), db_file=DB_TARGET)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        database.set_bot_status("last_scan_time", now_str, db_file=DB_TARGET)
        database.set_bot_status("bot_state", "scanning", db_file=DB_TARGET)

        try:
            is_logged_in, msg, activities = scraper.fetch_activities()
            if not is_logged_in:
                database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                database.log_event("WARN", f"Cookie IUH (PHPSESSID) đã hết hạn hoặc chưa đăng nhập: {msg}", db_file=DB_TARGET)
                now_ts = time.time()
                if now_ts - last_warn_time > 1800:
                    last_warn_time = now_ts
                    try:
                        warn_msg = (
                            "⚠️ [IUH BOT CẢNH BÁO]\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            "Phiên đăng nhập web trường (PHPSESSID) đã hết hạn!\n"
                            "Bot tạm thời không thể đọc dữ liệu từ doantn.iuh.edu.vn.\n\n"
                            "👉 Vui lòng vào Web Dashboard cập nhật Cookie mới để Bot tiếp tục săn hoạt động!"
                        )
                        # CHỈ GỬI CẢNH BÁO VỀ ZALO CÁ NHÂN (USER), TUYỆT ĐỐI KHÔNG GỬI VÀO NHÓM
                        user_targets = [
                            t for t in config.get("zalo", {}).get("target_groups", []) 
                            if t.get("enabled", True) and str(t.get("type", "")).upper() == "USER"
                        ]
                        if not user_targets:
                            user_targets = [{"id": "7662918962461429024", "name": "Trần Lê Phát", "type": "USER"}]

                        for t in user_targets:
                            tid = str(t["id"])
                            zalo.client.send(Message(text=warn_msg), thread_id=tid, thread_type=ThreadType.USER)
                            log_msg = f"Đã gửi cảnh báo Cookie hết hạn tới Zalo cá nhân [{t.get('name')}] ({tid})"
                            print(f"⚠️ [Zalo] {log_msg}")
                            database.log_event("WARN", log_msg, db_file=DB_TARGET)
                    except Exception as e:
                        print(f"❌ [Zalo] Lỗi gửi cảnh báo cá nhân: {e}")
            else:
                database.set_bot_status("portal_cookie_status", "valid", db_file=DB_TARGET)
                new_count = 0
                for act in activities:
                    aid = act["activity_id"]
                    seen_act = database.get_seen_activity(aid, db_file=DB_TARGET)
                    
                    is_new = seen_act is None
                    is_reopened = False
                    if not is_new and config.get("scanner", {}).get("notify_reopened_slots", True):
                        prev_status = (seen_act.get("status") or "").lower()
                        curr_status = act.get("status", "").lower()
                        if "đủ số lượng" in prev_status and "đủ số lượng" not in curr_status:
                            is_reopened = True

                    if is_new or is_reopened:
                        new_count += 1
                        act_type = "REOPEN" if is_reopened else "NEW"
                        database.record_seen_activity(act, is_sent=True, db_file=DB_TARGET)
                        database.add_crawled_activity(act, action_type=act_type, is_sent=True, db_file=DB_TARGET)
                        
                        action_label = "MỞ THÊM SLOT" if is_reopened else "MỚI"
                        database.log_event("ACTIVITY", f"Phát hiện hoạt động [{action_label}]: {act['title']} (+{act['points']} ĐRL)", db_file=DB_TARGET)
                        
                        send_zalo_iuh(zalo, act, is_reopened=is_reopened)
                    else:
                        database.update_activity_status(aid, act.get("status", ""), act.get("slots", ""), db_file=DB_TARGET)

                if new_count > 0:
                    print(f"🎉 [Chu kỳ #{cycle}] Bắn Zalo thành công {new_count} hoạt động mới / mở slot!")

        except Exception as e:
            print(f"⚠️ [Chu kỳ #{cycle}] Lỗi quét: {e}")
            database.log_event("ERROR", f"Lỗi quét: {e}", db_file=DB_TARGET)

        database.set_bot_status("bot_state", "running", db_file=DB_TARGET)
        time.sleep(interval)

if __name__ == "__main__":
    run_bot()
