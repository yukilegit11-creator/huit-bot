from scraper import FacebookCometScraper
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



def parse_ou_timestamp(val):
    if not val:
        return None
    if isinstance(val, (int, float)):
        return val / 1000.0 if val > 1e11 else float(val)
    if isinstance(val, str):
        val = val.strip()
        try:
            num = float(val)
            return num / 1000.0 if num > 1e11 else num
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(val, fmt).replace(tzinfo=VN_TZ)
                return dt.timestamp()
            except ValueError:
                pass
    return None

class OUPortalScraper:
    DOMAIN = "https://renluyensv.ou.edu.vn"
    DEFAULT_NHHK = "20261"

    def __init__(self, username="2654092020", password="079308035034", config_path=None, auto_relogin=True, cookies=None, nhhk=None):
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
        
        self.nhhk = str(nhhk).strip() if nhhk else self.get_current_nhhk()
        self.update_endpoints(self.nhhk)
        
        if cookies and isinstance(cookies, dict):
            for k, v in cookies.items():
                self.session.cookies.set(k, v, domain="ou.edu.vn")

    def get_current_nhhk(self) -> str:
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                val = cfg.get("ou_portal", {}).get("nhhk")
                if val:
                    return str(val).strip()
            except Exception:
                pass
        try:
            r = requests.get(self.DOMAIN, headers=DESKTOP_HEADERS, verify=False, timeout=8)
            m = re.search(r"href=[\"']/(\d{5})[\"']", r.text)
            if m:
                return m.group(1)
        except Exception:
            pass
        return self.DEFAULT_NHHK

    def update_endpoints(self, nhhk: str):
        self.nhhk = nhhk or self.DEFAULT_NHHK
        self.BASE_URL = f"https://renluyensv.ou.edu.vn/{self.nhhk}"
        self.LOGIN_URL = f"https://renluyensv.ou.edu.vn/auth/ousso/login?nhhk={self.nhhk}"
        self.EVENTS_URL = f"https://renluyensv.ou.edu.vn/{self.nhhk}/diemrl/dangkysukien"
        self.THONGBAO_URL = f"https://renluyensv.ou.edu.vn/{self.nhhk}/diemrl/thongbao"
        self.REGISTER_URL = f"https://renluyensv.ou.edu.vn/{self.nhhk}/diemrl/sv_dkthamgiask" 

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
                    or "renluyensv.ou.edu.vn" in r2.url
                    or any("renluyensv.ou.edu.vn" in h.url for h in r2.history)
                )

                if is_success:
                    # Kiểm tra lại bằng cách gọi thẳng trang sự kiện
                    r_verify = s.get(self.EVENTS_URL, verify=False, timeout=15)
                    if r_verify.status_code == 200 and ("DiemRL" in r_verify.text or "data-page" in r_verify.text):
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
                                cdata["ou_portal"]["nhhk"] = self.nhhk
                                cdata["ou_portal"]["base_url"] = self.BASE_URL
                                cdata["ou_portal"]["login_url"] = self.LOGIN_URL
                                cdata["ou_portal"]["events_url"] = self.EVENTS_URL
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
            kqdg = props.get("kqdg", [])
            registered_cauhoi_ids = set()
            if isinstance(kqdg, list):
                for item in kqdg:
                    if isinstance(item, dict):
                        cid = item.get("IDCAUHOI") or item.get("idcauhoi")
                        if cid:
                            registered_cauhoi_ids.add(str(cid))

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

                        current_ts = float(props.get("current_timestamp") or time.time())
                        t_bddky = q.get("THOIGIANBDDKY")
                        t_ktdky = q.get("THOIGIANKTDKY")
                        reg_start_ts = parse_ou_timestamp(t_bddky)
                        reg_end_ts = parse_ou_timestamp(t_ktdky)

                        str_bddky = datetime.fromtimestamp(reg_start_ts, tz=VN_TZ).strftime("%H:%M ngày %d/%m/%Y") if reg_start_ts else ""
                        str_ktdky = datetime.fromtimestamp(reg_end_ts, tz=VN_TZ).strftime("%H:%M ngày %d/%m/%Y") if reg_end_ts else ""

                        if reg_start_ts:
                            is_upcoming = (current_ts < reg_start_ts)
                            is_closed = bool(reg_end_ts and current_ts > reg_end_ts)
                            is_open = (not is_upcoming) and (not is_closed)
                        else:
                            is_upcoming = False
                            is_open = True
                            is_closed = False

                        makhoa = q.get("MAKHOA", "")
                        tenkhoa = q.get("PB_TEN") or q.get("pb_ten") or (f"Khoa {makhoa}" if makhoa else "Toàn trường")

                        dt_raw = str(q.get("DOITUONG_KHOAHOC", "") or "").strip()
                        dt_list = [x.strip() for x in dt_raw.split(",") if x.strip()] if dt_raw else ["Tất cả các khóa"]

                        iddieu = q.get("IDDIEU") or q.get("iddieu") or group.get("IDDIEU") or group.get("id") or 1
                        answers = q.get("TRALOI", {})
                        ans_list = list(answers.values()) if isinstance(answers, dict) else answers
                        diem_val = 0
                        chosen_ans_id = None
                        for a in ans_list:
                            if isinstance(a, dict):
                                try:
                                    pts = float(a.get("DIEM", 0))
                                    if pts >= diem_val:
                                        diem_val = pts
                                        chosen_ans_id = a.get("ID") or a.get("id")
                                except Exception:
                                    pass

                        events.append({
                            "activity_id": f"OU_EV_{qid}",
                            "id": f"OU_EV_{qid}",
                            "raw_id": str(qid),
                            "iddieu": iddieu,
                            "answer_id": chosen_ans_id,
                            "answers": ans_list,
                            "dieu": f"Điều {dieu_no}" if dieu_no else "",
                            "title": clean_title,
                            "unit": tenkhoa,
                            "points": diem_val,
                            "event_time": f"{ngaybd} → {ngaykt}" + (f" ({thoigianbd})" if thoigianbd else ""),
                            "reg_time": f"{str_bddky} → {str_ktdky}" if str_bddky else "Xem chi tiết trên cổng",
                            "target_courses": ", ".join(dt_list),
                            "reg_start_ts": reg_start_ts,
                            "reg_end_ts": reg_end_ts,
                            "reg_start_str": str_bddky,
                            "reg_end_str": str_ktdky,
                            "is_open": is_open,
                            "is_upcoming": is_upcoming,
                            "is_closed": is_closed,
                            "is_registered": str(qid) in registered_cauhoi_ids,
                            "register_url": self.EVENTS_URL,
                            "first_seen": datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
                        })
                        stt += 1

            return True, events, f"Lấy thành công {len(events)} sự kiện từ Cổng ĐRL OU"
        except Exception as e:
            return False, [], f"Lỗi lấy sự kiện từ Cổng ĐRL OU: {e}"

    def register_event(self, event: dict) -> tuple:
        """
        Tự động thực hiện đăng ký tham gia sự kiện trên cổng ĐRL OU.
        Duyệt qua tất cả các ca/buổi/phiên (TRALOI) cho đến khi tìm được mục còn chỗ và đăng ký thành công.
        Đối soát thực tế 100% bằng danh sách xác nhận (kqdg) của cổng trường.
        Trả về: (success: bool, message: str, registered_session_name: str, points: float)
        """
        import urllib.parse
        try:
            # 1. Đảm bảo session còn sống
            alive, _ = self.keep_alive()
            if not alive and self.auto_relogin:
                self.auto_login()

            s = self.session
            # 2. Lấy version Inertia và XSRF token
            r_get = s.get(self.EVENTS_URL, verify=False, timeout=15)
            version = ""
            soup = BeautifulSoup(r_get.text, "html.parser")
            tag_app = soup.find("script", {"data-page": "app"})
            if tag_app and tag_app.string:
                try:
                    d_page = json.loads(tag_app.string)
                    version = d_page.get("version", "")
                except Exception:
                    pass

            xsrf_token = ""
            for cookie in s.cookies:
                if cookie.name == "XSRF-TOKEN":
                    xsrf_token = urllib.parse.unquote(cookie.value)
                    if "ou.edu.vn" in getattr(cookie, "domain", ""):
                        break

            iddieu = event.get("iddieu") or 1
            idcauhoi = event.get("raw_id") or event.get("id")

            answers = event.get("answers", [])
            if not answers:
                ans_dict = event.get("TRALOI", {})
                answers = list(ans_dict.values()) if isinstance(ans_dict, dict) else ans_dict

            if not answers:
                answers = [{
                    "ID": event.get("answer_id") or 1,
                    "DIEM": event.get("points") or 0,
                    "NOIDUNG": event.get("title", "")
                }]

            headers = {
                "X-Inertia": "true",
                "X-Inertia-Version": version,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
                "Accept": "text/html, application/xhtml+xml",
                "Referer": self.EVENTS_URL
            }
            if xsrf_token:
                headers["X-XSRF-TOKEN"] = xsrf_token

            reg_url = self.REGISTER_URL
            last_err_msg = ""

            for idx, a in enumerate(answers, 1):
                if not isinstance(a, dict):
                    continue
                aid = a.get("ID") or a.get("id")
                if not aid:
                    continue
                noidung = BeautifulSoup(str(a.get("NOIDUNG") or ""), "html.parser").get_text(strip=True)
                diem = float(a.get("DIEM") or event.get("points") or 0)

                payload = {
                    "iddieu": iddieu,
                    "idcauhoi": idcauhoi,
                    "idtraloi": aid,
                    "d": diem
                }

                r_post = s.post(reg_url, json=payload, headers=headers, verify=False, timeout=15)

                if r_post.status_code in (200, 302, 303):
                    props_post = self._extract_page_props(r_post)
                    flash_post = props_post.get("flash", {}) if isinstance(props_post, dict) else {}
                    err_post = flash_post.get("error") or flash_post.get("message")

                    if err_post and any(k in err_post.lower() for k in ["đầy", "tối đa", "hết", "trùng"]):
                        last_err_msg = err_post
                        continue

                    # 3. Đối soát thực tế trên cổng để chắc chắn sự kiện đã được lưu vào kqdg
                    time.sleep(1)
                    r_check = s.get(self.EVENTS_URL, verify=False, timeout=15)
                    props_check = self._extract_page_props(r_check)
                    kqdg_check = props_check.get("kqdg", [])
                    reg_ids = set()
                    if isinstance(kqdg_check, list):
                        for item in kqdg_check:
                            if isinstance(item, dict):
                                cid = item.get("IDCAUHOI") or item.get("idcauhoi")
                                if cid:
                                    reg_ids.add(str(cid))

                    if str(idcauhoi) in reg_ids:
                        session_name = noidung if noidung else f"Mục #{aid}"
                        return True, f"Cổng trường xác nhận đăng ký thành công: {session_name}", session_name, diem

                    flash_check = props_check.get("flash", {}) if isinstance(props_check, dict) else {}
                    err_msg = (
                        flash_post.get("error")
                        or flash_check.get("error")
                        or flash_post.get("message")
                        or flash_check.get("message")
                        or "Cổng không ghi nhận đăng ký"
                    )
                    last_err_msg = err_msg
                    continue
                elif r_post.status_code == 419:
                    if self.auto_relogin:
                        self.auto_login()
                        return self.register_event(event)
                    return False, "Phiên đăng ký hết hạn (419 Page Expired)", "", 0
                else:
                    last_err_msg = f"HTTP {r_post.status_code}: {r_post.text[:100]}"
                    continue

            return False, f"Tất cả {len(answers)} ca/mục đều không thể đăng ký ({last_err_msg or 'Kín chỗ hoặc đã đóng'})", "", 0

        except Exception as e:
            return False, f"Lỗi ngoại lệ khi đăng ký sự kiện: {e}", "", 0

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


class OUFacebookScraper(FacebookCometScraper):
    def __init__(self, cookies: dict = None, page_url: str = "https://www.facebook.com/diemrenluyenou"):
        super().__init__(cookies=cookies)
        self.page_url = page_url
