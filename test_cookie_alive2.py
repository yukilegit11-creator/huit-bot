import sys
import json
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
})

for c in cookies_list:
    session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.facebook.com'))

resp = session.get("https://www.facebook.com/", allow_redirects=True, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Final URL: {resp.url}")
if "login" in resp.url or "checkpoint" in resp.url:
    print("❌ Cookie Facebook ĐÃ HẾT HẠN hoặc BỊ CHECKPOINT!")
else:
    print("✅ Cookie Facebook ĐANG HỢP LỆ VÀ SỐNG TỐT!")
