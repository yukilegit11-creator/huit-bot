import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

read_code = """
with open('/usr/local/lib/python3.10/dist-packages/fbchat_muqit/utils/stateHelper.py', 'r') as f:
    lines = f.readlines()

for i in range(195, 260):
    print(f"{i+1}: {lines[i]}", end='')
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/read_state4.py', 'w') as f:
    f.write(read_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/read_state4.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
ssh.close()
