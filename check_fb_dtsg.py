import sys
import json
import re
from curl_cffi import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

cookies = {c['name']: c['value'] for c in cookies_list}

resp = requests.get("https://www.facebook.com/", impersonate="chrome120", cookies=cookies)
html = resp.text

print(f"HTML len: {len(html)}")

# Check DTSGInitialData
dtsg_m = re.search(r'"DTSGInitialData".*?"token":"(.*?)"', html)
print("DTSGInitialData:", dtsg_m.group(1) if dtsg_m else "NOT FOUND")

# Check all occurrences of async_get_token
for m in re.finditer(r'async_get_token', html):
    start = max(0, m.start() - 60)
    end = min(len(html), m.end() + 100)
    print("Match async_get_token:", html[start:end])

if "async_get_token" not in html:
    print("async_get_token is NOT in HTML at all! Let's check DTSG in html:")
    for m in re.finditer(r'DTSG', html):
        print(html[max(0, m.start()-20):min(len(html), m.end()+100)])
