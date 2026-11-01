import json
import time
import base64
import os
import re
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

VN_TZ = timezone(timedelta(hours=7))

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

class FacebookCometScraper:
    def __init__(self, cookies: dict = None):
        self.session = requests.Session()
        self.session.headers.update(DESKTOP_HEADERS)
        if cookies:
            self.update_cookies(cookies)

    def update_cookies(self, cookies: dict):
        self.session.cookies.clear()
        self.session.cookies.update(cookies)

    def fetch_url(self, url: str) -> str:
        # Chuẩn hóa về Desktop URL
        target_url = url.replace("mbasic.facebook.com", "www.facebook.com")
        target_url = target_url.replace("m.facebook.com", "www.facebook.com")
        try:
            resp = self.session.get(target_url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"⚠️ Facebook trả về mã {resp.status_code} cho {target_url}")
                return ""
        except Exception as e:
            print(f"⚠️ Lỗi kết nối khi quét {target_url}: {e}")
            return ""

    @staticmethod
    def get_post_id_from_story_id(sid: str) -> str:
        if not sid or not isinstance(sid, str):
            return ""
        try:
            decoded = base64.b64decode(sid).decode("utf-8", errors="ignore")
            nums = re.findall(r"\d{10,}", decoded)
            if nums:
                return nums[-1]
        except Exception:
            pass
        return ""

    @staticmethod
    def is_valid_post(text: str) -> bool:
        if not text or len(text.strip()) < 15:
            return False

        txt_stripped = text.strip()
        # Loại bỏ các bài chia sẻ link trơ trụi
        if txt_stripped.startswith("http://") or txt_stripped.startswith("https://"):
            if len(txt_stripped.split("\n")) <= 1:
                return False

        garbage = [
            "sorry, something went wrong",
            "we are working on it",
            "đăng nhập",
            "log in",
            "cookie notice",
            "javascript is required",
            "bạn phải đăng nhập để tiếp tục",
            "tùy chọn về quyền riêng tư",
            "tiếp tục với tư cách",
            "chính sách quyền riêng tư"
        ]
        txt_lower = text.lower()
        for g in garbage:
            if g in txt_lower:
                return False

        return True

    def _extract_messages_from_json(self, obj, posts, metadata_map, default_page_url=""):
        if isinstance(obj, dict):
            if "message" in obj and isinstance(obj["message"], dict) and "text" in obj["message"]:
                txt = obj["message"]["text"]
                if self.is_valid_post(txt):
                    pid = obj.get("post_id") or self.get_post_id_from_story_id(obj.get("id"))
                    meta = metadata_map.get(pid, {}) if pid else {}
                    
                    url = meta.get("url") or obj.get("permalink_url") or obj.get("url") or ""
                    if not url and pid:
                        if "/groups/" in default_page_url:
                            base_grp = default_page_url.split("?")[0].rstrip("/")
                            url = f"{base_grp}/posts/{pid}/"
                        else:
                            url = f"https://www.facebook.com/{pid}"

                    creation_time = meta.get("creation_time") or obj.get("creation_time")
                    post_time_str = ""
                    if creation_time and isinstance(creation_time, (int, float)):
                        post_time_str = datetime.fromtimestamp(creation_time, tz=VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

                    author = meta.get("author") or ""
                    if not author and obj.get("actors") and isinstance(obj["actors"], list) and len(obj["actors"]) > 0:
                        author = obj["actors"][0].get("name", "")

                    posts.append({
                        "content": txt,
                        "post_url": url,
                        "creation_time": creation_time,
                        "posted_time": post_time_str,
                        "author": author or "Ẩn danh",
                        "post_id": pid
                    })

            for v in obj.values():
                self._extract_messages_from_json(v, posts, metadata_map, default_page_url)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_messages_from_json(item, posts, metadata_map, default_page_url)

    def parse_posts(self, html_text: str, max_age_hours: float = 1.0, page_url: str = "") -> list:
        if not html_text:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/json"})
        metadata_map = {}

        def index_metadata(d):
            if isinstance(d, dict):
                pid = d.get("post_id") or self.get_post_id_from_story_id(d.get("id"))
                if pid:
                    if pid not in metadata_map:
                        metadata_map[pid] = {}
                    if d.get("creation_time"):
                        metadata_map[pid]["creation_time"] = d["creation_time"]
                    if d.get("actors") and isinstance(d["actors"], list) and len(d["actors"]) > 0:
                        name = d["actors"][0].get("name")
                        if name:
                            metadata_map[pid]["author"] = name
                    u = d.get("permalink_url") or d.get("wwwURL") or d.get("url")
                    if u:
                        metadata_map[pid]["url"] = u
                for v in d.values():
                    index_metadata(v)
            elif isinstance(d, list):
                for item in d:
                    index_metadata(item)

        raw_posts = []
        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                index_metadata(data)
                self._extract_messages_from_json(data, raw_posts, metadata_map, page_url)
            except Exception:
                continue

        # Lọc trùng lặp & Lọc bài đăng trong vòng max_age_hours
        now_ts = datetime.now(tz=VN_TZ).timestamp()
        filtered = []
        seen_ids = set()

        for p in raw_posts:
            ident = p.get("post_id") or hashlib.md5(p["content"][:150].encode("utf-8")).hexdigest()
            if ident in seen_ids:
                continue
            seen_ids.add(ident)

            c_time = p.get("creation_time")
            if c_time and isinstance(c_time, (int, float)):
                age_hours = (now_ts - c_time) / 3600.0
                if age_hours > max_age_hours:
                    # Bỏ qua bài quá cũ
                    continue
            else:
                # Nếu không có mốc thời gian bóc tách được từ SSR Facebook,
                # bỏ qua để tuyệt đối chống bắn bài ghim cũ
                continue

            filtered.append(p)

        return filtered
