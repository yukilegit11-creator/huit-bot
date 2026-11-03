import sys
import json
import requests
import re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EMAIL = "fat14112008@gmail.com"
PASSWORD = "YUKILEGIT0"

def try_mbasic_login():
    print("Testing mbasic.facebook.com login...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    })

    # Step 1: GET login page
    resp = session.get("https://mbasic.facebook.com/login.php", timeout=15)
    print(f"Step 1 status: {resp.status_code}, url: {resp.url}")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", {"id": "login_form"}) or soup.find("form")
    if not form:
        print("No login form found on mbasic")
        return None

    action = form.get("action", "/login/device-based/regular/login/")
    if not action.startswith("http"):
        action = "https://mbasic.facebook.com" + action

    inputs = form.find_all("input")
    data = {}
    for inp in inputs:
        name = inp.get("name")
        val = inp.get("value", "")
        if name:
            data[name] = val

    data["email"] = EMAIL
    data["pass"] = PASSWORD
    print(f"Submitting form to: {action}")

    resp2 = session.post(action, data=data, timeout=15, allow_redirects=True)
    print(f"Step 2 status: {resp2.status_code}, final url: {resp2.url}")
    
    cookies = session.cookies.get_dict()
    print("Cookies received:", list(cookies.keys()))
    if "c_user" in cookies:
        print(f"LOGIN SUCCESS! c_user={cookies['c_user']}")
        return cookies
    else:
        print("Not logged in. Checking page content...")
        if "checkpoint" in resp2.url or "checkpoint" in resp2.text.lower():
            print("Checkpoint required (2FA or security check)")
        elif "login" in resp2.url:
            print("Redirected back to login (wrong pass or captcha)")
        return None

if __name__ == "__main__":
    try_mbasic_login()
