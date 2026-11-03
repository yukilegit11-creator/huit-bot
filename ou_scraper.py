import os
import sys
import time
import json
import re
import hashlib
from datetime import datetime, timezone, timedelta
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

try:
    import ddddocr
    HAS_DDDDOCR = True
except ImportError:
    HAS_DDDDOCR = False

VN_TZ = timezone(timedelta(hours=7))
_global_ocr = None

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}


class OUPortalScraper:
    BASE_URL = "https://diemrl.ou.edu.vn/test"
    LOGIN_URL = "https://diemrl.ou.edu.vn/test/auth/ousso/login"
    EVENTS_URL = "https://diemrl.ou.edu.vn/test/diemrl/dangkysukien"
    THONGBAO_URL = "https://diemrl.ou.edu.vn/test/diemrl/thongbao"

    def __init__(self, username="2654092020", password="079308035034", config_path=None, auto_relogin=True, cookies=None):
        self.username = str(username).strip()
        self.password = str(password).strip()
        self.config_path = config_path
        self.auto_relogin = bool(auto_relogin)
        self.session = requests.Session()
        self.session.headers.update(DESKTOP_HEADERS)
        self.last_touch_time = 0
        self.is_logged_in = False
        self.cookie_expired = False
        self.student_name = "Phan Thị Thu Phương"
        
        if cookies and isinstance(cookies, dict):
            for k, v in cookies.items():
                self.session.cookies.set(k, v, domain="diemrl.ou.edu.vn")

    def auto_login(self, max_attempts: int = 5) -> tuple:
        """
        Tự động giải mã Captcha bằng AI OCR (ddddocr) và đăng nhập vào cổng HCMCOU SSO / Điểm rèn luyện OU.
        Trả về (success: bool, message: str, cookies_dict: dict)
        """
        global _global_ocr
        if not HAS_DDDDOCR:
            return False, "Thiếu thư viện ddddocr để giải mã Captcha SSO OU", {}
        if not self.username or not self.password:
            return False, "Chưa cấu hình tài khoản/mật khẩu sinh viên OU", {}

        if _global_ocr is None:
            _global_ocr = ddddocr.DdddOcr(show_ad=False)
        ocr = _global_ocr

        for attempt in range(1, max_attempts + 1):
            try:
                s = requests.Session()
                s.headers.update(DESKTOP_HEADERS)

                # 1. Khởi động luồng SSO từ diemrl.ou.edu.vn
                r1 = s.get(self.LOGIN_URL, verify=False, timeout=15)
                soup = BeautifulSoup(r1.text, "html.parser")
                form = soup.find("form", id="login_form") or soup.find("form")
                if not form:
                    time.sleep(0.5)
                    continue

                token_tag = form.find("input", {"name": "_token"})
                csrf_token = token_tag.get("value") if token_tag else ""

                cap_img = form.find("img", src=re.compile(r"captcha", re.IGNORECASE))
                if not cap_img:
                    time.sleep(0.5)
                    continue

                cap_url = cap_img.get("src", "")
                if not cap_url.startswith("http"):
                    cap_url = "https://id.ou.edu.vn" + cap_url

                # 2. Tải ảnh Captcha và nhận diện bằng AI
                r_cap = s.get(cap_url, verify=False, timeout=12)
                cap_raw = ocr.classification(r_cap.content)
                cap_code = re.sub(r"[^a-zA-Z0-9]", "", cap_raw).strip()

                if len(cap_code) < 3:
                    time.sleep(0.4)
                    continue

                # 3. Gửi thông tin đăng nhập lên SSO OU
                login_data = {
                    "_token": csrf_token,
                    "form-usertype": "svcq",
                    "form-username": self.username,
                    "form-password": self.password,
                    "form-captcha": cap_code
                }

                r2 = s.post("https://id.ou.edu.vn/auth/login", data=login_data, verify=False, timeout=15)

                # 4. Kiểm tra xem đã hoàn tất chuỗi xác thực SSO và về trang chủ ĐRL chưa
                is_success = (
                    "dangkysukien" in r2.url
                    or "diemrl/home" in r2.url
                    or "diemrl.ou.edu.vn" in r2.url
                    or any("diemrl.ou.edu.vn" in h.url for h in r2.history)
                )

                if is_success:
                    # Kiểm tra lại bằng cách gọi thẳng trang sự kiện
                    r_verify = s.get(self.EVENTS_URL, verify=False, timeout=15)
                    if r_verify.status_code == 200 and "DiemRL" in r_verify.text:
                        self.session = s
                        self.is_logged_in = True
                        self.cookie_expired = False
                        self.last_touch_time = time.time()

                        cookie_dict = s.cookies.get_dict()
                        # Trích xuất tên sinh viên nếu có
                        soup_v = BeautifulSoup(r_verify.text, "html.parser")
                        tag_app = soup_v.find("script", {"data-page": "app"})
                        if tag_app:
                            try:
                                d_app = json.loads(tag_app.string)
                                u_info = d_app.get("props", {}).get("auth", {}).get("user", {})
                                if u_info.get("display_name"):
                                    self.student_name = u_info["display_name"]
                            except Exception:
                                pass

                        # Cập nhật cookies vào file config_ou.json nếu có
                        if self.config_path and os.path.exists(self.config_path):
                            try:
                                with open(self.config_path, "r", encoding="utf-8") as f_cfg:
                                    cdata = json.load(f_cfg)
                                cdata.setdefault("ou_portal", {})["cookies"] = cookie_dict
                                if self.student_name:
                                    cdata["ou_portal"]["student_name"] = self.student_name
                                with open(self.config_path, "w", encoding="utf-8") as f_cfg:
                                    json.dump(cdata, f_cfg, ensure_ascii=False, indent=2)
                            except Exception as e:
                                print(f"⚠️ Lỗi lưu cookie OU vào file cấu hình: {e}")

                        return True, f"Tự động giải captcha '{cap_code}' và đăng nhập SSO OU thành công (thử #{attempt})", cookie_dict

                time.sleep(0.5)
            except Exception as e:
                time.sleep(0.5)

        self.cookie_expired = True
        return False, f"Đăng nhập SSO OU thất bại sau {max_attempts} lần giải captcha", {}

    def keep_alive(self) -> tuple:
        """
        Gửi yêu cầu heartbeat ping nhẹ tới cổng ĐRL OU để giữ session sống liên tục (24/7).
        Nếu session hết hạn hoặc bị đăng xuất, tự động gọi auto_login() ngay lập tức.
        """
        try:
            r = self.session.get(self.EVENTS_URL, verify=False, timeout=15, allow_redirects=True)
            if r.status_code == 200 and ("auth/login" not in r.url) and ("DiemRL" in r.text or "data-page" in r.text):
                self.last_touch_time = time.time()
                self.is_logged_in = True
                self.cookie_expired = False
                return True, "Cổng ĐRL OU đang hoạt động bình thường (Session Alive)"
            
            # Session đã hết hạn hoặc bị chuyển hướng về trang login
            print("⚠️ Session ĐRL OU đã hết hạn. Đang tự động đăng nhập lại...")
            if self.auto_relogin:
                ok, msg, _ = self.auto_login()
                return ok, msg
            else:
                self.cookie_expired = True
                return False, "Session ĐRL OU đã hết hạn (Tự động đăng nhập đang tắt)"
        except Exception as e:
            if self.auto_relogin:
                ok, msg, _ = self.auto_login()
                return ok, msg
            self.cookie_expired = True
            return False, f"Lỗi kiểm tra session ĐRL OU: {e}"

    def _extract_page_props(self, response) -> dict:
        """Trích xuất Inertia props từ JSON response hoặc thẻ <script data-page='app'> trong HTML."""
        if not response or response.status_code != 200:
            return {}
        # 1. Thử parse trực tiếp JSON
        try:
            data = response.json()
            if isinstance(data, dict) and "props" in data:
                return data["props"]
        except Exception:
            pass

        # 2. Parse từ HTML nhúng thẻ data-page="app"
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            tag = soup.find("script", {"data-page": "app"})
            if tag and tag.string:
                data = json.loads(tag.string)
                if isinstance(data, dict) and "props" in data:
                    return data["props"]
        except Exception:
            pass
        return {}

    def fetch_events(self) -> tuple:
        """
        Bóc tách danh sách sự kiện đăng ký điểm rèn luyện từ https://diemrl.ou.edu.vn/test/diemrl/dangkysukien
        Trả về (success: bool, events: list, message: str)
        """
        try:
            r = self.session.get(self.EVENTS_URL, verify=False, timeout=15)
            if r.status_code != 200 or "auth/login" in r.url:
                if self.auto_relogin:
                    self.auto_login()
                    r = self.session.get(self.EVENTS_URL, verify=False, timeout=15)

            props = self._extract_page_props(r)
            if not props and "DiemRL" not in r.text and "auth/login" in r.url:
                return False, [], "Session hết hạn khi tải sự kiện ĐRL OU"

            events = []
            bdg = props.get("bdg", {})

            if isinstance(bdg, dict):
                bdg_items = list(bdg.values())
            elif isinstance(bdg, list):
                bdg_items = bdg
            else:
                bdg_items = []

            stt = 1
            for group in bdg_items:
                if not isinstance(group, dict):
                    continue
                dieu_no = group.get("STTDIEU") or group.get("sttdieu") or ""
                nhom_ch = group.get("NHOM_CAUHOI", {})
                nhom_list = list(nhom_ch.values()) if isinstance(nhom_ch, dict) else nhom_ch

                for nhom in nhom_list:
                    if not isinstance(nhom, dict):
                        continue
                    cauhoi_dict = nhom.get("CAUHOI", {})
                    ch_list = list(cauhoi_dict.values()) if isinstance(cauhoi_dict, dict) else cauhoi_dict

                    for q in ch_list:
                        if not isinstance(q, dict):
                            continue
                        qid = q.get("ID") or q.get("id")
                        title = q.get("CAUHOI") or q.get("noidung") or "Sự kiện rèn luyện"
                        clean_title = BeautifulSoup(str(title), "html.parser").get_text(strip=True)

                        ngaybd = q.get("NGAYBDSK") or ""
                        ngaykt = q.get("NGAYKTSK") or ""
                        thoigianbd = q.get("THOIGIANBD", "")

                        t_bddky = q.get("THOIGIANBDDKY")
                        t_ktdky = q.get("THOIGIANKTDKY")
                        str_bddky = datetime.fromtimestamp(t_bddky, tz=VN_TZ).strftime("%d/%m/%Y %H:%M") if t_bddky else ""
                        str_ktdky = datetime.fromtimestamp(t_ktdky, tz=VN_TZ).strftime("%d/%m/%Y %H:%M") if t_ktdky else ""

                        makhoa = q.get("MAKHOA", "")
                        tenkhoa = q.get("PB_TEN") or q.get("pb_ten") or (f"Khoa {makhoa}" if makhoa else "Toàn trường")

                        dt_raw = str(q.get("DOITUONG_KHOAHOC", "") or "").strip()
                        dt_list = [x.strip() for x in dt_raw.split(",") if x.strip()] if dt_raw else ["Tất cả các khóa"]

                        answers = q.get("TRALOI", {})
                        ans_list = list(answers.values()) if isinstance(answers, dict) else answers
                        diem_val = 0
                        for a in ans_list:
                            if isinstance(a, dict) and a.get("DIEM"):
                                try:
                                    diem_val = max(diem_val, float(a.get("DIEM")))
                                except Exception:
                                    pass

                        events.append({
                            "activity_id": f"OU_EV_{qid}",
                            "id": f"OU_EV_{qid}",
                            "raw_id": str(qid),
                            "dieu": f"Điều {dieu_no}" if dieu_no else "",
                            "title": clean_title,
                            "unit": tenkhoa,
                            "points": diem_val,
                            "event_time": f"{ngaybd} → {ngaykt}" + (f" ({thoigianbd})" if thoigianbd else ""),
                            "reg_time": f"{str_bddky} → {str_ktdky}" if str_bddky else "Xem chi tiết trên cổng",
                            "target_courses": ", ".join(dt_list),
                            "register_url": self.EVENTS_URL,
                            "first_seen": datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
                        })
                        stt += 1

            return True, events, f"Lấy thành công {len(events)} sự kiện từ Cổng ĐRL OU"
        except Exception as e:
            return False, [], f"Lỗi lấy sự kiện từ Cổng ĐRL OU: {e}"

    def fetch_announcements(self) -> tuple:
        """
        Bóc tách danh sách thông báo từ https://diemrl.ou.edu.vn/test/diemrl/thongbao
        Trả về (success: bool, announcements: list, message: str)
        """
        try:
            r = self.session.get(self.THONGBAO_URL, verify=False, timeout=15)
            props = self._extract_page_props(r)
            items = props.get("items", [])
            announcements = []
            for item in items:
                aid = item.get("id")
                cat = item.get("category", "Thông báo")
                content = item.get("content", "")
                created_at = item.get("created_at", "")
                clean_content = BeautifulSoup(str(content), "html.parser").get_text(strip=True)
                announcements.append({
                    "id": f"OU_TB_{aid}",
                    "raw_id": str(aid),
                    "category": cat,
                    "content": clean_content,
                    "created_at": created_at,
                    "url": self.THONGBAO_URL
                })
            return True, announcements, f"Lấy thành công {len(announcements)} thông báo ĐRL OU"
        except Exception as e:
            return False, [], f"Lỗi lấy thông báo ĐRL OU: {e}"


class OUFacebookScraper:
    def __init__(self, cookies: dict = None, page_url: str = "https://www.facebook.com/diemrenluyenou"):
        self.page_url = page_url
        self.session = requests.Session()
        self.session.headers.update(DESKTOP_HEADERS)
        self.cookie_expired = False
        if cookies:
            self.session.cookies.update(cookies)

    def update_cookies(self, cookies: dict):
        self.session.cookies.clear()
        self.session.cookies.update(cookies)
        self.cookie_expired = False

    def fetch_url(self, url: str) -> str:
        target_url = url.replace("mbasic.facebook.com", "www.facebook.com").replace("m.facebook.com", "www.facebook.com")
        try:
            resp = self.session.get(target_url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                text_low = resp.text.lower()
                is_chk = "/checkpoint/" in resp.url or "/login/" in resp.url or '"is_checkpointed":true' in text_low or 'id="login_top"' in text_low
                if is_chk:
                    self.cookie_expired = True
                    print(f"⚠️ Phát hiện Cookie Facebook OU bị Checkpoint/Hết hạn. Chuyển sang quét Ẩn danh (Guest Mode)...")
                    anon = requests.get(target_url, headers=DESKTOP_HEADERS, timeout=30, allow_redirects=True)
                    if anon.status_code == 200:
                        return anon.text
                return resp.text
            else:
                anon = requests.get(target_url, headers=DESKTOP_HEADERS, timeout=30, allow_redirects=True)
                return anon.text if anon.status_code == 200 else ""
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Facebook OU: {e}")
            try:
                anon = requests.get(target_url, headers=DESKTOP_HEADERS, timeout=30, allow_redirects=True)
                return anon.text if anon.status_code == 200 else ""
            except Exception:
                return ""

    def parse_posts(self, html_text: str, max_age_hours: float = 3.0) -> list:
        if not html_text:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/json"})
        posts = []
        now_ts = datetime.now(timezone.utc).timestamp()

        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                self._extract_from_json(data, posts, now_ts, max_age_hours)
            except Exception:
                pass

        # Deduplicate by post_id
        unique_posts = []
        seen_pids = set()
        for p in posts:
            pid = p["post_id"]
            if pid not in seen_pids:
                seen_pids.add(pid)
                unique_posts.append(p)

        return unique_posts

    def _extract_from_json(self, obj, posts: list, now_ts: float, max_age_hours: float):
        if isinstance(obj, dict):
            if "message" in obj and isinstance(obj["message"], dict) and "text" in obj["message"]:
                txt = str(obj["message"]["text"]).strip()
                if len(txt) >= 15:
                    pid = str(obj.get("post_id") or obj.get("id") or "")
                    if not pid or len(pid) < 5:
                        pid = hashlib.md5(txt[:120].encode("utf-8")).hexdigest()

                    # Extract creation time
                    ctime = obj.get("creation_time") or obj.get("publish_time")
                    post_time_str = "Vừa xong"
                    if ctime and isinstance(ctime, (int, float)):
                        if ctime > 1e11:
                            ctime = ctime / 1000.0
                        # Lọc thời gian bài viết (<= max_age_hours)
                        age_hours = (now_ts - ctime) / 3600.0
                        if age_hours > max_age_hours:
                            return
                        post_time_str = datetime.fromtimestamp(ctime, tz=timezone.utc).astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

                    author = "Điểm rèn luyện OU"
                    if obj.get("actors") and isinstance(obj["actors"], list) and len(obj["actors"]) > 0:
                        author = obj["actors"][0].get("name", author)

                    url = obj.get("permalink_url") or obj.get("url") or f"https://www.facebook.com/{pid}"

                    posts.append({
                        "post_id": pid,
                        "content": txt,
                        "post_url": url,
                        "posted_time": post_time_str,
                        "author": author,
                        "creation_time": ctime
                    })

            for v in obj.values():
                self._extract_from_json(v, posts, now_ts, max_age_hours)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_from_json(item, posts, now_ts, max_age_hours)
