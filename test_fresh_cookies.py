import json
import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

tests = [
    ("HUIT Scraper", r'c:\Users\Admin\Documents\HUIT\config.json', "fb_cookies", "dict"),
    ("VAA Scraper", r'c:\Users\Admin\Documents\HUIT\config_bot2.json', "fb_cookies", "dict"),
    ("Messenger", r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', None, "list")
]

for label, p, key, fmt in tests:
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if fmt == "dict":
        cookies = data.get(key, {})
    else:
        cookies = {c['name']: c['value'] for c in data if 'name' in c and 'value' in c}
    
    uid = cookies.get('c_user', 'N/A')
    print("=" * 60)
    print(f"Kiểm tra live {label} (UID: {uid}):")
    try:
        resp = requests.get("https://www.facebook.com/", cookies=cookies, impersonate="chrome120", timeout=15)
        print(f"  Status: {resp.status_code}")
        print(f"  Final URL: {resp.url}")
        if "checkpoint" in str(resp.url) or "login" in str(resp.url):
            print("  ❌ BỊ CHUYỂN HƯỚNG VỀ LOGIN / CHECKPOINT!")
        elif resp.status_code == 200:
            print(f"  🎉 HỢP LỆ VÀ SỐNG 100%! (Phản hồi {len(resp.text)} bytes)")
    except Exception as e:
        print(f"  Lỗi: {e}")
