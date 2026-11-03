import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

test_script = """import requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings()

r = requests.get('https://doantn.iuh.edu.vn/login.html', verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
for s in soup.find_all('script'):
    txt = s.get_text()
    if 'frmLogin' in txt or 'login' in txt.lower():
        print('Script content:')
        print(txt)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_login_js.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_login_js.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
