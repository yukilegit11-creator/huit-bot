import requests, ddddocr, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://doantn.iuh.edu.vn/login.html'
})

r_init = s.get('https://doantn.iuh.edu.vn/login.html', verify=False)
r_cap = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False)
cap_code = ocr.classification(r_cap.content).strip()
print('Solved Captcha:', cap_code)

data = {
    'mssv': '2564049',
    'password': 'phamhang1207',
    'security_code': cap_code,
    'btLogin': 'Đăng nhập'
}
r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False)
soup = BeautifulSoup(r_login.text, 'html.parser')
fc = soup.find(class_='container-login')
if fc:
    print('Form container text:', fc.get_text(separator=' | ', strip=True))

for div in soup.find_all(['div', 'p', 'span']):
    t = div.get_text(strip=True)
    if any(k in t.lower() for k in ['sai', 'không đúng', 'thành công', 'thất bại', 'chính xác', 'mật khẩu']):
        print('Matched text:', t)
