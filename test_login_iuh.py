import requests, ddddocr, urllib3, time
from bs4 import BeautifulSoup
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://doantn.iuh.edu.vn/login.html'
})

# 1. Get login page to establish session
r_init = s.get('https://doantn.iuh.edu.vn/login.html', verify=False)
phpsessid = s.cookies.get('PHPSESSID')
print('Initial PHPSESSID:', phpsessid)

# 2. Get captcha image within the same session
r_cap = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False)
cap_code = ocr.classification(r_cap.content).strip()
print('Solved Captcha:', cap_code)

# 3. Post login
data = {
    'mssv': '2564049',
    'password': 'phamhang1207',
    'security_code': cap_code,
    'btLogin': ''
}
r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False, allow_redirects=True)
print('Login HTTP status:', r_login.status_code)
print('Redirect history:', [r.status_code for r in r_login.history])
print('Contains doanvien.html / dang xuat:', 'doanvien.html' in r_login.text or 'thoat' in r_login.text.lower() or 'logout' in r_login.text.lower())

# 4. Try fetching doanvien.html
r_target = s.get('https://doantn.iuh.edu.vn/doanvien.html', verify=False)
print('doanvien.html length:', len(r_target.text))
soup = BeautifulSoup(r_target.text, 'html.parser')
tab1 = soup.find(id='tab1')
if tab1:
    rows = tab1.find_all('tr')
    print('Activities count in Tab 1:', len(rows) - 1)
else:
    print('Not logged in or tab1 not found. Text snippet:', r_target.text[:500])
