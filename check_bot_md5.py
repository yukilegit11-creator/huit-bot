import sys
import hashlib
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\bot.py', 'rb') as f:
    local_hash = hashlib.md5(f.read()).hexdigest()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

stdin, stdout, stderr = ssh.exec_command('md5sum /root/huit-bot/bot.py')
vps_hash = stdout.read().decode('utf-8').split()[0]
print(f"Local bot.py md5: {local_hash}")
print(f"VPS   bot.py md5: {vps_hash}")
print("MATCH?", local_hash == vps_hash)
ssh.close()
