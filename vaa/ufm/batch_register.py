import os
import sys
import json
import time
import re
import urllib3
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

urllib3.disable_warnings()

import database
from zalo_sender import ZaloDispatcher

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Trạng thái tiến trình bắn đăng ký theo thời gian thực
BATCH_PROGRESS = {
    "is_running": False,
    "activity_id": "",
    "activity_title": "",
    "total": 0,
    "completed": 0,
    "success": 0,
    "failed": 0,
    "start_time": 0,
    "logs": []
}

def parse_cookie_data(raw_data) -> dict:
    """Chuyển đổi linh hoạt mọi định dạng Cookie sang dict."""
    if not raw_data:
        return {}
    if isinstance(raw_data, dict):
        return raw_data
    if isinstance(raw_data, list):
        res = {}
        for item in raw_data:
            if isinstance(item, dict) and "name" in item and "value" in item:
                res[item["name"]] = item["value"]
        return res

    raw_str = str(raw_data).strip()
    if raw_str.startswith("{") or raw_str.startswith("["):
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                res = {}
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        res[item["name"]] = item["value"]
                return res
        except Exception:
            pass

    # Dạng chuỗi cookie thông thường: key=value; key2=value2
    res = {}
    for part in raw_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            res[k.strip()] = v.strip()
    return res

def check_student_cookie(student: dict) -> tuple:
    """Kiểm tra tính hợp lệ của Cookie sinh viên."""
    mssv = str(student.get("mssv", "")).strip()
    cookie_dict = parse_cookie_data(student.get("cookie_data"))
    if not cookie_dict:
        database.update_student_cookie_status(mssv, "expired")
        return False, student.get("full_name", ""), "Không có dữ liệu Cookie"

    session = requests.Session()
    for k, v in cookie_dict.items():
        session.cookies.set(k, v, domain="hoatdong.ufm.edu.vn")

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://hoatdong.ufm.edu.vn/"
    })

    try:
        r = session.get("https://hoatdong.ufm.edu.vn/DangKy", verify=False, timeout=12, allow_redirects=True)
        if "SignOut" in r.text or "Đăng xuất" in r.text:
            soup = BeautifulSoup(r.text, "html.parser")
            detected_name = ""
            for tag in soup.find_all(["span", "div", "p"]):
                txt = tag.get_text(strip=True)
                if mssv in txt and len(txt) < 80:
                    detected_name = txt.replace(mssv, "").replace("-", "").strip()
                    break

            final_name = detected_name or student.get("full_name") or mssv
            database.update_student_cookie_status(mssv, "valid", full_name=final_name)
            return True, final_name, "Cookie hợp lệ"
        else:
            database.update_student_cookie_status(mssv, "expired")
            return False, student.get("full_name", ""), "Cookie đã hết hạn hoặc chưa đăng nhập"
    except Exception as e:
        database.update_student_cookie_status(mssv, "error")
        return False, student.get("full_name", ""), f"Lỗi kết nối: {e}"

def register_single_student(student: dict, activity_id: str) -> tuple:
    """Thực hiện đăng ký 1 hoạt động cụ thể cho 1 sinh viên."""
    mssv = str(student.get("mssv", "")).strip()
    name = student.get("full_name") or mssv
    cookie_dict = parse_cookie_data(student.get("cookie_data"))

    if not cookie_dict:
        msg = "Thiếu dữ liệu Cookie"
        database.update_student_registered(mssv, activity_id, msg)
        return mssv, name, False, msg

    session = requests.Session()
    for k, v in cookie_dict.items():
        session.cookies.set(k, v, domain="hoatdong.ufm.edu.vn")

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://hoatdong.ufm.edu.vn/DangKy",
        "Origin": "https://hoatdong.ufm.edu.vn"
    })

    try:
        # Bước 1: GET trang /DangKy để lấy token Anti-Forgery của chính tài khoản này
        r_get = session.get("https://hoatdong.ufm.edu.vn/DangKy", verify=False, timeout=12)
        if "SignOut" not in r_get.text and "Đăng xuất" not in r_get.text:
            # Nếu cookie hết hạn nhưng tài khoản có password -> tự động relogin lấy cookie mới ngay lập tức
            pwd = student_data.get("password", "")
            if pwd:
                from smart_parser import enrich_student_from_ufm
                ok_login, msg_login, enriched = enrich_student_from_ufm(mssv, pwd)
                if ok_login and enriched.get("cookies"):
                    cookie_dict = enriched["cookies"]
                    session.cookies.update(cookie_dict)
                    database.update_student_cookie_status(mssv, "valid")
                    r_get = session.get("https://hoatdong.ufm.edu.vn/DangKy", verify=False, timeout=12)

            if "SignOut" not in r_get.text and "Đăng xuất" not in r_get.text:
                msg = "Cookie đã hết hạn (Không có mật khẩu hoặc mật khẩu sai)"
                database.update_student_cookie_status(mssv, "expired")
                database.update_student_registered(mssv, activity_id, msg)
                return mssv, name, False, msg

        soup = BeautifulSoup(r_get.text, "html.parser")
        token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
        token_val = token_tag.get("value") if token_tag else ""

        if not token_val:
            msg = "Không tìm thấy __RequestVerificationToken"
            database.update_student_registered(mssv, activity_id, msg)
            return mssv, name, False, msg

        # Bước 2: POST form đăng ký
        clean_aid = re.sub(r"^[A-Z]+_", "", str(activity_id).strip())
        post_url = f"https://hoatdong.ufm.edu.vn/DangKy/DangKy/{clean_aid}"
        payload = {"__RequestVerificationToken": token_val}

        r_post = session.post(post_url, data=payload, verify=False, timeout=15, allow_redirects=True)

        resp_text_lower = r_post.text.lower()
        if "thành công" in resp_text_lower or "đã đăng ký thành công" in resp_text_lower:
            msg = "Đăng ký thành công!"
            database.update_student_registered(mssv, clean_aid, msg)
            return mssv, name, True, msg
        elif "đã đăng ký" in resp_text_lower or "bạn đã đăng ký" in resp_text_lower:
            msg = "Đã đăng ký trước đó"
            database.update_student_registered(mssv, clean_aid, msg)
            return mssv, name, True, msg
        elif any(k in resp_text_lower for k in ["hết số lượng", "đầy", "đủ số lượng", "hết slot", "đã hết"]):
            msg = "Hoạt động đã hết slot"
            database.update_student_registered(mssv, clean_aid, msg)
            return mssv, name, False, msg
        elif "chưa mở" in resp_text_lower:
            msg = "Hoạt động chưa mở đăng ký"
            database.update_student_registered(mssv, clean_aid, msg)
            return mssv, name, False, msg
        else:
            if r_post.status_code == 200:
                msg = "Đã gửi request (Xem lịch sử trên web)"
                database.update_student_registered(mssv, clean_aid, msg)
                return mssv, name, True, msg
            else:
                msg = f"HTTP {r_post.status_code}"
                database.update_student_registered(mssv, clean_aid, msg)
                return mssv, name, False, msg

    except Exception as e:
        msg = f"Lỗi kết nối: {e}"
        database.update_student_registered(mssv, activity_id, msg)
        return mssv, name, False, msg


def execute_batch_registration(activity_id: str, activity_title: str = "", max_workers: int = 6):
    """Tiến trình thực thi bắn đăng ký cho toàn bộ tài khoản sinh viên đang bật."""
    global BATCH_PROGRESS

    students = database.get_all_students(active_only=True)
    total_students = len(students)

    BATCH_PROGRESS["is_running"] = True
    BATCH_PROGRESS["activity_id"] = str(activity_id)
    BATCH_PROGRESS["activity_title"] = activity_title or f"Hoạt động ID {activity_id}"
    BATCH_PROGRESS["total"] = total_students
    BATCH_PROGRESS["completed"] = 0
    BATCH_PROGRESS["success"] = 0
    BATCH_PROGRESS["failed"] = 0
    BATCH_PROGRESS["start_time"] = time.time()
    BATCH_PROGRESS["logs"] = []

    database.log_event("SNIPER", f"🚀 BẮT ĐẦU BẮN ĐĂNG KÝ HÀNG LOẠT cho {total_students} tài khoản (HĐ: {activity_id})")

    results = []

    def _worker(st):
        res = register_single_student(st, activity_id)
        time.sleep(0.15) # Giãn cách nhẹ để giữ đường truyền ổn định
        return res

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, s) for s in students]
        for f in futures:
            mssv, name, is_ok, msg = f.result()
            BATCH_PROGRESS["completed"] += 1
            if is_ok:
                BATCH_PROGRESS["success"] += 1
                status_icon = "✅"
            else:
                BATCH_PROGRESS["failed"] += 1
                status_icon = "❌"

            log_entry = f"{status_icon} [{mssv}] {name}: {msg}"
            BATCH_PROGRESS["logs"].append(log_entry)
            results.append((mssv, name, is_ok, msg))

    duration = round(time.time() - BATCH_PROGRESS["start_time"], 1)
    BATCH_PROGRESS["is_running"] = False

    summary_str = f"Hoàn tất bắn đăng ký ID {activity_id}: Thành công {BATCH_PROGRESS['success']}/{total_students} ({duration}s)"
    print(f"🎉 {summary_str}")
    database.log_event("SNIPER", summary_str)

    # Gửi thông báo báo cáo kết quả tổng kết vào Zalo
    try:
        zalo = ZaloDispatcher(CONFIG_FILE)
        if zalo.connect():
            report_lines = [
                "🎯 [UFM - BÁO CÁO KẾT QUẢ BẮN ĐĂNG KÝ HÀNG LOẠT] 🎯",
                "━━━━━━━━━━━━━━━━━━━━",
                f"📌 Hoạt động: [{activity_id}] {activity_title}",
                f"👥 Tổng số sinh viên xử lý: {total_students}",
                f"✅ Thành công: {BATCH_PROGRESS['success']} sinh viên",
                f"❌ Thất bại / Hết slot: {BATCH_PROGRESS['failed']} sinh viên",
                f"⏱️ Tổng thời gian thực thi: {duration} giây",
                "━━━━━━━━━━━━━━━━━━━━",
                "👉 Xem chi tiết danh sách từng sinh viên trên Web Dashboard:",
                "http://localhost:5004",
                "━━━━━━━━━━━━━━━━━━━━",
                "🤖 Yuki 4 (UFM Batch Sniper)"
            ]
            report_msg = "\n".join(report_lines)
            
            # Gửi vào các nhóm Zalo đang bật
            for grp in zalo.zalo_cfg.get("target_groups", []):
                if grp.get("enabled"):
                    from zlapi.models import Message, ThreadType
                    t_type = ThreadType.USER if str(grp.get("type")).upper() == "USER" else ThreadType.GROUP
                    try:
                        zalo.client.send(Message(text=report_msg), thread_id=str(grp.get("id")), thread_type=t_type)
                    except Exception:
                        pass
    except Exception as e:
        print(f"⚠️ Không thể gửi báo cáo Zalo: {e}")

    return results
