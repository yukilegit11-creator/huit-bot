import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

check_pkg = """
import fbchat_muqit, inspect, os
pkg_path = os.path.dirname(inspect.getfile(fbchat_muqit))
print('Package path:', pkg_path)
for root, dirs, files in os.walk(pkg_path):
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, 'r', encoding='utf-8', errors='ignore') as code_f:
                content = code_f.read()
                if 'async_get_token' in content:
                    print(f'Found async_get_token in {fp}')
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/check_fbchat_pkg.py', 'w') as f:
    f.write(check_pkg)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/check_fbchat_pkg.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
