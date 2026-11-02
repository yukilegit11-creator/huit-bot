import os
import sys
import re
import json
import urllib3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

urllib3.disable_warnings()

VN_TZ = timezone(timedelta(hours=7))

class UFMPortalScraper:
    BASE_URL = "https://hoatdong.ufm.edu.vn"
    SIGNIN_URL = "https://hoatdong.ufm.edu.vn/Account/SignIn"
    DANGKY_URL = "https://hoatdong.ufm.edu.vn/DangKy"
    SEMESTER_URL = "https://hoatdong.ufm.edu.vn/Activity/SemesterActivities"
    CUSTOM_URL = "https://hoatdong.ufm.edu.vn/CustomActivity"

    def __init__(self, cookies_data=None, username=None, password=None, config_path=None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        
        # Tự động nạp thông tin từ config.json nếu không truyền vào
        if (not cookies_data or not username or not password) and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                portal = cfg.get("ufm_portal", {})
                if not cookies_data:
                    cookies_data = portal.get("cookies", {})
                if not username:
                    username = portal.get("username", "")
                if not password:
                    password = portal.get("password", "")
            except Exception:
                pass

        self.username = username
        self.password = password
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://hoatdong.ufm.edu.vn/",
            "Connection": "keep-alive"
        }
        self.session.headers.update(self.headers)
        
        if cookies_data:
            self.set_cookies(cookies_data)

    def set_cookies(self, cookies_data):
        """Hỗ trợ nạp cookies từ dict, list chrome format hoặc JSON string."""
        if not cookies_data:
            return
        
        cookie_dict = {}
        if isinstance(cookies_data, str):
            try:
                cookies_data = json.loads(cookies_data)
            except Exception:
                for part in cookies_data.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        cookie_dict[k.strip()] = v.strip()

        if isinstance(cookies_data, list):
            for c in cookies_data:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    cookie_dict[c["name"]] = c["value"]
        elif isinstance(cookies_data, dict):
            cookie_dict = cookies_data

        for k, v in cookie_dict.items():
            self.session.cookies.set(k, v, domain="hoatdong.ufm.edu.vn")

    def get_cookie_dict(self) -> dict:
        return self.session.cookies.get_dict()

    def save_current_cookies_to_config(self):
        """Lưu cookie mới nhất vào file config.json."""
        if not self.config_path or not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "ufm_portal" not in cfg:
                cfg["ufm_portal"] = {}
            cfg["ufm_portal"]["cookies"] = self.get_cookie_dict()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print("💾 Đã cập nhật Cookie UFM tự động vào config.json")
        except Exception as e:
            print(f"⚠️ Lỗi lưu cookie UFM vào config.json: {e}")

    def login(self, username=None, password=None) -> tuple:
        """Tự động đăng nhập vào Cổng Hoạt Động UFM."""
        u = username or self.username
        p = password or self.password
        if not u or not p:
            return False, "Thiếu thông tin tài khoản hoặc mật khẩu UFM"

        try:
            r1 = self.session.get(self.SIGNIN_URL, verify=False, timeout=15)
            if r1.status_code != 200:
                return False, f"Không thể tải trang đăng nhập (HTTP {r1.status_code})"

            soup = BeautifulSoup(r1.text, "html.parser")
            token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
            if not token_tag:
                return False, "Không tìm thấy __RequestVerificationToken trên trang đăng nhập"

            token = token_tag.get("value", "")
            data = {
                "__RequestVerificationToken": token,
                "returnUrl": "/",
                "txtuser": u,
                "txtpass": p
            }

            r2 = self.session.post(self.SIGNIN_URL, data=data, verify=False, timeout=20, allow_redirects=True)
            if "SignOut" in r2.text or "Đăng xuất" in r2.text:
                self.save_current_cookies_to_config()
                return True, "Đăng nhập UFM thành công!"

            # Kiểm tra xem có thông báo lỗi từ server không
            soup2 = BeautifulSoup(r2.text, "html.parser")
            err_box = soup2.find(class_=lambda c: c and "alert" in c)
            err_text = err_box.get_text(strip=True) if err_box else "Sai tài khoản hoặc mật khẩu"
            return False, f"Đăng nhập thất bại: {err_text}"

        except Exception as e:
            return False, f"Lỗi kết nối khi đăng nhập UFM: {e}"

    def ensure_authenticated(self) -> bool:
        """Kiểm tra tính hợp lệ của phiên đăng nhập; nếu hết hạn thì tự động relogin."""
        try:
            r = self.session.get(self.DANGKY_URL, verify=False, timeout=15, allow_redirects=False)
            if r.status_code == 200 and ("Đăng xuất" in r.text or "SignOut" in r.text):
                return True
        except Exception:
            pass

        print("🔄 Phiên đăng nhập UFM đã hết hạn hoặc chưa kích hoạt, đang tiến hành tự động relogin...")
        success, msg = self.login()
        if success:
            print(f"✅ {msg}")
            return True
        else:
            print(f"❌ {msg}")
            return False

    def fetch_dangky_activities(self) -> tuple:
        """
        Bóc tách các hoạt động trên trang https://hoatdong.ufm.edu.vn/DangKy
        Nơi sinh viên đăng ký tham gia các hoạt động trực tiếp.
        """
        if not self.ensure_authenticated():
            return False, "Phiên đăng nhập UFM không hợp lệ", []

        try:
            r = self.session.get(self.DANGKY_URL, verify=False, timeout=20)
            if r.status_code != 200:
                return False, f"Mã trạng thái HTTP {r.status_code}", []

            soup = BeautifulSoup(r.text, "html.parser")
            activities = []

            # Tìm tất cả thẻ tiêu đề h5 chứa link chi tiết
            for h5 in soup.find_all("h5"):
                a_tag = h5.find("a")
                if not a_tag:
                    continue

                full_title = a_tag.get_text(strip=True)
                detail_path = a_tag.get("href", "")
                detail_url = f"{self.BASE_URL}{detail_path}" if detail_path.startswith("/") else detail_path

                # Trích xuất activity_id từ [ID 16454]
                id_match = re.search(r"\[ID\s*(\d+)\]", full_title, re.IGNORECASE)
                if id_match:
                    activity_id = id_match.group(1).strip()
                    clean_title = re.sub(r"\[ID\s*\d+\]\s*", "", full_title).strip()
                else:
                    id_match2 = re.search(r"Details/([a-zA-Z0-9_-]+)", detail_path)
                    activity_id = id_match2.group(1) if id_match2 else full_title[:30]
                    clean_title = full_title

                # Tìm thẻ container chứa các thông tin chi tiết
                container = h5.find_parent("div", class_="p-5") or h5.find_parent("div")
                unit = "Chưa rõ đơn vị"
                event_time = "Chưa rõ thời gian"
                location = "Chưa rõ địa điểm"
                group_criteria = ""
                points = 0.0
                ctxh = 0.0

                if container:
                    for p in container.find_all("p"):
                        txt = p.get_text(strip=True)
                        txt_lower = txt.lower()
                        if "đơn vị:" in txt_lower:
                            unit = txt.split(":", 1)[1].strip()
                        elif "thời gian:" in txt_lower:
                            event_time = txt.split(":", 1)[1].strip()
                        elif "địa điểm:" in txt_lower:
                            location = txt.split(":", 1)[1].strip()
                        elif "nhóm:" in txt_lower:
                            group_criteria = txt.split(":", 1)[1].strip()
                            # Trích xuất điểm ĐRL
                            pt_match = re.search(r"([\d\.]+)\s*(?:đrl|điểm)", txt, re.IGNORECASE)
                            if pt_match:
                                try:
                                    points = float(pt_match.group(1))
                                except Exception:
                                    pass
                            # Trích xuất điểm CTXH
                            ctxh_match = re.search(r"(\d+)\s*ctxh", txt, re.IGNORECASE)
                            if ctxh_match:
                                try:
                                    ctxh = float(ctxh_match.group(1))
                                except Exception:
                                    pass

                # Trạng thái đăng ký và Slot
                status = "Đang mở đăng ký"
                is_full = False
                card_root = container.parent if container else h5.parent
                if card_root:
                    btns = card_root.find_all(["button", "a"])
                    for b in btns:
                        if b.name == "a" and b.get("href") == detail_path:
                            continue
                        btn_txt = b.get_text(strip=True)
                        if any(k in btn_txt.lower() for k in ["đầy", "đủ số lượng", "hết", "chưa mở", "kết thúc", "hết slot"]):
                            status = btn_txt
                            is_full = True
                        elif "đăng ký" in btn_txt.lower() and not b.has_attr("disabled"):
                            status = "Đang mở đăng ký (Còn slot)"
                            is_full = False

                activities.append({
                    "activity_id": f"DK_{activity_id}",
                    "raw_id": activity_id,
                    "title": clean_title,
                    "unit": unit,
                    "event_time": event_time,
                    "location": location,
                    "group_criteria": group_criteria,
                    "points": points,
                    "ctxh": ctxh,
                    "status": status,
                    "is_full": is_full,
                    "detail_url": detail_url,
                    "register_url": self.DANGKY_URL,
                    "source": "Trang Mở Đăng Ký UFM (/DangKy)"
                })

            return True, f"Bóc tách thành công {len(activities)} hoạt động đăng ký", activities

        except Exception as e:
            return False, f"Lỗi bóc tách /DangKy: {e}", []

    def fetch_semester_activities(self, limit: int = 40) -> tuple:
        """
        Bóc tách danh sách hoạt động học kỳ tại https://hoatdong.ufm.edu.vn/Activity/SemesterActivities
        Bao gồm các hoạt động vừa được phê duyệt / tạo mới trên hệ thống.
        """
        if not self.ensure_authenticated():
            return False, "Phiên đăng nhập UFM không hợp lệ", []

        try:
            r = self.session.get(self.SEMESTER_URL, verify=False, timeout=25)
            if r.status_code != 200:
                return False, f"Mã trạng thái HTTP {r.status_code}", []

            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if not table:
                return True, "Không tìm thấy bảng hoạt động học kỳ", []

            rows = table.find_all("tr")
            activities = []

            for r_tag in rows[1:limit + 1]:
                cells = [td.get_text(strip=True) for td in r_tag.find_all(["td", "th"])]
                if len(cells) < 5:
                    continue

                raw_id_str = cells[0].replace("#", "").strip()
                title = cells[1].strip()
                unit = cells[2].strip()
                group_criteria = cells[3].strip()
                organize_date = cells[4].strip()

                # Dự đoán điểm từ nhóm tiêu chí nếu có
                points = 0.0
                pt_match = re.search(r"([\d\.]+)\s*(?:đrl|điểm)", group_criteria, re.IGNORECASE)
                if pt_match:
                    try:
                        points = float(pt_match.group(1))
                    except Exception:
                        pass

                activities.append({
                    "activity_id": f"SEM_{raw_id_str}",
                    "raw_id": raw_id_str,
                    "title": title,
                    "unit": unit,
                    "event_time": organize_date,
                    "location": "Theo thông báo của đơn vị",
                    "group_criteria": group_criteria,
                    "points": points,
                    "ctxh": 0.0,
                    "status": "Hoạt động học kỳ",
                    "is_full": False,
                    "detail_url": self.SEMESTER_URL,
                    "register_url": self.DANGKY_URL,
                    "source": "Danh Sách Hoạt Động Học Kỳ (/Activity/SemesterActivities)"
                })

            return True, f"Bóc tách thành công {len(activities)} hoạt động học kỳ", activities

        except Exception as e:
            return False, f"Lỗi bóc tách /Activity/SemesterActivities: {e}", []

    def fetch_custom_activities(self) -> tuple:
        """
        Bóc tách hoạt động chuyên đề và đối tác tại https://hoatdong.ufm.edu.vn/CustomActivity
        """
        if not self.ensure_authenticated():
            return False, "Phiên đăng nhập UFM không hợp lệ", []

        try:
            r = self.session.get(self.CUSTOM_URL, verify=False, timeout=20)
            if r.status_code != 200:
                return False, f"Mã trạng thái HTTP {r.status_code}", []

            soup = BeautifulSoup(r.text, "html.parser")
            activities = []

            for h3 in soup.find_all("h3"):
                title = h3.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                import hashlib
                c_id = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]

                parent = h3.find_parent("div", class_=lambda c: c and "card" in c) or h3.parent
                details = parent.get_text(separator=" | ", strip=True) if parent else ""

                activities.append({
                    "activity_id": f"CUST_{c_id}",
                    "raw_id": c_id,
                    "title": title,
                    "unit": "Đối tác / Chương trình chuyên đề UFM",
                    "event_time": "Xem chi tiết tại cổng",
                    "location": "Trực tuyến / Ngoài trường",
                    "group_criteria": "CTXH / Kỹ năng đối tác",
                    "points": 0.0,
                    "ctxh": 0.0,
                    "status": "Đang mở",
                    "is_full": False,
                    "detail_url": self.CUSTOM_URL,
                    "register_url": self.CUSTOM_URL,
                    "source": "Hoạt Động Chuyên Đề & Đối Tác (/CustomActivity)"
                })

            return True, f"Bóc tách thành công {len(activities)} hoạt động chuyên đề", activities

        except Exception as e:
            return False, f"Lỗi bóc tách /CustomActivity: {e}", []

    def fetch_all_events(self) -> tuple:
        """
        Gom toàn bộ hoạt động từ cả 3 nguồn:
        1. /DangKy (Ưu tiên số 1 - Có mở đăng ký trực tiếp)
        2. /Activity/SemesterActivities (Ưu tiên số 2 - Danh sách toàn trường mới nhất)
        3. /CustomActivity (Ưu tiên số 3 - Hoạt động đối tác / CTXH)
        """
        all_events = []
        seen_raw_ids = set()

        # 1. /DangKy
        ok_dk, msg_dk, events_dk = self.fetch_dangky_activities()
        if ok_dk:
            for ev in events_dk:
                seen_raw_ids.add(ev["raw_id"])
                all_events.append(ev)

        # 2. /Activity/SemesterActivities (chỉ lấy 30 bài mới nhất)
        ok_sem, msg_sem, events_sem = self.fetch_semester_activities(limit=30)
        if ok_sem:
            for ev in events_sem:
                # Nếu đã có trong /DangKy thì ưu tiên dữ liệu từ /DangKy (vì đầy đủ slot, điểm, thời gian hơn)
                if ev["raw_id"] not in seen_raw_ids:
                    seen_raw_ids.add(ev["raw_id"])
                    all_events.append(ev)

        # 3. /CustomActivity
        ok_cust, msg_cust, events_cust = self.fetch_custom_activities()
        if ok_cust:
            for ev in events_cust:
                all_events.append(ev)

        return True, f"Tổng cộng thu thập {len(all_events)} hoạt động từ hệ thống UFM", all_events
