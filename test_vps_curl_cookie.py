import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys, json
from curl_cffi import requests
cfg = json.load(open('/root/huit-bot/config.json'))
cookies = cfg.get('fb_cookies', {})
resp = requests.get('https://www.facebook.com/HUITFIT', cookies=cookies, impersonate='chrome120', timeout=20)
print('curl_cffi with Cookie 1 on VPS:')
print('Final URL:', resp.url)
print('Status:', resp.status_code)
print('Length:', len(resp.text))
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
