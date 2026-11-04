from datetime import datetime, timezone, timedelta
import os
import re
import json
import time
import hashlib
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

try:
    import ddddocr
    HAS_DDDDOCR = True
except ImportError:
    HAS_DDDDOCR = False

_global_ocr = None

class IUHPortalScraper:
    BASE_URL = "https://doantn.iuh.edu.vn"
    TARGET_URL = "https://doantn.iuh.edu.vn/doanvien.html"

    def __init__(self, cookie_raw=None, username=None, password=None, config_path=None, auto_relogin=True):
        self.config_path = config_path
        self.auto_relogin = bool(auto_relogin)
        self.student_name = ""

        # Tự động nạp thông tin từ file config nếu chưa được cung cấp
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f_cfg:
                    cfg_init = json.load(f_cfg)
                p_init = cfg_init.get("portal", {})
                if not cookie_raw:
                    cookie_raw = p_init.get("phpsessid", "")
                if not username:
                    username = p_init.get("username", "")
                if not password:
                    password = p_init.get("password", "")
                self.student_name = p_init.get("student_name", "")
            except Exception:
                pass

        self.phpsessid = self.extract_phpsessid(cookie_raw)
        self.username = str(username).strip() if username else ""
        self.password = str(password).strip() if password else ""
        self.session = requests.Session()
        if self.phpsessid:
            self.session.cookies.set("PHPSESSID", self.phpsessid, domain="doantn.iuh.edu.vn")
        
        # Thiết lập Browser Headers chuẩn Chrome Desktop chống bị chặn / đá phiên
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://doantn.iuh.edu.vn/home.html",
            "Connection": "keep-alive"
        }
        self.last_touch_time = time.time()

    @staticmethod
    def extract_phpsessid(raw) -> str:
        if not raw:
            return ""
        if isinstance(raw, dict):
            return raw.get("PHPSESSID", "")
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("name") == "PHPSESSID":
                    return item.get("value", "")
        raw_str = str(raw).strip()
        if raw_str.startswith("[") or raw_str.startswith("{"):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("name") == "PHPSESSID":
                            return item.get("value", "")
                elif isinstance(parsed, dict):
                    return parsed.get("PHPSESSID", "")
            except Exception:
                pass
        
        for part in raw_str.split(";"):
            part = part.strip()
            if part.startswith("PHPSESSID="):
                return part.split("=", 1)[1].strip()
        
        if re.match(r"^[a-zA-Z0-9_-]{15,45}$", raw_str):
            return raw_str

        return raw_str

    def update_cookie(self, new_cookie_raw):
        self.phpsessid = self.extract_phpsessid(new_cookie_raw)
        self.session.cookies.clear()
        if self.phpsessid:
            self.session.cookies.set("PHPSESSID", self.phpsessid, domain="doantn.iuh.edu.vn")
        self.last_touch_time = time.time()

    def auto_login(self, max_attempts: int = 12) -> tuple:
        """
        Tự động giải mã Captcha bằng AI OCR (ddddocr) và đăng nhập vào portal IUH.
        Lưu cookies PHPSESSID và thông tin sinh viên vào config_iuh.json.
        Trả về (success: bool, message: str, new_phpsessid: str)
        """
        if not HAS_DDDDOCR:
            return False, "Thiếu thư viện ddddocr trên môi trường", ""
        if not self.username or not self.password:
            return False, "Chưa cung cấp MSSV hoặc mật khẩu để tự đăng nhập", ""

        global _global_ocr
        if _global_ocr is None:
            _global_ocr = ddddocr.DdddOcr(show_ad=False)
        ocr = _global_ocr

        for attempt in range(1, max_attempts + 1):
            s = requests.Session()
            s.headers.update(self.headers)
            s.headers["Referer"] = "https://doantn.iuh.edu.vn/login.html"

            try:
                # 1. Tải trang đăng nhập
                s.get("https://doantn.iuh.edu.vn/login.html", verify=False, timeout=12)

                # 2. Tải ảnh captcha
                r_cap = s.get("https://doantn.iuh.edu.vn/components/com_contact/captcha.php", verify=False, timeout=12)
                cap_raw = ocr.classification(r_cap.content)
                cap_code = re.sub(r"[^a-zA-Z0-9]", "", cap_raw).strip()

                if len(cap_code) != 5:
                    time.sleep(0.3)
                    continue

                # 3. Gửi thông tin đăng nhập
                data = {
                    "mssv": self.username,
                    "password": self.password,
                    "security_code": cap_code,
                    "btLogin": "Đăng nhập"
                }
                s.post("https://doantn.iuh.edu.vn/login.html", data=data, verify=False, timeout=12)

                # 4. Kiểm tra trang cá nhân
                r_portal = s.get(self.TARGET_URL, verify=False, timeout=12)
                if any(k in r_portal.text for k in ["doanvien.html@profile", "KẾT QUẢ TRA CỨU", "Đăng xuất", "tblDoanvien", "MSSV:"]):
                    new_sid = s.cookies.get("PHPSESSID") or s.cookies.get_dict().get("PHPSESSID")
                    if not new_sid:
                        for c in s.cookies:
                            if c.name == "PHPSESSID":
                                new_sid = c.value
                                break

                    m_name = re.search(r"Sinh viên:\s*([^	\n\r<]+)", r_portal.text)
                    if m_name:
                        self.student_name = m_name.group(1).strip()

                    if new_sid:
                        self.phpsessid = new_sid
                        self.session = s
                        self.session.cookies.set("PHPSESSID", new_sid, domain="doantn.iuh.edu.vn")
                        self.last_touch_time = time.time()

                        # Lưu tự động vào file config_iuh.json
                        if self.config_path and os.path.exists(self.config_path):
                            try:
                                with open(self.config_path, "r", encoding="utf-8") as f:
                                    cdata = json.load(f)
                                cdata.setdefault("portal", {})["phpsessid"] = new_sid
                                if self.student_name:
                                    cdata["portal"]["student_name"] = self.student_name
                                cdata["portal"]["last_login"] = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
                                with open(self.config_path, "w", encoding="utf-8") as f:
                                    json.dump(cdata, f, ensure_ascii=False, indent=2)
                                print(f"💾 [IUH Scraper] Đã lưu Cookies mới ({new_sid[:8]}...) vào {self.config_path}!")
                            except Exception as e_save:
                                print(f"⚠️ Lỗi lưu config IUH: {e_save}")

                        st_info = f" ({self.student_name})" if self.student_name else ""
                        return True, f"Tự giải captcha '{cap_code}' và đăng nhập thành công{st_info} (lần thử #{attempt})", new_sid
                time.sleep(0.3)
            except Exception:
                time.sleep(0.3)

        return False, f"Tự đăng nhập không thành công sau {max_attempts} lần giải captcha", ""

    def keep_alive(self) -> tuple:
        """
        Gửi yêu cầu heartbeat ping nhẹ tới cổng portal IUH để reset idle timer của PHP session.
        Nếu session hết hạn hoặc bị đăng xuất, tự động gọi auto_login() ngay lập tức để lấy cookie mới và lưu config!
        """
        if not self.phpsessid:
            if self.auto_relogin and self.username and self.password and HAS_DDDDOCR:
                ok, msg, sid = self.auto_login()
                if ok:
                    return True, f"Đã tự khởi tạo phiên mới thành công: {msg}"
            return False, "Chưa thiết lập Cookie PHPSESSID"
        try:
            r = self.session.get(self.TARGET_URL, headers=self.headers, verify=False, timeout=15)
            self.last_touch_time = time.time()
            if r.status_code != 200:
                if self.auto_relogin and HAS_DDDDOCR:
                    ok, msg, _ = self.auto_login()
                    if ok:
                        return True, f"Phiên đã được tự động phục hồi qua AI Auto-Login ({msg})"
                return False, f"Heartbeat HTTP error: {r.status_code}"

            html = r.text
            if ("login.html" in html and ("<meta http-equiv='refresh'" in html or "URL=login.html" in html)) or ("KẾT QUẢ TRA CỨU" not in html and "tblDoanvien" not in html and "Đăng xuất" not in html):
                print("⚠️ Session Cổng IUH đã hết hạn. Đang tự động đăng nhập lại và lưu cookies...")
                if self.auto_relogin and self.username and self.password and HAS_DDDDOCR:
                    ok, msg, sid = self.auto_login()
                    if ok:
                        return True, f"Phiên đã được tự động phục hồi và lưu cookies ({msg})"
                return False, "Cookie PHPSESSID đã hết hạn hoặc bị đăng xuất"

            return True, "Session PHP vẫn sống và hợp lệ (Keep-Alive OK)"
        except Exception as e:
            if self.auto_relogin and HAS_DDDDOCR:
                ok, msg, _ = self.auto_login()
                if ok:
                    return True, f"Tự động kết nối lại thành công sau lỗi: {msg}"
            return False, f"Lỗi kết nối heartbeat: {e}"

    def fetch_activities(self, retries: int = 2) -> tuple:
        if not self.phpsessid:
            if self.auto_relogin and self.username and self.password and HAS_DDDDOCR:
                ok, msg, _ = self.auto_login()
                if not ok:
                    return False, f"Chưa thiết lập PHPSESSID ({msg})", []
            else:
                return False, "Chưa thiết lập Cookie PHPSESSID", []

        last_err = None
        r = None
        for attempt in range(retries):
            try:
                r = self.session.get(self.TARGET_URL, headers=self.headers, verify=False, timeout=20)
                self.last_touch_time = time.time()
                break
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(2)

        if r is None:
            return False, f"Lỗi kết nối tới doantn.iuh.edu.vn: {last_err}", []

        if r.status_code != 200:
            return False, f"Mã trạng thái HTTP {r.status_code}", []

        html = r.text

        if "login.html" in html and ("<meta http-equiv='refresh'" in html or "URL=login.html" in html):
            # Session hết hạn -> Thử tự động đăng nhập lại bằng AI OCR
            if self.auto_relogin and self.username and self.password and HAS_DDDDOCR:
                login_ok, login_msg, new_sid = self.auto_login()
                if login_ok:
                    print(f"🔄 [IUH Auto-Login] {login_msg}! Đang cào lại dữ liệu ngay lập tức...")
                    return self.fetch_activities(retries=1)
                else:
                    return False, f"Phiên đăng nhập hết hạn ({login_msg})", []
            return False, "Cookie PHPSESSID đã hết hạn hoặc chưa đăng nhập vào hệ thống", []

        soup = BeautifulSoup(html, "html.parser")
        tab1 = soup.find(id="tab1")
        if not tab1:
            tables = soup.find_all("table")
            for tbl in tables:
                if "Hoạt động" in tbl.get_text() or "Học kỳ" in tbl.get_text():
                    tab1 = tbl
                    break

        if not tab1:
            return True, "Trang cá nhân không có bảng Tab 1 (có thể không có hoạt động nào)", []

        modals = {}
        for m in soup.find_all(class_="modal"):
            mid = m.get("id", "").strip()
            body = m.find(class_="modal-body")
            if mid and body:
                body_text = body.get_text(separator="\n", strip=True)
                modals[mid] = body_text

        activities = []
        rows = tab1.find_all("tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 5:
                continue

            a_tag = tds[1].find("a")
            if a_tag:
                title = a_tag.get_text(strip=True)
                data_target = a_tag.get("data-target", "").replace("#", "").strip()
            else:
                title = tds[1].get_text(strip=True)
                data_target = ""

            if not title or title.lower() in ("hoạt động", "tt", "nội dung"):
                continue

            if data_target:
                activity_id = data_target.replace("myModal_", "").strip()
            else:
                activity_id = hashlib.md5(title.encode("utf-8")).hexdigest()[:12]

            semester = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            points_raw = tds[3].get_text(strip=True) if len(tds) > 3 else "0"
            try:
                points = float(re.findall(r"[\d\.]+", points_raw)[0]) if re.findall(r"[\d\.]+", points_raw) else 0.0
            except Exception:
                points = 0.0

            deadline = tds[4].get_text(strip=True) if len(tds) > 4 else ""
            status = tds[5].get_text(strip=True) if len(tds) > 5 else "Đang mở"

            slots_matches = re.findall(r"\((\d+\s*/\s*\d+)\)", title)
            slots = slots_matches[-1].replace(" ", "") if slots_matches else ""

            details = modals.get(data_target, "")

            activities.append({
                "activity_id": activity_id,
                "title": title,
                "semester": semester,
                "points": points,
                "deadline": deadline,
                "status": status,
                "slots": slots,
                "details": details,
                "url": self.TARGET_URL
            })

        return True, f"Bóc tách thành công {len(activities)} hoạt động", activities

    def check_cookie_validity(self) -> tuple:
        is_ok, msg, _ = self.fetch_activities()
        return is_ok, msg
