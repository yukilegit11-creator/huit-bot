import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

test_script = """
import os, sys, json
sys.path.insert(0, '/root/huit-bot')
from messenger_sender import FacebookMessengerDispatcher

msger = FacebookMessengerDispatcher('/root/huit-bot/config.json')
ok = msger.connect()
print('Connect result:', ok)
if ok:
    groups = msger.fetch_all_groups()
    print('Fetched groups count:', len(groups))
    for g in groups:
        print('Group:', g)
"""

stdin, stdout, stderr = ssh.exec_command(f"python3 -c {repr(test_script)}")
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
