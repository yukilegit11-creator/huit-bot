import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

py_cmd = """
import sqlite3
conn = sqlite3.connect('/root/huit-bot/huit_bot.db')
cur = conn.cursor()
cur.execute('SELECT post_id, page_name, author, content, post_url, posted_time FROM crawled_posts ORDER BY id DESC LIMIT 5')
rows = cur.fetchall()
print(f'Total rows fetched: {len(rows)}')
for r in rows:
    print('---')
    print('Page:', r[1])
    print('Author:', r[2])
    print('URL:', r[4])
    print('Time:', r[5])
    print('Content:', r[3][:200].replace('\\n', ' '))
"""
sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/view_huit_posts.py', 'w') as f:
    f.write(py_cmd)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/view_huit_posts.py')
print(stdout.read().decode('utf-8'))
ssh.close()
