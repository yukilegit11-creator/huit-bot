import json
import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

new_fb_cookies = [
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253638.676091,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_l",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253437.025433,
        "hostOnly": False,
        "httpOnly": True,
        "name": "datr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "-pbpavf2opPl_hPBKlMxbUIH"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1801469684.175353,
        "hostOnly": False,
        "httpOnly": True,
        "name": "fr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1CiOUQFlBL8Fpx5Sg.AWdPHvR2hPnvSF2d6F0ceeNkZ_DEvGJm7B4wHqiMfguIEsoG02E.Bq6Zfx..AAA.0.0.Bq6Zfx.AWeeC343YQvpO7XLsrWD_S3ryF8"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825229684.175415,
        "hostOnly": False,
        "httpOnly": True,
        "name": "xs",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "44%3AJgCm9M7gN7ZOfQ%3A2%3A1793693677%3A-1%3A-1%3A%3AAc2tN_FXNLsCp_Uef4MIEavYQ82lltykJX1KocWfUg"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825229684.175258,
        "hostOnly": False,
        "httpOnly": False,
        "name": "c_user",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "61595329828799"
    },
    {
        "domain": ".facebook.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "presence",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "C%7B%22lm3%22%3A%22sc.1431253205878741%22%2C%22t3%22%3A%5B%7B%22o%22%3A0%2C%22i%22%3A%22sc.2324038958345714%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22sc.1651682416603720%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22sc.1163374412916971%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22sc.1652823906584057%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22g.1620250146795363%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22sc.1124441913886581%22%7D%2C%7B%22o%22%3A0%2C%22i%22%3A%22sc.1763199451643483%22%7D%5D%2C%22utc3%22%3A1793696000203%2C%22v%22%3A1%7D"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794300144,
        "hostOnly": False,
        "httpOnly": False,
        "name": "dpr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1.125"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253638.676286,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_n",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253682.130137,
        "hostOnly": False,
        "httpOnly": True,
        "name": "sb",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "-5bpaiCSb5HDa411EdNDilYJ"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794300150,
        "hostOnly": False,
        "httpOnly": False,
        "name": "wd",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "2470x1190"
    }
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/fb_cookies.json', 'w') as f:
    json.dump(new_fb_cookies, f, indent=2)
sftp.close()
print("Wrote new fb_cookies.json to VPS!")

test_script = """
import os, sys, json
sys.path.insert(0, '/root/huit-bot')
from messenger_sender import MessengerDispatcher

# Update config.json on VPS with new cookies
with open('/root/huit-bot/config.json', 'r') as f:
    cfg = json.load(f)

with open('/root/huit-bot/fb_cookies.json', 'r') as f:
    new_cookies = json.load(f)

cfg['messenger']['cookies'] = new_cookies
cfg['messenger']['enabled'] = True
with open('/root/huit-bot/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)

print('Updated config.json on VPS with new cookies!')

msger = MessengerDispatcher('/root/huit-bot/config.json')
ok = msger.connect()
print('Messenger connect status:', ok)
if ok:
    demo_id = '1773570903700841'
    print(f'Sending test message to demo group {demo_id}...')
    succ, msg = msger.send_test_message(target_thread_id=demo_id)
    print('Send test message result:', succ, msg)
else:
    print('Failed to connect to Messenger with new cookies.')
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_new_fb.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_new_fb.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
