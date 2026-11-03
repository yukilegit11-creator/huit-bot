
import sqlite3

conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
c = conn.cursor()
c.execute("SELECT post_id, post_title, zalo_target_name, zalo_target_id, target_type, status, sent_at FROM delivery_history ORDER BY id DESC LIMIT 15")
rows = c.fetchall()
print(f"Total delivery rows: {len(rows)}")
for r in rows:
    print(r)
conn.close()
