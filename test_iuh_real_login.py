import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

test_script = """import requests, ddddocr, urllib3
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
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_real_login.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_real_login.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
