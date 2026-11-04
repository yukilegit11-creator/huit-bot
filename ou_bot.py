import os
import sys
import time
import json
import re
import hashlib
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows & Linux
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import database
from ou_scraper import OUPortalScraper, OUFacebookScraper
from zalo_sender import ZaloDispatcher

def extract_form_links(text: str) -> list:
    if not text:
        return []
    patterns = [
        r'https?://forms\.gle/[a-zA-Z0-9_\-]+',
        r'https?://docs\.google\.com/forms/[^\s\)\"\'>]+',
        r'https?://docs\.google\.com/document/[^\s\)\"\'>]+',
        r'https?://docs\.google\.com/spreadsheets/[^\s\)\"\'>]+',
        r'https?://forms\.office\.com/[^\s\)\"\'>]+',
        r'https?://(?:bit\.ly|tinyurl\.com|shorturl\.at)/[a-zA-Z0-9_\-]+',
    ]
    found = []
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            clean_m = m.rstrip('.,;:)')
            if clean_m not in found:
                found.append(clean_m)
    return found



def extract_reg_time_from_text(text: str) -> str:
    if not text:
        return ""
    pat = r'(?:thời gian|tgian|thời điểm|cổng|link|form)\s*(?:mở|bắt đầu|cho phép|đăng ký|đky|thực hiện)?\s*(?:đăng ký|đky|sẽ mở|mở)?[\s:]*([^\n\r]{5,65})'
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        return m.group(0).strip().rstrip('.,;:)')
    return ""

def extract_post_title(text: str, max_len: int = 150) -> str:
    if not text:
        return "Thông báo mới"
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        if line.startswith("http://") or line.startswith("https://"):
            continue
        cleaned = re.sub(r'^[\W_]+', '', line)
        if len(cleaned) >= 5:
            return cleaned[:max_len]
    return lines[0][:max_len] if lines else "Thông báo mới"

from zlapi.models import Message, ThreadType

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(ROOT_DIR, "config_ou.json")
DB_FILE = database.OU_DB_FILE
VN_TZ = timezone(timedelta(hours=7))

# Throttle cảnh báo lỗi cookie
last_cookie_alert_time = 0
COOKIE_ALERT_THROTTLE = 1800  # 30 phút gửi 1 lần tối đa


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_ou_fb_message(post: dict, bot_name: str = "Yuki 5 (OU ĐRL)") -> str:
    content = post.get("content", "").strip()
    author = post.get("author", "Điểm rèn luyện OU")
    posted_time = post.get("posted_time", "Vừa xong")
    post_url = post.get("post_url", "")

    form_links = extract_form_links(content)
    has_form = len(form_links) > 0

    header = "🔥 [OU - THÔNG BÁO CÓ FORM ĐĂNG KÝ] 🔥" if has_form else "📢 [OU - THÔNG BÁO ĐIỂM RÈN LUYỆN MỚI] 📢"
    title = extract_post_title(content, max_len=140)

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"📰 Tiêu đề: {title}",
        f"🏢 Đơn vị: {author}",
        f"⏰ Đăng lúc: {posted_time}"
    ]

    reg_time_hint = extract_reg_time_from_text(content)
    if reg_time_hint:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⏰ THỜI GIAN CHO PHÉP ĐĂNG KÝ: {reg_time_hint}")

    if has_form:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📝 LINK ĐIỀN FORM / ĐĂNG KÝ:")
        for idx, flink in enumerate(form_links, 1):
            lines.append(f"👉 Link {idx}: {flink}")

    if post_url:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🔗 Link Facebook: {post_url}")

    return "\n".join(lines)


def format_ou_event_message(event: dict, bot_name: str = "Yuki 5 (OU ĐRL)", auto_reg_result: tuple = None, student_name: str = "Phan Thị Thu Phương") -> str:
    title = event.get("title", "Sự kiện rèn luyện")
    unit = event.get("unit", "Trường ĐH Mở TP.HCM")
    points = event.get("points", 0)
    event_time = event.get("event_time", "Theo thông báo trên cổng")
    reg_time = event.get("reg_time", "Xem chi tiết trên cổng")
    target_courses = event.get("target_courses", "Tất cả các khóa")
    reg_url = event.get("register_url", "https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien")
    dieu = event.get("dieu", "")

    is_reg_ok = auto_reg_result[0] if auto_reg_result else False
    reg_msg = auto_reg_result[1] if auto_reg_result else ""

    if is_reg_ok:
        lines = [
            "🎉 [OU - TỰ ĐỘNG ĐĂNG KÝ THÀNH CÔNG] 🎉",
            "━━━━━━━━━━━━━━━━━━━━",
            f"👤 Sinh viên: {student_name} (2654092020)",
            f"✅ Trạng thái: {reg_msg}",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📌 Sự kiện: {title}",
            f"🏢 Đơn vị tổ chức: {unit}"
        ]
    else:
        lines = [
            "🔥 [OU - SỰ KIỆN MỞ ĐĂNG KÝ ĐRL MỚI] 🔥",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📌 Sự kiện: {title}",
            f"🏢 Đơn vị tổ chức: {unit}"
        ]
        if reg_msg:
            lines.append(f"ℹ️ Đăng ký tự động: {reg_msg}")

    if points > 0:
        lines.append(f"🎯 Điểm cộng: +{points:g} ĐRL {f'({dieu})' if dieu else ''}")
    elif dieu:
        lines.append(f"📊 Tiêu chí: {dieu}")

    if event_time and event_time != "None → None":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

    lines.append(f"⏰ Thời gian mở đăng ký: {reg_time}")
    lines.append(f"👥 Khóa áp dụng: {target_courses}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👉 Link kiểm tra trên cổng:\n{reg_url}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🤖 {bot_name}")

    return "\n".join(lines)



def format_ou_upcoming_event_message(event: dict, bot_name: str = "Yuki 5 (OU ĐRL)", student_name: str = "Phan Thị Thu Phương") -> str:
    title = event.get("title", "Sự kiện rèn luyện")
    unit = event.get("unit", "Trường ĐH Mở TP.HCM")
    points = event.get("points", 0)
    event_time = event.get("event_time", "")
    reg_start_str = event.get("reg_start_str") or "Theo thông báo trên cổng"
    reg_end_str = event.get("reg_end_str") or ""
    target_courses = event.get("target_courses", "Tất cả các khóa")
    reg_url = event.get("register_url", "https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien")
    dieu = event.get("dieu", "")

    lines = [
        "⏳ [OU - SỰ KIỆN MỚI: SẮP MỞ ĐĂNG KÝ] ⏳",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Sự kiện: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]
    if points > 0:
        lines.append(f"🎯 Điểm cộng: +{points:g} ĐRL {f'({dieu})' if dieu else ''}")
    elif dieu:
        lines.append(f"📊 Tiêu chí: {dieu}")

    if event_time and event_time != "None → None":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⏰ THỜI GIAN CHO PHÉP ĐĂNG KÝ:")
    lines.append(f"👉 BẮT ĐẦU: {reg_start_str}")
    if reg_end_str:
        lines.append(f"👉 KẾT THÚC: {reg_end_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👥 Khóa áp dụng: {target_courses}")
    lines.append(f"🤖 Bot Yuki đã ghi nhận và sẽ TỰ ĐỘNG ĐĂNG KÝ cho bạn {student_name} (2654092020) ngay khi cổng mở!")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👉 Link cổng: {reg_url}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🤖 {bot_name}")
    return "\n".join(lines)


def format_ou_registered_message(event: dict, bot_name: str = "Yuki 5 (OU ĐRL)", reg_msg: str = "", student_name: str = "Phan Thị Thu Phương", is_success: bool = True) -> str:
    title = event.get("title", "Sự kiện rèn luyện")
    unit = event.get("unit", "Trường ĐH Mở TP.HCM")
    points = event.get("points", 0)
    event_time = event.get("event_time", "")
    reg_url = event.get("register_url", "https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien")
    dieu = event.get("dieu", "")

    header = "🎉 [OU - TỰ ĐỘNG ĐĂNG KÝ THÀNH CÔNG] 🎉" if is_success else "⚠️ [OU - KẾT QUẢ TỰ ĐỘNG ĐĂNG KÝ] ⚠️"
    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 Sinh viên: {student_name} (2654092020)",
        f"✅ Trạng thái: {reg_msg or ('Đã đăng ký thành công!' if is_success else 'Chưa đăng ký được')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Sự kiện: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]
    if points > 0:
        lines.append(f"🎯 Điểm cộng: +{points:g} ĐRL {f'({dieu})' if dieu else ''}")
    if event_time and event_time != "None → None":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👉 Kiểm tra trên cổng:\n{reg_url}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🤖 {bot_name}")
    return "\n".join(lines)

def format_ou_announcement_message(ann: dict, bot_name: str = "Yuki 5 (OU ĐRL)") -> str:
    cat = ann.get("category", "Thông báo")
    content = ann.get("content", "")
    created_at = ann.get("created_at", "Vừa xong")
    url = ann.get("url", "https://renluyensv.ou.edu.vn/20261/diemrl/thongbao")

    lines = [
        f"📢 [OU - THÔNG BÁO CỔNG ĐRL: {cat.upper()}] 📢",
        "━━━━━━━━━━━━━━━━━━━━",
        f"⏰ Ngày tạo: {created_at}",
        f"📄 Nội dung thông báo:\n{content}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👉 Xem trên cổng: {url}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🤖 {bot_name}"
    ]
    return "\n".join(lines)


def send_cookie_error_alert(zalo_inst: ZaloDispatcher, error_source: str, error_detail: str):
    """Gửi cảnh báo lỗi Cookie trực tiếp về Nhóm demo (475259879796859360) và Admin Yuki khi có sự cố cookie."""
    global last_cookie_alert_time
    now_ts = time.time()
    if now_ts - last_cookie_alert_time < COOKIE_ALERT_THROTTLE:
        return
    last_cookie_alert_time = now_ts

    now_vn = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        "⚠️ [Yuki 5 (OU ĐRL) - CẢNH BÁO LỖI COOKIE] ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 Nguồn lỗi: {error_source}\n"
        f"❌ Chi tiết sự cố: {error_detail}\n"
        "🌐 Hệ thống: Đã bật chế độ tự phục hồi / Ẩn danh (Guest Mode).\n"
        f"⏰ Thời gian phát hiện: {now_vn}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 Vui lòng cập nhật Cookie mới tại Web Dashboard (mật khẩu YUKILEGIT0) để hệ thống hoạt động tối ưu nhất!"
    )

    try:
        if zalo_inst and zalo_inst.client:
            # Gửi duy nhất về Admin Trần Lê Phát (7662918962461429024)
            admin_uid = "7662918962461429024"
            try:
                zalo_inst.client.send(Message(text=warn_text), thread_id=admin_uid, thread_type=ThreadType.USER)
                print(f"🚨 [OU] Đã gửi thông báo lỗi cookie tới Admin Trần Lê Phát ({admin_uid})")
            except Exception as e_adm:
                print(f"⚠️ [OU] Lỗi gửi tin tới Admin: {e_adm}")

            database.log_event("WARN", f"Đã gửi cảnh báo lỗi cookie [{error_source}] tới Admin Trần Lê Phát.", db_file=DB_FILE)
    except Exception as e:
        print(f"⚠️ [OU] Lỗi trong hàm send_cookie_error_alert: {e}")


def dispatch_zalo_message(zalo_inst: ZaloDispatcher, message_text: str, item_id: str = "") -> int:
    """Gửi thông báo tới toàn bộ các nhóm và người dùng được kích hoạt (Bao gồm Thu Phương, nhóm demo, Admin)."""
    if not zalo_inst or not zalo_inst.client:
        if not zalo_inst.connect():
            print("❌ [OU] Không thể kết nối Zalo để gửi thông báo!")
            return 0

    cfg = load_config()
    target_groups = cfg.get("zalo", {}).get("target_groups", [])
    sent_count = 0

    for target in target_groups:
        if not target.get("enabled", False):
            continue

        tid = str(target.get("id", "")).strip()
        tname = target.get("name", "Mục nhận tin")
        ttype_str = str(target.get("type", "GROUP")).upper()

        # Nếu là Thu Phương nhưng chưa có ID thì tạm bỏ qua và ghi log nhắc nhở
        if not tid:
            if "phương" in tname.lower():
                print("ℹ️ [OU] Mục 'Thu Phương' chưa có UID Zalo. Đang chờ người dùng cung cấp UID/SĐT.")
            continue

        ttype = ThreadType.USER if ttype_str == "USER" else ThreadType.GROUP

        # Kiểm tra chống lặp nghiêm ngặt từng người nhận
        if item_id and database.is_activity_already_sent_zalo(str(item_id), target_id=tid, db_file=DB_FILE):
            print(f"🛑 [Chống lặp OU] Mục [{item_id}] đã được gửi tới {tname} ({tid}) trước đó, bỏ qua!")
            continue

        try:
            res = zalo_inst.client.send(Message(text=message_text), thread_id=tid, thread_type=ttype)
            sent_count += 1
            print(f"✅ [OU] Đã gửi thông báo thành công tới '{tname}' ({tid} - {ttype_str})")
            try:
                database.record_delivery(
                    post_id=item_id or "OU_NOTIF",
                    post_title="Thông báo điểm rèn luyện OU",
                    source_page="Điểm rèn luyện OU",
                    author="OU Bot",
                    post_url="https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien",
                    content_snippet=message_text[:120],
                    has_form=1 if "LINK ĐIỀN FORM" in message_text else 0,
                    matched_keyword="DRL OU",
                    zalo_target_id=tid,
                    zalo_target_name=tname,
                    target_type=ttype_str,
                    status="SUCCESS",
                    crawled_at=datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y"),
                    db_file=DB_FILE
                )
            except Exception:
                pass
        except Exception as e:
            print(f"❌ [OU] Lỗi gửi tin tới '{tname}' ({tid}): {e}")
            try:
                database.record_delivery(
                    post_id=item_id or "OU_NOTIF",
                    post_title="Thông báo điểm rèn luyện OU",
                    source_page="Điểm rèn luyện OU",
                    author="OU Bot",
                    post_url="https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien",
                    content_snippet=message_text[:120],
                    has_form=1 if "LINK ĐIỀN FORM" in message_text else 0,
                    matched_keyword="DRL OU",
                    zalo_target_id=tid,
                    zalo_target_name=tname,
                    target_type=ttype_str,
                    status="FAILED",
                    crawled_at=datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y"),
                    db_file=DB_FILE
                )
            except Exception:
                pass

    return sent_count


def get_initial_cycle() -> int:
    try:
        st = database.get_all_bot_status(db_file=DB_FILE).get("scan_cycle")
        if st and str(st).isdigit() and int(st) > 0:
            return int(st)
    except Exception:
        pass
    return 0


def main():
    print("=" * 60)
    print("🌟 KHỞI ĐỘNG BOT 5: YUKI 5 (OU ĐIỂM RÈN LUYỆN - ĐH MỞ TP.HCM)")
    print("=" * 60)

    # Khởi tạo cơ sở dữ liệu
    database.init_db(DB_FILE)
    database.init_iuh_db(DB_FILE)
    database.set_bot_enabled(True, db_file=DB_FILE)

    config = load_config()
    bot_name = config.get("bot_name", "Yuki 5 (OU ĐRL)")
    database.log_event("SYSTEM", f"{bot_name} bắt đầu vận hành 24/7.", db_file=DB_FILE)

    # Khởi tạo Zalo Dispatcher
    zalo_disp = ZaloDispatcher(config_file=CONFIG_FILE, db_file=DB_FILE)
    zalo_disp.bot_name = bot_name
    zalo_ok = zalo_disp.connect()
    if zalo_ok:
        print("✅ Kết nối Zalo thành công!")
    else:
        print("⚠️ Chưa thể kết nối Zalo. Sẽ tự kết nối lại khi có tin mới.")

    # Khởi tạo Portal Scraper
    portal_cfg = config.get("ou_portal", {})
    portal_scraper = OUPortalScraper(
        username=portal_cfg.get("username", "2654092020"),
        password=portal_cfg.get("password", "079308035034"),
        config_path=CONFIG_FILE,
        auto_relogin=portal_cfg.get("auto_relogin", True),
        cookies=portal_cfg.get("cookies", {})
    )

    # Đăng nhập Portal lần đầu nếu cần
    print("🔄 Kiểm tra phiên đăng nhập Cổng ĐRL OU...")
    alive, alive_msg = portal_scraper.keep_alive()
    if alive:
        print(f"✅ Cổng ĐRL OU: {alive_msg}")
    else:
        print(f"⚠️ Cổng ĐRL OU: {alive_msg}. Thử tự động đăng nhập...")
        ok_l, msg_l, _ = portal_scraper.auto_login()
        if ok_l:
            print(f"✅ {msg_l}")
        else:
            print(f"⚠️ {msg_l}")
            send_cookie_error_alert(zalo_disp, "Cổng ĐRL OU (SSO)", msg_l)

    # Khởi tạo Facebook Scraper với cookies VAA
    fb_cookies = config.get("fb_cookies", {})
    fb_scraper = OUFacebookScraper(cookies=fb_cookies)

    scan_cycle = get_initial_cycle()
    last_keepalive_time = time.time()

    print(f"🚀 Bắt đầu vòng lặp quét 24/7 cho {bot_name}...")

    while True:
        try:
            if not database.is_bot_enabled(db_file=DB_FILE):
                print(f"⏸️ [{bot_name}] Đang ở trạng thái TẠM DỪNG (Disabled). Chờ 15s...")
                time.sleep(15)
                continue

            scan_cycle += 1
            now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
            cycle_log = f"🔄 Chu kỳ #{scan_cycle} lúc {now_str}"
            print(f"\n{cycle_log}")
            database.set_bot_status("scan_cycle", str(scan_cycle), db_file=DB_FILE)
            database.set_bot_status("last_scan", now_str, db_file=DB_FILE)
            database.set_bot_status("status", "RUNNING", db_file=DB_FILE)

            fresh_cfg = load_config()
            scanner_cfg = fresh_cfg.get("scanner", {})
            fb_cfg = fresh_cfg.get("facebook", {})
            interval = scanner_cfg.get("check_interval_seconds", 25)
            max_age_hours = scanner_cfg.get("max_post_age_hours", 3.0)

            # Cập nhật cookies Facebook nếu có thay đổi từ config
            # Cập nhật cookies Facebook tự động kế thừa từ VAA
            vaa_cfg_path = os.path.join(ROOT_DIR, "vaabot.json")
            if os.path.exists(vaa_cfg_path):
                try:
                    with open(vaa_cfg_path, "r", encoding="utf-8") as vf:
                        v_cfg = json.load(vf)
                        v_cookies = v_cfg.get("fb_cookies", {})
                        if v_cookies:
                            fb_scraper.update_cookies(v_cookies)
                except Exception:
                    pass
            new_fb_cookies = fresh_cfg.get("fb_cookies", {})
            if new_fb_cookies:
                fb_scraper.update_cookies(new_fb_cookies)

            # --- 1. GIỮ WEB SỐNG LIÊN TỤC (Keep-Alive Heartbeat) ---
            if time.time() - last_keepalive_time >= 90:
                last_keepalive_time = time.time()
                is_alive, k_msg = portal_scraper.keep_alive()
                if not is_alive:
                    print(f"⚠️ [OU Portal] {k_msg}")
                    database.log_event("HEARTBEAT_ERR", f"⚠️ Mất kết nối Cổng ĐRL OU: {k_msg}", db_file=DB_FILE)
                    send_cookie_error_alert(zalo_disp, "Cổng ĐRL OU", k_msg)
                else:
                    print(f"💓 [OU Portal Heartbeat] {k_msg}")
                    database.log_event("HEARTBEAT", f"💓 Duy trì phiên Cổng ĐRL OU: {k_msg}", db_file=DB_FILE)

            # --- 2. QUÉT BÀI VIẾT FACEBOOK (Điểm rèn luyện OU) ---
            # --- 2. QUÉT BÀI VIẾT FACEBOOK (Tùy chọn, mặc định TẮT khi chỉ quét dangkysukien) ---
            if fb_cfg.get("enabled", True) and scanner_cfg.get("scan_facebook", True):
                fb_url = fb_cfg.get("target_page", "https://www.facebook.com/diemrenluyenou")
                print(f"🔎 [FB OU] Đang quét: {fb_url} (Không lọc từ khóa)...")
                html = fb_scraper.fetch_url(fb_url)

                if fb_scraper.cookie_expired:
                    print("⚠️ [FB OU] Cookie Facebook hết hạn hoặc bị Checkpoint!")
                    send_cookie_error_alert(zalo_disp, "Facebook Comet (VAA Cookies)", "Cookie Facebook bị Checkpoint/Hết hạn trên Fanpage OU")

                if html:
                    posts = fb_scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=fb_url)
                    print(f"  -> Tìm thấy {len(posts)} bài viết hợp lệ.")
                    new_fb_count = 0

                    for p in posts:
                        pid = p["post_id"]
                        content = p["content"]

                        # Kiểm tra xem bài đã được ghi nhận chưa
                        if not database.is_post_seen(pid, content, db_file=DB_FILE):
                            new_fb_count += 1
                            database.record_seen_post(pid, "Điểm rèn luyện OU", content, db_file=DB_FILE)
                            database.save_crawled_post(
                                post_id=pid,
                                page_name="Điểm rèn luyện OU",
                                author=p.get("author", "Điểm rèn luyện OU"),
                                content=content,
                                post_url=p.get("post_url", ""),
                                posted_time=p.get("posted_time", ""),
                                is_sent_zalo=0,
                                db_file=DB_FILE
                            )
                            database.log_event("POST_NEW", f"Phát hiện bài viết FB mới: {extract_post_title(content, 60)}", db_file=DB_FILE)

                            # Định dạng thông báo đẹp mắt và gửi
                            msg_text = format_ou_fb_message(p, bot_name=bot_name)
                            sent_num = dispatch_zalo_message(zalo_disp, msg_text, item_id=pid)
                            if sent_num > 0:
                                database.mark_post_sent_zalo(pid, db_file=DB_FILE)

                    if new_fb_count > 0:
                        print(f"🎉 [FB OU] Đã xử lý và gửi {new_fb_count} bài viết mới!")
                    database.log_event("FACEBOOK", f"🔎 [FB OU] Đã quét Fanpage: {len(posts)} bài viết hợp lệ ({new_fb_count} bài mới).", db_file=DB_FILE)
                else:
                    print("⚠️ [FB OU] Không tải được nội dung HTML của Fanpage.")

            # --- 3. QUÉT CỔNG ĐIỂM RÈN LUYỆN OU (https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien) ---
            if fresh_cfg.get("ou_portal", {}).get("enabled", True):
                print(f"🔎 [Cổng ĐRL OU] Đang quét: {portal_scraper.EVENTS_URL}...")
                ok_ev, events, msg_ev = portal_scraper.fetch_events()
                if ok_ev:
                    if len(events) == 0:
                        print("  -> Danh sách sự kiện: 0 (Chưa có sự kiện nào mở đăng ký).")
                    else:
                        print(f"  -> Tìm thấy {len(events)} sự kiện trên cổng!")
                        new_ev_count = 0

                        # CHẾ ĐỘ BASELINE: Lần quét đầu tiên khi DB chưa có sự kiện nào
                        try:
                            _conn = database.get_connection(DB_FILE)
                            seen_total = _conn.execute("SELECT COUNT(*) FROM seen_activities").fetchone()[0]
                            _conn.close()
                        except Exception:
                            seen_total = 1

                        if seen_total == 0 and events:
                            for ev in events:
                                eid = ev.get("activity_id") or ev.get("id")
                                ev_rec = dict(ev)
                                ev_rec["status"] = "BASELINE"
                                database.record_seen_activity(ev_rec, is_sent=True, db_file=DB_FILE)
                                database.add_crawled_activity(ev_rec, action_type="BASELINE", is_sent=True, db_file=DB_FILE)
                            msg_bl = f"📌 [OU Baseline] Đã ghi nhận {len(events)} sự kiện hiện có trên cổng ĐRL OU (không gửi Zalo, không đăng ký)."
                            print(msg_bl)
                            database.log_event("SYSTEM", msg_bl, db_file=DB_FILE)
                            events = []

                        auto_reg_enabled = fresh_cfg.get("ou_portal", {}).get("auto_register", False)

                        for ev in events:
                            eid = ev.get("activity_id") or ev.get("id")
                            title = ev.get("title", "Sự kiện")
                            is_upcoming = ev.get("is_upcoming", False)
                            is_open = ev.get("is_open", True)
                            reg_start_str = ev.get("reg_start_str", "")

                            seen_act = database.get_seen_activity(eid, db_file=DB_FILE)

                            if seen_act is None:
                                # Sự kiện mới xuất hiện trên cổng lần đầu
                                if is_upcoming:
                                    # TRƯỜNG HỢP 1: BÀI HIỆN TRƯỚC TRÊN WEB NHƯNG CHƯA MỞ ĐĂNG KÝ
                                    print(f"⏳ [OU Sắp mở ĐK] Sự kiện mới: {title} | Giờ mở: {reg_start_str}")
                                    database.log_event("EVENT_UPCOMING", f"Sự kiện sắp mở ĐK: {title[:50]} (Mở lúc: {reg_start_str})", db_file=DB_FILE)

                                    # Gửi thông báo công bố thời gian đăng ký về Zalo cho Thu Phương và các nhóm
                                    upcoming_msg = format_ou_upcoming_event_message(
                                        ev,
                                        bot_name=bot_name,
                                        student_name=portal_scraper.student_name
                                    )
                                    dispatch_zalo_message(zalo_disp, upcoming_msg, item_id=f"{eid}_UPCOMING")

                                    # Ghi nhận vào DB với trạng thái UPCOMING_NOTIFIED (Chưa đăng ký)
                                    ev_rec = dict(ev)
                                    ev_rec["status"] = "UPCOMING_NOTIFIED"
                                    database.record_seen_activity(ev_rec, is_sent=True, db_file=DB_FILE)
                                    database.add_crawled_activity(ev_rec, action_type="UPCOMING", is_sent=True, db_file=DB_FILE)

                                elif is_open:
                                    # TRƯỜNG HỢP 2: SỰ KIỆN ĐÃ MỞ ĐĂNG KÝ NGAY KHI PHÁT HIỆN
                                    if auto_reg_enabled:
                                        if ev.get("is_registered", False):
                                            print(f"ℹ️ [OU] Sự kiện đã được sinh viên đăng ký trên cổng: {title}")
                                            ok_reg, msg_reg = True, "Sinh viên đã đăng ký tham gia thành công trên cổng"
                                        else:
                                            print(f"⚡ [Tự động đăng ký OU] Sự kiện đang mở đăng ký: {title}...")
                                            ok_reg, msg_reg = portal_scraper.register_event(ev)
                                        reg_status_log = f"✅ Đăng ký thành công: {msg_reg}" if ok_reg else f"⚠️ Kết quả đăng ký: {msg_reg}"
                                        print(f"  -> {reg_status_log}")
                                        database.log_event("AUTO_REGISTER", f"Sự kiện '{title[:50]}': {reg_status_log}", db_file=DB_FILE)

                                        # Ghi nhận vào DB
                                        ev_rec = dict(ev)
                                        ev_rec["status"] = "REGISTERED" if ok_reg else "OPEN_NOTIFIED"
                                        database.record_seen_activity(ev_rec, is_sent=True, db_file=DB_FILE)
                                        database.add_crawled_activity(ev_rec, action_type="AUTO_REGISTER" if ok_reg else "OPEN", is_sent=True, db_file=DB_FILE)

                                        # Gửi thông báo kết quả đăng ký về Zalo
                                        ev_msg = format_ou_event_message(
                                            ev, 
                                            bot_name=bot_name, 
                                            auto_reg_result=(ok_reg, msg_reg),
                                            student_name=portal_scraper.student_name
                                        )
                                        dispatch_zalo_message(zalo_disp, ev_msg, item_id=eid)
                                    else:
                                        print(f"ℹ️ [OU] Tự động đăng ký đang TẮT. Chỉ gửi thông báo sự kiện mới: {title}")
                                        database.log_event("EVENT_OPEN", f"Phát hiện sự kiện mới: {title[:50]} (Tự động đăng ký: TẮT)", db_file=DB_FILE)
                                        ev_rec = dict(ev)
                                        ev_rec["status"] = "OPEN_NOTIFIED"
                                        database.record_seen_activity(ev_rec, is_sent=True, db_file=DB_FILE)
                                        database.add_crawled_activity(ev_rec, action_type="OPEN", is_sent=True, db_file=DB_FILE)

                                        ev_msg = format_ou_event_message(
                                            ev, 
                                            bot_name=bot_name, 
                                            auto_reg_result=None,
                                            student_name=portal_scraper.student_name
                                        )
                                        dispatch_zalo_message(zalo_disp, ev_msg, item_id=eid)

                            else:
                                # Sự kiện đã từng được thấy trước đó
                                cur_status = str(seen_act.get("status") or "").upper()
                                # Nếu sự kiện trước đó ở trạng thái UPCOMING_NOTIFIED (chờ giờ mở đăng ký)
                                # và hiện tại đã đến giờ mở đăng ký (is_open == True):
                                if cur_status == "UPCOMING_NOTIFIED" and is_open:
                                    if auto_reg_enabled:
                                        print(f"🔔 [Đến giờ mở ĐK OU] Kích hoạt tự động đăng ký cho {portal_scraper.student_name}: {title}...")
                                        ok_reg, msg_reg = portal_scraper.register_event(ev)
                                        reg_status_log = f"✅ Đăng ký thành công: {msg_reg}" if ok_reg else f"⚠️ Kết quả đăng ký: {msg_reg}"
                                        print(f"  -> {reg_status_log}")
                                        database.log_event("AUTO_REGISTER", f"Đến giờ mở ĐK '{title[:50]}': {reg_status_log}", db_file=DB_FILE)

                                        if ok_reg:
                                            database.update_activity_status(eid, status="REGISTERED", is_sent=True, db_file=DB_FILE)
                                        else:
                                            database.update_activity_status(eid, status="AUTO_REG_FAILED", is_sent=True, db_file=DB_FILE)

                                        # Gửi thông báo kết quả đăng ký chính thức về Zalo Thu Phương
                                        reg_msg_zalo = format_ou_registered_message(
                                            ev,
                                            bot_name=bot_name,
                                            reg_msg=msg_reg,
                                            student_name=portal_scraper.student_name,
                                            is_success=ok_reg
                                        )
                                        dispatch_zalo_message(zalo_disp, reg_msg_zalo, item_id=f"{eid}_REGISTERED")
                                    else:
                                        print(f"🔔 [Đến giờ mở ĐK OU] Tự động đăng ký đang TẮT. Gửi thông báo mở ĐK cho: {title}...")
                                        database.update_activity_status(eid, status="OPEN_NOTIFIED", is_sent=True, db_file=DB_FILE)
                                        open_msg = format_ou_event_message(
                                            ev,
                                            bot_name=bot_name,
                                            auto_reg_result=None,
                                            student_name=portal_scraper.student_name
                                        )
                                        dispatch_zalo_message(zalo_disp, open_msg, item_id=f"{eid}_NOW_OPEN")

                        if new_ev_count > 0:
                            print(f"🎉 [Cổng ĐRL OU] Đã phát hiện và gửi {new_ev_count} sự kiện mới!")
                    
                    ev_count = len(events)
                    database.log_event("PORTAL", f"🔎 [Cổng ĐRL OU] Đã quét trang đăng ký: {ev_count} sự kiện tìm thấy.", db_file=DB_FILE)
                else:
                    print(f"⚠️ [Cổng ĐRL OU] {msg_ev}")
                    database.log_event("PORTAL_WARN", f"⚠️ Cổng ĐRL OU phản hồi: {msg_ev}", db_file=DB_FILE)

            # Cập nhật trạng thái và ghi log chu kỳ quét chi tiết cho Bot 5 (OU)
            now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
            database.set_bot_status("scan_cycle", str(scan_cycle), db_file=DB_FILE)
            database.set_bot_status("last_scan", now_vn, db_file=DB_FILE)
            database.set_bot_status("total_scans", str(scan_cycle), db_file=DB_FILE)

            ev_str = f"{len(events)} sự kiện" if "events" in locals() else "0 sự kiện"
            fb_str = f"{len(posts)} bài FB" if "posts" in locals() and posts else "0 bài FB"
            detail_msg = f"✅ Chu kỳ #{scan_cycle}: Hoàn tất kiểm tra Cổng ĐRL OU ({ev_str}) & Fanpage ({fb_str}). Tạm nghỉ {interval}s."
            database.log_event("SCAN", detail_msg, db_file=DB_FILE)

            # Nghỉ ngơi giữa các chu kỳ quét
            time.sleep(interval)

        except KeyboardInterrupt:
            print(f"\n🛑 Dừng tiến trình {bot_name}.")
            break
        except Exception as e:
            print(f"❌ [Lỗi chu kỳ {bot_name}]: {e}")
            database.log_event("ERROR", f"Lỗi vòng lặp quét: {e}", db_file=DB_FILE)
            time.sleep(10)


if __name__ == "__main__":
    main()
