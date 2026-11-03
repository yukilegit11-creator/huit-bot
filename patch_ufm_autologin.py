import re

def patch_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update login method
    old_login = '''        try:
            r1 = self.session.get(self.SIGNIN_URL, verify=False, timeout=15)'''
    new_login = '''        try:
            self.session.cookies.clear()
            r1 = self.session.get(self.SIGNIN_URL, verify=False, timeout=15)'''
    if old_login in content:
        content = content.replace(old_login, new_login, 1)

    old_return = '"returnUrl": "/",\n                "txtuser": u,'
    new_return = '"returnUrl": "/DangKy",\n                "txtuser": u,'
    if old_return in content:
        content = content.replace(old_return, new_return, 1)

    old_signout = '''            r2 = self.session.post(self.SIGNIN_URL, data=data, verify=False, timeout=20, allow_redirects=True)
            if "SignOut" in r2.text or "Đăng xuất" in r2.text:'''
    new_signout = '''            r2 = self.session.post(self.SIGNIN_URL, data=data, verify=False, timeout=20, allow_redirects=True)
            has_auth = any(c.name == ".AspNetCore.Cookies" for c in self.session.cookies)
            if has_auth or "SignOut" in r2.text or "Đăng xuất" in r2.text or r2.url.endswith("/DangKy"):'''
    if old_signout in content:
        content = content.replace(old_signout, new_signout, 1)

    # 2. Update ensure_authenticated method
    old_auth = '''        try:
            r = self.session.get(self.DANGKY_URL, verify=False, timeout=15, allow_redirects=False)
            if r.status_code == 200 and ("Đăng xuất" in r.text or "SignOut" in r.text):
                return True
        except Exception:
            pass'''
    new_auth = '''        try:
            r = self.session.get(self.DANGKY_URL, verify=False, timeout=15, allow_redirects=False)
            if r.status_code == 200 and "Account/SignIn" not in r.text:
                return True
        except Exception:
            pass'''
    if old_auth in content:
        content = content.replace(old_auth, new_auth, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched: {path}")

patch_file(r'c:\Users\Admin\Documents\HUIT\ufm_scraper.py')
patch_file(r'c:\Users\Admin\Documents\HUIT\vaa\ufm\ufm_scraper.py')
