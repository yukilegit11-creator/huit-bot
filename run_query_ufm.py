import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

sftp = ssh.open_sftp()
sftp.put(r'C:\Users\Admin\Documents\HUIT\query_ufm.py', '/root/huit-bot/query_ufm.py')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/query_ufm.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
