import sys
import json
from curl_cffi import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

cookies = {c['name']: c['value'] for c in cookies_list}

resp = requests.get("https://www.facebook.com/", impersonate="chrome120", cookies=cookies)
print(f"Status: {resp.status_code}")
print(f"Final URL: {resp.url}")
if "login" in str(resp.url) or "checkpoint" in str(resp.url):
    print("❌ Cookie Facebook ĐÃ HẾT HẠN hoặc BỊ CHECKPOINT!")
else:
    print("✅ Cookie Facebook ĐANG HỢP LỆ VÀ SỐNG TỐT!")
