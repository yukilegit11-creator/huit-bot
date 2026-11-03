import sqlite3

conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
c = conn.cursor()
c.execute("PRAGMA table_info(delivery_history)")
print("delivery_history cols:", [r[1] for r in c.fetchall()])
c.execute("SELECT post_id, zalo_target_id, zalo_target_name, status, sent_at FROM delivery_history ORDER BY id DESC LIMIT 10")
print("recent deliveries:", c.fetchall())
conn.close()
