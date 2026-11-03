import sys
import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings()

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://hoatdong.ufm.edu.vn/Account/SignIn"
})

print("1. Fetching SignIn page to get __RequestVerificationToken and anti-forgery cookie...")
r_init = s.get("https://hoatdong.ufm.edu.vn/Account/SignIn", verify=False)
soup = BeautifulSoup(r_init.text, "html.parser")
token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
token = token_tag.get("value") if token_tag else ""
print(f"Token found: {token[:25]}... (len: {len(token)})")
print(f"Cookies after GET: {list(s.cookies.get_dict().keys())}")

payload = {
    "__RequestVerificationToken": token,
    "returnUrl": "/DangKy",
    "txtuser": "2621008460",
    "txtpass": "focusoncareer2111!!!"
}

print("\n2. Sending POST login...")
r_post = s.post("https://hoatdong.ufm.edu.vn/Account/SignIn", data=payload, verify=False, allow_redirects=False)
print("POST status code:", r_post.status_code)
print("Redirect location:", r_post.headers.get("Location"))
print("Cookies after POST:", list(s.cookies.get_dict().keys()))

for k, v in s.cookies.get_dict().items():
    print(f"  Cookie: {k} = {v[:30]}...")

print("\n3. Testing access to /DangKy with the new session...")
r_dangky = s.get("https://hoatdong.ufm.edu.vn/DangKy", verify=False, allow_redirects=False)
print("DangKy status code:", r_dangky.status_code)
print("DangKy Location:", r_dangky.headers.get("Location"))
if r_dangky.status_code == 200:
    print("🎉 LOGIN SUCCESSFUL! Access to /DangKy granted without redirect!")
    soup_dk = BeautifulSoup(r_dangky.text, "html.parser")
    h5s = soup_dk.find_all("h5")
    print(f"Found {len(h5s)} h5 cards on /DangKy!")
else:
    print("❌ Failed or redirected, status:", r_dangky.status_code)
