import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys, json, requests
c_list = json.load(open('/root/huit-bot/fb_cookies.json'))
cookies = {c['name']: c['value'] for c in c_list if 'name' in c and 'value' in c}
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
})
s.cookies.update(cookies)
resp = s.get('https://www.facebook.com/HUITFIT', timeout=20, allow_redirects=True)
print('Testing Cookie 2 (c_user =', cookies.get('c_user'), '):')
print('Final URL:', resp.url)
print('Has /login/ in URL?:', '/login/' in resp.url)
print('Length of response:', len(resp.text))
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
