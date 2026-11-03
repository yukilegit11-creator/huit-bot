import requests, ddddocr, urllib3
from bs4 import BeautifulSoup
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
print('Solved Captcha:', cap_code)

data = {
    'mssv': '25640491',
    'password': 'phamhang1207',
    'security_code': cap_code,
    'btLogin': 'Đăng nhập'
}
r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False, allow_redirects=True)
print('Status code:', r_login.status_code)
print('Current URL:', r_login.url)
print('Cookies:', s.cookies.get_dict())

# Check doanvien.html
r_portal = s.get('https://doantn.iuh.edu.vn/doanvien.html', verify=False)
if 'KẾT QUẢ TRA CỨU' in r_portal.text or 'Phạm Thị Minh Hằng' in r_portal.text:
    print('LOGIN_SUCCESS! Logged in as Pham Thi Minh Hang!')
elif 'Đăng nhập không thành công' in r_login.text:
    print('LOGIN_FAILED: Dang nhap khong thanh cong')
else:
    print('LOGIN_RESULT_TEXT:', r_login.text[:500])
