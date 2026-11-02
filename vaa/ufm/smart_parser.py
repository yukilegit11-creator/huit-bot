import re
import json
import requests
import urllib3
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings()

SIGNIN_URL = "https://hoatdong.ufm.edu.vn/Account/SignIn"
CARD_URL = "https://hoatdong.ufm.edu.vn/TheSinhVien"
DANGKY_URL = "https://hoatdong.ufm.edu.vn/DangKy"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
}

def extract_cookie_dict(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        res = {}
        for item in raw:
            if isinstance(item, dict) and "name" in item and "value" in item:
                res[item["name"]] = item["value"]
        return res
    raw_str = str(raw).strip()
    if raw_str.startswith("{") or raw_str.startswith("["):
        try:
            parsed = json.loads(raw_str)
            return extract_cookie_dict(parsed)
        except Exception:
            pass
    # Regex parse ASP.NET cookie strings
    res = {}
    cookie_pairs = re.findall(r'([^=;\s]+)=([^;\s]+)', raw_str)
    for k, v in cookie_pairs:
        if k.startswith(".AspNetCore") or k in ("__RequestVerificationToken", "ASP.NET_SessionId"):
            res[k] = v
    return res

def parse_single_block(text: str) -> dict:
    """Bóc tách thông tin sinh viên từ một khối văn bản."""
    res = {
        "mssv": "",
        "password": "",
        "full_name": "",
        "cookie_data": "",
        "raw_text": text.strip()
    }

    # 1. Trích xuất MSSV (Dãy 10 số, ví dụ 2621008460)
    mssv_m = re.search(r'(?:mssv|mã\s*số(?:\s*sv)?|tài\s*khoản|tk|acc|user|id)[\s:=]*([0-9]{8,11})', text, re.I)
    if mssv_m:
        res["mssv"] = mssv_m.group(1).strip()
    else:
        digits_10 = re.findall(r'\b(2[0-9]{9})\b', text)
        if digits_10:
            res["mssv"] = digits_10[0]
        else:
            any_8_11 = re.findall(r'\b([0-9]{8,11})\b', text)
            if any_8_11:
                res["mssv"] = any_8_11[0]

    # 2. Trích xuất Cookie nếu có chuỗi đặc thù
    json_match = re.search(r'(\[[\s\S]*?\{[\s\S]*?\"name\"[\s\S]*?\]|\{[\s\S]*?\"\.AspNetCore[\s\S]*?\})', text)
    if json_match:
        res["cookie_data"] = json_match.group(1).strip()
    else:
        asp_match = re.search(r'(\.AspNetCore\.Cookies=[A-Za-z0-9_-]+[^\r\n]*)', text)
        if asp_match:
            res["cookie_data"] = asp_match.group(1).strip()

    # 3. Trích xuất Mật khẩu có nhãn rõ ràng
    pass_m = re.search(r'(?:pass|password|mật\s*khẩu|mat\s*khau|mk|pwd)[\s:=]+([^\r\n,;|]+)', text, re.I)
    if pass_m:
        p_val = pass_m.group(1).strip()
        p_val = re.split(r'\s+(?:tên|họ|cookie|mssv)[\s:=]', p_val, flags=re.I)[0].strip()
        if not p_val.startswith("CfDJ8") and len(p_val) < 60:
            res["password"] = p_val

    # 4. Trích xuất Họ tên có nhãn rõ ràng
    name_m = re.search(r'(?:họ\s*và\s*tên|họ\s*tên|tên(?:\s*sv)?|name|sinh\s*viên)[\s:=]+([^\r\n,;|]+)', text, re.I)
    if name_m:
        n_val = name_m.group(1).strip()
        n_val = re.split(r'\s+(?:pass|mk|mật|cookie|mssv)[\s:=]', n_val, flags=re.I)[0].strip()
        if not re.search(r'mssv|pass|mk|cookie', n_val, re.I):
            res["full_name"] = n_val

    # 5. Phân tích dạng 1 dòng phân cách bằng pipe: 2621008460 | pass123 | Nguyen Van A
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        for p in parts:
            if re.match(r'^[0-9]{8,11}$', p):
                res["mssv"] = p
            elif any(k in p.lower() for k in ["cfdj8", ".aspnetcore"]):
                res["cookie_data"] = p
            elif not res["password"] and not re.search(r'^[0-9]{8,11}$', p) and not any(k in p.lower() for k in ['http', 'cfdj8']):
                if len(p.split()) >= 2 and any(c.isalpha() for c in p) and not any(c in p for c in '!@#$%^&*'):
                    res["full_name"] = p
                else:
                    res["password"] = p
            elif not res["full_name"] and len(p.split()) >= 2 and any(c.isalpha() for c in p):
                res["full_name"] = p

    return res

def parse_bulk_text(raw_text: str) -> list:
    """
    Bóc tách hàng loạt từ tin nhắn Zalo, text copy-paste tự do, hoặc nhiều dòng.
    Tự động chia nhỏ khối theo từng MSSV xuất hiện trong văn bản.
    """
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.strip()
    
    # Tìm tất cả các điểm bắt đầu có MSSV
    matches = list(re.finditer(r'(?:(?:mssv|mã\s*số|tk|tài\s*khoản)[\s:=]*)?(\b2[0-9]{9}\b|\b[0-9]{8,11}\b)', text, re.I))
    
    blocks = []
    if len(matches) <= 1:
        blocks = [text]
    else:
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            blocks.append(text[start:end])

    students = []
    for b in blocks:
        parsed = parse_single_block(b)
        if parsed["mssv"]:
            students.append(parsed)

    # Khử trùng lặp theo MSSV (Ưu tiên bản ghi có mật khẩu hoặc cookie)
    unique_map = {}
    for st in students:
        m = st["mssv"]
        if m not in unique_map:
            unique_map[m] = st
        else:
            if st.get("password") and not unique_map[m].get("password"):
                unique_map[m]["password"] = st["password"]
            if st.get("cookie_data") and not unique_map[m].get("cookie_data"):
                unique_map[m]["cookie_data"] = st["cookie_data"]
            if st.get("full_name") and not unique_map[m].get("full_name"):
                unique_map[m]["full_name"] = st["full_name"]

    return list(unique_map.values())


def enrich_student_from_ufm(mssv: str, password: str = "", cookie_raw = None) -> tuple:
    """
    Đăng nhập hoặc xác thực với Cổng UFM:
    - Nếu có mật khẩu: Tự động đăng nhập, lấy cookies tươi mới, và lấy tên thật/lớp/khoa từ Thẻ sinh viên điện tử.
    - Nếu chỉ có cookie: Kiểm tra cookie có truy cập được Thẻ sinh viên không.
    Trả về: (success: bool, message: str, enriched_info: dict)
    """
    clean_mssv = str(mssv).strip()
    session = requests.Session()
    session.headers.update(HEADERS)

    # Trường hợp 1: Có mật khẩu -> Đăng nhập chính thống
    if password and str(password).strip():
        clean_pwd = str(password).strip()
        try:
            r1 = session.get(SIGNIN_URL, verify=False, timeout=12)
            if r1.status_code != 200:
                return False, f"Không thể tải trang đăng nhập UFM (HTTP {r1.status_code})", {}

            soup1 = BeautifulSoup(r1.text, "html.parser")
            tok_tag = soup1.find("input", {"name": "__RequestVerificationToken"})
            token = tok_tag.get("value", "") if tok_tag else ""

            post_data = {
                "__RequestVerificationToken": token,
                "returnUrl": "/",
                "txtuser": clean_mssv,
                "txtpass": clean_pwd
            }

            r2 = session.post(SIGNIN_URL, data=post_data, verify=False, timeout=18, allow_redirects=True)
            if "SignOut" not in r2.text and "Đăng xuất" not in r2.text:
                soup2 = BeautifulSoup(r2.text, "html.parser")
                err_box = soup2.find(class_=lambda c: c and "alert" in c)
                err_msg = err_box.get_text(strip=True) if err_box else "Sai tài khoản hoặc mật khẩu UFM"
                return False, f"Đăng nhập UFM thất bại: {err_msg}", {}

            # Đăng nhập thành công -> Lấy thông tin chính thức từ Thẻ Sinh Viên
            cookies_dict = session.cookies.get_dict()
            card_info = fetch_student_card_info(session)

            return True, "Xác thực và đăng nhập cổng UFM thành công!", {
                "mssv": clean_mssv,
                "password": clean_pwd,
                "full_name": card_info.get("full_name") or f"Sinh viên {clean_mssv}",
                "class_name": card_info.get("class_name", ""),
                "faculty": card_info.get("faculty", ""),
                "study_status": card_info.get("study_status", "Còn học"),
                "cookies": cookies_dict,
                "cookie_status": "valid"
            }
        except Exception as ex:
            return False, f"Lỗi kết nối khi xác thực UFM: {ex}", {}

    # Trường hợp 2: Không có mật khẩu nhưng có Cookie
    cookie_dict = extract_cookie_dict(cookie_raw)
    if cookie_dict:
        try:
            session.cookies.update(cookie_dict)
            card_info = fetch_student_card_info(session)
            if card_info.get("is_authenticated"):
                return True, "Cookie UFM hợp lệ!", {
                    "mssv": clean_mssv,
                    "password": "",
                    "full_name": card_info.get("full_name") or f"Sinh viên {clean_mssv}",
                    "class_name": card_info.get("class_name", ""),
                    "faculty": card_info.get("faculty", ""),
                    "study_status": card_info.get("study_status", "Còn học"),
                    "cookies": cookie_dict,
                    "cookie_status": "valid"
                }
            else:
                return False, "Cookie UFM đã hết hạn và không có mật khẩu để tự đăng nhập lại.", {}
        except Exception as ex:
            return False, f"Lỗi kiểm tra Cookie: {ex}", {}

    return False, "Thiếu cả mật khẩu lẫn cookie hợp lệ để xác thực.", {}


def fetch_student_card_info(session: requests.Session) -> dict:
    """Truy cập trang Thẻ Sinh Viên để bóc tách thông tin chính quy."""
    try:
        r = session.get(CARD_URL, verify=False, timeout=12)
        if r.status_code != 200 or "THẺ SINH VIÊN" not in r.text.upper():
            return {"is_authenticated": False}

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        name_m = re.search(r'HỌ\s*VÀ\s*TÊN:\s*([^\r\n]+)', text, re.I)
        class_m = re.search(r'LỚP:\s*([^\r\n]+)', text, re.I)
        fac_m = re.search(r'KHOA:\s*([^\r\n]+)', text, re.I)
        status_m = re.search(r'TÌNH\s*TRẠNG:\s*([^\r\n]+)', text, re.I)

        return {
            "is_authenticated": True,
            "full_name": name_m.group(1).strip() if name_m else "",
            "class_name": class_m.group(1).strip() if class_m else "",
            "faculty": fac_m.group(1).strip() if fac_m else "",
            "study_status": status_m.group(1).strip() if status_m else "Còn học"
        }
    except Exception:
        return {"is_authenticated": False}


def bulk_enrich_and_save(raw_text: str, database_module, zalo_sender_id: str = "", zalo_sender_name: str = "", db_file=None) -> dict:
    """
    Hàm tổng hợp: Bóc tách văn bản, chạy đa luồng xác thực trên UFM và nạp vào database.
    """
    students = parse_bulk_text(raw_text)
    if not students:
        return {
            "success": False,
            "message": "Không tìm thấy Mã số sinh viên hợp lệ trong nội dung đã nhập.",
            "total": 0,
            "added": 0,
            "failed": 0,
            "items": []
        }

    results = []
    
    def process_one(st):
        mssv = st["mssv"]
        pwd = st.get("password", "")
        raw_cookie = st.get("cookie_data", "")
        fallback_name = st.get("full_name", "")

        ok, msg, enriched = enrich_student_from_ufm(mssv, pwd, raw_cookie)
        
        final_name = enriched.get("full_name") or fallback_name or f"Sinh viên {mssv}"
        final_class = enriched.get("class_name", "")
        final_fac = enriched.get("faculty", "")
        final_cookies = enriched.get("cookies", {})
        final_cookie_str = json.dumps(final_cookies, ensure_ascii=False) if final_cookies else (raw_cookie if isinstance(raw_cookie, str) else json.dumps(raw_cookie))
        cookie_status = "valid" if ok else "expired"

        # Lưu vào database
        saved = database_module.add_or_update_student(
            mssv=mssv,
            full_name=final_name,
            password=pwd,
            cookie_data=final_cookie_str,
            class_name=final_class,
            faculty=final_fac,
            is_active=1,
            cookie_status=cookie_status,
            zalo_sender_id=zalo_sender_id,
            zalo_sender_name=zalo_sender_name,
            db_file=db_file
        )

        return {
            "mssv": mssv,
            "full_name": final_name,
            "class_name": final_class,
            "has_password": bool(pwd),
            "status": "success" if ok else "warning",
            "message": msg,
            "saved": saved
        }

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_one, students))

    success_count = sum(1 for r in results if r["status"] == "success")
    fail_count = len(results) - success_count

    return {
        "success": True,
        "message": f"Đã xử lý xong {len(students)} sinh viên: {success_count} thành công, {fail_count} cần kiểm tra lại.",
        "total": len(students),
        "added": success_count,
        "failed": fail_count,
        "items": results
    }
