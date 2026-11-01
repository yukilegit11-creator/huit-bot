import requests
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class SupabaseDispatcher:
    def __init__(self, config_file=CONFIG_PATH):
        self.config_file = config_file
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.cfg = data.get("supabase", {})
                self.url = self.cfg.get("url", "").rstrip("/")
                self.key = self.cfg.get("anon_key", "")
                self.enabled = self.cfg.get("enabled", True)
        except Exception:
            self.enabled = False

    def push_post(self, post_data: dict, page_name: str) -> bool:
        if not self.enabled or not self.url or not self.key:
            return False

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        # Chuẩn bị dữ liệu đúng cấu trúc bảng posts của Supabase
        payload = {
            "title": f"[{page_name}] {post_data.get('author', 'Tin tức')} - {post_data.get('posted_time', '')}",
            "description": post_data.get("content", ""),
            "category": "Facebook",
            "status": "published",
            "price": 0,
            "contact_link": post_data.get("post_url", "https://www.facebook.com")
        }

        try:
            endpoint = f"{self.url}/rest/v1/posts"
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=12)
            if resp.status_code in (200, 201, 204):
                print(f"🌐 [Supabase] Đồng bộ bài viết lên Supabase thành công!")
                return True
            else:
                print(f"⚠️ [Supabase] Trả về mã {resp.status_code}: {resp.text[:120]}")
                return False
        except Exception as e:
            print(f"⚠️ [Supabase] Lỗi khi gửi dữ liệu: {e}")
            return False

    def get_seen_identifiers(self) -> set:
        if not self.enabled or not self.url or not self.key:
            return set()
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        try:
            import re
            import hashlib
            endpoint = f"{self.url}/rest/v1/posts?select=contact_link,title,description&limit=1000"
            resp = requests.get(endpoint, headers=headers, timeout=10)
            if resp.status_code == 200:
                rows = resp.json()
                seen = set()
                for r in rows:
                    link = r.get("contact_link", "")
                    if link:
                        seen.add(link)
                        nums = re.findall(r"\d{10,}", link)
                        for n in nums:
                            seen.add(n)
                    desc = r.get("description", "")
                    if desc:
                        c_hash = hashlib.md5(desc.strip()[:150].encode("utf-8")).hexdigest()
                        seen.add(c_hash)
                return seen
        except Exception as e:
            print(f"⚠️ [Supabase] Lỗi lấy danh sách bài cũ: {e}")
        return set()

if __name__ == "__main__":
    dispatcher = SupabaseDispatcher()
    ok = dispatcher.push_post({
        "author": "Test Author",
        "posted_time": "02/11/2026",
        "content": "Kiểm tra push trực tiếp từ supabase_client",
        "post_url": "https://facebook.com"
    }, "Group Test")
    print("Push result:", ok)
