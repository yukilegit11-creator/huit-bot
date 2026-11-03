import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

stdin, stdout, stderr = ssh.exec_command('journalctl -u huit-bot --no-pager -n 40')
print("=== RECENT VPS LOGS ===")
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
