import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

test_script = """import requests, ddddocr, urllib3, re, time
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
with open('/root/huit-bot/last_cap.png', 'wb') as f:
    f.write(r_cap.content)
cap_raw = ocr.classification(r_cap.content)
cap_code = re.sub(r'[^a-zA-Z0-9]', '', cap_raw).strip()
print('Raw OCR:', cap_raw, 'Cleaned:', cap_code)

data = {
    'mssv': '25640491',
    'password': 'phamhang1207',
    'security_code': cap_code,
    'btLogin': 'Đăng nhập'
}
r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False)
soup = BeautifulSoup(r_login.text, 'html.parser')
print('Alert or error text:')
for el in soup.find_all(class_=re.compile(r'alert|error|message|msg', re.I)):
    print(' ', el.get_text(strip=True))

for div in soup.find_all(['div', 'span', 'p']):
    t = div.get_text(strip=True)
    if any(k in t.lower() for k in ['sai', 'mã bảo vệ', 'không đúng', 'thất bại', 'không thành công']):
        print(' Match:', t)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_login_debug.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_login_debug.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
