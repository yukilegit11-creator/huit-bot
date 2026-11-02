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
        target_url = url.replace("mbasic.facebook.com", "www.facebook.com")
        target_url = target_url.replace("m.facebook.com", "www.facebook.com")
        try:
            resp = self.session.get(target_url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            else:
                return ""
        except Exception as e:
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
                        url = f"https://www.facebook.com/{pid}"

                    creation_time = meta.get("creation_time") or obj.get("creation_time") or obj.get("publish_time")
                    post_time_str = ""
                    if creation_time and isinstance(creation_time, (int, float)):
                        if creation_time > 1e11:
                            creation_time = creation_time / 1000.0
                        post_time_str = datetime.fromtimestamp(creation_time, tz=timezone.utc).astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

                    author = meta.get("author") or ""
                    if not author and obj.get("actors") and isinstance(obj["actors"], list) and len(obj["actors"]) > 0:
                        author = obj["actors"][0].get("name", "")

                    if not pid:
                        pid = hashlib.md5(txt[:150].encode("utf-8")).hexdigest()

                    posts.append({
                        "post_id": pid,
                        "content": txt,
                        "post_url": url,
                        "creation_time": creation_time,
                        "posted_time": post_time_str,
                        "author": author or "Trang Fanpage"
                    })

            for v in obj.values():
                self._extract_messages_from_json(v, posts, metadata_map, default_page_url)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_messages_from_json(item, posts, metadata_map, default_page_url)

    def parse_posts(self, html_text: str, max_age_hours: float = 0.5, page_url: str = "") -> list:
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
                    c_ts = d.get("creation_time") or d.get("publish_time") or d.get("post_creation_time")
                    if c_ts:
                        metadata_map[pid]["creation_time"] = c_ts
                    if d.get("actors") and isinstance(d["actors"], list) and len(d["actors"]) > 0:
                        name = d["actors"][0].get("name")
                        if name:
                            metadata_map[pid]["author"] = name
                    u = d.get("permalink_url") or d.get("wwwURL") or d.get("url")
                    if u and isinstance(u, str):
                        metadata_map[pid]["url"] = u
                for v in d.values():
                    index_metadata(v)
            elif isinstance(d, list):
                for v in d:
                    index_metadata(v)

        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                index_metadata(data)
            except Exception:
                pass

        found_posts = []
        for s in scripts:
            if not s.string:
                continue
            if '"message":{"text":' in s.string or '"story":' in s.string or '"comet_sections":' in s.string:
                try:
                    data = json.loads(s.string)
                    self._extract_messages_from_json(data, found_posts, metadata_map, page_url)
                except Exception:
                    pass

        if not found_posts:
            matches = re.findall(r'"message":\{"text":"(.*?)"\}', html_text)
            for m in matches:
                try:
                    dec = json.loads(f'"{m}"')
                except Exception:
                    dec = m.encode("utf-8").decode("unicode_escape", errors="ignore")
                if self.is_valid_post(dec):
                    found_posts.append({
                        "post_id": hashlib.md5(dec[:150].encode("utf-8")).hexdigest(),
                        "content": dec,
                        "post_url": page_url,
                        "creation_time": None,
                        "posted_time": "",
                        "author": "Trang Fanpage"
                    })

        unique_dict = {}
        for p in found_posts:
            key = p["content"].strip()
            if key not in unique_dict:
                unique_dict[key] = p

        now_ts = time.time()
        fresh_posts = []
        for p in list(unique_dict.values()):
            c_time = p.get("creation_time")
            if c_time and isinstance(c_time, (int, float)):
                if c_ts := c_time:
                    if c_ts > 1e11:
                        c_ts = c_ts / 1000.0
                    age_hours = (now_ts - c_ts) / 3600.0
                    # Giới hạn bài mới theo max_age_hours (mặc định 3 giờ hoặc cấu hình)
                    if age_hours > max(max_age_hours, 3.0) or age_hours < -0.2:
                        continue
            fresh_posts.append(p)

        fresh_posts.sort(key=lambda x: x.get("creation_time") or 0, reverse=True)
        return fresh_posts
