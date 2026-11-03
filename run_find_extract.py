import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

find_call = """
import os
for root, dirs, files in os.walk('/usr/local/lib/python3.10/dist-packages/fbchat_muqit'):
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, 'r') as code_f:
                for idx, line in enumerate(code_f):
                    if 'extract_tokens_from_html' in line:
                        print(f"{fp}:{idx+1} {line.strip()}")
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/find_extract.py', 'w') as f:
    f.write(find_call)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/find_extract.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
ssh.close()
