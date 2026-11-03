import sqlite3
conn = sqlite3.connect('/root/huit-bot/ou_bot.db')
c = conn.cursor()
c.execute("SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 20")
rows = c.fetchall()
print(f"Total OU system_logs: {len(rows)}")
for r in rows:
    print(" ", r)
c.execute("SELECT key, value FROM bot_status")
print("Bot status:")
for r in c.fetchall():
    print(" ", r)
conn.close()
