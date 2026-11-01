import re
import json
import hashlib
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

class IUHPortalScraper:
    BASE_URL = "https://doantn.iuh.edu.vn"
    TARGET_URL = "https://doantn.iuh.edu.vn/doanvien.html"

    def __init__(self, cookie_raw=None):
        self.phpsessid = self.extract_phpsessid(cookie_raw)
        self.session = requests.Session()
        if self.phpsessid:
            self.session.cookies.set("PHPSESSID", self.phpsessid, domain="doantn.iuh.edu.vn")
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://doantn.iuh.edu.vn/home.html",
            "Connection": "keep-alive"
        }

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

    def fetch_activities(self) -> tuple:
        if not self.phpsessid:
            return False, "Chưa thiết lập Cookie PHPSESSID", []

        try:
            r = self.session.get(self.TARGET_URL, headers=self.headers, verify=False, timeout=20)
        except Exception as e:
            return False, f"Lỗi kết nối tới doantn.iuh.edu.vn: {e}", []

        if r.status_code != 200:
            return False, f"Mã trạng thái HTTP {r.status_code}", []

        html = r.text

        if "login.html" in html and ("<meta http-equiv='refresh'" in html or "URL=login.html" in html):
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

            slots_match = re.search(r"\(?(\d+\s*/\s*\d+)\)?", title)
            slots = slots_match.group(1).replace(" ", "") if slots_match else ""

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
