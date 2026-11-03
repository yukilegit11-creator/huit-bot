import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

check_html = """
import aiohttp, asyncio
from fbchat_muqit.utils.stateHelper import load_json_cookies_async

async def main():
    jar = await load_json_cookies_async('/root/huit-bot/fb_cookies.json')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        async with session.get('https://www.facebook.com/', headers=headers) as resp:
            text = await resp.text()
            print('Status:', resp.status)
            print('Headers:', dict(resp.headers))
            print('Body sample:')
            print(text[:1000])

asyncio.run(main())
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/print_400.py', 'w') as f:
    f.write(check_html)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/print_400.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
