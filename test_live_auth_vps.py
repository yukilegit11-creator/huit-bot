import sys
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://180.93.125.40:8000"

# 1. Access root without auth
r1 = requests.get(BASE + "/", allow_redirects=False)
print("1. GET / without auth:", r1.status_code, "Location:", r1.headers.get("location"))

# 2. Access login page
r2 = requests.get(BASE + "/login")
print("2. GET /login:", r2.status_code, "Title in HTML:", "Yuki Multi-Bot" in r2.text)

# 3. Test wrong password
r3 = requests.post(BASE + "/login", json={"password": "wrong_password"})
print("3. POST /login wrong pass:", r3.status_code, r3.json())

# 4. Test correct password
s = requests.Session()
r4 = s.post(BASE + "/login", json={"password": "YUKILEGIT0", "remember": True})
print("4. POST /login correct pass:", r4.status_code, r4.json())
print("   Cookies:", s.cookies.get_dict())

# 5. Access root with authenticated session
r5 = s.get(BASE + "/")
print("5. GET / with session:", r5.status_code, "Length:", len(r5.text))

# 6. Access UFM subapp without auth
r6_no_auth = requests.get(BASE + "/ufm/", allow_redirects=False)
print("6a. GET /ufm/ without auth:", r6_no_auth.status_code, "Location:", r6_no_auth.headers.get("location"))

# 7. Access UFM subapp with authenticated session
r6_auth = s.get(BASE + "/ufm/")
print("6b. GET /ufm/ with session:", r6_auth.status_code, "Length:", len(r6_auth.text))

# 8. Test API endpoint with session vs without session
r7_no_auth = requests.get(BASE + "/api/stats")
print("7a. GET /api/stats without auth:", r7_no_auth.status_code, r7_no_auth.json())

r7_auth = s.get(BASE + "/api/stats")
print("7b. GET /api/stats with session:", r7_auth.status_code, "Has stats:", bool(r7_auth.json()))
