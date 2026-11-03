import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST = "180.93.125.40"
PORT = 22
USER = "root"
PASS = "2tLGYzo2Ihgl6wKX"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PASS, timeout=15)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep python")
print("Python processes on VPS:")
print(stdout.read().decode("utf-8"))

stdin, stdout, stderr = ssh.exec_command("journalctl -u huit-bot -n 40 --no-pager")
print("\nJournalctl logs of huit-bot:")
print(stdout.read().decode("utf-8"))

ssh.close()
