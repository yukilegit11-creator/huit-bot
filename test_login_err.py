import requests, ddddocr, urllib3
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://doantn.iuh.edu.vn/login.html'
})

r_init = s.get('https://doantn.iuh.edu.vn/login.html', verify=False)
r_cap = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False)
cap_code = ocr.classification(r_cap.content).strip()

data = {
    'mssv': '2564049',
    'password': 'phamhang1207',
    'security_code': cap_code,
    'btLogin': 'Đăng nhập'
}
r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False, allow_redirects=True)
print('Response text excerpt:')
for line in r_login.text.split('\n'):
    if any(k in line.lower() for k in ['alert', 'script', 'sai', 'mật khẩu', 'thất bại', 'location', 'window']):
        print(' -', line.strip())
