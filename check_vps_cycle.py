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

stdin, stdout, stderr = ssh.exec_command("python3 -c \"import sqlite3; conn = sqlite3.connect('/root/huit-bot/huit_bot.db'); cur = conn.cursor(); cur.execute('SELECT message FROM system_logs WHERE message LIKE \\\"%Chu kỳ #%\\\" ORDER BY id DESC LIMIT 10'); print(cur.fetchall())\"")
print("VPS system_logs cycle rows:")
print(stdout.read().decode("utf-8"))

ssh.close()
