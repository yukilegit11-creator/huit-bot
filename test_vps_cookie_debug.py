import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX')

sftp = ssh.open_sftp()
code = """
import json, requests, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for bot, path in [('Bot 1 (HUIT)', '/root/huit-bot/config.json'), ('Bot 2 (VAA)', '/root/huit-bot/config_bot2.json')]:
    print('=== ' + bot + ' ===')
    cfg = json.load(open(path, encoding='utf-8'))
    cookies = cfg.get('fb_cookies', {})
    c_user = cookies.get('c_user')
    print('c_user:', c_user, 'keys:', list(cookies.keys()))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document'
    }

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    test_url = 'https://www.facebook.com/Daisutruyenthonghuit' if 'HUIT' in bot else 'https://www.facebook.com/vaa.ys2016'
    resp = session.get(test_url, timeout=20, allow_redirects=True)
    print('Status:', resp.status_code)
    print('Final URL:', resp.url)
    print('Len HTML:', len(resp.text))
    text_low = resp.text.lower()
    print('Has /checkpoint/ in URL:', '/checkpoint/' in resp.url)
    print('Has /login/ in URL:', '/login/' in resp.url)
    print('Has checkpoint in text:', 'checkpoint' in text_low)
    print('Has id=\"login_top\" in text:', 'id=\"login_top\"' in text_low)
    if '/checkpoint/' in resp.url or '/login/' in resp.url or 'checkpoint' in text_low:
        if 'checkpoint' in text_low:
            idx = text_low.find('checkpoint')
            print('Context of checkpoint:', resp.text[max(0, idx-40):min(len(resp.text), idx+60)])
"""

with sftp.file('/tmp/debug_fb_cookie.py', 'w') as f:
    f.write(code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/debug_fb_cookie.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
ssh.close()
