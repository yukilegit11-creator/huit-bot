import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

py_cmd = """
import sqlite3
for name, db in [('Bot 1 HUIT', '/root/huit-bot/huit_bot.db'), ('Bot 2 VAA', '/root/huit-bot/bot2.db'), ('Bot 3 IUH', '/root/huit-bot/iuh_bot.db'), ('Bot 4 UFM', '/root/huit-bot/ufm_bot.db')]:
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        print('=== ' + name + ' ===')
        cur.execute('SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 3')
        for r in cur.fetchall():
            print(f'  [{r[2]}] [{r[0]}] {r[1]}')
        conn.close()
    except Exception as e:
        print('Err:', name, e)
"""
sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/view_logs.py', 'w') as f:
    f.write(py_cmd)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/view_logs.py')
print(stdout.read().decode('utf-8'))
ssh.close()
