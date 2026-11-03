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

stdin, stdout, stderr = ssh.exec_command("ls -la /root/huit-bot/ufm_bot.db /root/huit-bot/vaa/ufm/ufm_bot.db")
print("Database files on VPS:")
print(stdout.read().decode("utf-8"))

ssh.close()
