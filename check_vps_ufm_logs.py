import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

script = """
import sqlite3
for db in ['/root/huit-bot/ufm_bot.db', '/root/huit-bot/vaa/ufm/ufm_bot.db']:
    print('=== DB:', db)
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        rows = cur.execute('SELECT event_type, message, created_at FROM system_logs ORDER BY id DESC LIMIT 20').fetchall()
        for r in rows:
            print(f'[{r[2]}] [{r[0]}] {r[1]}')
        conn.close()
    except Exception as e:
        print('Error:', e)
"""

stdin, stdout, stderr = ssh.exec_command(f"python3 -c {repr(script)}")
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
