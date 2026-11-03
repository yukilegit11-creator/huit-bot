import requests, ddddocr, urllib3, re, time
from bs4 import BeautifulSoup
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)

def attempt_login(mssv, password, max_attempts=15):
    for att in range(1, max_attempts + 1):
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': 'https://doantn.iuh.edu.vn/login.html'
        })
        
        # 1. Init login page
        r_init = s.get('https://doantn.iuh.edu.vn/login.html', verify=False, timeout=10)
        
        # 2. Get captcha
        r_cap = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False, timeout=10)
        cap_raw = ocr.classification(r_cap.content)
        cap_code = re.sub(r'[^a-zA-Z0-9]', '', cap_raw).strip()
        
        if len(cap_code) != 5:
            # print(f"Skip att #{att}: len={len(cap_code)} ({cap_code})")
            time.sleep(0.5)
            continue
            
        data = {
            'mssv': mssv,
            'password': password,
            'security_code': cap_code,
            'btLogin': 'Đăng nhập'
        }
        r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False, timeout=10)
        
        # Check portal
        r_portal = s.get('https://doantn.iuh.edu.vn/doanvien.html', verify=False, timeout=10)
        if 'doanvien.html@profile' in r_portal.text or 'Phạm Thị Minh Hằng' in r_portal.text:
            sess_id = s.cookies.get('PHPSESSID')
            print(f"🎉 LOGIN SUCCESS ON ATTEMPT #{att}! Captcha used: {cap_code}")
            print(f"🔑 New PHPSESSID: {sess_id}")
            return True, sess_id
        else:
            print(f"Att #{att} ({cap_code}) failed")
            time.sleep(0.5)
            
    return False, None

success, sid = attempt_login('25640491', 'phamhang1207')
print('FINAL RESULT:', success, sid)
