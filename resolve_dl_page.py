import sys
from curl_cffi import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

url = "https://www.facebook.com/doankhoadulichhufi"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

resp = requests.get(url, impersonate="chrome120", headers=headers, allow_redirects=True)
print("Final URL:", resp.url)

soup = BeautifulSoup(resp.text, "html.parser")
title = soup.title.string if soup.title else "Unknown"
print("Title:", title)

og_title = soup.find("meta", property="og:title")
if og_title:
    print("og:title:", og_title.get("content"))
