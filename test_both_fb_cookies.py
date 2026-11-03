import json
import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 1. Test Cookie 1: Scraping cookie (c_user: 61574475721537)
with open(r'c:\Users\Admin\Documents\HUIT\config.json', 'r', encoding='utf-8') as f:
    cfg1 = json.load(f)
c1 = cfg1.get('fb_cookies', {})

print("=" * 60)
print(f"Kiểm tra Cookie 1 (Dùng để CÀO BÀI VIẾT - Bot 1 HUIT & Bot 2 VAA):")
print(f"UID (c_user): {c1.get('c_user')}")
try:
    resp1 = requests.get("https://www.facebook.com/", cookies=c1, impersonate="chrome120", timeout=15)
    print(f"Status Code: {resp1.status_code}")
    print(f"URL đích: {resp1.url}")
    if "checkpoint" in str(resp1.url) or "login" in str(resp1.url):
        print("❌ Cookie 1 ĐÃ HẾT HẠN hoặc BỊ CHECKPOINT (Cần cấp lại)!")
    elif resp1.status_code == 200:
        if 'c_user' in resp1.text or c1.get('c_user', '') in resp1.text or '"CurrentUserInitialData"' in resp1.text:
            print("✅ Cookie 1 ĐANG HOẠT ĐỘNG TỐT (Đã đăng nhập thành công)!")
        else:
            print("⚠️ Cookie 1 đã bị đăng xuất trên Facebook web (trả về trang khách)!")
except Exception as e:
    print(f"Lỗi kiểm tra Cookie 1: {e}")

print("=" * 60)

# 2. Test Cookie 2: Messenger / Profile cookie (c_user: 61595329828799)
with open(r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', 'r', encoding='utf-8') as f:
    c2_list = json.load(f)
c2 = {item['name']: item['value'] for item in c2_list if 'name' in item and 'value' in item}

print(f"Kiểm tra Cookie 2 (Dùng để GỬI MESSENGER - Tài khoản Yu Ki):")
print(f"UID (c_user): {c2.get('c_user')}")
try:
    resp2 = requests.get("https://www.facebook.com/", cookies=c2, impersonate="chrome120", timeout=15)
    print(f"Status Code: {resp2.status_code}")
    print(f"URL đích: {resp2.url}")
    if "checkpoint" in str(resp2.url) or "login" in str(resp2.url):
        print("❌ Cookie 2 ĐÃ HẾT HẠN hoặc BỊ CHECKPOINT (Cần cấp lại)!")
    elif resp2.status_code == 200:
        if 'c_user' in resp2.text or c2.get('c_user', '') in resp2.text or '"CurrentUserInitialData"' in resp2.text:
            print("✅ Cookie 2 ĐANG HOẠT ĐỘNG TỐT (Đã đăng nhập thành công)!")
        else:
            print("⚠️ Cookie 2 đã bị đăng xuất trên Facebook web (trả về trang khách)!")
except Exception as e:
    print(f"Lỗi kiểm tra Cookie 2: {e}")
print("=" * 60)
