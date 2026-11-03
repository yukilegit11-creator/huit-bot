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

print("Searching for endpoint or mqtt in HTML...")
for m in re.finditer(r'endpoint', html):
    print(html[max(0, m.start()-40):min(len(html), m.end()+120)])

for m in re.finditer(r'wss://', html):
    print("WSS:", html[max(0, m.start()-20):min(len(html), m.end()+120)])
