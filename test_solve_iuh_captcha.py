import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

test_script = """import requests, ddddocr, urllib3
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

for i in range(3):
    r = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False)
    res = ocr.classification(r.content)
    print(f'Sample #{i+1} captcha solved:', res)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_captcha.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_captcha.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
