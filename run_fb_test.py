import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

sftp = ssh.open_sftp()
sftp.put(r'C:\Users\Admin\Documents\HUIT\test_remote_fb.py', '/root/huit-bot/test_remote_fb.py')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_remote_fb.py')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')
print("STDOUT:\n", out)
print("STDERR:\n", err)
ssh.close()
