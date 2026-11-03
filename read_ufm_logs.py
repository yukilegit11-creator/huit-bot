import sqlite3
conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
c = conn.cursor()
c.execute("SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 10")
for r in c.fetchall():
    print(r)
conn.close()
