import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

stdin, stdout, stderr = ssh.exec_command('python3 -c "import asyncio, aiohttp; from fbchat_muqit.utils.stateHelper import load_json_cookies_async; async def m(): jar = await load_json_cookies_async(\'/root/huit-bot/fb_cookies.json\'); async with aiohttp.ClientSession(cookie_jar=jar) as s: async with s.get(\'https://www.facebook.com/\') as r: print(await r.text()); asyncio.run(m())"')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
