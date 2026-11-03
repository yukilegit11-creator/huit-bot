import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

test_script = """import requests, ddddocr, urllib3
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
for line in r_login.text.split('\\n'):
    if any(k in line.lower() for k in ['alert', 'script', 'sai', 'mật khẩu', 'thất bại', 'location', 'window']):
        print(' -', line.strip())
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_login_err.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_login_err.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
