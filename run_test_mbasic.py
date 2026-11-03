import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

test_mbasic = """
import urllib.request, json, ssl
with open('/root/huit-bot/fb_cookies.json') as f:
    cookies = json.load(f)

# Only send essential cookies
c_dict = {c['name']: c['value'] for c in cookies if c['name'] in ['c_user', 'xs', 'fr', 'datr', 'sb']}
c_str = '; '.join([f'{k}={v}' for k, v in c_dict.items()])

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://mbasic.facebook.com/',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Cookie': c_str,
    }
)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
        print('Status:', r.status)
        print('URL:', r.geturl())
        if 'mbasic_logout_button' in html or 'logout.php' in html:
            print('Mbasic: LOGGED IN!')
        else:
            print('Mbasic: NOT LOGGED IN / REDIRECTED TO LOGIN')
except Exception as e:
    print('Error:', e)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_mbasic.py', 'w') as f:
    f.write(test_mbasic)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_mbasic.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
