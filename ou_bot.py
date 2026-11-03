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

    # Trích xuất tiêu đề bài viết
    title = extract_post_title(content, max_len=140)

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"📰 Tiêu đề: {title}",
        f"🏢 Đơn vị: {author}",
        f"⏰ Đăng lúc: {posted_time}"
    ]

    if has_form:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📝 LINK ĐIỀN FORM / ĐĂNG KÝ:")
        for idx, flink in enumerate(form_links, 1):
            lines.append(f"👉 Link {idx}: {flink}")

    # Nội dung tóm tắt
    preview_len = 350
    content_clean = content.replace("\r", "")
    if len(content_clean) > preview_len:
        content_summary = content_clean[:preview_len].rsplit(" ", 1)[0] + "..."
    else:
        content_summary = content_clean

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📄 Nội dung chi tiết:\n{content_summary}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if post_url:
        lines.append(f"🔗 Xem bài gốc trên Facebook:\n{post_url}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🤖 {bot_name}")

    return "\n".join(lines)


def format_ou_event_message(event: dict, bot_name: str = "Yuki 5 (OU ĐRL)", auto_reg_result: tuple = None, student_name: str = "Phan Thị Thu Phương") -> str:
    title = event.get("title", "Sự kiện rèn luyện")
    unit = event.get("unit", "Trường ĐH Mở TP.HCM")
    points = event.get("points", 0)
    event_time = event.get("event_time", "Theo thông báo trên cổng")
    reg_time = event.get("reg_time", "Xem chi tiết trên cổng")
    target_courses = event.get("target_courses", "Tất cả các khóa")
    reg_url = event.get("register_url", "https://diemrl.ou.edu.vn/test/diemrl/dangkysukien")
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


def format_ou_announcement_message(ann: dict, bot_name: str = "Yuki 5 (OU ĐRL)") -> str:
    cat = ann.get("category", "Thông báo")
    content = ann.get("content", "")
    created_at = ann.get("created_at", "Vừa xong")
    url = ann.get("url", "https://diemrl.ou.edu.vn/test/diemrl/thongbao")

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
    """Gửi cảnh báo lỗi Cookie trực tiếp về Nhóm demo (7456361874031804652) và Admin Yuki khi có sự cố cookie."""
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
            # 1. Gửi về nhóm demo (7456361874031804652)
            demo_group_id = "7456361874031804652"
            try:
                zalo_inst.client.send(Message(text=warn_text), thread_id=demo_group_id, thread_type=ThreadType.GROUP)
                print(f"🚨 [OU] Đã gửi thông báo lỗi cookie vào Nhóm demo ({demo_group_id})")
            except Exception as e_demo:
                print(f"⚠️ [OU] Lỗi gửi tin tới Nhóm demo: {e_demo}")

            # 2. Gửi về Admin Yuki (7662918962461429024)
            admin_uid = "7662918962461429024"
            try:
                zalo_inst.client.send(Message(text=warn_text), thread_id=admin_uid, thread_type=ThreadType.USER)
                print(f"🚨 [OU] Đã gửi thông báo lỗi cookie tới Admin Yuki ({admin_uid})")
            except Exception as e_adm:
                print(f"⚠️ [OU] Lỗi gửi tin tới Admin Yuki: {e_adm}")

            database.log_event("WARN", f"Đã gửi cảnh báo lỗi cookie [{error_source}] tới Nhóm demo & Admin.", db_file=DB_FILE)
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
                    post_url="https://diemrl.ou.edu.vn/test/diemrl/dangkysukien",
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
                    post_url="https://diemrl.ou.edu.vn/test/diemrl/dangkysukien",
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
                    send_cookie_error_alert(zalo_disp, "Cổng ĐRL OU", k_msg)
                else:
                    print(f"💓 [OU Portal Heartbeat] {k_msg}")

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
                else:
                    print("⚠️ [FB OU] Không tải được nội dung HTML của Fanpage.")

            # --- 3. QUÉT CỔNG ĐIỂM RÈN LUYỆN OU (https://diemrl.ou.edu.vn/test/diemrl/dangkysukien) ---
            if fresh_cfg.get("ou_portal", {}).get("enabled", True):
                print(f"🔎 [Cổng ĐRL OU] Đang quét: {portal_scraper.EVENTS_URL}...")
                ok_ev, events, msg_ev = portal_scraper.fetch_events()
                if ok_ev:
                    if len(events) == 0:
                        print("  -> Danh sách sự kiện: 0 (Chưa có sự kiện nào mở đăng ký).")
                    else:
                        print(f"  -> Tìm thấy {len(events)} sự kiện trên cổng!")
                        new_ev_count = 0
                        for ev in events:
                            eid = ev.get("activity_id") or ev.get("id")
                            title = ev.get("title", "Sự kiện")

                            if not database.is_activity_seen(eid, db_file=DB_FILE):
                                new_ev_count += 1
                                # 1. TỰ ĐỘNG ĐĂNG KÝ SỰ KIỆN CHO SINH VIÊN (Phan Thị Thu Phương)
                                print(f"⚡ [Tự động đăng ký OU] Đang đăng ký sự kiện: {title}...")
                                ok_reg, msg_reg = portal_scraper.register_event(ev)
                                reg_status_log = f"✅ Đăng ký thành công: {msg_reg}" if ok_reg else f"⚠️ Chưa thể đăng ký: {msg_reg}"
                                print(f"  -> {reg_status_log}")
                                database.log_event("AUTO_REGISTER", f"Sự kiện '{title[:50]}': {reg_status_log}", db_file=DB_FILE)

                                # 2. Lưu vào DB chống lặp vĩnh viễn
                                database.record_seen_activity(ev, is_sent=True, db_file=DB_FILE)
                                database.add_crawled_activity(ev, action_type="AUTO_REGISTER" if ok_reg else "NEW", is_sent=True, db_file=DB_FILE)
                                database.log_event("ACTIVITY_NEW", f"Phát hiện sự kiện ĐRL OU mới: {title[:60]}", db_file=DB_FILE)

                                # 3. Gửi thông báo kết quả tới Thu Phương và các nhóm chỉ định
                                ev_msg = format_ou_event_message(
                                    ev, 
                                    bot_name=bot_name, 
                                    auto_reg_result=(ok_reg, msg_reg),
                                    student_name=portal_scraper.student_name
                                )
                                dispatch_zalo_message(zalo_disp, ev_msg, item_id=eid)

                        if new_ev_count > 0:
                            print(f"🎉 [Cổng ĐRL OU] Đã phát hiện và gửi {new_ev_count} sự kiện mới!")
                else:
                    print(f"⚠️ [Cổng ĐRL OU] {msg_ev}")

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
