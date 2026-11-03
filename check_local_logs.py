import sqlite3
conn = sqlite3.connect("c:/Users/Admin/Documents/HUIT/huit_bot.db")
cur = conn.cursor()
cur.execute("SELECT id, level, message FROM system_logs ORDER BY id DESC LIMIT 10")
for r in cur.fetchall():
    print(r)
